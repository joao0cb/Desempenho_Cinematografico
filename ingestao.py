"""Ingestão: TMDB -> SQLite. Única ponte entre rede e banco.

Fluxo: tmdb.descobrir_filmes -> ids -> tmdb.detalhar_filme -> dados.para_movie
-> db.inserir_filmes. Módulo com I/O (rede e banco).

A gravação acontece página a página, cada uma em sua transação: se a rede cair
no meio, o que já foi gravado permanece e o banco continua consistente.
"""
from __future__ import annotations

import argparse
import sys
from contextlib import closing
from pathlib import Path
from typing import Iterator, NamedTuple, Sequence

import tmdb
from dados import para_movie
from db import DB_PADRAO, conectar, inicializar_schema, inserir_filmes
from dominio import Movie

POR_PAGINA: int = 20
"""Filmes que o TMDB devolve por página do /discover/movie."""

LIMITE_PADRAO: int = 400


class ResumoIngestao(NamedTuple):
    """Contagens da ingestão: para o resumo no terminal e para os testes."""

    buscados: int
    gravados: int
    descartados: int


def paginas_para(limite: int) -> int:
    """Quantas páginas são necessárias para `limite` filmes (mínimo 1)."""
    return max(1, -(-limite // POR_PAGINA))


def _ids_da_pagina(token: str, pagina: int) -> tuple[int, ...]:
    """Ids válidos de uma página do discover (ignora entradas sem id)."""
    resultados = tmdb.descobrir_filmes(token, pagina).get("results", ())
    return tuple(
        id_
        for id_ in (item.get("id") for item in resultados if isinstance(item, dict))
        if isinstance(id_, int) and id_ > 0
    )


def _pagina(token: str, pagina: int) -> tuple[tuple[int, ...], tuple[Movie, ...]]:
    """(ids encontrados, filmes convertidos) de uma página do discover.

    Filmes que `para_movie` rejeita (sem id, título ou data de lançamento) saem
    daqui como descartados.
    """
    ids = _ids_da_pagina(token, pagina)
    filmes = tuple(
        filme
        for filme in map(para_movie, (tmdb.detalhar_filme(token, id_) for id_ in ids))
        if filme is not None
    )
    return ids, filmes


def coletar_filmes(token: str, paginas: int) -> Iterator[Movie]:
    """Gera (lazy) Movies válidos a partir de `paginas` páginas do discover.

    Nada é requisitado antes da iteração, e cada página só é buscada quando a
    anterior acabou: dá para parar no meio (ex.: `islice`) sem baixar o resto.
    """
    return (
        filme
        for pagina in range(1, paginas + 1)
        for filme in _pagina(token, pagina)[1]
    )


def _ingerir(token: str, paginas: int, caminho_db: Path | str) -> ResumoIngestao:
    """Grava página a página; uma falha no meio preserva o já gravado."""
    buscados = convertidos = gravados = 0
    with closing(conectar(caminho_db)) as conn:
        inicializar_schema(conn)
        for pagina in range(1, paginas + 1):
            ids, filmes = _pagina(token, pagina)
            if not ids:
                break                        # o TMDB não tem mais páginas
            buscados += len(ids)
            convertidos += len(filmes)
            gravados += inserir_filmes(conn, filmes)
    return ResumoIngestao(buscados, gravados, buscados - convertidos)


def ingerir(paginas: int = 25, caminho_db: Path | str = DB_PADRAO) -> int:
    """Cria o schema, coleta e grava os filmes; devolve quantos foram gravados.

    Lê TMDB_TOKEN do ambiente/.env, grava em `caminho_db` (criando a pasta do
    banco se faltar) e imprime o resumo: buscados / gravados / descartados.
    """
    resumo = _ingerir(tmdb.carregar_token(), paginas, caminho_db)
    print(
        f"{caminho_db}: {resumo.buscados} buscados, {resumo.gravados} gravados, "
        f"{resumo.descartados} descartados (sem id, título ou data de lançamento)."
    )
    return resumo.gravados


# --------------------------------------------------------------------------
# CLI: python ingestao.py --limite 400 [--banco data/cinema.db]
# --------------------------------------------------------------------------

def construir_analisador() -> argparse.ArgumentParser:
    """Argumentos da linha de comando da ingestão."""
    analisador = argparse.ArgumentParser(
        description="Baixa filmes do TMDB e grava em um banco SQLite."
    )
    analisador.add_argument(
        "--limite",
        type=int,
        default=LIMITE_PADRAO,
        help=f"quantos filmes buscar (padrão: {LIMITE_PADRAO})",
    )
    analisador.add_argument(
        "--banco",
        default=str(DB_PADRAO),
        help=f"caminho do banco (padrão: {DB_PADRAO})",
    )
    return analisador


def main(argv: Sequence[str] | None = None) -> int:
    """Executa a ingestão pedida; devolve o código de saída (0 = sucesso)."""
    if hasattr(sys.stdout, "reconfigure"):      # acentos no terminal do Windows
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    argumentos = construir_analisador().parse_args(argv)
    try:
        ingerir(paginas_para(argumentos.limite), argumentos.banco)
    except RuntimeError as erro:
        print(f"erro: {erro}")
        return 1
    except KeyboardInterrupt:
        print("ingestão interrompida; o que já foi gravado está no banco.")
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())