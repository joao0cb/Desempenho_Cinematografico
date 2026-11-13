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
| `GET /movie/{id}` | Detalhes de cada filme. | `title`, `release_date`, `genres`, `budget`, `revenue`, `vote_average`, `runtime`, `original_language`, `credits`, `release_dates`, `production_countries`, `production_companies`, `belongs_to_collection` |

Por que dois endpoints: `/discover/movie` não traz `budget` nem `revenue`; esses campos só
existem em `/movie/{id}`. Usamos `language=pt-BR` para os gêneros virem em português.

> Observação sobre viés: os critérios de `/discover/movie` (ordenação, `vote_count.gte`...)
> definem quais filmes entram na base e, portanto, influenciam as conclusões. Os parâmetros
> exatos são fixados em `ingestao.py` e documentados aqui quando a ingestão for implementada.

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
- É **proibido** usar `GROUP BY`, `AVG`, `SUM` etc. para fazer o trabalho analítico:
  isso descaracterizaria o projeto de programação funcional.
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
├── metricas.py      # década, lucro, ROI, soma, média, mediana + dimensões
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
│   ├── test_dominio.py
│   ├── test_dados.py
│   ├── test_db.py
│   ├── test_metricas.py
│   └── test_pureza.py
├── .env.example     # TMDB_TOKEN=
└── requirements.txt # requests, python-dotenv, pytest
```

## 4. Formato dos dados

### Registro `Movie` (`dominio.py`)

Imutável (`NamedTuple`): não há atribuição de campos; transformar = criar nova tupla
(`filme._replace(...)`). Só `id`, `titulo` e `ano` são obrigatórios.

| Campo | Tipo | Origem no TMDB | Convenção de "desconhecido" |
|---|---|---|---|
| `id` | `int` | `id` | — (chave primária) |
| `titulo` | `str` | `title` | `''` |
| `ano` | `int` | `release_date[:4]` | `0` |
| `data_lancamento` | `str` | `release_date` | `''` (ISO `AAAA-MM-DD`) |
| `generos` | `tuple[str, ...]` | `genres[].name` | `()` |
| `orcamento` | `int` | `budget` | `0` (USD) |
| `faturamento` | `int` | `revenue` | `0` (USD) |
| `nota` | `float` | `vote_average` | `0.0` (0 a 10) |
| `popularidade` | `float` | `popularity` | `0.0` |
| `duracao` | `int` | `runtime` | `0` (minutos) |
| `idioma_original` | `str` | `original_language` | `''` |
| `classificacao` | `str` | `release_dates` (EUA) | `''` |
| `diretor` | `str` | `credits.crew` (`job == 'Director'`) | `''` |
| `elenco` | `tuple[str, ...]` | `credits.cast` (5 primeiros) | `()` |
| `paises` | `tuple[str, ...]` | `production_countries[].iso_3166_1` | `()` |
| `empresas` | `tuple[str, ...]` | `production_companies[].name` | `()` |
| `colecao` | `str` | `belongs_to_collection.name` | `''` |

Consequências das convenções: o ROI só é calculado com `orcamento > 0`; correlações e
comparações financeiras usam apenas filmes com orçamento e faturamento válidos
(`dados.tem_financeiro_valido`). O ROI é uma **estimativa**
`(faturamento - orcamento) / orcamento`, não uma apuração completa de lucro.

### Schema (`schema.sql`)

17 colunas, **na mesma ordem dos campos de `Movie`** — `db.py` monta a lista de colunas a
partir de `Movie._fields` e `tests/test_db.py` garante que o schema segue essa ordem.
Campos de lista (`generos`, `elenco`, `paises`, `empresas`) são gravados como texto JSON
(`'["Ação", "Ficção científica"]'`).

```sql
CREATE TABLE IF NOT EXISTS filmes (
    id              INTEGER PRIMARY KEY,
    titulo          TEXT    NOT NULL,
    ano             INTEGER NOT NULL,
    data_lancamento TEXT    NOT NULL DEFAULT '',
    generos         TEXT    NOT NULL DEFAULT '[]',
    orcamento       INTEGER NOT NULL DEFAULT 0 CHECK (orcamento   >= 0),
    faturamento     INTEGER NOT NULL DEFAULT 0 CHECK (faturamento >= 0),
    nota            REAL    NOT NULL DEFAULT 0.0 CHECK (nota BETWEEN 0 AND 10),
    popularidade    REAL    NOT NULL DEFAULT 0.0 CHECK (popularidade >= 0),
    duracao         INTEGER NOT NULL DEFAULT 0 CHECK (duracao >= 0),
    idioma_original TEXT    NOT NULL DEFAULT '',
    classificacao   TEXT    NOT NULL DEFAULT '',
    diretor         TEXT    NOT NULL DEFAULT '',
    elenco          TEXT    NOT NULL DEFAULT '[]',
    paises          TEXT    NOT NULL DEFAULT '[]',
    empresas        TEXT    NOT NULL DEFAULT '[]',
    colecao         TEXT    NOT NULL DEFAULT ''
);
```

## 5. Contrato público dos módulos

Assinaturas que as duas frentes devem respeitar. Alterar uma assinatura exige combinar
com a dupla. **[ok]** = implementado; **[stub]** = só assinatura, `NotImplementedError`.

### `dominio.py` — tipos compartilhados (puro) [ok]

```python
class Movie(NamedTuple): ...        # 17 campos, ver seção 4
class ResumoGrupo(NamedTuple):
    quantidade: int
    indicadores: Mapping[str, float | None]

Predicado = Callable[[Movie], bool]
Seletor   = Callable[[Movie], float | None]
Chave     = tuple[Hashable, ...]
Dimensao  = Callable[[Movie], tuple[Hashable, ...]]

CAMPOS_NUMERICOS / CAMPOS_TEXTO / CAMPOS_LISTA: tuple[str, ...]
```

### `dados.py` — preparação, validação e limpeza (puro) [ok, exceto `para_movie`]

```python
def linha_para_movie(linha) -> Movie | None          # tolera nulos, texto numérico, JSON inválido
def filme_para_linha(filme: Movie) -> tuple          # listas -> JSON (usa dominio.CAMPOS_LISTA)
def para_filmes(linhas) -> Iterator[Movie]           # descarta linhas inutilizáveis (lazy)
def para_movie(detalhe: Mapping[str, Any]) -> Movie | None   # [stub] ingestão
def tem_valor(campo: str) -> Predicado               # HOF: predicado por nome de campo
def tem_orcamento_valido / tem_faturamento_valido / tem_financeiro_valido / tem_nota_valida / tem_ano_valido(filme) -> bool
def eh_valido(filme: Movie) -> bool
def limpar_com(exigencias: Iterable[Predicado], filmes) -> Iterator[Movie]
def limpar(filmes) -> Iterator[Movie]                # exige os 4 REQUISITOS_PADRAO
def com_financeiro_valido / com_nota_valida(filmes) -> Iterator[Movie]
def amostra(filmes, n: int, inicio: int = 0) -> Iterator[Movie]   # islice
```

### `metricas.py` — métricas e dimensões (puro) [ok]

```python
def decada(filme) -> int            # 1994 -> 1990
def mes(filme) -> int | None        # 1..12, a partir de data_lancamento
def trimestre(filme) -> int | None  # 1..4
def lucro(filme) -> int             # faturamento - orcamento (pode ser negativo)
def roi(filme) -> float | None      # None se orcamento <= 0
def soma(valores) -> float                              # reduce
def media(valores) -> float | None                      # reduce com acumulador (soma, contagem)
def mediana(valores) -> float | None                    # sorted, sem alterar a entrada
def metrica(nome: str) -> Seletor       # catálogo: NOMES_METRICAS
def dimensao(nome: str) -> Dimensao     # catálogo: NOMES_DIMENSOES
```

`NOMES_METRICAS`: `orcamento, faturamento, lucro, roi, nota, popularidade, duracao, ano`.
`NOMES_DIMENSOES`: `genero, decada, ano, mes, trimestre, idioma, classificacao, diretor,
ator, pais, empresa, colecao, em_franquia, faixa_orcamento, faixa_nota, faixa_duracao`.
Dimensões de lista devolvem **uma chave por item** (o filme entra em vários grupos);
campo desconhecido devolve `()` e o filme fica fora daquele agrupamento.

### `filtros.py` — filtros (funções de alta ordem) (puro) [stub]

```python
def por_genero(genero: str) -> Predicado
def por_decada(decada: int) -> Predicado
def por_faixa(campo: str, minimo: float | None = None, maximo: float | None = None) -> Predicado
def por_valor(campo: str, *valores: object) -> Predicado
def contendo(campo: str, *valores: str) -> Predicado
def combinar(*predicados: Predicado) -> Predicado     # E
def qualquer(*predicados: Predicado) -> Predicado     # OU
def negar(predicado: Predicado) -> Predicado
def filtrar(predicado: Predicado, filmes) -> Iterator[Movie]
```

### `analises.py` — agrupamento e comparação (puro) [stub]

```python
def agrupar_por(chave: Callable[[Movie], K], filmes) -> Mapping[K, tuple[Movie, ...]]
def resumir(filmes) -> ResumoGrupo
def comparar_por_genero(filmes) -> Mapping[str, ResumoGrupo]
def comparar_por_decada(filmes) -> Mapping[int, ResumoGrupo]
```

> Pendência de contrato: `metricas.dimensao()` devolve **várias** chaves por filme
> (`dominio.Dimensao`), mas `agrupar_por` recebe uma chave única. Ao implementar a issue
> de agrupamento, `agrupar_por` deve aceitar `Dimensao` para consumir `dimensao("genero")`.

### `correlacao.py` — Pearson (puro) [stub]

```python
def pearson(xs: Sequence[float], ys: Sequence[float]) -> float | None
def correlacionar(x: Seletor, y: Seletor, filmes) -> float | None
def orcamento_vs_faturamento(filmes) -> float | None
def orcamento_vs_nota(filmes) -> float | None
```

### `ranking.py` — rankings (puro) [stub]

```python
def top_filmes(n: int, chave: Seletor, filmes, decrescente: bool = True) -> tuple[Movie, ...]
def top_grupos(n: int, indicador: str, grupos: Mapping[Chave, ResumoGrupo],
               decrescente: bool = True) -> tuple[tuple[Chave, ResumoGrupo], ...]
```

### `formatacao.py` — formatação e exibição (I/O: terminal) [stub]

```python
def formatar_moeda(valor: float) -> str          # 1234567 -> 'US$ 1.234.567'
def formatar_percentual(valor: float | None) -> str   # 3.0 -> '300,0%'; None -> '-'
def formatar_filmes(filmes) -> str
def formatar_comparacao(titulo: str, grupos) -> str
def formatar_correlacao(rotulo: str, r: float | None) -> str
def exibir(texto: str) -> None
```

### `tmdb.py` — cliente da API (I/O: rede) [stub]

```python
def carregar_token() -> str                      # TMDB_TOKEN do ambiente/.env
def descobrir_filmes(token: str, pagina: int = 1) -> Mapping[str, Any]
def detalhar_filme(token: str, filme_id: int) -> Mapping[str, Any]
```

### `db.py` — persistência SQLite (I/O: banco) [ok]

```python
def conectar(caminho: Path | str = DB_PADRAO) -> sqlite3.Connection
def inicializar_schema(conn) -> None
def inserir_filmes(conn, filmes: Iterable[Movie]) -> int
def ler_linhas(conn) -> Iterator[tuple]
def ler_filmes(conn) -> Iterator[Movie]
```

### `ingestao.py` — TMDB -> SQLite (I/O: rede + banco) [stub]

```python
def coletar_filmes(token: str, paginas: int) -> Iterator[Movie]
def ingerir(paginas: int = 25, caminho_db: Path | str = DB_PADRAO) -> int
```

### `main.py` — CLI (I/O: terminal) [stub]

```python
def main(argv: Sequence[str] | None = None) -> int
```

## 6. Como executar (Windows / PowerShell)

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

Copy-Item .env.example .env      # depois edite o .env e preencha TMDB_TOKEN

python -m pytest                 # testes (98 atualmente)
python main.py                   # CLI (a ser implementada)
```

O `.env` está no `.gitignore`: **nunca** commite o token.

## 7. Estado das entregas

| Issue | Escopo | Estado |
|---|---|---|
| #2 | Contrato de dados, schema e esqueleto | concluída |
| #1 | Leitura preguiçosa do banco e limpeza (`dados.py`, `db.py`) | concluída |
| #3 | Métricas e dimensões (`metricas.py`) | concluída |
| #13 | Cliente TMDB (`tmdb.py`) | pendente |
| #12 | Ingestão e persistência (`ingestao.py`) | pendente |
| #8 / #4 / #5 | Análises, rankings e correlação | pendente |
| #6 | Filtros | pendente |
| #11 / #10 | CLI, README final e roteiro | pendente |
| #7 | Testes do cliente e do banco | pendente |

Critérios já verificados:

- [x] `Movie` imutável, 17 campos, schema na mesma ordem (`tests/test_db.py`)
- [x] Leitura em streaming, sem `fetchall()` (`tests/test_db.py`)
- [x] Nenhuma agregação na consulta SQL (`tests/test_db.py`)
- [x] Núcleo sem I/O (`tests/test_pureza.py`, via AST)
- [x] Funções preguiçosas testadas com gerador infinito (`tests/test_dados.py`)
- [x] `metricas` cobertas por testes, incluindo casos de borda (`tests/test_metricas.py`)
