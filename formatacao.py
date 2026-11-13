"""Formatação e exibição no terminal.

As funções `formatar_*` são puras (devolvem str); só `exibir` escreve no terminal.
Módulo com I/O (terminal).
"""
from __future__ import annotations

from typing import Iterable

from dominio import Movie, ResumoGrupo


def formatar_moeda(valor: float) -> str:
    """Ex.: 1234567 -> 'US$ 1.234.567'."""
    raise NotImplementedError


def formatar_percentual(valor: float | None) -> str:
    """Ex.: 3.0 -> '300,0%'; None -> '-'."""
    raise NotImplementedError


def formatar_filmes(filmes: Iterable[Movie]) -> str:
    """Tabela de texto com os filmes."""
    raise NotImplementedError


def formatar_comparacao(titulo: str, grupos: Iterable[tuple[object, ResumoGrupo]]) -> str:
    """Tabela de texto comparando grupos (gênero, década...)."""
    raise NotImplementedError


def formatar_correlacao(rotulo: str, r: float | None) -> str:
    """Linha de texto com o coeficiente (e aviso de que não é causalidade)."""
    raise NotImplementedError


def exibir(texto: str) -> None:
    """Escreve o texto no terminal."""
    raise NotImplementedError
