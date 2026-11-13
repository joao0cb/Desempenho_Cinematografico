"""Preparação dos dados: normalização e validação (funções puras)."""
from __future__ import annotations

from typing import Any, Iterable, Iterator, Mapping

from dominio import Movie


def para_movie(detalhe: Mapping[str, Any]) -> Movie | None:
    """Converte o JSON de /movie/{id} em Movie.

    Devolve None se faltar campo essencial (título, ano de lançamento ou gênero).
    Usa o primeiro gênero como `genero`; budget/revenue ausentes viram 0.
    """
    raise NotImplementedError


def tem_orcamento_valido(filme: Movie) -> bool:
    """True se orcamento > 0 (requisito para calcular ROI)."""
    raise NotImplementedError


def tem_faturamento_valido(filme: Movie) -> bool:
    """True se faturamento > 0."""
    raise NotImplementedError


def tem_financeiro_valido(filme: Movie) -> bool:
    """True se orçamento e faturamento são ambos > 0."""
    raise NotImplementedError


def tem_nota_valida(filme: Movie) -> bool:
    """True se nota > 0 (filme tem avaliações)."""
    raise NotImplementedError


def com_financeiro_valido(filmes: Iterable[Movie]) -> Iterator[Movie]:
    """Mantém (lazy) só os filmes com orçamento e faturamento válidos."""
    raise NotImplementedError


def com_nota_valida(filmes: Iterable[Movie]) -> Iterator[Movie]:
    """Mantém (lazy) só os filmes com nota válida."""
    raise NotImplementedError
