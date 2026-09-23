

import sqlite3

conexao = sqlite3.connect("empresa.db")
cursor = conexao.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS produtos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT,
    preco REAL,
    quantidade INTEGER
)
""")

conexao.commit()
conexao.close()


def cadastrar_produto(nome, preco, quantidade):
    conexao = sqlite3.connect("empresa.db")
    cursor = conexao.cursor()
    cursor.execute("INSERT INTO produtos (nome, preco, quantidade) VALUES (?, ?, ?)", (nome, preco, quantidade))
    conexao.commit()
    conexao.close()

def listar_produtos():
    conexao = sqlite3.connect("empresa.db")
    cursor = conexao.cursor()

    cursor.execute("SELECT * FROM produtos")
    produtos = cursor.fetchall()

    conexao.close()

    return produtos

def buscar_produtos(nome):
    conexao = sqlite3.connect("empresa.db")
    cursor = conexao.cursor()

    cursor.execute(
        "SELECT * FROM produtos WHERE nome LIKE ?",
        (f"%{nome}%",)
    )

    produtos = cursor.fetchall()

    conexao.close()

    return produtos

def buscar_produto_por_id(id):
    conexao = sqlite3.connect("empresa.db")
    cursor = conexao.cursor()

    cursor.execute(
        "SELECT * FROM produtos WHERE id = ?",
        (id,)
    )

    produto = cursor.fetchone()

    conexao.close() 
    
    return produto

def produto_existe(nome):
    conexao = sqlite3.connect("empresa.db")
    cursor = conexao.cursor()

    cursor.execute(
        "SELECT * FROM produtos WHERE nome = ?",
        (nome,)
    )

    produto = cursor.fetchone()

    conexao.close()

    return produto

def outro_produto_existe(nome, id):
    conexao = sqlite3.connect("empresa.db")
    cursor = conexao.cursor()

    cursor.execute(
        "SELECT * FROM produtos WHERE nome = ? AND id != ?",
        (nome, id)
    )

    produto = cursor.fetchone()

    conexao.close()

    return produto


def editar_produto(id, nome, preco, quantidade):
    conexao = sqlite3.connect("empresa.db")
    cursor = conexao.cursor()
    cursor.execute("UPDATE produtos SET nome = ?, preco = ?, quantidade = ? WHERE id = ?", (nome, preco, quantidade, id))

    if cursor.rowcount == 0:
        conexao.close()
        return False

    conexao.commit()
    conexao.close()
    return True


def deletar_produto(id):
    conexao = sqlite3.connect("empresa.db")
    cursor = conexao.cursor()

    cursor.execute(
        "DELETE FROM produtos WHERE id = ?",
        (id,)
    )

    if cursor.rowcount == 0:
        conexao.close()
        return False

    conexao.commit()
    conexao.close()
    return True




