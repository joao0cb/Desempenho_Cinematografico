"""Correlação de Pearson entre variáveis numéricas (puro).

Correlação não implica causalidade: a interpretação é de quem lê o resultado.
"""
from __future__ import annotations

from math import sqrt
from operator import attrgetter, itemgetter, mul
from typing import Callable, Iterable, Iterator, Sequence

from dominio import Movie, Seletor
from metricas import soma


def compor(f: Callable, g: Callable) -> Callable:
    """Composição de funções: compor(f, g)(x) == f(g(x))."""
    return lambda x: f(g(x))


def _desvios(valores: Sequence[float]) -> tuple[float, ...]:
    """Cada valor menos a média da série (desvios usados na covariância)."""
    media_da_serie = soma(valores) / len(valores)
    return tuple(map(lambda valor: valor - media_da_serie, valores))


def pearson(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    """Coeficiente de Pearson; None se houver menos de 2 pares ou série constante."""
    pares = tuple(zip(xs, ys))
    valores_x = tuple(map(itemgetter(0), pares))
    valores_y = tuple(map(itemgetter(1), pares))

    if len(pares) < 2 or len(frozenset(valores_x)) < 2 or len(frozenset(valores_y)) < 2:
        return None

    desvios_x, desvios_y = _desvios(valores_x), _desvios(valores_y)
    covariancia = soma(map(mul, desvios_x, desvios_y))
    variancia_x = soma(map(lambda desvio: desvio * desvio, desvios_x))
    variancia_y = soma(map(lambda desvio: desvio * desvio, desvios_y))

    # O limitador absorve erro de ponto flutuante (ex.: 1.0000000000000002).
    return max(-1.0, min(1.0, covariancia / sqrt(variancia_x * variancia_y)))


def correlacionar(x: Seletor, y: Seletor, filmes: Iterable[Movie]) -> float | None:
    """Correlação entre dois seletores, descartando filmes em que algum devolve None."""
    candidatos = map(lambda filme: (x(filme), y(filme)), filmes)
    validos = tuple(filter(lambda par: None not in par, candidatos))
    return pearson(
        tuple(map(itemgetter(0), validos)),
        tuple(map(itemgetter(1), validos)),
    )


def pares_orcamento_faturamento(filmes: Iterable[Movie]) -> Iterator[tuple[float, float]]:
    """Pares (orçamento, faturamento) válidos, gerados sob demanda.

    Ficam de fora os filmes em que algum dos dois é desconhecido (0 no TMDB).
    """
    return (
        (float(filme.orcamento), float(filme.faturamento))
        for filme in filmes
        if filme.orcamento > 0 and filme.faturamento > 0
    )


def _positivo(valor: float | None) -> float | None:
    """O TMDB usa 0 para 'não informado': para Análise, zero equivale a ausente."""
    return valor if valor is not None and valor > 0 else None


_orcamento: Seletor = compor(_positivo, attrgetter("orcamento"))
_faturamento: Seletor = compor(_positivo, attrgetter("faturamento"))
_nota: Seletor = compor(_positivo, attrgetter("nota"))


def orcamento_vs_faturamento(filmes: Iterable[Movie]) -> float | None:
    """Correlação orçamento x faturamento (só filmes com financeiro válido)."""
    return correlacionar(_orcamento, _faturamento, filmes)


def orcamento_vs_nota(filmes: Iterable[Movie]) -> float | None:
    """Correlação orçamento x nota (só filmes com orçamento e nota válidos)."""
    return correlacionar(_orcamento, _nota, filmes)


def relatorio_correlacao(filmes: Iterable[Movie]) -> str:
    """Texto com o coeficiente, a quantidade de pares usados e o aviso de causalidade.

    Devolve string (nada de `print`): quem exibe é a borda (`formatacao`).
    """
    pares = tuple(pares_orcamento_faturamento(filmes))
    r = pearson(
        tuple(map(itemgetter(0), pares)),
        tuple(map(itemgetter(1), pares)),
    )

    motivo = (
        ("  (não calculável: menos de 2 pares ou uma das séries é constante)",)
        if r is None
        else ()
    )
    return "\n".join((
        "Correlação orçamento x faturamento",
        f"  pares usados: {len(pares)}",
        f"  coeficiente de Pearson: {'-' if r is None else f'{r:.3f}'}",
        *motivo,
        "  Correlação não implica causalidade: um coeficiente alto não prova "
        "que o orçamento causou o faturamento.",
    ))