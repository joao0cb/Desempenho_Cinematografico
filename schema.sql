-- Schema do banco data/cinema.db (SQLite).
-- Contrato: uma linha de `filmes` corresponde exatamente a um `Movie` (dominio.py),
-- na mesma ordem de colunas. O banco é apenas ARMAZENAMENTO: nenhuma análise
-- (GROUP BY, AVG, SUM...) é feita aqui; o cálculo acontece em Python puro.

CREATE TABLE IF NOT EXISTS filmes (
    id          INTEGER PRIMARY KEY,                       -- id do filme no TMDB
    titulo      TEXT    NOT NULL,
    ano         INTEGER NOT NULL,                          -- ano de lançamento
    genero      TEXT    NOT NULL,                          -- gênero principal (primeiro de /movie/{id})
    orcamento   INTEGER NOT NULL DEFAULT 0 CHECK (orcamento   >= 0),  -- USD; 0 = desconhecido
    faturamento INTEGER NOT NULL DEFAULT 0 CHECK (faturamento >= 0),  -- USD; 0 = desconhecido
    nota        REAL    NOT NULL DEFAULT 0.0 CHECK (nota BETWEEN 0 AND 10)  -- vote_average; 0.0 = sem votos
);
