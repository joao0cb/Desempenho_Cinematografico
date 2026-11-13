"""Rankings de filmes e de grupos (puros)."""
from __future__ import annotations

from typing import Callable, Iterable, Mapping, TypeVar

from dominio import Movie, ResumoGrupo, Seletor

K = TypeVar("K")


def top_filmes(
    n: int, chave: Seletor, filmes: Iterable[Movie], decrescente: bool = True
) -> tuple[Movie, ...]:
    """Os n primeiros filmes pela chave (ex.: faturamento, nota, metricas.roi).

    Filmes cuja chave é None ficam de fora.
    """
    raise NotImplementedError


def top_grupos(
    n: int,
    chave: Callable[[ResumoGrupo], float | None],
    grupos: Mapping[K, ResumoGrupo],
    decrescente: bool = True,
) -> tuple[tuple[K, ResumoGrupo], ...]:
    """Os n primeiros grupos pela chave (ex.: lambda r: r.roi_medio)."""
    raise NotImplementedError
