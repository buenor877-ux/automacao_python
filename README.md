# Sistema de Controle de Estoque

Sistema em Python para controlar produtos, entradas e saídas de estoque, com interface no navegador, planilhas Excel e rotinas automáticas de backup.

## Funcionalidades

| Página | O que faz |
|---|---|
| 📊 **Painel** | Indicadores (produtos, unidades, valor total, itens a repor) e gráficos |
| 📦 **Produtos** | Cadastro, busca, edição direto na tabela e exclusão com confirmação |
| 🔄 **Movimentações** | Registro de entradas e saídas com histórico filtrável |
| 📑 **Planilhas** | Exporta Excel completo e importa produtos de `.xlsx` ou `.csv` |
| ⚙️ **Automações** | Backup do banco, rotina diária e registro de atividades |

**Regras do sistema**
- A quantidade só muda por entrada ou saída, e toda movimentação fica registrada com data e observação.
- Não é possível dar saída maior que o estoque disponível.
- Produtos no estoque mínimo ou abaixo dele geram alerta no Painel e na planilha.
- Nomes de produtos não se repetem (maiúsculas e minúsculas contam como iguais).

## Como usar

**Instalação** (apenas na primeira vez):
```bash
pip install -r requirements.txt
```

**Abrir o sistema:** dê dois cliques em `Abrir Sistema.bat` ou rode `python main.py`. O sistema abre no navegador em `http://localhost:8501`. Para encerrar, feche a janela preta.

**Rotina automática:** dê dois cliques em `agendar_rotina.bat` para agendar no Windows uma execução diária às 18h, que faz o backup e gera a planilha do dia. Para remover o agendamento:
```bash
schtasks /Delete /TN "Rotina Estoque" /F
```

**Importar planilha:** a planilha precisa das colunas `nome`, `preco` e `quantidade`. A coluna `estoque_minimo` é opcional. Um modelo pronto pode ser baixado na página Planilhas. Produtos novos são cadastrados; produtos já existentes recebem uma entrada com a quantidade da planilha.

## Estrutura do projeto

```
automacao_python/
├── app.py                 Interface (páginas e menu lateral)
├── banco.py               Banco de dados SQLite: tabelas, produtos e movimentações
├── automacoes.py          Planilhas, backup, rotina diária e log
├── main.py                Abre a interface ou roda a rotina (--rotina)
├── Abrir Sistema.bat      Atalho para abrir o sistema
├── agendar_rotina.bat     Agenda a rotina diária no Windows
├── requirements.txt       Bibliotecas necessárias
├── .streamlit/config.toml Tema e configurações da interface
│
├── empresa.db             Banco de dados (não vai para o Git)
├── backups/               Cópias do banco (mantém as 10 mais recentes)
├── relatorios/            Planilhas geradas pela rotina diária
└── logs/automacao.log     Registro das automações
```

**Tecnologias:** Python 3, SQLite, [Streamlit](https://streamlit.io) (interface), pandas e openpyxl (planilhas).

**Banco de dados**
- `produtos`: id, nome, preco, quantidade, estoque_minimo
- `movimentacoes`: id, produto_id, tipo (entrada/saida), quantidade, observacao, data

Bancos de versões anteriores são atualizados automaticamente ao abrir o sistema, sem perda de dados.

## Histórico de versões

**v3 – Interface no navegador**
- Interface com menu lateral, painel com gráficos e tabela editável.
- Planilhas com pandas: Excel com 4 abas (Resumo, Estoque, Repor, Movimentações) e importação com pré-visualização.
- O menu de terminal foi substituído pela interface, o que reduziu o código.
- Banco de dados e cache deixaram de ser versionados no Git.

**v2 – Automações**
- Movimentações de estoque com histórico e alertas de estoque mínimo.
- Backup automático, exportação e importação de planilhas, relatório diário e log.
- Rotina diária agendável pelo Windows.
- Correções: o banco é encontrado de qualquer pasta, o preço aceita vírgula, nomes duplicados com maiúsculas diferentes são bloqueados e a exclusão pede confirmação.

**v1 – Cadastro de produtos**
- Menu no terminal com cadastro, listagem, busca, edição e exclusão de produtos.
- Cálculo do valor total e da quantidade em estoque.

## Próximos passos sugeridos
- Enviar o relatório diário por e-mail.
- Testes automáticos com `pytest`.
- Cadastro de fornecedores e categorias de produtos.
