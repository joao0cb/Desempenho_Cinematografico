"""Filtros: funções de alta ordem que fabricam predicados (puras).

Um predicado é só uma função `Movie -> bool`. As fábricas abaixo recebem os
parâmetros de um critério e devolvem o predicado correspondente (currying: dá
para fixar o critério agora e decidir sobre o filme depois). Como predicados são
valores, dá para guardá-los em listas, recebê-los como parâmetro e combiná-los
com `todos`, `qualquer` e `negar` sem repetir lógica.

Funcionam com QUALQUER campo de `Movie`: cada fábrica recebe o nome do campo
(ver `dominio.CAMPOS_NUMERICOS`, `CAMPOS_TEXTO` e `CAMPOS_LISTA`).
"""
from __future__ import annotations

from types import MappingProxyType
from typing import Callable, Iterable, Iterator, Mapping, Sequence

from dominio import CAMPOS_LISTA, CAMPOS_NUMERICOS, CAMPOS_TEXTO, Movie, Predicado


# --------------------------------------------------------------------------
# Predicados atômicos (Movie -> bool), um por tipo de critério
# --------------------------------------------------------------------------

def _exigir_campo(campo: str, permitidos: Sequence[str], tipo: str) -> None:
    """Valida o nome do campo: nome errado deve estourar aqui, não silenciosamente."""
    if campo not in permitidos:
        raise ValueError(f"campo não {tipo}: {campo!r}; use um de {tuple(permitidos)}")


def por_genero(genero: str) -> Predicado:
    """Predicado: o filme tem o gênero entre os seus (sem diferenciar maiúsculas)."""
    alvo = genero.strip().casefold()
    return lambda filme: any(item.casefold() == alvo for item in filme.generos)


def por_decada(decada: int) -> Predicado:
    """Predicado: filme lançado na década informada (ex.: 1990 -> 1990..1999).

    1994 é normalizado para 1990: o parâmetro é a década, não o ano. Filmes com
    ano desconhecido (0) nunca casam.
    """
    inicio = (decada // 10) * 10
    return lambda filme: filme.ano > 0 and inicio <= filme.ano <= inicio + 9


def a_partir_da_decada(decada: int) -> Predicado:
    """Predicado: filme da década informada em diante (ex.: 2010 -> 2010, 2011, ...)."""
    inicio = (decada // 10) * 10
    return lambda filme: filme.ano > 0 and filme.ano >= inicio


def por_faixa(campo: str, minimo: float | None = None, maximo: float | None = None) -> Predicado:
    """Predicado: minimo <= campo <= maximo para um campo NUMÉRICO (None = sem limite).

    Ex.: por_faixa('orcamento', 1_000_000), por_faixa('nota', 7), por_faixa('duracao', 90, 120).
    """
    _exigir_campo(campo, CAMPOS_NUMERICOS, "numérico")

    def predicado(filme: Movie) -> bool:
        valor = getattr(filme, campo)
        if minimo is not None and valor < minimo:
            return False
        return maximo is None or valor <= maximo

    return predicado


def orcamento_minimo(valor: float) -> Predicado:
    """Atalho legível para `por_faixa('orcamento', minimo=valor)`."""
    return por_faixa("orcamento", minimo=valor)


def faturamento_minimo(valor: float) -> Predicado:
    """Atalho legível para `por_faixa('faturamento', minimo=valor)`."""
    return por_faixa("faturamento", minimo=valor)


def nota_minima(valor: float) -> Predicado:
    """Atalho legível para `por_faixa('nota', minimo=valor)`."""
    return por_faixa("nota", minimo=valor)


def por_valor(campo: str, *valores: object) -> Predicado:
    """Predicado: campo de valor único (texto ou número) igual a algum dos valores.

    Ex.: por_valor('idioma_original', 'en', 'pt'), por_valor('diretor', 'Christopher Nolan').
    """
    _exigir_campo(campo, CAMPOS_TEXTO + CAMPOS_NUMERICOS, "de valor único")
    alvos = frozenset(valores)
    return lambda filme: getattr(filme, campo) in alvos


def contendo(campo: str, *valores: str) -> Predicado:
    """Predicado: campo-LISTA contém algum dos valores (sem diferenciar maiúsculas).

    Ex.: contendo('elenco', 'Tom Hanks'), contendo('paises', 'BR'), contendo('empresas', 'Pixar').
    Sem valores, rejeita todos os filmes.
    """
    _exigir_campo(campo, CAMPOS_LISTA, "lista")
    alvos = frozenset(valor.strip().casefold() for valor in valores)
    return lambda filme: any(item.casefold() in alvos for item in getattr(filme, campo))


# --------------------------------------------------------------------------
# Combinadores (recebem predicados e devolvem predicado: alta ordem)
# --------------------------------------------------------------------------

def todos(*predicados: Predicado) -> Predicado:
    """E lógico dos predicados, com curto-circuito; sem argumentos, aceita tudo."""
    return lambda filme: all(predicado(filme) for predicado in predicados)


def combinar(*predicados: Predicado) -> Predicado:
    """Mesmo que `todos` (nome que o README/CLI usa para o E lógico)."""
    return todos(*predicados)


def qualquer(*predicados: Predicado) -> Predicado:
    """OU lógico dos predicados, com curto-circuito; sem argumentos, rejeita tudo."""
    return lambda filme: any(predicado(filme) for predicado in predicados)


def negar(predicado: Predicado) -> Predicado:
    """Inverte um predicado."""
    return lambda filme: not predicado(filme)


def filtrar(predicado: Predicado, filmes: Iterable[Movie]) -> Iterator[Movie]:
    """Aplica o predicado de forma preguiçosa (wrapper de `filter`)."""
    return filter(predicado, filmes)


# --------------------------------------------------------------------------
# make_filtro: o critério vem por nome, na forma de palavras-chave
# --------------------------------------------------------------------------

def _fabrica_de_faixa(campo: str, limite: str) -> Callable[..., Predicado]:
    """Fecha o campo e o lado do limite, deixando só o valor em aberto (currying)."""
    return lambda valor: por_faixa(campo, **{limite: valor})


_FAIXAS: Mapping[str, Callable[..., Predicado]] = MappingProxyType({
    **{f"{campo}_min": _fabrica_de_faixa(campo, "minimo") for campo in CAMPOS_NUMERICOS},
    **{f"{campo}_max": _fabrica_de_faixa(campo, "maximo") for campo in CAMPOS_NUMERICOS},
})

_CRITERIOS: Mapping[str, Callable[..., Predicado]] = MappingProxyType({
    **_FAIXAS,
    "genero": por_genero,
    "decada": por_decada,
    "a_partir_de": a_partir_da_decada,
    "ano": lambda valor: por_valor("ano", valor),
    "idioma": lambda valor: por_valor("idioma_original", valor),
    "classificacao": lambda valor: por_valor("classificacao", valor),
    "diretor": lambda valor: por_valor("diretor", valor),
    "colecao": lambda valor: por_valor("colecao", valor),
    "ator": lambda valor: contendo("elenco", valor),
    "pais": lambda valor: contendo("paises", valor),
    "empresa": lambda valor: contendo("empresas", valor),
})


def make_filtro(**criterios: object) -> Predicado:
    """Predicado pronto a partir de critérios nomeados; sem critérios, aceita tudo.

    Critérios aceitos (todos opcionais, combinados com E):
      genero, decada, a_partir_de, ano, idioma, classificacao, diretor, colecao,
      ator, pais, empresa e, para cada campo numérico, '<campo>_min' e
      '<campo>_max' (ex.: orcamento_min=10_000_000, nota_min=7, duracao_max=120).

    Ex.: make_filtro(genero='Terror', a_partir_de=2010, nota_min=7)
    Levanta ValueError para critério desconhecido.
    """
    try:
        predicados = tuple(_CRITERIOS[nome](valor) for nome, valor in criterios.items())
    except KeyError as erro:
        raise ValueError(
            f"critério desconhecido: {erro.args[0]!r}; use um de {tuple(sorted(_CRITERIOS))}"
        ) from None
    return todos(*predicados)