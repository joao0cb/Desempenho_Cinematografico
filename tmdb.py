"""Cliente da API do TMDB (v3, autenticação por Bearer token).

Só faz requisições e devolve o JSON cru; a normalização é de `dados.para_movie`.
Módulo com I/O (rede).
"""
from __future__ import annotations

from typing import Any, Mapping

BASE_URL = "https://api.themoviedb.org/3"


def carregar_token() -> str:
    """Lê TMDB_TOKEN do ambiente/.env; levanta RuntimeError se ausente."""
    raise NotImplementedError


def descobrir_filmes(token: str, pagina: int = 1) -> Mapping[str, Any]:
    """GET /discover/movie (uma página): lista de filmes com seus ids."""
    raise NotImplementedError


def detalhar_filme(token: str, filme_id: int) -> Mapping[str, Any]:
    """GET /movie/{id}: detalhes do filme (budget, revenue, genres...)."""
    raise NotImplementedError
