import sqlite3

import pytest

import banco


def buscar(id):
    with banco.conectar() as conexao:
        return conexao.execute("SELECT * FROM produtos WHERE id = ?", (id,)).fetchone()


def test_cadastro_registra_estoque_inicial_no_historico():
    id = banco.cadastrar_produto("Caneta", 2.5, 10)

    historico = banco.consultar("SELECT tipo, quantidade FROM movimentacoes WHERE produto_id = ?", (id,))
    assert historico.to_dict("records") == [{"tipo": "entrada", "quantidade": 10}]


def test_nome_duplicado_ignora_maiusculas():
    id = banco.cadastrar_produto("Caneta", 2.5, 10)

    assert banco.produto_existe("CANETA") is not None
    assert banco.produto_existe("caneta", ignorar_id=id) is None


def test_entrada_e_saida_atualizam_quantidade():
    id = banco.cadastrar_produto("Caneta", 2.5, 10)

    assert banco.registrar_movimentacao(id, "entrada", 5) == 15
    assert banco.registrar_movimentacao(id, "saida", 12) == 3
    assert buscar(id)["quantidade"] == 3


def test_saida_maior_que_estoque_e_bloqueada():
    id = banco.cadastrar_produto("Caneta", 2.5, 10)

    with pytest.raises(ValueError, match="Estoque insuficiente"):
        banco.registrar_movimentacao(id, "saida", 11)
    assert buscar(id)["quantidade"] == 10


@pytest.mark.parametrize("tipo, quantidade", [("ajuste", 1), ("entrada", 0), ("saida", -3)])
def test_movimentacao_invalida(tipo, quantidade):
    id = banco.cadastrar_produto("Caneta", 2.5, 10)

    with pytest.raises(ValueError):
        banco.registrar_movimentacao(id, tipo, quantidade)


def test_editar_altera_so_os_campos_informados():
    categoria = banco.adicionar("categorias", nome="Papelaria")
    id = banco.cadastrar_produto("Caneta", 2.5, 10, 3, categoria_id=categoria)

    banco.editar_produto(id, preco=3.0, quantidade=999)  # quantidade não é editável

    produto = buscar(id)
    assert produto["preco"] == 3.0
    assert produto["quantidade"] == 10
    assert produto["categoria_id"] == categoria
    assert produto["estoque_minimo"] == 3


def test_excluir_produto_apaga_historico():
    id = banco.cadastrar_produto("Caneta", 2.5, 10)

    assert banco.deletar_produto(id)
    assert banco.consultar("SELECT * FROM movimentacoes").empty


def test_categoria_duplicada_e_recusada():
    banco.adicionar("categorias", nome="Papelaria")

    with pytest.raises(ValueError, match="já está cadastrado"):
        banco.adicionar("categorias", nome="papelaria")


def test_excluir_fornecedor_mantem_produto_sem_fornecedor():
    fornecedor = banco.adicionar("fornecedores", nome="Distribuidora", telefone="1199999-0000")
    id = banco.cadastrar_produto("Caneta", 2.5, 10, fornecedor_id=fornecedor)

    banco.excluir("fornecedores", fornecedor)

    assert buscar(id)["fornecedor_id"] is None


def test_obter_ou_criar_reaproveita_existente():
    primeiro = banco.obter_ou_criar("categorias", "Papelaria")

    assert banco.obter_ou_criar("categorias", " papelaria ") == primeiro
    assert banco.obter_ou_criar("categorias", "") is None
    assert len(banco.listar("categorias")) == 1


def test_tabela_desconhecida_e_recusada():
    with pytest.raises(ValueError):
        banco.listar("produtos; DROP TABLE produtos")


def test_banco_da_primeira_versao_e_atualizado_sem_perder_dados(tmp_path, monkeypatch):
    antigo = tmp_path / "antigo.db"
    conexao = sqlite3.connect(antigo)
    conexao.execute("CREATE TABLE produtos (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT, preco REAL, quantidade INTEGER)")
    conexao.execute("INSERT INTO produtos (nome, preco, quantidade) VALUES ('teclado gamer', 100, 3)")
    conexao.commit()
    conexao.close()
    monkeypatch.setattr(banco, "CAMINHO_DB", str(antigo))

    banco.inicializar_banco()

    produto = buscar(1)
    assert (produto["nome"], produto["quantidade"], produto["estoque_minimo"]) == ("teclado gamer", 3, 0)
    assert produto["categoria_id"] is None
