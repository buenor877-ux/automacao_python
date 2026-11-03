import io
import logging
import os
import sqlite3
from datetime import datetime

import pandas as pd

import banco

PASTA_BACKUPS = os.path.join(banco.PASTA_PROJETO, "backups")
PASTA_RELATORIOS = os.path.join(banco.PASTA_PROJETO, "relatorios")
PASTA_LOGS = os.path.join(banco.PASTA_PROJETO, "logs")
ARQUIVO_LOG = os.path.join(PASTA_LOGS, "automacao.log")

log = logging.getLogger("automacao")


def configurar_log():
    os.makedirs(PASTA_LOGS, exist_ok=True)
    if not log.handlers:
        handler = logging.FileHandler(ARQUIVO_LOG, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%d/%m/%Y %H:%M:%S"))
        log.addHandler(handler)
        log.setLevel(logging.INFO)


def formatar_moeda(valor):
    # 1234.5 -> "R$ 1.234,50"
    texto = f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {texto}"


def converter_numero(texto):
    # Aceita 10.5, "10,50", "10.50" e "1.234,56"
    if isinstance(texto, (int, float)):
        return float(texto)
    original = texto
    texto = str(texto).strip().replace("R$", "").strip()
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    try:
        return float(texto)
    except ValueError:
        raise ValueError(f"número inválido: '{original}'") from None


# TABELAS (pandas)

def tabela_estoque():
    df = banco.consultar(
        "SELECT id, nome, preco, quantidade, estoque_minimo FROM produtos ORDER BY nome COLLATE NOCASE"
    )
    df["valor_total"] = df["preco"] * df["quantidade"]
    repor = (df["estoque_minimo"] > 0) & (df["quantidade"] <= df["estoque_minimo"])
    df["situacao"] = repor.map({True: "Repor", False: "OK"})
    return df


def tabela_movimentacoes():
    df = banco.consultar("""
        SELECT m.id, m.data, p.nome AS produto, m.tipo, m.quantidade, m.observacao
        FROM movimentacoes m JOIN produtos p ON p.id = m.produto_id
        ORDER BY m.id DESC
    """)
    df["data"] = pd.to_datetime(df["data"])
    return df


# BACKUP

def fazer_backup(manter=10):
    """Copia o banco para backups/ e apaga os backups mais antigos além de `manter`."""
    os.makedirs(PASTA_BACKUPS, exist_ok=True)
    destino = os.path.join(PASTA_BACKUPS, f"empresa_{datetime.now():%Y-%m-%d_%H-%M-%S}.db")

    # A API de backup do SQLite copia com segurança mesmo com o banco aberto
    origem, copia = sqlite3.connect(banco.CAMINHO_DB), sqlite3.connect(destino)
    try:
        origem.backup(copia)
    finally:
        copia.close()
        origem.close()

    for antigo in listar_backups()[manter:]:
        os.remove(os.path.join(PASTA_BACKUPS, antigo))

    log.info("Backup criado: %s", os.path.basename(destino))
    return destino


def listar_backups():
    if not os.path.isdir(PASTA_BACKUPS):
        return []
    return sorted(
        (arquivo for arquivo in os.listdir(PASTA_BACKUPS) if arquivo.startswith("empresa_") and arquivo.endswith(".db")),
        reverse=True,
    )


# PLANILHAS

def gerar_planilha(destino=None):
    """
    Gera um Excel com as abas Resumo, Estoque, Repor e Movimentações.
    Sem `destino`, devolve os bytes do arquivo (para o botão de download).
    """
    estoque = tabela_estoque()
    movimentacoes = tabela_movimentacoes()
    resumo = pd.DataFrame({
        "Indicador": ["Gerado em", "Produtos cadastrados", "Unidades em estoque", "Valor do estoque", "Produtos para repor"],
        "Valor": [
            f"{datetime.now():%d/%m/%Y %H:%M}",
            len(estoque),
            int(estoque["quantidade"].sum()),
            formatar_moeda(estoque["valor_total"].sum()),
            int((estoque["situacao"] == "Repor").sum()),
        ],
    })

    nomes_colunas = {
        "id": "ID", "nome": "Nome", "preco": "Preço", "quantidade": "Quantidade",
        "estoque_minimo": "Estoque mínimo", "valor_total": "Valor total", "situacao": "Situação",
        "data": "Data", "produto": "Produto", "tipo": "Tipo", "observacao": "Observação",
    }
    abas = {
        "Resumo": resumo,
        "Estoque": estoque.rename(columns=nomes_colunas),
        "Repor": estoque[estoque["situacao"] == "Repor"].rename(columns=nomes_colunas),
        "Movimentações": movimentacoes.rename(columns=nomes_colunas),
    }

    saida = destino or io.BytesIO()
    with pd.ExcelWriter(saida, engine="openpyxl", datetime_format="DD/MM/YYYY HH:MM") as excel:
        for nome, df in abas.items():
            df.to_excel(excel, sheet_name=nome, index=False)
            aba = excel.sheets[nome]
            aba.freeze_panes = "A2"
            aba.auto_filter.ref = aba.dimensions
            # Largura de cada coluna de acordo com o maior texto
            for coluna in aba.columns:
                largura = max(len(str(celula.value or "")) for celula in coluna)
                aba.column_dimensions[coluna[0].column_letter].width = min(largura + 3, 45)
                if coluna[0].value in ("Preço", "Valor total"):
                    for celula in coluna[1:]:
                        celula.number_format = '"R$" #,##0.00'

    if destino is None:
        return saida.getvalue()
    log.info("Planilha gerada: %s", os.path.basename(destino))
    return destino


def modelo_importacao():
    """Planilha de exemplo para o usuário preencher e importar."""
    exemplo = pd.DataFrame({
        "nome": ["Caneta azul", "Caderno 10 matérias"],
        "preco": [2.50, 24.90],
        "quantidade": [100, 30],
        "estoque_minimo": [20, 5],
    })
    saida = io.BytesIO()
    exemplo.to_excel(saida, index=False)
    return saida.getvalue()


def ler_planilha(arquivo, nome_arquivo):
    """Lê .xlsx ou .csv (caminho ou arquivo enviado) e padroniza os nomes das colunas."""
    if nome_arquivo.lower().endswith((".xlsx", ".xls")):
        df = pd.read_excel(arquivo, dtype=str)
    else:
        # sep=None descobre sozinho se o separador é ";" ou ","
        df = pd.read_csv(arquivo, sep=None, engine="python", dtype=str, encoding="utf-8-sig")

    df.columns = (
        df.columns.str.strip().str.lower()
        .str.replace("ç", "c").str.replace("í", "i").str.replace(" ", "_")
    )
    faltando = {"nome", "preco", "quantidade"} - set(df.columns)
    if faltando:
        raise ValueError(f"Colunas obrigatórias faltando: {', '.join(sorted(faltando))}")
    if "estoque_minimo" not in df.columns:
        df["estoque_minimo"] = "0"
    return df.dropna(how="all")


def importar_planilha(df):
    """
    Produto novo é cadastrado; produto existente recebe uma entrada com a quantidade.
    Retorna um dicionário com o resumo da importação.
    """
    resumo = {"cadastrados": 0, "atualizados": 0, "erros": []}

    for numero, linha in enumerate(df.fillna("").to_dict("records"), start=2):
        try:
            nome = str(linha["nome"]).strip()
            if not nome:
                raise ValueError("nome vazio")
            preco = converter_numero(linha["preco"])
            quantidade = int(converter_numero(linha["quantidade"] or 0))
            estoque_minimo = int(converter_numero(linha["estoque_minimo"] or 0))
            if min(preco, quantidade, estoque_minimo) < 0:
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
        "Importação: %d cadastrados, %d atualizados, %d erros",
        resumo["cadastrados"], resumo["atualizados"], len(resumo["erros"])
    )
    return resumo


# ROTINA DIÁRIA

def rotina_diaria():
    """O que roda sozinho todo dia: backup do banco e planilha completa em relatorios/."""
    log.info("Rotina diária iniciada")
    os.makedirs(PASTA_RELATORIOS, exist_ok=True)
    tarefas = [
        fazer_backup,
        lambda: gerar_planilha(os.path.join(PASTA_RELATORIOS, f"estoque_{datetime.now():%Y-%m-%d}.xlsx")),
    ]
    arquivos = []
    for tarefa in tarefas:
        try:
            arquivos.append(tarefa())
        except Exception:
            # Uma tarefa que falha não impede as outras; o erro completo fica no log
            log.exception("Falha na rotina diária")
    log.info("Rotina diária finalizada")
    return arquivos


def ultimas_linhas_log(quantidade=30):
    if not os.path.isfile(ARQUIVO_LOG):
        return ""
    with open(ARQUIVO_LOG, encoding="utf-8") as arquivo:
        return "".join(arquivo.readlines()[-quantidade:])
