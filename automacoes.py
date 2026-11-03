import csv
import logging
import os
import sqlite3
from datetime import datetime

import banco

PASTA_BACKUPS = os.path.join(banco.PASTA_PROJETO, "backups")
PASTA_RELATORIOS = os.path.join(banco.PASTA_PROJETO, "relatorios")
PASTA_LOGS = os.path.join(banco.PASTA_PROJETO, "logs")

# O Excel é opcional: sem o openpyxl instalado, os relatórios saem em CSV
try:
    import openpyxl
    from openpyxl.styles import Font, PatternFill
except ImportError:
    openpyxl = None

log = logging.getLogger("automacao")


def configurar_log():
    os.makedirs(PASTA_LOGS, exist_ok=True)
    if not log.handlers:
        handler = logging.FileHandler(os.path.join(PASTA_LOGS, "automacao.log"), encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%d/%m/%Y %H:%M:%S"))
        log.addHandler(handler)
        log.setLevel(logging.INFO)


def formatar_moeda(valor):
    # 1234.5 -> "R$ 1.234,50"
    texto = f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {texto}"


def converter_numero(texto):
    # Aceita "10,50", "10.50" e "1.234,56"
    original = texto
    texto = str(texto).strip().replace("R$", "").strip()
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    try:
        return float(texto)
    except ValueError:
        raise ValueError(f"número inválido: '{original}'") from None


# BACKUP

def fazer_backup(manter=10):
    """Copia o banco para a pasta backups/ e apaga os backups mais antigos além de `manter`."""
    os.makedirs(PASTA_BACKUPS, exist_ok=True)
    nome = f"empresa_{datetime.now():%Y-%m-%d_%H-%M-%S}.db"
    destino = os.path.join(PASTA_BACKUPS, nome)

    # A API de backup do SQLite copia com segurança mesmo com o banco aberto
    origem = sqlite3.connect(banco.CAMINHO_DB)
    copia = sqlite3.connect(destino)
    try:
        origem.backup(copia)
    finally:
        copia.close()
        origem.close()

    backups = sorted(
        arquivo for arquivo in os.listdir(PASTA_BACKUPS)
        if arquivo.startswith("empresa_") and arquivo.endswith(".db")
    )
    for antigo in backups[:-manter]:
        os.remove(os.path.join(PASTA_BACKUPS, antigo))

    log.info("Backup criado: %s", nome)
    return destino


# EXPORTAÇÃO

def exportar_estoque():
    """Gera a planilha do estoque em relatorios/. Retorna o caminho do arquivo."""
    os.makedirs(PASTA_RELATORIOS, exist_ok=True)
    produtos = banco.listar_produtos()
    cabecalho = ["ID", "Nome", "Preço", "Quantidade", "Estoque mínimo", "Valor total", "Situação"]

    linhas = []
    for produto in produtos:
        abaixo = produto["estoque_minimo"] > 0 and produto["quantidade"] <= produto["estoque_minimo"]
        linhas.append([
            produto["id"],
            produto["nome"],
            produto["preco"],
            produto["quantidade"],
            produto["estoque_minimo"],
            produto["preco"] * produto["quantidade"],
            "REPOR" if abaixo else "OK",
        ])

    data = f"{datetime.now():%Y-%m-%d}"

    if openpyxl is not None:
        caminho = os.path.join(PASTA_RELATORIOS, f"estoque_{data}.xlsx")
        planilha = openpyxl.Workbook()
        aba = planilha.active
        aba.title = "Estoque"
        aba.append(cabecalho)

        for celula in aba[1]:
            celula.font = Font(bold=True, color="FFFFFF")
            celula.fill = PatternFill("solid", fgColor="305496")

        for linha in linhas:
            aba.append(linha)
            if linha[-1] == "REPOR":
                for celula in aba[aba.max_row]:
                    celula.fill = PatternFill("solid", fgColor="F8CBAD")

        for linha in aba.iter_rows(min_row=2):
            linha[2].number_format = '"R$" #,##0.00'
            linha[5].number_format = '"R$" #,##0.00'

        larguras = [6, 30, 14, 12, 16, 16, 10]
        for indice, largura in enumerate(larguras):
            aba.column_dimensions[chr(65 + indice)].width = largura

        planilha.save(caminho)
    else:
        caminho = os.path.join(PASTA_RELATORIOS, f"estoque_{data}.csv")
        # utf-8-sig e ";" fazem o Excel em português abrir o CSV direto, com acentos certos
        with open(caminho, "w", newline="", encoding="utf-8-sig") as arquivo:
            escritor = csv.writer(arquivo, delimiter=";")
            escritor.writerow(cabecalho)
            for linha in linhas:
                linha[2] = f"{linha[2]:.2f}".replace(".", ",")
                linha[5] = f"{linha[5]:.2f}".replace(".", ",")
                escritor.writerow(linha)

    log.info("Estoque exportado: %s", os.path.basename(caminho))
    return caminho


# IMPORTAÇÃO

def ler_planilha(caminho):
    """Lê um .csv ou .xlsx e devolve uma lista de dicionários com cabeçalhos em minúsculo."""
    if caminho.lower().endswith(".xlsx"):
        if openpyxl is None:
            raise RuntimeError("Para ler .xlsx instale o openpyxl: pip install openpyxl")
        planilha = openpyxl.load_workbook(caminho, read_only=True, data_only=True)
        linhas = list(planilha.active.iter_rows(values_only=True))
        planilha.close()
        if not linhas:
            return []
        cabecalho = [str(coluna or "").strip().lower() for coluna in linhas[0]]
        return [dict(zip(cabecalho, linha)) for linha in linhas[1:] if any(linha)]

    with open(caminho, newline="", encoding="utf-8-sig") as arquivo:
        amostra = arquivo.read(2048)
        arquivo.seek(0)
        separador = ";" if amostra.count(";") >= amostra.count(",") else ","
        leitor = csv.DictReader(arquivo, delimiter=separador)
        return [
            {chave.strip().lower(): valor for chave, valor in linha.items() if chave}
            for linha in leitor
        ]


def importar_planilha(caminho):
    """
    Colunas esperadas: nome, preco, quantidade e, opcionalmente, estoque_minimo.
    Produto novo é cadastrado; produto existente recebe uma entrada com a quantidade.
    Retorna um dicionário com o resumo da importação.
    """
    resumo = {"cadastrados": 0, "atualizados": 0, "erros": []}

    for numero, linha in enumerate(ler_planilha(caminho), start=2):
        try:
            nome = str(linha.get("nome") or "").strip()
            if not nome:
                raise ValueError("nome vazio")

            preco = converter_numero(linha.get("preco") or linha.get("preço"))
            quantidade = int(converter_numero(linha.get("quantidade") or 0))
            minimo = linha.get("estoque_minimo") or linha.get("estoque mínimo") or 0
            estoque_minimo = int(converter_numero(minimo))

            if preco < 0 or quantidade < 0 or estoque_minimo < 0:
                raise ValueError("valores negativos")

            existente = banco.produto_existe(nome)
            if existente is None:
                banco.cadastrar_produto(nome, preco, quantidade, estoque_minimo, "Importado de planilha")
                resumo["cadastrados"] += 1
            else:
                banco.editar_produto(existente["id"], existente["nome"], preco, estoque_minimo or existente["estoque_minimo"])
                if quantidade > 0:
                    banco.registrar_movimentacao(existente["id"], "entrada", quantidade, "Importado de planilha")
                resumo["atualizados"] += 1

        except (ValueError, TypeError) as erro:
            resumo["erros"].append(f"Linha {numero}: {erro}")

    log.info(
        "Importação de %s: %d cadastrados, %d atualizados, %d erros",
        os.path.basename(caminho), resumo["cadastrados"], resumo["atualizados"], len(resumo["erros"])
    )
    return resumo


# RELATÓRIO DIÁRIO

def gerar_relatorio_diario():
    """Gera relatorios/relatorio_AAAA-MM-DD.txt com resumo, alertas e movimentações do dia."""
    os.makedirs(PASTA_RELATORIOS, exist_ok=True)
    hoje = datetime.now()
    caminho = os.path.join(PASTA_RELATORIOS, f"relatorio_{hoje:%Y-%m-%d}.txt")

    abaixo = banco.produtos_abaixo_do_minimo()
    movimentacoes = banco.movimentacoes_do_dia(f"{hoje:%Y-%m-%d}")

    linhas = [
        f"RELATÓRIO DE ESTOQUE - {hoje:%d/%m/%Y %H:%M}",
        "=" * 50,
        f"Produtos cadastrados: {banco.total_produtos()}",
        f"Unidades em estoque:  {banco.quantidade_estoque()}",
        f"Valor do estoque:     {formatar_moeda(banco.total_estoque())}",
        "",
        f"ALERTAS - PRODUTOS PARA REPOR ({len(abaixo)})",
        "-" * 50,
    ]
    if abaixo:
        for produto in abaixo:
            linhas.append(
                f"  {produto['nome']}: {produto['quantidade']} em estoque (mínimo {produto['estoque_minimo']})"
            )
    else:
        linhas.append("  Nenhum produto abaixo do estoque mínimo.")

    linhas += ["", f"MOVIMENTAÇÕES DE HOJE ({len(movimentacoes)})", "-" * 50]
    if movimentacoes:
        for mov in movimentacoes:
            sinal = "+" if mov["tipo"] == "entrada" else "-"
            obs = f" ({mov['observacao']})" if mov["observacao"] else ""
            linhas.append(f"  {mov['data'][11:16]}  {sinal}{mov['quantidade']:<5} {mov['nome']}{obs}")
    else:
        linhas.append("  Nenhuma movimentação hoje.")

    with open(caminho, "w", encoding="utf-8") as arquivo:
        arquivo.write("\n".join(linhas) + "\n")

    log.info("Relatório diário gerado: %s", os.path.basename(caminho))
    return caminho


def rotina_diaria():
    """Tudo o que deve rodar sozinho todo dia: backup, planilha e relatório."""
    log.info("Rotina diária iniciada")
    arquivos = []
    for tarefa in (fazer_backup, exportar_estoque, gerar_relatorio_diario):
        try:
            arquivos.append(tarefa())
        except Exception:
            # Uma tarefa que falha não impede as outras; o erro completo fica no log
            log.exception("Falha em %s", tarefa.__name__)
    log.info("Rotina diária finalizada")
    return arquivos
