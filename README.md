# Análise de Desempenho Cinematográfico — Programação Funcional em Python

Projeto da disciplina **Paradigmas de Linguagens de Programação** (UNICAP 2026.2).
Sistema de terminal que compara o desempenho financeiro e crítico de filmes (orçamento,
faturamento, ROI, nota, gênero e década) usando o paradigma funcional: imutabilidade,
funções puras, funções de alta ordem, `filter`/`map`/`reduce`, lambdas e geradores.

**Prazos:** código em 16/11/2026 até 23:55 · apresentações a partir de 17/11/2026.

---

## 1. Fonte dos dados: TMDB

Os dados vêm da API do [The Movie Database (TMDB)](https://developer.themoviedb.org/) (v3),
autenticada por *Bearer token* (`TMDB_TOKEN`, ver `.env.example`).

| Endpoint | Uso | Campos aproveitados |
|---|---|---|
| `GET /discover/movie` | Descobrir filmes, paginado (20 por página). Fornece os **ids**. | `id` |
| `GET /movie/{id}` | Detalhes de cada filme. | `title`, `release_date`, `genres`, `budget`, `revenue`, `vote_average` |

Por que dois endpoints: `/discover/movie` não traz `budget` nem `revenue`; esses campos só
existem em `/movie/{id}`. Usamos `language=pt-BR` para os gêneros virem em português.

> Observação sobre viés: os critérios de `/discover/movie` (ordenação, `vote_count.gte`...)
> definem quais filmes entram na base e, portanto, influenciam as conclusões. Os parâmetros
> exatos serão fixados e documentados na issue de ingestão.

## 2. Por que SQLite

- **Atende ao requisito** do trabalho (consumo de API + banco de dados) sem infraestrutura:
  o banco é um único arquivo, `data/cinema.db`.
- **Zero configuração**: `sqlite3` vem na biblioteca padrão do Python; nada para instalar
  ou subir antes da apresentação.
- **Reprodutível**: depois da ingestão, a análise roda offline, sem token e sem depender
  de rede ou de limite de requisições da API.
- **Escala suficiente**: alguns milhares de filmes cabem com folga.

### Decisão de arquitetura: o banco é só armazenamento

```
TMDB ──► tmdb.py ──► dados.para_movie ──► db.inserir_filmes ──► data/cinema.db
                                                                      │ SELECT simples
terminal ◄── formatacao ◄── núcleo puro (filtros, métricas, ...) ◄── db.ler_filmes
```

- A **ingestão grava**; a **análise lê** com `SELECT` e **calcula em Python puro**.
- É **proibido** usar `GROUP BY`, `AVG`, `SUM`, `ORDER BY` analítico etc. para fazer o
  trabalho analítico: isso descaracterizaria o projeto de programação funcional.
- `db.ler_filmes` devolve um **gerador** de `Movie` (avaliação preguiçosa).

### Regra de I/O

Apenas **`main.py`, `formatacao.py`, `tmdb.py`, `db.py` e `ingestao.py`** tocam rede, banco
ou terminal. O **núcleo** (`dominio`, `dados`, `filtros`, `metricas`, `analises`,
`correlacao`, `ranking`) é composto só de funções puras. `tests/test_pureza.py` verifica
isso automaticamente (sem imports de I/O nem chamadas a `print`/`open`/`input`).

## 3. Estrutura do projeto

```
.
├── main.py          # CLI: orquestra leitura -> núcleo -> exibição
├── dominio.py       # Movie, ResumoGrupo, aliases de tipos
├── dados.py         # normalização/validação de registros
├── filtros.py       # fábricas de predicados
├── metricas.py      # década, lucro, ROI, soma, média, mediana
├── analises.py      # agrupar_por, resumir, comparações
├── correlacao.py    # Pearson
├── ranking.py       # top de filmes e de grupos
├── formatacao.py    # texto formatado e exibição
├── tmdb.py          # cliente HTTP do TMDB
├── db.py            # SQLite (conectar, schema, inserir, ler)
├── ingestao.py      # TMDB -> SQLite
├── schema.sql       # tabela `filmes`
├── data/            # cinema.db (gerado pela ingestão)
├── tests/
├── .env.example     # TMDB_TOKEN=
└── requirements.txt
```

## 4. Formato dos dados

### Registro `Movie` (`dominio.py`)

Imutável (`NamedTuple`): não há atribuição de campos; transformar = criar nova tupla.

| Campo | Tipo | Origem no TMDB | Convenção |
|---|---|---|---|
| `id` | `int` | `id` | chave primária |
| `titulo` | `str` | `title` | — |
| `ano` | `int` | `release_date[:4]` | filmes sem data de lançamento são descartados na ingestão |
| `genero` | `str` | `genres[0].name` | **gênero principal** (um por filme); sem gênero → descartado |
| `orcamento` | `int` | `budget` | USD; **0 = desconhecido** |
| `faturamento` | `int` | `revenue` | USD; **0 = desconhecido** |
| `nota` | `float` | `vote_average` | 0 a 10; **0.0 = sem avaliações** |

Consequências das convenções: o ROI só é calculado com `orcamento > 0`; correlações e
comparações financeiras usam apenas filmes com orçamento e faturamento válidos
(`dados.tem_financeiro_valido`). O ROI é uma **estimativa** `(faturamento - orcamento) / orcamento`,
não uma apuração completa de lucro.

### Schema (`schema.sql`)

```sql
CREATE TABLE IF NOT EXISTS filmes (
    id          INTEGER PRIMARY KEY,
    titulo      TEXT    NOT NULL,
    ano         INTEGER NOT NULL,
    genero      TEXT    NOT NULL,
    orcamento   INTEGER NOT NULL DEFAULT 0 CHECK (orcamento   >= 0),
    faturamento INTEGER NOT NULL DEFAULT 0 CHECK (faturamento >= 0),
    nota        REAL    NOT NULL DEFAULT 0.0 CHECK (nota BETWEEN 0 AND 10)
);
```

A ordem das colunas é a ordem dos campos de `Movie`: `Movie(*linha)` lê e a própria tupla
é gravada.

### Exemplo de linha

| id | titulo | ano | genero | orcamento | faturamento | nota |
|---|---|---|---|---|---|---|
| 603 | Matrix | 1999 | Ação | 63000000 | 463517383 | 8.2 |

## 5. Contrato público dos módulos

Assinaturas (com *type hints*) que as duas frentes devem respeitar. Os corpos ainda são
`raise NotImplementedError`, exceto `dominio.py` e `db.py`. Alterar uma assinatura exige
combinar com a dupla.

### `dominio.py` — Domínio (tipos compartilhados) (puro)

```python
class Movie(NamedTuple):
    id: int
    titulo: str
    ano: int
    genero: str
    orcamento: int
    faturamento: int
    nota: float

class ResumoGrupo(NamedTuple):
    quantidade: int
    roi_medio: float | None
    nota_media: float | None
    faturamento_medio: float | None

Predicado = Callable[[Movie], bool]

Seletor = Callable[[Movie], float | None]
```

### `dados.py` — Preparação e validação dos dados (puro)

```python
# Converte o JSON de /movie/{id} em Movie.
def para_movie(detalhe: Mapping[str, Any]) -> Movie | None

# True se orcamento > 0 (requisito para calcular ROI).
def tem_orcamento_valido(filme: Movie) -> bool

# True se faturamento > 0.
def tem_faturamento_valido(filme: Movie) -> bool

# True se orçamento e faturamento são ambos > 0.
def tem_financeiro_valido(filme: Movie) -> bool

# True se nota > 0 (filme tem avaliações).
def tem_nota_valida(filme: Movie) -> bool

# Mantém (lazy) só os filmes com orçamento e faturamento válidos.
def com_financeiro_valido(filmes: Iterable[Movie]) -> Iterator[Movie]

# Mantém (lazy) só os filmes com nota válida.
def com_nota_valida(filmes: Iterable[Movie]) -> Iterator[Movie]
```

### `filtros.py` — Filtros (funções de alta ordem) (puro)

```python
# Predicado: filme do gênero informado (sem diferenciar maiúsculas).
def por_genero(genero: str) -> Predicado

# Predicado: filme lançado na década informada (ex.: 1990 -> 1990..1999).
def por_decada(decada: int) -> Predicado

# Predicado: minimo <= orcamento <= maximo (maximo=None -> sem limite).
def por_faixa_orcamento(minimo: int=0, maximo: int | None=None) -> Predicado

# Predicado: minimo <= faturamento <= maximo (maximo=None -> sem limite).
def por_faixa_faturamento(minimo: int=0, maximo: int | None=None) -> Predicado

# Predicado: minimo <= nota <= maximo.
def por_faixa_nota(minimo: float=0.0, maximo: float=10.0) -> Predicado

# Composição (E lógico) de predicados; sem argumentos, aceita tudo.
def combinar(*predicados: Predicado) -> Predicado

# Aplica o predicado de forma preguiçosa (wrapper de `filter`).
def filtrar(predicado: Predicado, filmes: Iterable[Movie]) -> Iterator[Movie]
```

### `metricas.py` — Métricas elementares (puro)

```python
# Década de lançamento (ex.: 1994 -> 1990).
def decada(filme: Movie) -> int

# faturamento - orcamento (estimativa; ignora outros custos).
def lucro(filme: Movie) -> int

# (faturamento - orcamento) / orcamento; None se orcamento <= 0.
def roi(filme: Movie) -> float | None

# Soma via reduce; 0.0 para sequência vazia.
def soma(valores: Iterable[float]) -> float

# Média aritmética; None para sequência vazia.
def media(valores: Iterable[float]) -> float | None

# Mediana; None para sequência vazia.
def mediana(valores: Iterable[float]) -> float | None
```

### `analises.py` — Agrupamento e comparação de grupos (puro)

```python
# Agrupa filmes pela chave sem mutar a entrada (ex.: genero, metricas.decada).
def agrupar_por(chave: Callable[[Movie], K], filmes: Iterable[Movie]) -> Mapping[K, tuple[Movie, ...]]

# Calcula quantidade, ROI médio, nota média e faturamento médio do grupo.
def resumir(filmes: Iterable[Movie]) -> ResumoGrupo

# Indicadores por gênero.
def comparar_por_genero(filmes: Iterable[Movie]) -> Mapping[str, ResumoGrupo]

# Indicadores por década.
def comparar_por_decada(filmes: Iterable[Movie]) -> Mapping[int, ResumoGrupo]
```

### `correlacao.py` — Correlação de Pearson (puro)

```python
# Coeficiente de Pearson; None se < 2 pares ou variância zero.
def pearson(xs: Sequence[float], ys: Sequence[float]) -> float | None

# Correlação entre dois seletores, descartando filmes em que algum é None.
def correlacionar(x: Seletor, y: Seletor, filmes: Iterable[Movie]) -> float | None

# Correlação orçamento x faturamento (só filmes com financeiro válido).
def orcamento_vs_faturamento(filmes: Iterable[Movie]) -> float | None

# Correlação orçamento x nota (só filmes com orçamento e nota válidos).
def orcamento_vs_nota(filmes: Iterable[Movie]) -> float | None
```

### `ranking.py` — Rankings (puro)

```python
# Os n primeiros filmes pela chave (ex.: faturamento, nota, metricas.roi).
def top_filmes(n: int, chave: Seletor, filmes: Iterable[Movie], decrescente: bool=True) -> tuple[Movie, ...]

# Os n primeiros grupos pela chave (ex.: lambda r: r.roi_medio).
def top_grupos(n: int, chave: Callable[[ResumoGrupo], float | None], grupos: Mapping[K, ResumoGrupo], decrescente: bool=True) -> tuple[tuple[K, ResumoGrupo], ...]
```

### `formatacao.py` — Formatação e exibição (I/O: terminal)

```python
# Ex.: 1234567 -> 'US$ 1.234.567'.
def formatar_moeda(valor: float) -> str

# Ex.: 3.0 -> '300,0%'; None -> '-'.
def formatar_percentual(valor: float | None) -> str

# Tabela de texto com os filmes.
def formatar_filmes(filmes: Iterable[Movie]) -> str

# Tabela de texto comparando grupos (gênero, década...).
def formatar_comparacao(titulo: str, grupos: Iterable[tuple[object, ResumoGrupo]]) -> str

# Linha de texto com o coeficiente (e aviso de que não é causalidade).
def formatar_correlacao(rotulo: str, r: float | None) -> str

# Escreve o texto no terminal.
def exibir(texto: str) -> None
```

### `tmdb.py` — Cliente da API do TMDB (I/O: rede)

```python
# Lê TMDB_TOKEN do ambiente/.env; levanta RuntimeError se ausente.
def carregar_token() -> str

# GET /discover/movie (uma página): lista de filmes com seus ids.
def descobrir_filmes(token: str, pagina: int=1) -> Mapping[str, Any]

# GET /movie/{id}: detalhes do filme (budget, revenue, genres...).
def detalhar_filme(token: str, filme_id: int) -> Mapping[str, Any]
```

### `db.py` — Persistência SQLite (I/O: banco)

```python
# Abre (e cria, se preciso) o banco. Aceita ':memory:' para testes.
def conectar(caminho: Path | str=DB_PADRAO) -> sqlite3.Connection

# Cria a tabela `filmes` a partir de schema.sql (idempotente).
def inicializar_schema(conn: sqlite3.Connection) -> None

# Grava (insere ou substitui por id) os filmes; devolve quantos foram gravados.
def inserir_filmes(conn: sqlite3.Connection, filmes: Iterable[Movie]) -> int

# Gerador de todos os filmes (SELECT simples, sem agregação).
def ler_filmes(conn: sqlite3.Connection) -> Iterator[Movie]
```

### `ingestao.py` — Ingestão TMDB → SQLite (I/O: rede + banco)

```python
# Gera (lazy) Movies válidos a partir de `paginas` páginas do discover.
def coletar_filmes(token: str, paginas: int) -> Iterator[Movie]

# Cria o schema, coleta e grava os filmes; devolve quantos foram gravados.
def ingerir(paginas: int=25, caminho_db: Path | str=DB_PADRAO) -> int
```

### `main.py` — CLI / orquestração (I/O: terminal)

```python
# Interpreta os argumentos, executa a análise pedida e devolve o código de saída.
def main(argv: Sequence[str] | None=None) -> int
```


## 6. Como executar (Windows / PowerShell)

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

Copy-Item .env.example .env      # depois edite o .env e preencha TMDB_TOKEN

python -m pytest                 # testes
python main.py                   # CLI (a ser implementado)
```

O `.env` está no `.gitignore`: **nunca** commite o token.

## 7. Critérios de aceite da issue 1

- [x] Esqueleto commitado (arquivos e pastas da seção 3).
- [x] `README.md` com contrato, schema e formato dos dados.
- [x] Nenhum módulo do núcleo faz I/O (verificado por `tests/test_pureza.py`).
