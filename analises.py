"""Análises: agrupamento e comparação de grupos (puras, sem SQL)."""
from __future__ import annotations

from itertools import chain, groupby
from operator import itemgetter
from types import MappingProxyType
from typing import Hashable, Iterable, Mapping, Sequence, TypeVar

from dominio import Dimensao, Movie, ResumoGrupo
from metricas import dimensao, media, metrica

K = TypeVar("K", bound=Hashable)

INDICADORES_PADRAO: tuple[str, ...] = ("roi", "nota", "faturamento")
"""Indicadores calculados por `resumir` (nomes do catálogo `metricas.metrica`)."""


def _pares_chave_filme(
    dim: Dimensao, filmes: Iterable[Movie]
) -> Iterable[tuple[Hashable, Movie]]:
    """Um par (chave, filme) para CADA chave da dimensão; preguiçoso.

    `dict.fromkeys` tira chaves repetidas do mesmo filme (ex.: gênero listado
    duas vezes) preservando a ordem, para o filme não entrar duas vezes no grupo.
    """
    return chain.from_iterable(
        map(
            lambda filme: map(lambda chave: (chave, filme), dict.fromkeys(dim(filme))),
            filmes,
        )
    )


def agrupar_por(
    dim: Dimensao, filmes: Iterable[Movie]
) -> Mapping[Hashable, tuple[Movie, ...]]:
    """Agrupa filmes pelas chaves de uma dimensão, sem mutar a entrada.

    `dim` é uma `Dimensao` (ex.: `metricas.dimensao("genero")`): devolve TODAS as
    chaves a que o filme pertence. Filme de vários gêneros entra em vários
    grupos; tupla vazia deixa o filme fora do agrupamento.

    `sorted` devolve lista nova e é estável (a ordem de entrada se mantém dentro
    de cada grupo); `groupby` só junta vizinhos, por isso a ordenação vem antes.
    As chaves de uma mesma dimensão precisam ser comparáveis (todas str ou todas int).
    """
    ordenados = sorted(_pares_chave_filme(dim, filmes), key=itemgetter(0))
    return dict(
        map(
            lambda grupo: (grupo[0], tuple(map(itemgetter(1), grupo[1]))),
            groupby(ordenados, key=itemgetter(0)),
        )
    )


def resumir(
    filmes: Iterable[Movie], indicadores: Sequence[str] = INDICADORES_PADRAO
) -> ResumoGrupo:
    """Calcula quantidade, ROI médio, nota média e faturamento médio do grupo.

    ROI só considera filmes com orçamento válido; nota só filmes com nota válida
    (o "dado ausente" de cada métrica já é None em `metricas.metrica`). Se nenhum
    filme tem dado válido para um indicador, ele vale None. `indicadores` é
    opcional: aceita qualquer nome de `metricas.NOMES_METRICAS`.
    """
    base = tuple(filmes)
    medias = map(
        lambda nome: (
            nome,
            media(filter(lambda v: v is not None, map(metrica(nome), base))),
        ),
        indicadores,
    )
    return ResumoGrupo(len(base), MappingProxyType(dict(medias)))


def comparar_por(
    dim: Dimensao, filmes: Iterable[Movie]
) -> Mapping[Hashable, ResumoGrupo]:
    """Resumo de cada grupo de uma dimensão qualquer (genero, decada, faixa_nota...)."""
    grupos = agrupar_por(dim, filmes)
    return MappingProxyType(
        dict(map(lambda par: (par[0], resumir(par[1])), grupos.items()))
    )


def comparar_por_genero(filmes: Iterable[Movie]) -> Mapping[str, ResumoGrupo]:
    """Indicadores por gênero."""
    return comparar_por(dimensao("genero"), filmes)


def comparar_por_decada(filmes: Iterable[Movie]) -> Mapping[int, ResumoGrupo]:
    """Indicadores por década."""
    return comparar_por(dimensao("decada"), filmes)