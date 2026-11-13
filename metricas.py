"""Métricas: cálculos elementares sobre filmes e sequências (puros)."""
from __future__ import annotations

from typing import Iterable

from dominio import Movie


def decada(filme: Movie) -> int:
    """Década de lançamento (ex.: 1994 -> 1990)."""
    raise NotImplementedError


def lucro(filme: Movie) -> int:
    """faturamento - orcamento (estimativa; ignora outros custos)."""
    raise NotImplementedError


def roi(filme: Movie) -> float | None:
    """(faturamento - orcamento) / orcamento; None se orcamento <= 0."""
    raise NotImplementedError


def soma(valores: Iterable[float]) -> float:
    """Soma via reduce; 0.0 para sequência vazia."""
    raise NotImplementedError


def media(valores: Iterable[float]) -> float | None:
    """Média aritmética; None para sequência vazia."""
    raise NotImplementedError


def mediana(valores: Iterable[float]) -> float | None:
    """Mediana; None para sequência vazia."""
    raise NotImplementedError
