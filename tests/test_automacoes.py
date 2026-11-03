import io
import os

import pandas as pd
import pytest

import automacoes
import banco


@pytest.mark.parametrize("texto, esperado", [
    ("10,50", 10.5), ("10.50", 10.5), ("1.234,56", 1234.56), ("R$ 7,90", 7.9), (3, 3.0),
])
def test_converter_numero(texto, esperado):
    assert automacoes.converter_numero(texto) == esperado


def test_converter_numero_invalido():
    with pytest.raises(ValueError, match="número inválido"):
        automacoes.converter_numero("abc")


def test_formatar_moeda():
    assert automacoes.formatar_moeda(1234.5) == "R$ 1.234,50"


def test_tabela_estoque_marca_produtos_para_repor():
    banco.cadastrar_produto("Caneta", 2.0, 100, 20)
    banco.cadastrar_produto("Mouse", 50.0, 3, 5)
    banco.cadastrar_produto("Sem alerta", 1.0, 0, 0)

    estoque = automacoes.tabela_estoque().set_index("nome")

    assert estoque.loc["Caneta", "situacao"] == "OK"
    assert estoque.loc["Mouse", "situacao"] == "Repor"
    assert estoque.loc["Sem alerta", "situacao"] == "OK"  # mínimo 0 = sem alerta
    assert estoque.loc["Mouse", "valor_total"] == 150.0


def test_importar_planilha_csv():
    banco.cadastrar_produto("Teclado", 100.0, 2, 3)
    csv = (
        "nome;preco;quantidade;estoque_minimo;categoria;fornecedor\n"
        "Caneta azul;2,50;100;20;Papelaria;Distribuidora X\n"
        "teclado;120,00;5;;Informática;\n"
        ";5;1;0;;\n"
        "Caderno;abc;3;0;;\n"
    )
    df = automacoes.ler_planilha(io.StringIO(csv), "produtos.csv")

    resumo = automacoes.importar_planilha(df)

    assert (resumo["cadastrados"], resumo["atualizados"]) == (1, 1)
    assert resumo["erros"] == ["Linha 4: nome vazio", "Linha 5: número inválido: 'abc'"]

    estoque = automacoes.tabela_estoque().set_index("nome")
    assert estoque.loc["Caneta azul", "categoria"] == "Papelaria"
    assert estoque.loc["Caneta azul", "fornecedor"] == "Distribuidora X"
    assert estoque.loc["Teclado", "quantidade"] == 7       # 2 + entrada de 5
    assert estoque.loc["Teclado", "preco"] == 120.0
    assert estoque.loc["Teclado", "estoque_minimo"] == 3   # vazio na planilha mantém o atual


def test_planilha_sem_coluna_obrigatoria():
    with pytest.raises(ValueError, match="preco"):
        automacoes.ler_planilha(io.StringIO("nome;quantidade\nCaneta;1\n"), "x.csv")


def test_modelo_de_importacao_pode_ser_importado():
    df = automacoes.ler_planilha(io.BytesIO(automacoes.modelo_importacao()), "modelo.xlsx")

    resumo = automacoes.importar_planilha(df)

    assert resumo == {"cadastrados": 2, "atualizados": 0, "erros": []}


def test_gerar_planilha_tem_quatro_abas():
    fornecedor = banco.adicionar("fornecedores", nome="Distribuidora", telefone="1199999-0000")
    banco.cadastrar_produto("Caneta", 2.0, 100, 20)
    banco.cadastrar_produto("Mouse", 50.0, 3, 5, fornecedor_id=fornecedor)

    abas = pd.read_excel(io.BytesIO(automacoes.gerar_planilha()), sheet_name=None)

    assert list(abas) == ["Resumo", "Estoque", "Repor", "Movimentações"]
    assert len(abas["Estoque"]) == 2
    assert abas["Repor"]["Nome"].tolist() == ["Mouse"]
    assert abas["Repor"]["Telefone do fornecedor"].tolist() == ["1199999-0000"]
    assert len(abas["Movimentações"]) == 2


def test_backup_mantem_apenas_os_mais_recentes(monkeypatch):
    horarios = iter(f"2026-01-01_10-00-{segundo:02d}" for segundo in range(5))

    class DataFalsa:
        @staticmethod
        def now():
            class Agora:
                def __format__(self, _):
                    return next(horarios)
            return Agora()

    monkeypatch.setattr(automacoes, "datetime", DataFalsa)

    for _ in range(5):
        automacoes.fazer_backup(manter=3)

    assert automacoes.listar_backups() == [
        "empresa_2026-01-01_10-00-04.db", "empresa_2026-01-01_10-00-03.db", "empresa_2026-01-01_10-00-02.db",
    ]


class SMTPFalso:
    """Substitui o servidor de e-mail: guarda a mensagem em vez de enviar."""
    enviados = []

    def __init__(self, servidor, porta, timeout=None):
        self.servidor = servidor

    def __enter__(self):
        return self

    def __exit__(self, *erro):
        pass

    def starttls(self):
        pass

    def login(self, usuario, senha):
        self.usuario = usuario

    def send_message(self, mensagem):
        SMTPFalso.enviados.append(mensagem)


CONFIG_EMAIL = {
    "ativo": True, "servidor": "smtp.teste.com", "porta": 465,
    "usuario": "loja@teste.com", "senha": "senha-de-app", "destinatarios": "a@teste.com; b@teste.com",
}


def test_enviar_relatorio_email(monkeypatch):
    monkeypatch.setattr(automacoes.smtplib, "SMTP_SSL", SMTPFalso)
    SMTPFalso.enviados.clear()
    banco.cadastrar_produto("Mouse", 50.0, 3, 5)

    destinatarios = automacoes.enviar_relatorio_email(CONFIG_EMAIL)

    assert destinatarios == ["a@teste.com", "b@teste.com"]
    mensagem = SMTPFalso.enviados[0]
    assert mensagem["Subject"].startswith("Relatório de estoque")
    assert mensagem["To"] == "a@teste.com, b@teste.com"
    anexos = [parte.get_filename() for parte in mensagem.iter_attachments()]
    assert len(anexos) == 1 and anexos[0].endswith(".xlsx")
    assert "Mouse" in mensagem.get_body(("html",)).get_content()


def test_email_sem_configuracao_avisa():
    with pytest.raises(ValueError, match="Preencha"):
        automacoes.enviar_relatorio_email()


def test_rotina_diaria_envia_email_quando_ativado(monkeypatch):
    monkeypatch.setattr(automacoes.smtplib, "SMTP_SSL", SMTPFalso)
    SMTPFalso.enviados.clear()
    automacoes.salvar_config_email(CONFIG_EMAIL)

    resultados = automacoes.rotina_diaria()

    assert len(resultados) == 3
    assert os.path.isfile(resultados[0]) and os.path.isfile(resultados[1])
    assert resultados[2].startswith("E-mail enviado")
    assert len(SMTPFalso.enviados) == 1
