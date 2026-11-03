from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

import automacoes as auto
import banco
from automacoes import formatar_moeda

st.set_page_config(page_title="Controle de Estoque", page_icon="📦", layout="wide")
banco.inicializar_banco()
auto.configurar_log()


def avisar(mensagem, icone="✅"):
    """Mostra a mensagem depois do st.rerun(), quando a tela já foi atualizada."""
    st.session_state["aviso"] = (mensagem, icone)


if "aviso" in st.session_state:
    mensagem, icone = st.session_state.pop("aviso")
    st.toast(mensagem, icon=icone)


# PÁGINAS

def painel():
    st.title("📊 Painel")
    estoque = auto.tabela_estoque()
    movimentacoes = auto.tabela_movimentacoes()
    repor = estoque[estoque["situacao"] == "Repor"]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📦 Produtos", len(estoque), border=True)
    c2.metric("🔢 Unidades", int(estoque["quantidade"].sum()), border=True)
    c3.metric("💰 Valor", formatar_moeda(estoque["valor_total"].sum()), border=True)
    c4.metric("⚠️ Repor", len(repor), border=True)

    if not repor.empty:
        st.warning(f"**{len(repor)} produto(s) no estoque mínimo ou abaixo dele:**")
        st.dataframe(
            repor[["nome", "quantidade", "estoque_minimo"]],
            column_config={"nome": "Produto", "quantidade": "Em estoque", "estoque_minimo": "Mínimo"},
            hide_index=True,
        )

    if estoque.empty:
        st.info("Nenhum produto cadastrado ainda. Comece pela página **Produtos** ou importe uma planilha.")
        return

    esquerda, direita = st.columns(2)
    with esquerda:
        st.subheader("Valor em estoque por produto")
        st.bar_chart(
            estoque.nlargest(15, "valor_total"), x="nome", y="valor_total",
            x_label="", y_label="R$", horizontal=True,
        )
    with direita:
        st.subheader("Entradas e saídas (últimos 30 dias)")
        recentes = movimentacoes[movimentacoes["data"] >= datetime.now() - timedelta(days=30)]
        if recentes.empty:
            st.caption("Nenhuma movimentação nos últimos 30 dias.")
        else:
            por_dia = recentes.pivot_table(
                index=recentes["data"].dt.date, columns="tipo", values="quantidade", aggfunc="sum", fill_value=0
            )
            st.bar_chart(por_dia, color=["#2e9d5b", "#d9534f"][: len(por_dia.columns)], stack=False)


def produtos():
    st.title("📦 Produtos")
    estoque = auto.tabela_estoque()

    with st.expander("➕ Cadastrar novo produto"):
        with st.form("novo_produto", clear_on_submit=True):
            nome = st.text_input("Nome do produto")
            c1, c2, c3 = st.columns(3)
            preco = c1.number_input("Preço (R$)", min_value=0.0, step=0.5, format="%.2f")
            quantidade = c2.number_input("Quantidade inicial", min_value=0, step=1)
            minimo = c3.number_input("Estoque mínimo (0 = sem alerta)", min_value=0, step=1)

            if st.form_submit_button("Cadastrar", type="primary"):
                nome = nome.strip()
                if not nome:
                    st.error("Digite o nome do produto.")
                elif banco.produto_existe(nome):
                    st.error(f"Já existe um produto chamado \"{nome}\".")
                else:
                    banco.cadastrar_produto(nome, preco, quantidade, minimo)
                    avisar(f"{nome} cadastrado.")
                    st.rerun()

    busca = st.text_input("🔎 Buscar produto", placeholder="Digite parte do nome...")
    if busca:
        estoque = estoque[estoque["nome"].str.contains(busca, case=False, regex=False)]

    st.caption("Edite nome, preço e estoque mínimo direto na tabela e clique em **Salvar alterações**. "
               "A quantidade muda pela página Movimentações.")

    editado = st.data_editor(
        estoque,
        key="tabela_produtos",
        hide_index=True,
        width="stretch",
        disabled=["id", "quantidade", "valor_total", "situacao"],
        column_config={
            "id": st.column_config.NumberColumn("ID", width="small"),
            "nome": st.column_config.TextColumn("Nome", required=True),
            "preco": st.column_config.NumberColumn("Preço", format="R$ %.2f", min_value=0),
            "quantidade": st.column_config.NumberColumn("Quantidade"),
            "estoque_minimo": st.column_config.NumberColumn("Estoque mínimo", min_value=0, step=1),
            "valor_total": st.column_config.NumberColumn("Valor total", format="R$ %.2f"),
            "situacao": st.column_config.TextColumn("Situação"),
        },
    )

    alterados = editado[(editado[["nome", "preco", "estoque_minimo"]] != estoque[["nome", "preco", "estoque_minimo"]]).any(axis=1)]
    if st.button(f"💾 Salvar alterações ({len(alterados)})", disabled=alterados.empty, type="primary"):
        erros = []
        for produto in alterados.itertuples():
            nome = str(produto.nome).strip()
            if not nome or banco.produto_existe(nome, ignorar_id=produto.id):
                erros.append(f"ID {produto.id}: nome vazio ou já usado por outro produto")
                continue
            banco.editar_produto(produto.id, nome, float(produto.preco), int(produto.estoque_minimo))
        if erros:
            st.error("\n\n".join(erros))
        else:
            avisar(f"{len(alterados)} produto(s) atualizado(s).")
            st.rerun()

    with st.expander("🗑️ Excluir produto"):
        opcoes = dict(zip(estoque["nome"], estoque["id"]))
        escolhido = st.selectbox("Produto", list(opcoes), index=None, placeholder="Escolha o produto")
        confirmar = st.checkbox("Confirmo que quero excluir este produto e todo o histórico dele")
        if st.button("Excluir", disabled=not (escolhido and confirmar)):
            banco.deletar_produto(int(opcoes[escolhido]))
            avisar(f"{escolhido} excluído.", "🗑️")
            st.rerun()


def movimentacoes():
    st.title("🔄 Movimentações")
    estoque = auto.tabela_estoque()

    if estoque.empty:
        st.info("Cadastre um produto antes de registrar movimentações.")
        return

    with st.form("movimentacao", clear_on_submit=True, border=True):
        st.subheader("Registrar entrada ou saída")
        tipo = st.segmented_control("Tipo", ["⬆️ Entrada", "⬇️ Saída"], default="⬆️ Entrada")
        produtos_por_id = estoque.set_index("id")
        produto_id = st.selectbox(
            "Produto", produtos_por_id.index,
            format_func=lambda i: f"{produtos_por_id.at[i, 'nome']}  (em estoque: {produtos_por_id.at[i, 'quantidade']})",
        )
        c1, c2 = st.columns([1, 3])
        quantidade = c1.number_input("Quantidade", min_value=1, step=1)
        observacao = c2.text_input("Observação", placeholder="Ex.: venda balcão, NF 1234, compra fornecedor")

        if st.form_submit_button("Registrar", type="primary"):
            tipo_banco = "entrada" if tipo and "Entrada" in tipo else "saida"
            try:
                nova = banco.registrar_movimentacao(int(produto_id), tipo_banco, int(quantidade), observacao)
            except ValueError as erro:
                st.error(str(erro))
            else:
                produto = produtos_por_id.loc[produto_id]
                if tipo_banco == "saida" and 0 < produto["estoque_minimo"] >= nova:
                    avisar(f"{produto['nome']} chegou ao estoque mínimo ({nova} un.). Hora de repor!", "⚠️")
                else:
                    avisar(f"Movimentação registrada. Novo estoque de {produto['nome']}: {nova}")
                st.rerun()

    st.subheader("Histórico")
    historico = auto.tabela_movimentacoes()
    c1, c2, c3 = st.columns([2, 1, 1])
    filtro_produto = c1.multiselect("Produtos", sorted(historico["produto"].unique()), placeholder="Todos")
    filtro_tipo = c2.selectbox("Tipo", ["Todos", "entrada", "saida"])
    periodo = c3.date_input("Período", value=(datetime.now().date() - timedelta(days=30), datetime.now().date()))

    if filtro_produto:
        historico = historico[historico["produto"].isin(filtro_produto)]
    if filtro_tipo != "Todos":
        historico = historico[historico["tipo"] == filtro_tipo]
    if isinstance(periodo, tuple) and len(periodo) == 2:
        historico = historico[historico["data"].dt.date.between(*periodo)]

    st.dataframe(
        historico.drop(columns="id"),
        hide_index=True,
        width="stretch",
        column_config={
            "data": st.column_config.DatetimeColumn("Data", format="DD/MM/YYYY HH:mm"),
            "produto": "Produto", "tipo": "Tipo", "quantidade": "Quantidade", "observacao": "Observação",
        },
    )
    st.download_button(
        "⬇️ Baixar histórico filtrado (CSV)",
        historico.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig"),
        file_name=f"movimentacoes_{datetime.now():%Y-%m-%d}.csv",
        mime="text/csv",
    )


def planilhas():
    st.title("📑 Planilhas")
    exportar, importar = st.tabs(["⬇️ Exportar", "⬆️ Importar"])

    with exportar:
        st.write("Planilha Excel completa com as abas **Resumo**, **Estoque**, **Repor** e **Movimentações**, "
                 "já formatada com filtros e valores em reais.")
        st.download_button(
            "📥 Baixar planilha do estoque",
            auto.gerar_planilha(),
            file_name=f"estoque_{datetime.now():%Y-%m-%d}.xlsx",
            type="primary",
        )

    with importar:
        st.write("Envie um **.xlsx** ou **.csv** com as colunas `nome`, `preco`, `quantidade` "
                 "e, se quiser, `estoque_minimo`. Produtos novos são cadastrados; "
                 "produtos que já existem recebem uma entrada com a quantidade da planilha.")
        st.download_button("📄 Baixar planilha modelo", auto.modelo_importacao(), file_name="modelo_importacao.xlsx")

        arquivo = st.file_uploader("Planilha", type=["xlsx", "csv"])
        if arquivo is None:
            return
        try:
            df = auto.ler_planilha(arquivo, arquivo.name)
        except Exception as erro:
            st.error(f"Não foi possível ler a planilha: {erro}")
            return

        st.write(f"Pré-visualização ({len(df)} linhas):")
        st.dataframe(df, hide_index=True, width="stretch")

        if st.button("Importar estas linhas", type="primary"):
            resumo = auto.importar_planilha(df)
            st.success(f"Cadastrados: **{resumo['cadastrados']}** · Atualizados: **{resumo['atualizados']}** · "
                       f"Erros: **{len(resumo['erros'])}**")
            for erro in resumo["erros"]:
                st.error(erro)


def automacoes():
    st.title("⚙️ Automações")

    c1, c2 = st.columns(2)
    with c1, st.container(border=True):
        st.subheader("💾 Backup do banco")
        st.caption("Copia o banco para a pasta backups/ e mantém os 10 mais recentes.")
        if st.button("Fazer backup agora", type="primary"):
            caminho = auto.fazer_backup()
            st.success(f"Backup salvo: {caminho}")
        backups = auto.listar_backups()
        if backups:
            st.write(f"Último backup: **{backups[0]}** ({len(backups)} guardados)")

    with c2, st.container(border=True):
        st.subheader("🗓️ Rotina diária")
        st.caption("Faz o backup e salva a planilha completa do dia em relatorios/.")
        if st.button("Rodar rotina agora", type="primary"):
            for arquivo in auto.rotina_diaria():
                st.success(f"Gerado: {arquivo}")
        st.info("Para rodar sozinha todo dia às 18h, dê dois cliques em **agendar_rotina.bat** na pasta do projeto.")

    st.subheader("📜 Registro de atividades")
    st.code(auto.ultimas_linhas_log() or "Nenhuma atividade registrada ainda.", language=None)


# MENU LATERAL

menu = st.navigation([
    st.Page(painel, title="Painel", icon="📊", default=True),
    st.Page(produtos, title="Produtos", icon="📦"),
    st.Page(movimentacoes, title="Movimentações", icon="🔄"),
    st.Page(planilhas, title="Planilhas", icon="📑"),
    st.Page(automacoes, title="Automações", icon="⚙️"),
])
st.sidebar.caption(f"Banco: {banco.CAMINHO_DB}")
menu.run()
