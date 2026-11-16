-- Schema do banco data/cinema.db (SQLite).
--
-- Este arquivo fica AO LADO do main.py: `main.SCHEMA_PATH` o localiza com
-- `Path(__file__).with_name("schema.sql")`, e `inicializar_schema` o executa
-- antes de qualquer gravação. Sem ele, `python main.py --ingerir` falha com
-- FileNotFoundError e o banco não é criado.
--
-- Contrato: uma linha de `filmes` corresponde exatamente a um `Movie`
-- (main.py, seção 2 — domínio), com as colunas NA MESMA ORDEM dos campos.
-- `tests/test_db.py` verifica isso: a ordem de Movie._fields manda, e o
-- INSERT do main.py é montado a partir dela.
--
-- O banco é apenas ARMAZENAMENTO: nenhuma análise (GROUP BY, AVG, SUM...) é
-- feita aqui; todo o cálculo acontece em Python puro.
--
-- Campos com vários valores (generos, elenco, paises, empresas) ficam em uma
-- coluna TEXT como lista JSON, ex.: '["Ação", "Ficção científica"]'.
-- Convenção de "desconhecido": 0 (números), '' (textos) e '[]' (listas).

CREATE TABLE IF NOT EXISTS filmes (
    id              INTEGER PRIMARY KEY,                       -- id do filme no TMDB
    titulo          TEXT    NOT NULL,
    ano             INTEGER NOT NULL,                          -- ano de lançamento
    data_lancamento TEXT    NOT NULL DEFAULT '',               -- 'AAAA-MM-DD'
    generos         TEXT    NOT NULL DEFAULT '[]',             -- lista JSON
    orcamento       INTEGER NOT NULL DEFAULT 0 CHECK (orcamento   >= 0),  -- USD
    faturamento     INTEGER NOT NULL DEFAULT 0 CHECK (faturamento >= 0),  -- USD
    nota            REAL    NOT NULL DEFAULT 0.0 CHECK (nota BETWEEN 0 AND 10),
    popularidade    REAL    NOT NULL DEFAULT 0.0 CHECK (popularidade >= 0),
    duracao         INTEGER NOT NULL DEFAULT 0 CHECK (duracao >= 0),      -- minutos
    idioma_original TEXT    NOT NULL DEFAULT '',
    classificacao   TEXT    NOT NULL DEFAULT '',
    diretor         TEXT    NOT NULL DEFAULT '',
    elenco          TEXT    NOT NULL DEFAULT '[]',             -- lista JSON
    paises          TEXT    NOT NULL DEFAULT '[]',             -- lista JSON
    empresas        TEXT    NOT NULL DEFAULT '[]',             -- lista JSON
    colecao         TEXT    NOT NULL DEFAULT ''
);
