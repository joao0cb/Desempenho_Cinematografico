"""Domínio: tipos imutáveis compartilhados por todos os módulos.

Módulo PURO: sem I/O e sem dependências do projeto.
"""
from __future__ import annotations

from typing import Callable, NamedTuple


class Movie(NamedTuple):
    """Registro imutável de um filme (espelha uma linha da tabela `filmes`).

    Convenções (mesmas do TMDB):
      - orcamento / faturamento: dólares (USD); 0 significa "desconhecido".
      - nota: `vote_average` de 0 a 10; 0.0 significa "sem avaliações".
      - genero: gênero principal (o primeiro retornado por /movie/{id}).
    """

    id: int
    titulo: str
    ano: int
    genero: str
    orcamento: int
    faturamento: int
    nota: float


class ResumoGrupo(NamedTuple):
    """Indicadores agregados de um grupo de filmes (gênero, década...).

    Os campos opcionais são None quando nenhum filme do grupo tem dado válido
    para calculá-los (ex.: nenhum com orçamento > 0 para o ROI).
    """

    quantidade: int
    roi_medio: float | None
    nota_media: float | None
    faturamento_medio: float | None


# Aliases usados nas assinaturas de funções de alta ordem.
Predicado = Callable[[Movie], bool]
"""Critério de seleção: recebe um filme e diz se ele entra."""

Seletor = Callable[[Movie], float | None]
"""Extrai um valor numérico de um filme; None significa 'sem dado' (descartado)."""
