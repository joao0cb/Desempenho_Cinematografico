"""Filtros: funções de alta ordem que fabricam predicados (puras).

Funcionam com QUALQUER campo de `Movie`: cada fábrica recebe o nome do campo
(ver `dominio.CAMPOS_NUMERICOS`, `CAMPOS_TEXTO` e `CAMPOS_LISTA`).
"""
from __future__ import annotations

from typing import Iterable, Iterator

from dominio import Movie, Predicado


def por_genero(genero: str) -> Predicado:
    """Predicado: o filme tem o gênero entre os seus (sem diferenciar maiúsculas)."""
    raise NotImplementedError


def por_decada(decada: int) -> Predicado:
    """Predicado: filme lançado na década informada (ex.: 1990 -> 1990..1999)."""
    raise NotImplementedError


def por_faixa(campo: str, minimo: float | None = None, maximo: float | None = None) -> Predicado:
    """Predicado: minimo <= campo <= maximo para um campo NUMÉRICO (None = sem limite).

    Ex.: por_faixa('orcamento', 1_000_000), por_faixa('nota', 7), por_faixa('duracao', 90, 120).
    """
    raise NotImplementedError


def por_valor(campo: str, *valores: object) -> Predicado:
    """Predicado: campo de valor único (texto ou número) igual a algum dos valores.

    Ex.: por_valor('idioma_original', 'en', 'pt'), por_valor('diretor', 'Christopher Nolan').
    """
    raise NotImplementedError


def contendo(campo: str, *valores: str) -> Predicado:
    """Predicado: campo-LISTA contém algum dos valores (sem diferenciar maiúsculas).

    Ex.: contendo('elenco', 'Tom Hanks'), contendo('paises', 'BR'), contendo('empresas', 'Pixar').
    """
    raise NotImplementedError


def combinar(*predicados: Predicado) -> Predicado:
    """E lógico de predicados; sem argumentos, aceita tudo."""
    raise NotImplementedError


def qualquer(*predicados: Predicado) -> Predicado:
    """OU lógico de predicados; sem argumentos, rejeita tudo."""
    raise NotImplementedError


def negar(predicado: Predicado) -> Predicado:
    """Inverte um predicado."""
    raise NotImplementedError


def filtrar(predicado: Predicado, filmes: Iterable[Movie]) -> Iterator[Movie]:
    """Aplica o predicado de forma preguiçosa (wrapper de `filter`)."""
    raise NotImplementedError