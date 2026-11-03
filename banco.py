import os
import sqlite3
from contextlib import contextmanager

import pandas as pd

# Caminho fixo ao lado deste arquivo: funciona de qualquer pasta onde o script for executado
PASTA_PROJETO = os.path.dirname(os.path.abspath(__file__))
CAMINHO_DB = os.path.join(PASTA_PROJETO, "empresa.db")

# Campos de cada cadastro auxiliar (usado pelas funções genéricas e pela interface)
CADASTROS = {
    "categorias": ["nome"],
    "fornecedores": ["nome", "telefone", "email"],
}


@contextmanager
def conectar():
    """Abre a conexão, faz commit se tudo der certo e sempre fecha no final."""
    conexao = sqlite3.connect(CAMINHO_DB)
    conexao.row_factory = sqlite3.Row
    conexao.execute("PRAGMA foreign_keys = ON")
    try:
        yield conexao
        conexao.commit()
    except Exception:
        conexao.rollback()
        raise
    finally:
        conexao.close()


def consultar(sql, parametros=()):
    """Roda um SELECT e devolve o resultado como tabela do pandas."""
    with conectar() as conexao:
        return pd.read_sql_query(sql, conexao, params=parametros)


def inicializar_banco():
    with conectar() as conexao:
        conexao.executescript("""
        CREATE TABLE IF NOT EXISTS categorias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL UNIQUE COLLATE NOCASE
        );

        CREATE TABLE IF NOT EXISTS fornecedores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL UNIQUE COLLATE NOCASE,
            telefone TEXT,
            email TEXT
        );

        CREATE TABLE IF NOT EXISTS produtos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            preco REAL NOT NULL,
            quantidade INTEGER NOT NULL DEFAULT 0,
            estoque_minimo INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS movimentacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            produto_id INTEGER NOT NULL REFERENCES produtos(id) ON DELETE CASCADE,
            tipo TEXT NOT NULL CHECK (tipo IN ('entrada', 'saida')),
            quantidade INTEGER NOT NULL CHECK (quantidade > 0),
            observacao TEXT,
            data TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
        );
        """)

        # Bancos de versões anteriores não têm estas colunas: são adicionadas sem perder dados
        colunas_novas = {
            "estoque_minimo": "INTEGER NOT NULL DEFAULT 0",
            "categoria_id": "INTEGER REFERENCES categorias(id) ON DELETE SET NULL",
            "fornecedor_id": "INTEGER REFERENCES fornecedores(id) ON DELETE SET NULL",
        }
        existentes = [coluna["name"] for coluna in conexao.execute("PRAGMA table_info(produtos)")]
        for coluna, definicao in colunas_novas.items():
            if coluna not in existentes:
                conexao.execute(f"ALTER TABLE produtos ADD COLUMN {coluna} {definicao}")


# CATEGORIAS E FORNECEDORES

def _validar_tabela(tabela):
    if tabela not in CADASTROS:
        raise ValueError(f"Cadastro desconhecido: {tabela}")


def listar(tabela):
    _validar_tabela(tabela)
    return consultar(f"SELECT * FROM {tabela} ORDER BY nome")


def adicionar(tabela, **campos):
    """Adiciona uma categoria ou fornecedor. Gera ValueError se o nome já existir."""
    _validar_tabela(tabela)
    campos = {chave: valor for chave, valor in campos.items() if chave in CADASTROS[tabela]}
    try:
        with conectar() as conexao:
            cursor = conexao.execute(
                f"INSERT INTO {tabela} ({', '.join(campos)}) VALUES ({', '.join('?' * len(campos))})",
                tuple(campos.values())
            )
            return cursor.lastrowid
    except sqlite3.IntegrityError:
        raise ValueError(f"\"{campos.get('nome')}\" já está cadastrado.") from None


def excluir(tabela, id):
    # Os produtos ligados a este registro ficam "sem categoria"/"sem fornecedor"
    _validar_tabela(tabela)
    with conectar() as conexao:
        return conexao.execute(f"DELETE FROM {tabela} WHERE id = ?", (id,)).rowcount > 0


def obter_ou_criar(tabela, nome):
    """Devolve o id do registro com esse nome, criando se não existir. Nome vazio -> None."""
    _validar_tabela(tabela)
    nome = str(nome or "").strip()
    if not nome:
        return None
    with conectar() as conexao:
        linha = conexao.execute(f"SELECT id FROM {tabela} WHERE nome = ?", (nome,)).fetchone()
    return linha["id"] if linha else adicionar(tabela, nome=nome)


# PRODUTOS

def cadastrar_produto(nome, preco, quantidade, estoque_minimo=0, observacao="Cadastro inicial",
                      categoria_id=None, fornecedor_id=None):
    with conectar() as conexao:
        cursor = conexao.execute(
            """INSERT INTO produtos (nome, preco, quantidade, estoque_minimo, categoria_id, fornecedor_id)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (nome, preco, quantidade, estoque_minimo, categoria_id, fornecedor_id)
        )
        # O estoque inicial também entra no histórico
        if quantidade > 0:
            conexao.execute(
                "INSERT INTO movimentacoes (produto_id, tipo, quantidade, observacao) VALUES (?, 'entrada', ?, ?)",
                (cursor.lastrowid, quantidade, observacao)
            )
        return cursor.lastrowid


def produto_existe(nome, ignorar_id=None):
    # COLLATE NOCASE: "Caneta" e "caneta" contam como o mesmo produto
    with conectar() as conexao:
        return conexao.execute(
            "SELECT * FROM produtos WHERE nome = ? COLLATE NOCASE AND id != ?",
            (nome, ignorar_id or 0)
        ).fetchone()


CAMPOS_EDITAVEIS = ("nome", "preco", "estoque_minimo", "categoria_id", "fornecedor_id")


def editar_produto(id, **campos):
    """
    Altera só os campos informados, ex.: editar_produto(3, preco=9.9).
    A quantidade não é editada aqui: ela só muda por entrada/saída, para manter o histórico.
    """
    campos = {chave: valor for chave, valor in campos.items() if chave in CAMPOS_EDITAVEIS}
    if not campos:
        return False
    with conectar() as conexao:
        cursor = conexao.execute(
            f"UPDATE produtos SET {', '.join(f'{chave} = ?' for chave in campos)} WHERE id = ?",
            (*campos.values(), id)
        )
        return cursor.rowcount > 0


def deletar_produto(id):
    with conectar() as conexao:
        return conexao.execute("DELETE FROM produtos WHERE id = ?", (id,)).rowcount > 0


# MOVIMENTAÇÕES DE ESTOQUE

def registrar_movimentacao(produto_id, tipo, quantidade, observacao=""):
    """Registra entrada ou saída e atualiza o estoque. Retorna a nova quantidade."""
    if tipo not in ("entrada", "saida"):
        raise ValueError("Tipo de movimentação inválido.")
    if quantidade <= 0:
        raise ValueError("A quantidade deve ser maior que zero.")

    with conectar() as conexao:
        produto = conexao.execute(
            "SELECT quantidade FROM produtos WHERE id = ?", (produto_id,)
        ).fetchone()

        if produto is None:
            raise ValueError("Produto não encontrado.")
        if tipo == "saida" and quantidade > produto["quantidade"]:
            raise ValueError(f"Estoque insuficiente. Disponível: {produto['quantidade']}.")

        nova_quantidade = produto["quantidade"] + (quantidade if tipo == "entrada" else -quantidade)

        conexao.execute("UPDATE produtos SET quantidade = ? WHERE id = ?", (nova_quantidade, produto_id))
        conexao.execute(
            "INSERT INTO movimentacoes (produto_id, tipo, quantidade, observacao) VALUES (?, ?, ?, ?)",
            (produto_id, tipo, quantidade, observacao)
        )
        return nova_quantidade
