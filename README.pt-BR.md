# Data to App

### Seus arquivos viram software. Suas decisões permanecem na próxima importação.

[English](README.md) · [Tiếng Việt](README.vi.md) · [한국어](README.ko.md) · [日本語](README.ja.md) · [Español](README.es.md) · [Português](README.pt-BR.md) · [简体中文](README.zh-CN.md) · [ไทย](README.th.md) · [Français](README.fr.md)

**Entregue ao Claude ou Codex seus arquivos e um trabalho real. Receba um aplicativo que você pode executar, inspecionar e tornar seu.**

Data to App transforma CSV e Excel em software operacional que acompanha a origem dos dados: registros pesquisáveis, visualizações úteis, edições permitidas e importações repetíveis. O agente molda o fluxo; um motor determinístico de Python/SQLite separa origem, edições locais e novos snapshots. Você recebe o app funcional, seu código e seus dados locais.

**[Crie seu primeiro ambiente](#execute-o-ambiente-de-estoque)** · **[Instalar para Claude ou Codex](docs/INSTALL.md)** · **[Explorar o contrato de dados](docs/DATA-CONTRACT.md)** · **[Explore a demonstração guiada](https://hieunguyenak92.github.io/data-to-app/)**

![Workspace de estoque sintético gerado pelo Data to App](docs/assets/workspace.jpg)

*Runtime local real com dados sintéticos. O próximo snapshot foi conciliado preservando uma decisão local.*

> **A próxima importação, explícita.** O valor de origem é `12`. Você muda para `20`. O novo arquivo traz `14`. Data to App mantém seu `20` e apresenta o conflito entre origem, local e entrada para você decidir. Mudanças iguais convergem; decisões diferentes continuam visíveis.

## Comece com um trabalho real

Depois de [instalar a skill](docs/INSTALL.md), peça ao agente:

> Use Data to App em `./exports`. Crie uma ferramenta local de estoque com pesquisa, uma visualização de itens abaixo do limite e edição de níveis de reposição e notas. Preserve essas edições ao importar o próximo arquivo e mostre mudanças que exigem uma decisão. Inicie o app e verifique as ações principais.

A skill orienta o agente a inspecionar os arquivos, escolher identidades e operações, construir o app e utilizá-lo. Você descreve o trabalho; o agente cuida do modelo técnico. Uma ambiguidade relevante em chave, unidade ou regra de negócio pode exigir uma resposta clara sua.

Boas aplicações iniciais incluem exportações de estoque e pedidos, listas de contatos que precisam de correções contínuas e registros de projetos ou serviços recebidos periodicamente. A primeira versão se concentra em tabelas locais com chaves próprias e nos fluxos solicitados.

## Projetado para a segunda importação

| Capacidade | O que entrega |
| --- | --- |
| **Perfil orientado à identidade** | Evidências sobre chaves candidatas, valores ausentes, duplicatas e identificadores com zeros à esquerda. |
| **Verificação prévia de joins** | Detecta chaves sem correspondência e multiplicação de linhas antes de combinar dados. |
| **Reconciliação em três vias** | Separa origem, alterações locais e valores recebidos, com decisões por campo em conflitos. |
| **Prévia da importação** | Revise inclusões, atualizações, registros ausentes e conflitos antes de aplicar o snapshot. |
| **Interface operacional** | Pesquisa, visualizações configuradas, edição permitida, resolução de conflitos, histórico e exportação CSV. |
| **Código portátil do aplicativo** | Gera um app Python/SQLite com recursos locais que funciona independentemente da skill instalada. |

Esses mecanismos fornecem evidências para as decisões do agente. Uma coluna única é candidata a chave, mas não prova uma identidade de negócio estável. Um join bem-sucedido também não prova que os totais têm o significado pretendido.

## Execute o ambiente de estoque

Requer **Python 3.10+**. A leitura CSV e o runtime gerado usam a biblioteca padrão. Os dados incluídos são sintéticos.

```bash
git clone https://github.com/hieunguyenak92/data-to-app.git
cd data-to-app
python3 skills/data-to-app/scripts/dta.py demo --out ./inventory-app
python3 inventory-app/app.py --port 8765
```

Abra **http://127.0.0.1:8765**. Pesquise um produto, abra o editor, altere um campo permitido e exporte o resultado. O estado fica no banco SQLite do ambiente e é preservado ao reiniciar o app.

Para visualizar o próximo snapshot de produtos, use outro terminal no diretório do repositório:

```bash
python3 skills/data-to-app/scripts/dta.py import ./inventory-app --table products --file skills/data-to-app/assets/examples/inventory/next/products.csv
```

Adicione `--apply` para aplicá-lo ou use a prévia e a confirmação no app. Edite um campo que também muda no arquivo recebido para experimentar a resolução de conflitos.

Uma importação representa um **snapshot completo de uma tabela**. Registros ausentes são marcados e retidos. Um arquivo parcial marcará os registros omitidos como ausentes. Mudanças de esquema e chaves duplicadas com valores diferentes são rejeitadas antes da alteração de dados.

## Use seus arquivos

CSV é uma tabela de texto; XLSX é uma pasta de trabalho do Excel. Para XLSX, instale o leitor opcional no ambiente Python usado pelas ferramentas:

```bash
python3 -m pip install openpyxl==3.1.5 defusedxml==0.7.1 et-xmlfile==2.0.0
```

Limites de entrada: **10 MiB por arquivo, 50,000 linhas por tabela, 200 colunas e 1,000,000 células**. XLSX usa a primeira planilha por padrão e avisa quando existem outras. Fórmulas não são recalculadas.

Comece com o prompt acima ou inspecione os arquivos diretamente:

```bash
python3 skills/data-to-app/scripts/dta.py inspect ./exports
```

O agente pode usar o perfil para configurar o modelo e construir o ambiente. Os detalhes técnicos estão no [guia de instalação e CLI em inglês](docs/INSTALL.md).

## Exportação, propriedade e limites

O CSV exportado contém os valores efetivos dos registros ativos, incluindo edições locais aceitas. A proteção contra fórmulas pode acrescentar um apóstrofo a células exportadas de risco; os valores armazenados permanecem iguais. Registros ausentes continuam retidos localmente.

O servidor gerado escuta em `127.0.0.1`, usa recursos locais e não exige serviço hospedado para as operações centrais. Durante a criação, continuam valendo as políticas de arquivos e dados do host de IA. Bancos, entradas e exportações podem conter informações sensíveis. [Privacidade, em inglês](docs/PRIVACY.md).

Esta versão é um ambiente local, sem autenticação multiusuário ou garantia de implantação em nuvem. Não executa fórmulas de planilha, deduz todas as regras de negócio, suporta migrações arbitrárias de esquema ou promete recuperação universal. Confira resultados importantes antes de usá-los na operação.

**Comece com o ambiente sintético. Depois, dê ao agente um trabalho real.**
