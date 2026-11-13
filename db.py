"""Persistência em SQLite. O banco é só ARMAZENAMENTO.

- Escrita: `inserir_filmes` (usada pela ingestão), convertendo cada `Movie` na
  linha correspondente via `dados.filme_para_linha` (listas viram JSON).
- Leitura: `ler_linhas` itera o cursor (streaming) e `ler_filmes` converte cada
  linha em `Movie` via `dados.para_filmes`. Agregações ficam em Python puro
  (analises.py), nunca em SQL.

As colunas vêm de `Movie._fields`: existe UMA fonte da verdade para o contrato
(o NamedTuple), e `tests/test_db.py` garante que o schema segue essa ordem.

Módulo com I/O (banco).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable, Iterator

from dados import filme_para_linha, para_filmes
from dominio import Movie

DB_PADRAO: Path = Path("data") / "cinema.db"
SCHEMA_PATH: Path = Path(__file__).with_name("schema.sql")

_COLUNAS: str = ", ".join(Movie._fields)
"""Colunas na mesma ordem dos campos de `Movie` (contrato único)."""
_PLACEHOLDERS: str = ", ".join("?" * len(Movie._fields))

CONSULTA_FILMES: str = f"SELECT {_COLUNAS} FROM filmes ORDER BY id"
"""Leitura simples e ordenada. Proibido agregar aqui (GROUP BY, AVG, SUM...)."""


def conectar(caminho: Path | str = DB_PADRAO) -> sqlite3.Connection:
    """Abre (e cria, se preciso) o banco. Aceita ':memory:' para testes."""
    destino = str(caminho)
    if destino != ":memory:":
        Path(destino).parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(destino)


def inicializar_schema(conn: sqlite3.Connection) -> None:
    """Cria a tabela `filmes` a partir de schema.sql (idempotente)."""
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))


def inserir_filmes(conn: sqlite3.Connection, filmes: Iterable[Movie]) -> int:
    """Grava (insere ou substitui por id) os filmes; devolve quantos foram gravados.

    `filme_para_linha` é obrigatório: campos-lista (`generos`, `elenco`...) são
    tuplas em Python e precisam virar texto JSON antes de chegar ao SQLite.
    """
    antes = conn.total_changes
    conn.executemany(
        f"INSERT OR REPLACE INTO filmes ({_COLUNAS}) VALUES ({_PLACEHOLDERS})",
        map(filme_para_linha, filmes),
    )
    conn.commit()
    return conn.total_changes - antes


def ler_linhas(conn: sqlite3.Connection) -> Iterator[tuple]:
    """Itera o cursor linha a linha (streaming): nunca usa fetchall() nem monta lista.

    A conexão precisa continuar aberta enquanto o gerador é consumido.
    """
    yield from conn.execute(CONSULTA_FILMES)


def ler_filmes(conn: sqlite3.Connection) -> Iterator[Movie]:
    """Todos os filmes do banco, sob demanda (linha a linha -> `dados.para_filmes`).

    O SQLite só entrega linhas; a conversão e a limpeza são Python puro (dados.py).
    """
    return para_filmes(ler_linhas(conn))
