"""Domínio: tipos imutáveis compartilhados por todos os módulos.

Módulo PURO: sem I/O e sem dependências do projeto.
"""
from __future__ import annotations

from typing import Callable, Hashable, Mapping, NamedTuple


class Movie(NamedTuple):
    """Registro imutável de um filme (espelha uma linha da tabela `filmes`).

    Só `id`, `titulo` e `ano` são obrigatórios. Todo o resto tem como padrão o
    valor "desconhecido" (mesma convenção do TMDB):
      - números: 0 (ou 0.0) = desconhecido;
      - textos: '' = desconhecido;
      - listas (tuplas): () = desconhecido.
    A ordem dos campos é a ordem das colunas de `schema.sql`.
    """

    id: int
    titulo: str
    ano: int
    data_lancamento: str = ""        # ISO 'AAAA-MM-DD'
    generos: tuple[str, ...] = ()    # todos os gêneros do filme
    orcamento: int = 0               # USD
    faturamento: int = 0             # USD
    nota: float = 0.0                # 0 a 10 (vote_average)
    popularidade: float = 0.0        # índice de popularidade do TMDB
    duracao: int = 0                 # minutos
    idioma_original: str = ""        # código ISO 639-1 ('en', 'pt'...)
    classificacao: str = ""          # classificação indicativa dos EUA ('PG-13', 'R'...)
    diretor: str = ""                # primeiro diretor creditado
    elenco: tuple[str, ...] = ()     # até 5 atores, na ordem de crédito
    paises: tuple[str, ...] = ()     # países de produção (ISO 3166-1: 'US', 'BR'...)
    empresas: tuple[str, ...] = ()   # produtoras
    colecao: str = ""                # franquia/coleção ('' = fora de franquia)


# Classificação dos campos por tipo (úteis para filtros e dimensões genéricos).
CAMPOS_NUMERICOS: tuple[str, ...] = (
    "ano", "orcamento", "faturamento", "nota", "popularidade", "duracao",
)
CAMPOS_TEXTO: tuple[str, ...] = (
    "titulo", "data_lancamento", "idioma_original", "classificacao",
    "diretor", "colecao",
)
CAMPOS_LISTA: tuple[str, ...] = (
    "generos", "elenco", "paises", "empresas",
)


# Aliases usados nas assinaturas de funções de alta ordem.
Predicado = Callable[[Movie], bool]
"""Critério de seleção: recebe um filme e diz se ele entra."""

Seletor = Callable[[Movie], float | None]
"""Extrai um valor numérico de um filme; None significa 'sem dado' (descartado)."""

Chave = tuple[Hashable, ...]
"""Chave de um grupo: uma posição por dimensão (ex.: ('Ação', 1990) = gênero x década)."""

Dimensao = Callable[[Movie], tuple[Hashable, ...]]
"""Eixo de agrupamento: devolve TODAS as chaves a que o filme pertence.

Campo de valor único -> tupla de 1 elemento (ex.: (1990,) para década).
Campo de lista (gêneros, elenco...) -> um elemento por item; o filme entra em
vários grupos. Tupla vazia -> o filme fica fora do agrupamento.
"""


class ResumoGrupo(NamedTuple):
    """Indicadores agregados de um grupo de filmes.

    `indicadores` mapeia nome da métrica -> média no grupo (ex.: 'roi', 'nota',
    'faturamento'); vale None quando nenhum filme do grupo tem dado válido para ela.
    Trate o mapeamento como somente leitura (construa com `MappingProxyType`).
    """

    quantidade: int
    indicadores: Mapping[str, float | None]