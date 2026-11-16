# Desempenho Cinematográfico

Análise exploratória de filmes do TMDB feita apenas com Programação Funcional.

O programa usa os dados públicos do TMDB (The Movie Database) e responde a perguntas sobre os filmes **sem usar bancos SQL para calcular nada e sem `for`/`if`/`def` no cálculo**. O resultado é texto: quer saber quantos filmes um gênero teve, como o gênero compara, se orçamento e faturamento andam juntos ou quais são os filmes mais bilheteros. A interface é um menu simples.

## Ideia central

Programação funcional aqui é: descrever o resultado como uma sequência de transformações, sem laço (`for`/`while`) e sem mudar variáveis. O código divide-se naturalmente:

- **Cálculo (função pura):** filtra, mede, agrupa, compara e ranking — nada de banco, rede ou terminal aí.
- **Bordas de I/O:** banco, rede e terminal. Aí o programa fala com o mundo.

Essa separação é intencional: é o que permite usar funções puras reutilizáveis e ao mesmo tempo ter um programa que roda e guarda dados.

## O que você pode perguntar (menu)

1. **Filtrar filmes** — por gênero, década e nota mínima (mentendo os critérios ao mesmo tempo).
2. **Indicadores gerais** — quantidade, ROI médio, nota média, faturamento médio e as medianas de orçamento e faturamento.
3. **Comparar gêneros** — os gêneros, do maior ROI médio para o menor.
4. **Comparar décadas** — as décadas por nota média.
5. **Correlação orçamento × faturamento** e **orçamento × nota** — Pearson, com o aviso de que correlação não é causalidade.
6. **Rankings** — filmes com maior faturamento, maior nota, maior ROI; gêneros e décadas por indicador.
7. **Montar análise** — o cruzamento livre: você escolhe os atributos (um ou vários, para cruzar) e as estatísticas, e o programa monta a tabela do grupo por indicador.

## Como funciona (sem fundir nas páginas)

Para não misturar o cálculo com o I/O, o núcleo de cálculo é **funcional**: não tem `def`/`for`/`while`/`if` como instrução, `try`/`raise`/`class`. Só usa lambda, função com nome (`x = lambda ...`), `map`/`filter`/`reduce`, compreensões e expressões.

Os truques que aparecem e que vale conhecer:

- `(lambda x: ...)(valor)` — variável local que só vive naquele trecho.
- `(passo1, passo2, resultado)[-1]` — executa passos em ordem e devolve o que interessa.
- `_lancar`/`_tentar` — `raise` e `try` de bolso, só porque os dois são instruções e aí não cabem. Só são usados onde o erro é inevitável: argumento/campo inválido, data/JSON ilegível e falha de rede ou de banco.
- Funções são valores: `metrica("roi")` e `dimensao("genero")` devolvem seletores, e o mesmo `top_filmes` serve para qualquer métrica ou grupo.

O banco e a rede são tratados como camada de I/O (onde `def`/`try`/`if` são normais), separados do que o programa calcula.

## Tecnologia

Python e SQLite, tudo em um único arquivo. O banco é um arquivo local (por padrão `data/cinema.db`), criado e popular a partir dos dados públicos do TMDB.

## Instalação e execução

```bash
# 1. Banco virtual e dependências
python -m venv .venv
.venv/bin/pip install -r requirements.txt

# 2. (opcional) configura o token do TMDB
cp .env.example .env
# edite .env com TMDB_TOKEN = seu "Token de Acesso de Leitura da API"
```

A **ingestão** só é necessária se você quiser regenerar a base a partir do TMDB. Se já existe `data/cinema.db`, você pode pular:

```bash
.venv/bin/python main.py          # abre o menu (usa data/cinema.db)
```

Sem banco, o menu mostra um erro e mostra como criar a base. A ingestão só funciona se `TMDB_TOKEN` estiver no `.env`.

## Referências rápidas

| Coisas | Onde está |
|---|---|
| Modelo do filme e conversão | `Movie`, conversores, `limpar` |
| Filtro (gênero, década, nota, orçamento…) | `make_filtro`, `por_genero`, `por_faixa` |
| Ranking e agrupamento | `top_filmes`, `top_grupos`, `comparar_por_genero` |
| Indicadores (média ROI, nota…) | `metrica`, `media`, `mediana`, `resumir` |
| Cruzamento livre (opção 7) | `analisar`, `_acao_analise` |
| Correlação | `pearson`, `correlacionar`, `formatar_correlacao` |
| Banco e ingestão | `conectar`, `inserir_filmes`, `ler_filmes`, `descobrir_filmes`, `ingerir` |
| Menu e execução | `ACOES`, `_laco`, `main` |

## Artefato de entrega

`A pasta `entrega/` tem o que vai entregue:` o código do termo projeto (`main.py`, `schema.sql`, `requirements.txt`, `.env.example`, `.gitignore`) e os testes. O `main.py` é o arquivo único do trabalho.