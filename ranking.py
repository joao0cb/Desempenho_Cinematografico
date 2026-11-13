"""Rankings de filmes e de grupos (puros)."""
from __future__ import annotations

from typing import Iterable, Mapping

from dominio import Chave, Movie, ResumoGrupo, Seletor


def top_filmes(
    n: int, chave: Seletor, filmes: Iterable[Movie], decrescente: bool = True
) -> tuple[Movie, ...]:
    """Os n primeiros filmes pela chave (qualquer métrica: faturamento, nota, roi, duracao...).

    Filmes cuja chave é None ficam de fora.
    """
    raise NotImplementedError


def top_grupos(
    n: int,
    indicador: str,
    grupos: Mapping[Chave, ResumoGrupo],
    decrescente: bool = True,
) -> tuple[tuple[Chave, ResumoGrupo], ...]:
    """Os n primeiros grupos por um indicador do resumo (ex.: 'roi', 'nota').

    Grupos em que o indicador é None ficam de fora.
    """
    raise NotImplementedError