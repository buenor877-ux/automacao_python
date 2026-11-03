import io
import json
import logging
import os
import smtplib
import sqlite3
from datetime import datetime
from email.message import EmailMessage

import pandas as pd

import banco

PASTA_BACKUPS = os.path.join(banco.PASTA_PROJETO, "backups")
PASTA_RELATORIOS = os.path.join(banco.PASTA_PROJETO, "relatorios")
PASTA_LOGS = os.path.join(banco.PASTA_PROJETO, "logs")
ARQUIVO_LOG = os.path.join(PASTA_LOGS, "automacao.log")
ARQUIVO_CONFIG_EMAIL = os.path.join(banco.PASTA_PROJETO, "config_email.json")

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
    df = banco.consultar("""
        SELECT p.id, p.nome, c.nome AS categoria, f.nome AS fornecedor,
               p.preco, p.quantidade, p.estoque_minimo,
               f.telefone AS fornecedor_telefone, f.email AS fornecedor_email
        FROM produtos p
        LEFT JOIN categorias c ON c.id = p.categoria_id
        LEFT JOIN fornecedores f ON f.id = p.fornecedor_id
        ORDER BY p.nome COLLATE NOCASE
    """)
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


def resumo_estoque(estoque):
    return {
        "Produtos cadastrados": len(estoque),
        "Unidades em estoque": int(estoque["quantidade"].sum()),
        "Valor do estoque": formatar_moeda(estoque["valor_total"].sum()),
        "Produtos para repor": int((estoque["situacao"] == "Repor").sum()),
    }


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

NOMES_COLUNAS = {
    "id": "ID", "nome": "Nome", "categoria": "Categoria", "fornecedor": "Fornecedor",
    "preco": "Preço", "quantidade": "Quantidade", "estoque_minimo": "Estoque mínimo",
    "valor_total": "Valor total", "situacao": "Situação",
    "fornecedor_telefone": "Telefone do fornecedor", "fornecedor_email": "E-mail do fornecedor",
    "data": "Data", "produto": "Produto", "tipo": "Tipo", "observacao": "Observação",
}


def gerar_planilha(destino=None):
    """
    Gera um Excel com as abas Resumo, Estoque, Repor e Movimentações.
    Sem `destino`, devolve os bytes do arquivo (para download ou anexo de e-mail).
    """
    estoque = tabela_estoque()
    resumo = {"Gerado em": f"{datetime.now():%d/%m/%Y %H:%M}", **resumo_estoque(estoque)}
    contatos = ["fornecedor_telefone", "fornecedor_email"]

    abas = {
        "Resumo": pd.DataFrame({"Indicador": list(resumo), "Valor": list(resumo.values())}),
        "Estoque": estoque.drop(columns=contatos),
        # Na aba Repor o contato do fornecedor já aparece, para facilitar o pedido de compra
        "Repor": estoque[estoque["situacao"] == "Repor"].drop(columns=["valor_total", "situacao"]),
        "Movimentações": tabela_movimentacoes(),
    }

    saida = destino or io.BytesIO()
    with pd.ExcelWriter(saida, engine="openpyxl", datetime_format="DD/MM/YYYY HH:MM") as excel:
        for nome, df in abas.items():
            df.rename(columns=NOMES_COLUNAS).to_excel(excel, sheet_name=nome, index=False)
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
        "categoria": ["Papelaria", "Papelaria"],
        "fornecedor": ["Distribuidora Exemplo", ""],
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
    for opcional in ("estoque_minimo", "categoria", "fornecedor"):
        if opcional not in df.columns:
            df[opcional] = ""
    return df.dropna(how="all")


def importar_planilha(df):
    """
    Produto novo é cadastrado; produto existente recebe uma entrada com a quantidade.
    Categorias e fornecedores que ainda não existem são criados automaticamente.
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

            ligacoes = {
                "categoria_id": banco.obter_ou_criar("categorias", linha["categoria"]),
                "fornecedor_id": banco.obter_ou_criar("fornecedores", linha["fornecedor"]),
            }
            # Coluna vazia na planilha não apaga a categoria/fornecedor que o produto já tem
            ligacoes = {chave: valor for chave, valor in ligacoes.items() if valor is not None}

            existente = banco.produto_existe(nome)
            if existente is None:
                banco.cadastrar_produto(nome, preco, quantidade, estoque_minimo, "Importado de planilha", **ligacoes)
                resumo["cadastrados"] += 1
            else:
                banco.editar_produto(existente["id"], preco=preco, **ligacoes,
                                     **({"estoque_minimo": estoque_minimo} if estoque_minimo else {}))
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


# E-MAIL

CONFIG_EMAIL_PADRAO = {
    "ativo": False,
    "servidor": "smtp.gmail.com",
    "porta": 465,
    "usuario": "",
    "senha": "",
    "destinatarios": "",
}


def carregar_config_email():
    if not os.path.isfile(ARQUIVO_CONFIG_EMAIL):
        return dict(CONFIG_EMAIL_PADRAO)
    with open(ARQUIVO_CONFIG_EMAIL, encoding="utf-8") as arquivo:
        return {**CONFIG_EMAIL_PADRAO, **json.load(arquivo)}


def salvar_config_email(config):
    with open(ARQUIVO_CONFIG_EMAIL, "w", encoding="utf-8") as arquivo:
        json.dump(config, arquivo, indent=2, ensure_ascii=False)


def enviar_relatorio_email(config=None):
    """Envia o resumo do estoque no corpo do e-mail e a planilha completa em anexo."""
    config = config or carregar_config_email()
    destinatarios = [
        email.strip() for email in config["destinatarios"].replace(";", ",").split(",") if email.strip()
    ]
    if not (config["servidor"] and config["usuario"] and config["senha"] and destinatarios):
        raise ValueError("Preencha servidor, usuário, senha e destinatários nas configurações de e-mail.")

    estoque = tabela_estoque()
    resumo = resumo_estoque(estoque)
    repor = estoque[estoque["situacao"] == "Repor"][["nome", "quantidade", "estoque_minimo", "fornecedor"]]
    hoje = datetime.now()

    mensagem = EmailMessage()
    mensagem["Subject"] = f"Relatório de estoque - {hoje:%d/%m/%Y}"
    mensagem["From"] = config["usuario"]
    mensagem["To"] = ", ".join(destinatarios)

    texto = "\n".join(f"{chave}: {valor}" for chave, valor in resumo.items())
    mensagem.set_content(f"Relatório de estoque de {hoje:%d/%m/%Y}\n\n{texto}\n\nPlanilha completa em anexo.")

    tabela_repor = (
        repor.fillna("").rename(columns=NOMES_COLUNAS).to_html(index=False, border=0)
        if not repor.empty else "<p>Nenhum produto abaixo do estoque mínimo. 👍</p>"
    )
    linhas_resumo = "".join(f"<tr><td>{chave}</td><td><b>{valor}</b></td></tr>" for chave, valor in resumo.items())
    mensagem.add_alternative(f"""
        <html><body style="font-family: Arial, sans-serif; color: #1f2937">
        <h2 style="color: #2563eb">Relatório de estoque - {hoje:%d/%m/%Y}</h2>
        <table cellpadding="6">{linhas_resumo}</table>
        <h3>Produtos para repor</h3>
        {tabela_repor}
        <p style="color: #6b7280">Planilha completa em anexo.</p>
        </body></html>
    """, subtype="html")

    mensagem.add_attachment(
        gerar_planilha(),
        maintype="application",
        subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=f"estoque_{hoje:%Y-%m-%d}.xlsx",
    )

    porta = int(config["porta"])
    # Porta 465 usa conexão segura direta; as outras (ex.: 587) usam STARTTLS
    if porta == 465:
        servidor = smtplib.SMTP_SSL(config["servidor"], porta, timeout=30)
    else:
        servidor = smtplib.SMTP(config["servidor"], porta, timeout=30)
        servidor.starttls()
    with servidor:
        servidor.login(config["usuario"], config["senha"])
        servidor.send_message(mensagem)

    log.info("Relatório enviado por e-mail para %s", ", ".join(destinatarios))
    return destinatarios


# ROTINA DIÁRIA

def rotina_diaria():
    """O que roda sozinho todo dia: backup, planilha em relatorios/ e, se ativado, o e-mail."""
    log.info("Rotina diária iniciada")
    os.makedirs(PASTA_RELATORIOS, exist_ok=True)
    tarefas = [
        fazer_backup,
        lambda: gerar_planilha(os.path.join(PASTA_RELATORIOS, f"estoque_{datetime.now():%Y-%m-%d}.xlsx")),
    ]
    if carregar_config_email()["ativo"]:
        tarefas.append(lambda: "E-mail enviado para " + ", ".join(enviar_relatorio_email()))

    resultados = []
    for tarefa in tarefas:
        try:
            resultados.append(tarefa())
        except Exception:
            # Uma tarefa que falha não impede as outras; o erro completo fica no log
            log.exception("Falha na rotina diária")
    log.info("Rotina diária finalizada")
    return resultados


def ultimas_linhas_log(quantidade=30):
    if not os.path.isfile(ARQUIVO_LOG):
        return ""
    with open(ARQUIVO_LOG, encoding="utf-8") as arquivo:
        return "".join(arquivo.readlines()[-quantidade:])
