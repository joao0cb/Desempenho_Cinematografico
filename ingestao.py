"""Ingestão: TMDB -> SQLite. Única ponte entre rede e banco.

Fluxo: tmdb.descobrir_filmes -> ids -> tmdb.detalhar_filme -> dados.para_movie
-> db.inserir_filmes. Módulo com I/O (rede e banco).
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterator

from db import DB_PADRAO
from dominio import Movie


def coletar_filmes(token: str, paginas: int) -> Iterator[Movie]:
    """Gera (lazy) Movies válidos a partir de `paginas` páginas do discover."""
    raise NotImplementedError


def ingerir(paginas: int = 25, caminho_db: Path | str = DB_PADRAO) -> int:
    """Cria o schema, coleta e grava os filmes; devolve quantos foram gravados."""
    raise NotImplementedError
