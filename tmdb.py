"""Cliente da API do TMDB (v3, autenticação por Bearer token).

Só faz requisições e devolve o JSON cru; a normalização é de `dados.para_movie`.
Módulo com I/O (rede): é a única porta de saída do programa para a internet.

Mensagens de erro nunca incluem o token: quem lê o terminal pode estar gravando
a sessão, e o token vale como senha.
"""
from __future__ import annotations

import os
import time
from typing import Any, Mapping

import requests
from dotenv import load_dotenv

BASE_URL = "https://api.themoviedb.org/3"

TIMEOUT_PADRAO: float = 10.0
"""Segundos antes de desistir de uma requisição (não travar a ingestão)."""

TENTATIVAS_RATE_LIMIT: int = 2
"""Novas tentativas depois de um 429 (limite de requisições do TMDB)."""

ESPERA_RATE_LIMIT: float = 2.0
"""Espera padrão em segundos quando o TMDB não informa `Retry-After`."""

ESPERA_MAXIMA: float = 10.0
"""Teto da espera, para uma resposta estranha não travar o programa."""


def carregar_token() -> str:
    """Lê TMDB_TOKEN do ambiente/.env; levanta RuntimeError se ausente."""
    load_dotenv()  # não sobrescreve o que já está no ambiente
    token = os.environ.get("TMDB_TOKEN", "").strip()
    if not token:
        raise RuntimeError(
            "TMDB_TOKEN não configurado. Copie .env.example para .env e preencha "
            "com o 'Token de Acesso de Leitura da API' "
            "(TMDB > Configurações > API). O .env não deve ser commitado."
        )
    return token


def _cabecalhos(token: str) -> Mapping[str, str]:
    """Bearer token no header: o token nunca vai na URL (evita vazar em log)."""
    return {"Authorization": f"Bearer {token}", "Accept": "application/json"}


def _espera_da_resposta(resposta: requests.Response) -> float:
    """Respeita o `Retry-After` quando o TMDB manda; senão usa o padrão."""
    try:
        informado = float(resposta.headers.get("Retry-After", ""))
    except (TypeError, ValueError):
        return ESPERA_RATE_LIMIT
    return min(max(informado, 0.0), ESPERA_MAXIMA)


def _obter(token: str, caminho: str, parametros: Mapping[str, Any]) -> Mapping[str, Any]:
    """GET autenticado com timeout, tratamento de 401/429 e mensagens claras."""
    url = f"{BASE_URL}{caminho}"
    for tentativa in range(TENTATIVAS_RATE_LIMIT + 1):
        try:
            resposta = requests.get(
                url,
                headers=_cabecalhos(token),
                params=parametros,
                timeout=TIMEOUT_PADRAO,
            )
        except requests.Timeout:
            raise RuntimeError(
                f"tempo esgotado ao consultar o TMDB ({caminho}) após "
                f"{TIMEOUT_PADRAO:.0f}s. Verifique a conexão e tente de novo."
            ) from None
        except requests.RequestException as erro:
            raise RuntimeError(
                f"falha de rede ao consultar o TMDB ({caminho}): {type(erro).__name__}."
            ) from None

        if resposta.status_code == 401:
            raise RuntimeError(
                "token do TMDB recusado (401). Confira TMDB_TOKEN no .env: "
                "ele precisa ser o 'Token de Acesso de Leitura da API' (começa com 'eyJ')."
            )
        if resposta.status_code == 429:
            if tentativa == TENTATIVAS_RATE_LIMIT:
                raise RuntimeError(
                    "limite de requisições do TMDB atingido (429). "
                    "Aguarde alguns instantes e rode a ingestão novamente."
                )
            time.sleep(_espera_da_resposta(resposta))
            continue
        if not resposta.ok:
            raise RuntimeError(
                f"o TMDB respondeu {resposta.status_code} em {caminho}."
            )
        return resposta.json()

    # Inalcançável: o laço só termina voltando um valor ou levantando erro.
    raise RuntimeError(f"não foi possível consultar {caminho}.")


def descobrir_filmes(token: str, pagina: int = 1) -> Mapping[str, Any]:
    """GET /discover/movie (uma página): lista de filmes com seus ids.

    Critérios fixos: maior faturamento primeiro, pelo menos 100 votos (tira os
    filmes obscuros, sem dados) e textos em pt-BR. Esses parâmetros definem quais
    filmes entram na base e estão documentados no README (viés de amostragem).
    """
    return _obter(
        token,
        "/discover/movie",
        {
            "sort_by": "revenue.desc",
            "vote_count.gte": 100,
            "language": "pt-BR",
            "page": pagina,
        },
    )


def detalhar_filme(token: str, filme_id: int) -> Mapping[str, Any]:
    """GET /movie/{id}?language=pt-BR&append_to_response=credits,release_dates.

    Uma única requisição traz detalhes, elenco/equipe e classificações indicativas.
    É o único endpoint que devolve `budget` e `revenue`.
    """
    return _obter(
        token,
        f"/movie/{filme_id}",
        {"language": "pt-BR", "append_to_response": "credits,release_dates"},
    )


# --------------------------------------------------------------------------
# Atalhos que leem o token do ambiente (uso manual/CLI)
# --------------------------------------------------------------------------

def buscar_pagina(pagina: int = 1) -> list[dict]:
    """Uma página de /discover/movie, usando o token do ambiente/.env."""
    return list(descobrir_filmes(carregar_token(), pagina).get("results", []))


def buscar_detalhes(filme_id: int) -> dict:
    """JSON completo de um filme, usando o token do ambiente/.env."""
    return dict(detalhar_filme(carregar_token(), filme_id))