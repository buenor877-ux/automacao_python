# Sistema de Controle de Estoque

Sistema em Python para controlar produtos, entradas e saídas de estoque, com interface no navegador, planilhas Excel e rotinas automáticas de backup.

## Funcionalidades

| Página | O que faz |
|---|---|
| 📊 **Painel** | Indicadores (produtos, unidades, valor total, itens a repor) e gráficos |
| 📦 **Produtos** | Cadastro, busca, filtro por categoria, edição direto na tabela e exclusão com confirmação |
| 🔄 **Movimentações** | Registro de entradas e saídas com histórico filtrável |
| 🏷️ **Categorias e fornecedores** | Cadastro de categorias e de fornecedores (nome, telefone, e-mail) |
| 📑 **Planilhas** | Exporta Excel completo e importa produtos de `.xlsx` ou `.csv` |
| ⚙️ **Automações** | Backup do banco, rotina diária, relatório por e-mail e registro de atividades |

**Regras do sistema**
- A quantidade só muda por entrada ou saída, e toda movimentação fica registrada com data e observação.
- Não é possível dar saída maior que o estoque disponível.
- Produtos no estoque mínimo ou abaixo dele geram alerta no Painel e na planilha.
- Nomes de produtos, categorias e fornecedores não se repetem (maiúsculas e minúsculas contam como iguais).
- Excluir uma categoria ou um fornecedor não exclui os produtos: eles apenas ficam sem categoria ou sem fornecedor.

## Como usar

**Instalação** (apenas na primeira vez):
```bash
pip install -r requirements.txt
```

**Abrir o sistema:** dê dois cliques em `Abrir Sistema.bat` ou rode `python main.py`. O sistema abre no navegador em `http://localhost:8501`. Para encerrar, feche a janela preta.

**Rotina automática:** dê dois cliques em `agendar_rotina.bat` para agendar no Windows uma execução diária às 18h. Ela faz o backup, gera a planilha do dia e, se ativado, envia o relatório por e-mail. Para remover o agendamento:
```bash
schtasks /Delete /TN "Rotina Estoque" /F
```

**Relatório por e-mail:** em Automações, preencha o servidor, o e-mail remetente, a senha de app e os destinatários, e use **Enviar e-mail de teste agora** para conferir. O e-mail traz o resumo do estoque e os produtos para repor, com a planilha completa em anexo.
- **Gmail:** servidor `smtp.gmail.com`, porta `465`. Use uma *senha de app*, criada em myaccount.google.com/apppasswords (exige a verificação em duas etapas), e não a senha normal da conta.
- **Outlook/Hotmail:** servidor `smtp-mail.outlook.com`, porta `587`.
- As configurações ficam em `config_email.json`, só neste computador. Esse arquivo não vai para o Git.

**Importar planilha:** a planilha precisa das colunas `nome`, `preco` e `quantidade`. As colunas `estoque_minimo`, `categoria` e `fornecedor` são opcionais; categorias e fornecedores que ainda não existem são criados automaticamente. Um modelo pronto pode ser baixado na página Planilhas. Produtos novos são cadastrados; produtos já existentes recebem uma entrada com a quantidade da planilha.

**Testes automáticos:** os testes verificam as regras do sistema usando um banco temporário, sem tocar no `empresa.db`. Para rodar:
```bash
python -m pytest
```

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
├── tests/                 Testes automáticos (pytest)
├── pytest.ini             Configuração dos testes
│
├── empresa.db             Banco de dados (não vai para o Git)
├── config_email.json      Configuração de e-mail (não vai para o Git)
├── backups/               Cópias do banco (mantém as 10 mais recentes)
├── relatorios/            Planilhas geradas pela rotina diária
└── logs/automacao.log     Registro das automações
```

**Tecnologias:** Python 3, SQLite, [Streamlit](https://streamlit.io) (interface), pandas e openpyxl (planilhas), smtplib (e-mail) e pytest (testes).

**Banco de dados**
- `produtos`: id, nome, preco, quantidade, estoque_minimo, categoria_id, fornecedor_id
- `movimentacoes`: id, produto_id, tipo (entrada/saida), quantidade, observacao, data
- `categorias`: id, nome
- `fornecedores`: id, nome, telefone, email

Bancos de versões anteriores são atualizados automaticamente ao abrir o sistema, sem perda de dados.

## Histórico de versões

**v4 – Categorias, fornecedores, e-mail e testes**
- Cadastro de categorias e fornecedores, com seleção na tabela de produtos e filtro por categoria.
- Painel com gráfico de valor por categoria e contato do fornecedor nos alertas de reposição.
- A aba Repor da planilha passou a trazer o telefone e o e-mail do fornecedor.
- Relatório diário por e-mail com resumo, produtos para repor e planilha em anexo.
- 30 testes automáticos com pytest.

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
- Pedido de compra automático para os produtos a repor, agrupado por fornecedor.
- Login com usuários e registro de quem fez cada movimentação.
- Leitura de código de barras nas entradas e saídas.
