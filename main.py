import banco


def mostrar_produto(produto):
    print(f"ID: {produto[0]}")
    print(f"Nome: {produto[1]}")

    preco = f"{produto[2]:.2f}".replace(".", ",")
    print(f"Preço: R$ {preco}")

    print(f"Quantidade: {produto[3]}")
    print("---------------------------")


def pedir_preco():
    while True:
        try:
            preco = float(input("Digite o preço do produto: "))

            if preco < 0:
                print("Erro: Preço inválido.")
            else:
                return preco
        except ValueError:
            print("Erro: Preço inválido.")

            


while True:
    print("===Sistema de Produtos===")
    print("1. Cadastrar Produto")
    print("2. Listar Produtos")
    print("3. Editar Produto")
    print("4. Deletar Produto")
    print("5. Ver Valor total do estoque")
    print("6. Ver quantidade de produtos")
    print("7. Sair")

    try:
        opcao = int(input("Digite a opção: "))
    except ValueError:
        print("Erro: Opção inválida.")
        continue

    # CADASTRAR PRODUTO
    if opcao == 1:

        while True:
            nome = input("Digite o nome do produto: ").strip()

            produto_existente = banco.produto_existe(nome)

            if nome == "":
                print("Erro: Nome do produto inválido.")

            elif produto_existente is not None:
                print("Erro: Produto já cadastrado.")

            else:
                break

        preco = pedir_preco()

        while True:
            try:
                quantidade = int(input("Digite a quantidade do produto: "))

                if quantidade < 0:
                    print("Erro: Quantidade inválida.")
                else:
                    break

            except ValueError:
                print("Erro: Quantidade inválida.")

        banco.cadastrar_produto(nome, preco, quantidade)

        print("Produto cadastrado com sucesso.")

    # LISTAR / BUSCAR PRODUTOS
    elif opcao == 2:

        while True:
            print("=== Produtos ===")
            print("1. Listar todos")
            print("2. Buscar produto")
            print("3. Voltar")

            try:
                escolha = int(input("Digite a opção: "))
            except ValueError:
                print("Erro: Opção inválida.")
                continue

            # LISTAR TODOS
            if escolha == 1:

                produtos = banco.listar_produtos()

                print("=== Produtos cadastrados ===")

                if len(produtos) == 0:
                    print("Nenhum produto cadastrado.")

                else:
                    for produto in produtos:
                        mostrar_produto(produto)

            # BUSCAR PRODUTO
            elif escolha == 2:

                nome = input("Digite o nome do produto: ")

                if nome.strip() == "":
                    print("Erro: Nome do produto inválido.")
                    continue

                produtos = banco.buscar_produtos(nome)

                if len(produtos) == 0:
                    print("Nenhum produto encontrado.")

                else:
                    for produto in produtos:
                        mostrar_produto(produto)

            # VOLTAR
            elif escolha == 3:
                break

            else:
                print("Erro: Opção inválida.")

    # EDITAR PRODUTO
    elif opcao == 3:

        while True:
            try:
                id = int(input("Digite o ID do produto: "))

                if id <= 0:
                    print("Erro: ID inválido.")
                else:
                    break

            except ValueError:
                print("Erro: ID inválido.")

        produto = banco.buscar_produto_por_id(id)


        if produto is None:
            print("Erro: Produto não encontrado.")
            continue

        mostrar_produto(produto)

        while True:
            nome = input("Digite o nome do produto: ").strip()

            outro_produto = banco.outro_produto_existe(nome, id)

            if nome == "":
                print("Erro: Nome do produto inválido.")

            elif outro_produto is not None:
                print("Erro: Produto já cadastrado.")

            else:
                break


        preco = pedir_preco()   

        while True:
            try:
                quantidade = int(input("Digite a quantidade do produto: "))

                if quantidade < 0:
                    print("Erro: Quantidade inválida.")
                else:
                    break

            except ValueError:
                print("Erro: Quantidade inválida.")

        resultado = banco.editar_produto(
            id,
            nome,
            preco,
            quantidade
        )

        if resultado:
            print("Produto editado com sucesso.")
        else:
            print("Erro: Produto não encontrado.")

    # DELETAR PRODUTO
    elif opcao == 4:

        while True:
            try:
                id = int(input("Digite o ID do produto: "))

                if id <= 0:
                    print("Erro: ID inválido.")
                else:
                    break

            except ValueError:
                print("Erro: ID inválido.")

        resultado = banco.deletar_produto(id)

        if resultado:
            print("Produto deletado com sucesso.")
        else:
            print("Erro: Produto não encontrado.")
    # VER VALOR TOTAL DO ESTOQUE
    elif opcao == 5:
        total = banco.total_estoque()
        total_formatado = f"{total:.2f}".replace(".", ",")
        print(f"Valor total do estoque: R$ {total_formatado}")

    # VER QUANTIDADE DE PRODUTOS
    elif opcao == 6:
        quantidade = banco.quantidade_estoque()
        print(f"Quantidade de produtos: {quantidade}")

    # SAIR
    elif opcao == 7:
        print("Programa encerrado.")
        break

    else:
        print("Erro: Opção inválida.")
        continue
    

    