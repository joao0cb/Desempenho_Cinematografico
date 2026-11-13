"""Correlação de Pearson entre variáveis numéricas (pura).

Correlação não implica causalidade: a interpretação é de quem lê o resultado.
"""
from __future__ import annotations

from typing import Iterable, Sequence

from dominio import Movie, Seletor


def pearson(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    """Coeficiente de Pearson; None se < 2 pares ou variância zero."""
    raise NotImplementedError


def correlacionar(x: Seletor, y: Seletor, filmes: Iterable[Movie]) -> float | None:
    """Correlação entre dois seletores, descartando filmes em que algum é None."""
    raise NotImplementedError


def orcamento_vs_faturamento(filmes: Iterable[Movie]) -> float | None:
    """Correlação orçamento x faturamento (só filmes com financeiro válido)."""
    raise NotImplementedError


def orcamento_vs_nota(filmes: Iterable[Movie]) -> float | None:
    """Correlação orçamento x nota (só filmes com orçamento e nota válidos)."""
    raise NotImplementedError
