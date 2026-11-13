"""Análises: agrupamento e comparação de grupos (puras, sem SQL)."""
from __future__ import annotations

from typing import Callable, Iterable, Mapping, TypeVar

from dominio import Movie, ResumoGrupo

K = TypeVar("K")


def agrupar_por(
    chave: Callable[[Movie], K], filmes: Iterable[Movie]
) -> Mapping[K, tuple[Movie, ...]]:
    """Agrupa filmes pela chave sem mutar a entrada (ex.: genero, metricas.decada)."""
    raise NotImplementedError


def resumir(filmes: Iterable[Movie]) -> ResumoGrupo:
    """Calcula quantidade, ROI médio, nota média e faturamento médio do grupo.

    ROI só considera filmes com orçamento válido; nota só filmes com nota válida.
    """
    raise NotImplementedError


def comparar_por_genero(filmes: Iterable[Movie]) -> Mapping[str, ResumoGrupo]:
    """Indicadores por gênero."""
    raise NotImplementedError


def comparar_por_decada(filmes: Iterable[Movie]) -> Mapping[int, ResumoGrupo]:
    """Indicadores por década."""
    raise NotImplementedError
