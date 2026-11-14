"""Rankings de filmes e de grupos (puros)."""
from __future__ import annotations

from itertools import islice
from operator import itemgetter
from typing import Iterable, Mapping

from dominio import Chave, Movie, ResumoGrupo, Seletor


def top_filmes(
    n: int, chave: Seletor, filmes: Iterable[Movie], decrescente: bool = True
) -> tuple[Movie, ...]:
    """Os n primeiros filmes pela chave (qualquer métrica: faturamento, nota, roi, duracao...).

    Filmes cuja chave é None ficam de fora. A chave é calculada UMA vez por filme
    (o par (valor, filme) é montado antes de ordenar). `sorted` devolve lista nova
    e é estável, mesmo com `reverse=True`: empates mantêm a ordem de entrada.
    n <= 0 devolve tupla vazia; n maior que o total devolve todos os filmes com dado.
    """
    pares = map(lambda filme: (chave(filme), filme), filmes)
    com_valor = filter(lambda par: par[0] is not None, pares)
    ordenados = sorted(com_valor, key=itemgetter(0), reverse=decrescente)
    return tuple(islice(map(itemgetter(1), ordenados), max(n, 0)))


def top_grupos(
    n: int,
    indicador: str,
    grupos: Mapping[Chave, ResumoGrupo],
    decrescente: bool = True,
) -> tuple[tuple[Chave, ResumoGrupo], ...]:
    """Os n primeiros grupos por um indicador do resumo (ex.: 'roi', 'nota').

    Grupos em que o indicador é None (ou não existe no resumo) ficam de fora.
    Empates mantêm a ordem do mapeamento. n <= 0 devolve tupla vazia.
    """
    com_valor = filter(
        lambda par: par[1].indicadores.get(indicador) is not None, grupos.items()
    )
    ordenados = sorted(
        com_valor, key=lambda par: par[1].indicadores[indicador], reverse=decrescente
    )
    return tuple(islice(ordenados, max(n, 0)))