import argparse
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import automacoes  # type: ignore[import-not-found]
import banco  # type: ignore[import-not-found]
from automacoes import formatar_moeda  # type: ignore[import-not-found]


# ENTRADA DE DADOS

def pedir_texto(mensagem, padrao=None):
    while True:
        texto = input(mensagem).strip()
        if texto:
            return texto
        if padrao is not None:
            return padrao
        print("Erro: Valor não pode ser vazio.")


def pedir_inteiro(mensagem, minimo=0, padrao=None):
    while True:
        texto = input(mensagem).strip()
        if texto == "" and padrao is not None:
            return padrao
        try:
            valor = int(texto)
            if valor < minimo:
                print(f"Erro: Digite um número a partir de {minimo}.")
            else:
                return valor
        except ValueError:
            print("Erro: Digite um número inteiro.")


def pedir_preco(mensagem="Digite o preço do produto: ", padrao=None):
    while True:
        texto = input(mensagem).strip()
        if texto == "" and padrao is not None:
            return padrao
        try:
            preco = automacoes.converter_numero(texto)  # aceita 10,50 e 10.50
            if preco < 0:
                print("Erro: Preço inválido.")
            else:
                return preco
        except ValueError:
            print("Erro: Preço inválido.")


def confirmar(mensagem):
    return input(f"{mensagem} (s/n): ").strip().lower() in ("s", "sim")


def pedir_produto():
    """Pede um ID e devolve o produto, ou None se não existir."""
    id = pedir_inteiro("Digite o ID do produto: ", minimo=1)
    produto = banco.buscar_produto_por_id(id)
    if produto is None:
        print("Erro: Produto não encontrado.")
    return produto


def pedir_nome_unico(id_atual=None, padrao=None):
    while True:
        nome = pedir_texto("Nome do produto: ", padrao)
        if id_atual is None:
            existente = banco.produto_existe(nome)
        else:
            existente = banco.outro_produto_existe(nome, id_atual)

        if existente is not None:
            print(f"Erro: Já existe o produto \"{existente['nome']}\" (ID {existente['id']}).")
        else:
            return nome


# EXIBIÇÃO

def mostrar_produto(produto):
    alerta = ""
    if produto["estoque_minimo"] > 0 and produto["quantidade"] <= produto["estoque_minimo"]:
        alerta = "  <-- REPOR"

    print(f"ID: {produto['id']}")
    print(f"Nome: {produto['nome']}")
    print(f"Preço: {formatar_moeda(produto['preco'])}")
    print(f"Quantidade: {produto['quantidade']}{alerta}")
    print(f"Estoque mínimo: {produto['estoque_minimo']}")
    print("---------------------------")


def mostrar_tabela(produtos):
    print(f"{'ID':>4}  {'Nome':<28} {'Preço':>14} {'Qtd':>6} {'Mín':>5}")
    print("-" * 62)
    for produto in produtos:
        alerta = " !" if produto["estoque_minimo"] > 0 and produto["quantidade"] <= produto["estoque_minimo"] else ""
        print(
            f"{produto['id']:>4}  {produto['nome'][:28]:<28} {formatar_moeda(produto['preco']):>14} "
            f"{produto['quantidade']:>6} {produto['estoque_minimo']:>5}{alerta}"
        )
    print("(! = abaixo do estoque mínimo)")


def mostrar_alertas():
    abaixo = banco.produtos_abaixo_do_minimo()
    if abaixo:
        print(f"\n*** ATENÇÃO: {len(abaixo)} produto(s) abaixo do estoque mínimo ***")
        for produto in abaixo:
            print(f"   - {produto['nome']}: {produto['quantidade']} (mínimo {produto['estoque_minimo']})")


# AÇÕES DO MENU

def cadastrar():
    nome = pedir_nome_unico()
    preco = pedir_preco()
    quantidade = pedir_inteiro("Quantidade inicial: ")
    estoque_minimo = pedir_inteiro("Estoque mínimo (0 = sem alerta): ")

    banco.cadastrar_produto(nome, preco, quantidade, estoque_minimo)
    print("Produto cadastrado com sucesso.")


def listar_ou_buscar():
    while True:
        print("\n=== Produtos ===")
        print("1. Listar todos")
        print("2. Buscar por nome")
        print("3. Ver detalhes de um produto")
        print("0. Voltar")

        escolha = input("Digite a opção: ").strip()

        if escolha == "1":
            produtos = banco.listar_produtos()
            if produtos:
                mostrar_tabela(produtos)
            else:
                print("Nenhum produto cadastrado.")

        elif escolha == "2":
            produtos = banco.buscar_produtos(pedir_texto("Digite o nome do produto: "))
            if produtos:
                mostrar_tabela(produtos)
            else:
                print("Nenhum produto encontrado.")

        elif escolha == "3":
            produto = pedir_produto()
            if produto is not None:
                mostrar_produto(produto)

        elif escolha == "0":
            return

        else:
            print("Erro: Opção inválida.")


def editar():
    produto = pedir_produto()
    if produto is None:
        return

    mostrar_produto(produto)
    print("(Pressione Enter para manter o valor atual. Para mudar a quantidade use Entrada/Saída.)")

    nome = pedir_nome_unico(produto["id"], padrao=produto["nome"])
    preco = pedir_preco(f"Preço [{formatar_moeda(produto['preco'])}]: ", padrao=produto["preco"])
    estoque_minimo = pedir_inteiro(
        f"Estoque mínimo [{produto['estoque_minimo']}]: ", padrao=produto["estoque_minimo"]
    )

    if banco.editar_produto(produto["id"], nome, preco, estoque_minimo):
        print("Produto editado com sucesso.")
    else:
        print("Erro: Produto não encontrado.")


def excluir():
    produto = pedir_produto()
    if produto is None:
        return

    mostrar_produto(produto)
    if not confirmar("Excluir este produto e todo o histórico dele?"):
        print("Exclusão cancelada.")
        return

    if banco.deletar_produto(produto["id"]):
        print("Produto excluído com sucesso.")
    else:
        print("Erro: Produto não encontrado.")


def movimentar(tipo):
    produto = pedir_produto()
    if produto is None:
        return

    print(f"{produto['nome']} - em estoque: {produto['quantidade']}")
    quantidade = pedir_inteiro(
        "Quantidade que entrou: " if tipo == "entrada" else "Quantidade que saiu: ", minimo=1
    )
    observacao = input("Observação (opcional, ex.: nota fiscal, venda): ").strip()

    try:
        nova = banco.registrar_movimentacao(produto["id"], tipo, quantidade, observacao)
    except ValueError as erro:
        print(f"Erro: {erro}")
        return

    print(f"Movimentação registrada. Novo estoque: {nova}")
    if tipo == "saida" and 0 < produto["estoque_minimo"] and nova <= produto["estoque_minimo"]:
        print(f"*** ATENÇÃO: {produto['nome']} chegou ao estoque mínimo ({produto['estoque_minimo']}). Hora de repor! ***")


def ver_historico():
    print("Deixe em branco para ver as últimas movimentações de todos os produtos.")
    texto = input("ID do produto: ").strip()

    produto_id = None
    if texto:
        try:
            produto_id = int(texto)
        except ValueError:
            print("Erro: ID inválido.")
            return

    movimentacoes = banco.historico_movimentacoes(produto_id)
    if not movimentacoes:
        print("Nenhuma movimentação encontrada.")
        return

    print(f"{'Data':<17} {'Tipo':<8} {'Qtd':>5}  {'Produto':<24} Observação")
    print("-" * 75)
    for mov in movimentacoes:
        data = f"{mov['data'][8:10]}/{mov['data'][5:7]}/{mov['data'][:4]} {mov['data'][11:16]}"
        print(f"{data:<17} {mov['tipo']:<8} {mov['quantidade']:>5}  {mov['nome'][:24]:<24} {mov['observacao'] or ''}")


def ver_resumo():
    print("\n=== Resumo do estoque ===")
    print(f"Produtos cadastrados: {banco.total_produtos()}")
    print(f"Unidades em estoque:  {banco.quantidade_estoque()}")
    print(f"Valor do estoque:     {formatar_moeda(banco.total_estoque())}")
    mostrar_alertas()


def menu_automacoes():
    while True:
        print("\n=== Automações ===")
        print("1. Fazer backup do banco agora")
        print("2. Exportar estoque para planilha")
        print("3. Importar produtos de planilha (.csv / .xlsx)")
        print("4. Gerar relatório do dia")
        print("5. Rodar rotina diária completa (backup + planilha + relatório)")
        print("0. Voltar")

        escolha = input("Digite a opção: ").strip()

        try:
            if escolha == "1":
                print(f"Backup salvo em: {automacoes.fazer_backup()}")

            elif escolha == "2":
                print(f"Planilha salva em: {automacoes.exportar_estoque()}")

            elif escolha == "3":
                print("A planilha precisa das colunas: nome, preco, quantidade (estoque_minimo é opcional).")
                caminho = pedir_texto("Caminho do arquivo: ").strip('"')
                if not os.path.isfile(caminho):
                    print("Erro: Arquivo não encontrado.")
                    continue
                resumo = automacoes.importar_planilha(caminho)
                print(f"Cadastrados: {resumo['cadastrados']} | Atualizados: {resumo['atualizados']} | Erros: {len(resumo['erros'])}")
                for erro in resumo["erros"]:
                    print(f"  - {erro}")

            elif escolha == "4":
                print(f"Relatório salvo em: {automacoes.gerar_relatorio_diario()}")

            elif escolha == "5":
                for arquivo in automacoes.rotina_diaria():
                    print(f"Gerado: {arquivo}")

            elif escolha == "0":
                return

            else:
                print("Erro: Opção inválida.")

        except Exception as erro:
            print(f"Erro ao executar a automação: {erro}")


# PROGRAMA PRINCIPAL

OPCOES = {
    "1": ("Cadastrar produto", cadastrar),
    "2": ("Listar / buscar produtos", listar_ou_buscar),
    "3": ("Editar produto", editar),
    "4": ("Excluir produto", excluir),
    "5": ("Entrada de estoque", lambda: movimentar("entrada")),
    "6": ("Saída de estoque", lambda: movimentar("saida")),
    "7": ("Histórico de movimentações", ver_historico),
    "8": ("Resumo do estoque", ver_resumo),
    "9": ("Automações", menu_automacoes),
}


def menu_principal():
    mostrar_alertas()

    while True:
        print("\n=== Sistema de Estoque ===")
        for chave, (descricao, _) in OPCOES.items():
            print(f"{chave}. {descricao}")
        print("0. Sair")

        escolha = input("Digite a opção: ").strip()

        if escolha == "0":
            print("Programa encerrado.")
            return

        if escolha in OPCOES:
            OPCOES[escolha][1]()
        else:
            print("Erro: Opção inválida.")


def main():
    parser = argparse.ArgumentParser(description="Sistema de controle de estoque")
    parser.add_argument(
        "--rotina", action="store_true",
        help="roda a rotina diária (backup + planilha + relatório) sem abrir o menu"
    )
    argumentos = parser.parse_args()

    automacoes.configurar_log()
    banco.inicializar_banco()

    if argumentos.rotina:
        # Modo usado pelo Agendador de Tarefas do Windows
        for arquivo in automacoes.rotina_diaria():
            print(f"Gerado: {arquivo}")
        return

    try:
        menu_principal()
    except (KeyboardInterrupt, EOFError):
        print("\nPrograma encerrado.")


if __name__ == "__main__":
    main()
