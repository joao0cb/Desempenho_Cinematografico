"""Filtros: funções de alta ordem que fabricam predicados (puras)."""
from __future__ import annotations

from typing import Iterable, Iterator

from dominio import Movie, Predicado


def por_genero(genero: str) -> Predicado:
    """Predicado: filme do gênero informado (sem diferenciar maiúsculas)."""
    raise NotImplementedError


def por_decada(decada: int) -> Predicado:
    """Predicado: filme lançado na década informada (ex.: 1990 -> 1990..1999)."""
    raise NotImplementedError


def por_faixa_orcamento(minimo: int = 0, maximo: int | None = None) -> Predicado:
    """Predicado: minimo <= orcamento <= maximo (maximo=None -> sem limite)."""
    raise NotImplementedError


def por_faixa_faturamento(minimo: int = 0, maximo: int | None = None) -> Predicado:
    """Predicado: minimo <= faturamento <= maximo (maximo=None -> sem limite)."""
    raise NotImplementedError


def por_faixa_nota(minimo: float = 0.0, maximo: float = 10.0) -> Predicado:
    """Predicado: minimo <= nota <= maximo."""
    raise NotImplementedError


def combinar(*predicados: Predicado) -> Predicado:
    """Composição (E lógico) de predicados; sem argumentos, aceita tudo."""
    raise NotImplementedError


def filtrar(predicado: Predicado, filmes: Iterable[Movie]) -> Iterator[Movie]:
    """Aplica o predicado de forma preguiçosa (wrapper de `filter`)."""
    raise NotImplementedError
