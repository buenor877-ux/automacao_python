import os
import sqlite3
from contextlib import contextmanager

import pandas as pd

# Caminho fixo ao lado deste arquivo: funciona de qualquer pasta onde o script for executado
PASTA_PROJETO = os.path.dirname(os.path.abspath(__file__))
CAMINHO_DB = os.path.join(PASTA_PROJETO, "empresa.db")


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
        conexao.execute("""
        CREATE TABLE IF NOT EXISTS produtos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            preco REAL NOT NULL,
            quantidade INTEGER NOT NULL DEFAULT 0,
            estoque_minimo INTEGER NOT NULL DEFAULT 0
        )
        """)

        # Bancos criados pela primeira versão não têm a coluna estoque_minimo
        colunas = [coluna["name"] for coluna in conexao.execute("PRAGMA table_info(produtos)")]
        if "estoque_minimo" not in colunas:
            conexao.execute(
                "ALTER TABLE produtos ADD COLUMN estoque_minimo INTEGER NOT NULL DEFAULT 0"
            )

        conexao.execute("""
        CREATE TABLE IF NOT EXISTS movimentacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            produto_id INTEGER NOT NULL REFERENCES produtos(id) ON DELETE CASCADE,
            tipo TEXT NOT NULL CHECK (tipo IN ('entrada', 'saida')),
            quantidade INTEGER NOT NULL CHECK (quantidade > 0),
            observacao TEXT,
            data TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
        )
        """)


# PRODUTOS

def cadastrar_produto(nome, preco, quantidade, estoque_minimo=0, observacao="Cadastro inicial"):
    with conectar() as conexao:
        cursor = conexao.execute(
            "INSERT INTO produtos (nome, preco, quantidade, estoque_minimo) VALUES (?, ?, ?, ?)",
            (nome, preco, quantidade, estoque_minimo)
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


def editar_produto(id, nome, preco, estoque_minimo):
    # A quantidade não é editada aqui: ela só muda por entrada/saída, para manter o histórico
    with conectar() as conexao:
        cursor = conexao.execute(
            "UPDATE produtos SET nome = ?, preco = ?, estoque_minimo = ? WHERE id = ?",
            (nome, preco, estoque_minimo, id)
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
