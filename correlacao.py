"""Correlação de Pearson entre variáveis numéricas (pura).

Correlação não implica causalidade: a interpretação é de quem lê o resultado.
"""

from __future__ import annotations
from math import sqrt
from functools import reduce
from operator import add, attrgetter, itemgetter, mul
from typing import Callable, Iterable, Sequence
from dominio import Movie, Seletor


def compor(f: Callable, g: Callable) -> Callable:
    "Composição de funções: Compor(f,g)(X) == f(g(x))"
    return lambda x: f(g(x))


def _somar(values: Iterable[float]) -> float:
    "Soma por redução: reduce(add, ...) substitui um laço com um acumulador mutável"
    return reduce(add, values, 0.0)


def _desvios(values: Sequence[float]) -> float:
    mean = _somar(values) / len(values)
    return tuple(map(lambda v: v - mean, values))


def pearson(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    """Coeficiente de Pearson; None se < 2 pares ou variância zero."""
    pairs = tuple(zip(xs, ys))
    colunas_x = tuple(map(itemgetter(0), pairs))
    colunas_y = tuple(map(itemgetter(1), pairs))

    if len(pairs) < 2 or len(frozenset(colunas_x)) < 2 or len(frozenset(colunas_y)) < 2:
        return None

    dx, dy = _desvios(colunas_x), _desvios(colunas_y)
    covariancia = _somar(map(mul, dx, dy))
    var_x = _somar(map(lambda d: d * d, dx))
    var_y = _somar(map(lambda d: d * d, dy))
    return max(-1.0, min(1.0, covariancia / sqrt(var_x * var_y)))


def correlacionar(x: Seletor, y: Seletor, movies: Iterable[Movie]) -> float | None:
    """Correlação entre dois seletores, descartando filmes em que algum é None."""
    candidates = map(lambda movie: (x(movie), y(movie)), movies)
    valids = tuple(filter(lambda pair: None not in pair, candidates))
    return pearson(
        tuple(map(itemgetter(0), valids)),
        tuple(map(itemgetter(1), valids)),
    )


def _positivo(value: float | None) -> float | None:
    "O TMDB usa 0 para não informado: para Análise, zero equivale a ausente"
    return value if value is not None and value > 0 else None


_budget: Seletor = compor(_positivo, attrgetter("orcamento"))
_revenue: Seletor = compor(_positivo, attrgetter("faturamento"))
_score: Seletor = compor(_positivo, attrgetter("nota"))


def orcamento_vs_faturamento(movies: Iterable[Movie]) -> float | None:
    """Correlação orçamento x faturamento (só filmes com financeiro válido)."""
    return correlacionar(_budget, _revenue, movies)


def orcamento_vs_nota(movies: Iterable[Movie]) -> float | None:
    """Correlação orçamento x nota (só filmes com orçamento e nota válidos)."""
    return correlacionar(_budget, _score, movies)
