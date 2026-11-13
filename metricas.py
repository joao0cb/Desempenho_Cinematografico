"""Métricas e dimensões: tudo o que dá para medir ou agrupar em um filme (puro).

- MÉTRICA (`Seletor`): Movie -> número ou None. Entra em médias, rankings e correlações.
- DIMENSÃO (`Dimensao`): Movie -> chaves de grupo. Entra em agrupamentos e comparações.

Combinando várias dimensões e várias métricas sai a análise (ex.: gênero x década -> ROI e nota).

Nenhuma função aqui faz I/O, guarda estado ou altera o filme recebido: todas são
funções puras e podem ser passadas como valor para `filter`, `sorted` e `reduce`.
"""
from __future__ import annotations

from functools import reduce
from operator import add
from types import MappingProxyType
from typing import Iterable, Mapping

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


# --------------------------------------------------------------------------
# Métricas escalares (Movie -> número | None)
# --------------------------------------------------------------------------

def decada(filme: Movie) -> int:
    """Década de lançamento (ex.: 1994 -> 1990). Ano desconhecido (0) -> 0."""
    return (filme.ano // 10) * 10


def mes(filme: Movie) -> int | None:
    """Mês de lançamento (1 a 12) a partir de `data_lancamento`; None se desconhecida."""
    texto = filme.data_lancamento
    if len(texto) < 7:
        return None
    try:
        numero = int(texto[5:7])
    except ValueError:
        return None
    return numero if 1 <= numero <= 12 else None


def trimestre(filme: Movie) -> int | None:
    """Trimestre de lançamento (1 a 4); None se o mês for desconhecido."""
    numero = mes(filme)
    return None if numero is None else (numero - 1) // 3 + 1


def lucro(filme: Movie) -> int:
    """faturamento - orcamento (estimativa; ignora outros custos). Pode ser negativo."""
    return filme.faturamento - filme.orcamento


def roi(filme: Movie) -> float | None:
    """(faturamento - orcamento) / orcamento; None se orcamento <= 0.

    Pode ser negativo (prejuízo). É uma estimativa baseada apenas nos dois campos
    registrados no TMDB, não uma apuração completa de lucro.
    """
    if filme.orcamento <= 0:
        return None
    return (filme.faturamento - filme.orcamento) / filme.orcamento


# --------------------------------------------------------------------------
# Agregações (reduce puro)
# --------------------------------------------------------------------------

def soma(valores: Iterable[float]) -> float:
    """Soma via reduce; 0.0 para sequência vazia."""
    return float(reduce(add, valores, 0.0))


def media(valores: Iterable[float]) -> float | None:
    """Média aritmética; None para sequência vazia.

    O acumulador é a tupla (soma, contagem): dá para calcular em uma passada,
    sem variável mutável e sem materializar a sequência.
    """
    total, quantidade = reduce(
        lambda acumulado, valor: (acumulado[0] + valor, acumulado[1] + 1),
        valores,
        (0.0, 0),
    )
    return None if quantidade == 0 else total / quantidade


def mediana(valores: Iterable[float]) -> float | None:
    """Mediana; None para sequência vazia.

    Usa `sorted` (que devolve lista nova) em vez de ordenar no lugar: a entrada
    nunca é alterada.
    """
    ordenados = sorted(valores)
    total = len(ordenados)
    if total == 0:
        return None
    meio = total // 2
    if total % 2 == 1:
        return float(ordenados[meio])
    return (float(ordenados[meio - 1]) + float(ordenados[meio])) / 2


# --------------------------------------------------------------------------
# Catálogo de métricas (nome -> função), para a CLI montar as análises
# --------------------------------------------------------------------------

def _positivo(valor: float) -> float | None:
    """0 é o 'não informado' do TMDB: vira None para não poluir médias e rankings."""
    return valor if valor > 0 else None


_SELETORES: Mapping[str, Seletor] = MappingProxyType({
    "orcamento": lambda filme: _positivo(float(filme.orcamento)),
    "faturamento": lambda filme: _positivo(float(filme.faturamento)),
    "lucro": lambda filme: float(lucro(filme)),
    "roi": roi,
    "nota": lambda filme: _positivo(filme.nota),
    "popularidade": lambda filme: _positivo(filme.popularidade),
    "duracao": lambda filme: _positivo(float(filme.duracao)),
    "ano": lambda filme: _positivo(float(filme.ano)),
})


def metrica(nome: str) -> Seletor:
    """Seletor da métrica `nome` (um de NOMES_METRICAS); None quando o filme não tem o dado.

    Levanta ValueError para nome desconhecido.
    """
    try:
        return _SELETORES[nome]
    except KeyError:
        raise ValueError(
            f"métrica desconhecida: {nome!r}; use uma de {NOMES_METRICAS}"
        ) from None


# --------------------------------------------------------------------------
# Dimensões (Movie -> chaves de grupo)
# --------------------------------------------------------------------------

def _uma(chave: object) -> tuple[object, ...]:
    """Chave única: tupla de 1 elemento; valor "desconhecido" fica fora do agrupamento."""
    if chave is None or chave == "" or chave == 0:
        return ()
    return (chave,)


def _d_genero(filme: Movie) -> tuple:
    return tuple(filme.generos)


def _d_decada(filme: Movie) -> tuple:
    return _uma(decada(filme))


def _d_ano(filme: Movie) -> tuple:
    return _uma(filme.ano)


def _d_mes(filme: Movie) -> tuple:
    return _uma(mes(filme))


def _d_trimestre(filme: Movie) -> tuple:
    return _uma(trimestre(filme))


def _d_idioma(filme: Movie) -> tuple:
    return _uma(filme.idioma_original)


def _d_classificacao(filme: Movie) -> tuple:
    return _uma(filme.classificacao)


def _d_diretor(filme: Movie) -> tuple:
    return _uma(filme.diretor)


def _d_ator(filme: Movie) -> tuple:
    return tuple(filme.elenco)


def _d_pais(filme: Movie) -> tuple:
    return tuple(filme.paises)


def _d_empresa(filme: Movie) -> tuple:
    return tuple(filme.empresas)


def _d_colecao(filme: Movie) -> tuple:
    return _uma(filme.colecao)


def _d_em_franquia(filme: Movie) -> tuple:
    return ("em franquia" if filme.colecao else "fora de franquia",)


# Faixas: (limite superior exclusivo, rótulo) + rótulo da última faixa.
FAIXAS_ORCAMENTO: tuple[tuple[float, str], ...] = (
    (10_000_000, "até US$ 10 mi"),
    (50_000_000, "US$ 10-50 mi"),
    (100_000_000, "US$ 50-100 mi"),
)
FAIXA_ORCAMENTO_FINAL: str = "acima de US$ 100 mi"

FAIXAS_NOTA: tuple[tuple[float, str], ...] = (
    (5.0, "0-5"),
    (7.0, "5-7"),
    (8.0, "7-8"),
)
FAIXA_NOTA_FINAL: str = "8-10"

FAIXAS_DURACAO: tuple[tuple[float, str], ...] = (
    (90, "até 90 min"),
    (120, "90-120 min"),
    (150, "120-150 min"),
)
FAIXA_DURACAO_FINAL: str = "150 min ou mais"


def _faixa(
    valor: float, faixas: tuple[tuple[float, str], ...], ultima: str
) -> tuple[str, ...]:
    """Primeira faixa cujo limite superior é maior que o valor; senão, a última.

    Usa `next` com gerador: nenhuma faixa é avaliada além da necessária.
    """
    rotulo = next(
        (nome for limite, nome in faixas if valor < limite),
        ultima,
    )
    return (rotulo,)


def _d_faixa_orcamento(filme: Movie) -> tuple:
    if filme.orcamento <= 0:
        return ()
    return _faixa(filme.orcamento, FAIXAS_ORCAMENTO, FAIXA_ORCAMENTO_FINAL)


def _d_faixa_nota(filme: Movie) -> tuple:
    if filme.nota <= 0:
        return ()
    return _faixa(filme.nota, FAIXAS_NOTA, FAIXA_NOTA_FINAL)


def _d_faixa_duracao(filme: Movie) -> tuple:
    if filme.duracao <= 0:
        return ()
    return _faixa(filme.duracao, FAIXAS_DURACAO, FAIXA_DURACAO_FINAL)


_DIMENSOES: Mapping[str, Dimensao] = MappingProxyType({
    "genero": _d_genero,
    "decada": _d_decada,
    "ano": _d_ano,
    "mes": _d_mes,
    "trimestre": _d_trimestre,
    "idioma": _d_idioma,
    "classificacao": _d_classificacao,
    "diretor": _d_diretor,
    "ator": _d_ator,
    "pais": _d_pais,
    "empresa": _d_empresa,
    "colecao": _d_colecao,
    "em_franquia": _d_em_franquia,
    "faixa_orcamento": _d_faixa_orcamento,
    "faixa_nota": _d_faixa_nota,
    "faixa_duracao": _d_faixa_duracao,
})


def dimensao(nome: str) -> Dimensao:
    """Dimensão `nome` (uma de NOMES_DIMENSOES); tupla vazia quando o filme não tem o dado.

    Levanta ValueError para nome desconhecido.
    """
    try:
        return _DIMENSOES[nome]
    except KeyError:
        raise ValueError(
            f"dimensão desconhecida: {nome!r}; use uma de {NOMES_DIMENSOES}"
        ) from None
