"""Métricas e dimensões: tudo o que dá para medir ou agrupar em um filme (puro).

- MÉTRICA (`Seletor`): Movie -> número ou None. Entra em médias, rankings e correlações.
- DIMENSÃO (`Dimensao`): Movie -> chaves de grupo. Entra em agrupamentos e comparações.
Combinando várias dimensões e várias métricas sai a análise (ex.: gênero x década -> ROI e nota).
"""
from __future__ import annotations

from typing import Iterable

from dominio import Dimensao, Movie, Seletor

NOMES_METRICAS: tuple[str, ...] = (
    "orcamento", "faturamento", "lucro", "roi", "nota",
    "popularidade", "duracao", "ano",
)
"""Métricas disponíveis em `metrica(nome)`."""

NOMES_DIMENSOES: tuple[str, ...] = (
    "genero", "decada", "ano", "mes", "trimestre", "idioma", "classificacao",
    "diretor", "ator", "pais", "empresa", "colecao", "em_franquia",
    "faixa_orcamento", "faixa_nota", "faixa_duracao",
)
"""Dimensões disponíveis em `dimensao(nome)`. 'genero', 'ator', 'pais' e 'empresa'
são multivaloradas: o filme entra em um grupo por item."""


def decada(filme: Movie) -> int:
    """Década de lançamento (ex.: 1994 -> 1990)."""
    raise NotImplementedError


def mes(filme: Movie) -> int | None:
    """Mês de lançamento (1 a 12) a partir de `data_lancamento`; None se desconhecida."""
    raise NotImplementedError


def lucro(filme: Movie) -> int:
    """faturamento - orcamento (estimativa; ignora outros custos)."""
    raise NotImplementedError


def roi(filme: Movie) -> float | None:
    """(faturamento - orcamento) / orcamento; None se orcamento <= 0."""
    raise NotImplementedError


def soma(valores: Iterable[float]) -> float:
    """Soma via reduce; 0.0 para sequência vazia."""
    raise NotImplementedError


def media(valores: Iterable[float]) -> float | None:
    """Média aritmética; None para sequência vazia."""
    raise NotImplementedError


def mediana(valores: Iterable[float]) -> float | None:
    """Mediana; None para sequência vazia."""
    raise NotImplementedError


def metrica(nome: str) -> Seletor:
    """Seletor da métrica `nome` (um de NOMES_METRICAS); None quando o filme não tem o dado.

    Levanta ValueError para nome desconhecido.
    """
    raise NotImplementedError


def dimensao(nome: str) -> Dimensao:
    """Dimensão `nome` (uma de NOMES_DIMENSOES); tupla vazia quando o filme não tem o dado.

    Levanta ValueError para nome desconhecido.
    """
    raise NotImplementedError