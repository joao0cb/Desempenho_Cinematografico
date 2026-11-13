"""Persistência em SQLite. O banco é só ARMAZENAMENTO.

- Escrita: `inserir_filmes` (usada pela ingestão).
- Leitura: `ler_filmes` faz SELECT simples e devolve `Movie` sob demanda.
  Agregações ficam em Python puro (analises.py), nunca em SQL.

Módulo com I/O (banco).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable, Iterator

from dominio import Movie

DB_PADRAO: Path = Path("data") / "cinema.db"
SCHEMA_PATH: Path = Path(__file__).with_name("schema.sql")

_COLUNAS = "id, titulo, ano, genero, orcamento, faturamento, nota"


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
    """Grava (insere ou substitui por id) os filmes; devolve quantos foram gravados."""
    antes = conn.total_changes
    conn.executemany(
        f"INSERT OR REPLACE INTO filmes ({_COLUNAS}) VALUES (?, ?, ?, ?, ?, ?, ?)",
        filmes,  # Movie é uma tupla na mesma ordem das colunas
    )
    conn.commit()
    return conn.total_changes - antes


def ler_filmes(conn: sqlite3.Connection) -> Iterator[Movie]:
    """Gerador de todos os filmes (SELECT simples, sem agregação).

    A conexão precisa continuar aberta enquanto o gerador é consumido.
    """
    for linha in conn.execute(f"SELECT {_COLUNAS} FROM filmes ORDER BY id"):
        yield Movie(*linha)
