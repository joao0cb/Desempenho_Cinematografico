"""Análise de desempenho cinematográfico — trabalho de Programação Funcional.

O programa lê um banco SQLite com filmes (dados do TMDB) e responde perguntas
sobre eles: filtrar, resumir indicadores, comparar grupos, medir correlação,
montar rankings e cruzar atributos com estatísticas.

AS DUAS REGRAS DO TRABALHO
  1. NÚCLEO (seções 1-12: filtragem, transformação e cálculo) — funcional:
     nada de `def`, `for`, `while`, `if` como instrução, `try`, `raise` ou `class`.
     Só lambdas, compreensões, `map`/`filter`/`reduce` e expressões.
  2. MENU (seção 13: conversa com o terminal) — Python comum: é a borda de I/O,
     então usa `def`, laço, `if` e `try/except` normalmente.

COMO LER O NÚCLEO (os cinco truques que aparecem o tempo todo)
  · lambda com nome        `soma = lambda xs: ...` — faz o papel de uma função.
  · aplicar na hora        `(lambda x: ...)(valor)` — é como declarar uma variável
                           local: o parâmetro vale só dentro daquele trecho.
  · sequência de passos    `(passo1, passo2, resultado)[-1]` ou `_depois(efeito,
                           valor)` — executa em ordem e devolve só o que importa.
  · repetição              `map` (transformar), `filter` (selecionar) e `reduce`
                           (agregar), ou compreensões dentro de lambda.
  · erro como expressão    `_lancar` (raise) e `_tentar` (try/except) da seção 1,
                           porque `raise` e `try` não cabem em uma lambda.

MAPA DO PROJETO (o que o documento pede e onde está)
  modelo de dados imutável .......... seção 2 (Movie)
  limpeza e validação ............... seção 3
  métricas e dimensões .............. seção 4
  filtrar filmes .................... seção 5  (+ menu 1)
  indicadores ....................... seção 4 e 6  (+ menu 2)
  comparar grupos ................... seção 6  (+ menus 3 e 4)
  investigar relações (correlação) .. seção 7  (+ menu 5)
  rankings .......................... seção 8  (+ menu 6)
  cruzar atributos × estatísticas ... seção 6 e 9  (+ menu 7)
  persistência e coleta dos dados ... seções 10 a 12
  interface de terminal ............. seção 13
"""
import argparse
import contextlib
import json
import math
import os
import re
import sqlite3
import sys
import time
from collections import namedtuple
from collections.abc import Iterable, Mapping
from datetime import date
from functools import partial, reduce
from itertools import chain, groupby, islice, product, starmap, takewhile
from operator import add, attrgetter, itemgetter, mul
from pathlib import Path
from types import MappingProxyType

import requests
from dotenv import load_dotenv


 
# ==========================================================================
# 1. BASE: erro e exceção como EXPRESSÃO
# ==========================================================================

# `raise` como expressão: o gerador vazio recebe a exceção no `throw` e a levanta.
_lancar = lambda excecao: (_ for _ in ()).throw(excecao)


# `try/except` como expressão. Um context manager devolve True no `__exit__`
# quando a exceção é de um dos tipos pedidos, e é isso que faz o Python engolir
# o erro. A classe nasce de `type(...)` porque `class` também é proibido aqui.
_Armadilha = type("Armadilha", (contextlib.ContextDecorator,), {
    "__init__": lambda self, *tipos: setattr(self, "tipos", tipos),
    "__enter__": lambda self: self,
    "__exit__": lambda self, tipo, valor, rastro: (
        tipo is not None
        and issubclass(tipo, self.tipos)
        and (setattr(self, "erro", valor) or True)          # guarda o erro e engole
    ),
})

# _tentar(funcao, *tipos) -> (True, resultado)  quando deu certo
#                         -> (False, exceção)  quando caiu em um dos tipos
# Exceções de outros tipos continuam subindo normalmente.
_tentar = lambda funcao, *tipos: (
    lambda armadilha: (
        lambda resultado: (False, armadilha.erro) if resultado is None else (True, resultado[0])
    )(armadilha(lambda: (funcao(),))())          # `(funcao(),)` guarda o retorno
)(_Armadilha(*tipos))
    
# Resultado de `funcao`, ou `padrao` se ocorrer uma das exceções.
_ou = lambda funcao, padrao, *tipos: (
    lambda leitura: leitura[1] if leitura[0] else padrao
)(_tentar(funcao, *tipos))

# Faz `efeito` e devolve `valor` — o "passo 1, passo 2" sem precisar de várias
# linhas: os dois argumentos são avaliados da esquerda para a direita.
_depois = lambda efeito, valor: (efeito, valor)[-1]

# ==========================================================================
# 2. DOMÍNIO: um tipo imutável para o filme
# ==========================================================================

# Registro imutável de um filme (uma linha da tabela `filmes`, na mesma ordem).
# Só id, titulo e ano são obrigatórios; o resto fica com o valor "desconhecido":
# números 0, textos '' e listas ().
Movie = namedtuple(
    "Movie",
    ("id", "titulo", "ano", "data_lancamento", "generos", "orcamento", "faturamento",
     "nota", "popularidade", "duracao", "idioma_original", "classificacao", "diretor",
     "elenco", "paises", "empresas", "colecao"),
    defaults=("", (), 0, 0, 0.0, 0.0, 0, "", "", "", (), (), (), ""),
)

# Indicadores de um grupo: `indicadores` mapeia nome da métrica -> média (ou None).
ResumoGrupo = namedtuple("ResumoGrupo", ("quantidade", "indicadores"))

CAMPOS_NUMERICOS = ("ano", "orcamento", "faturamento", "nota", "popularidade", "duracao")
CAMPOS_TEXTO = ("titulo", "data_lancamento", "idioma_original", "classificacao",
                "diretor", "colecao")
CAMPOS_LISTA = ("generos", "elenco", "paises", "empresas")

# ==========================================================================
# 3. DADOS: conversão, validação e limpeza (funções puras)
# ==========================================================================

ANO_MIN = 1888      # primeiro filme da história
ANO_MAX = 2100      # teto de sanidade
NOTA_MAX = 10.0

# Único formato de texto aceito como número. Testar o formato ANTES de converter
# é o que permite converter sem capturar exceção ('nan', 'inf' e lixo ficam fora).
_TEXTO_NUMERICO = re.compile(r"^[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?$")

# float | None: None se ausente, booleano, ilegível, NaN ou infinito.
_numero = lambda valor: (
    None if valor is None or isinstance(valor, bool)
    else float(valor) if isinstance(valor, (int, float)) and math.isfinite(valor)
    else float(valor.strip()) if isinstance(valor, str) and _TEXTO_NUMERICO.match(valor.strip())
    else None
)
# int; 0 se ausente ou ilegível ('63000000.0' -> 63000000).
_inteiro = lambda valor: (
    valor if isinstance(valor, int) and not isinstance(valor, bool)
    else int(_numero(valor) or 0)
)
# float; 0.0 se ausente ou ilegível.
_decimal = lambda valor: _numero(valor) or 0.0
# str sem espaços nas pontas; '' se ausente.
_texto = lambda valor: "" if valor is None else str(valor).strip()
# 'AAAA-MM-DD'; '' se ausente ou inválida ('1999-03-31T00:00' -> '1999-03-31').
_data = lambda valor: _ou(lambda: date.fromisoformat(_texto(valor)[:10]).isoformat(),
                          "", ValueError)


# Texto JSON -> lista (ou [] se não for um JSON de lista).
_lista_do_json = lambda texto: (
    lambda itens: itens if isinstance(itens, list) else []
)(_ou(lambda: json.loads(texto), [], ValueError, TypeError))
# Texto JSON ou sequência -> lista de itens (qualquer outra coisa vira []).
_como_lista = lambda valor: (
    _lista_do_json(valor) if isinstance(valor, str)
    else list(valor) if isinstance(valor, (list, tuple))
    else [])
# ... e daí -> tupla de textos, sem vazios e sem repetição.
_lista = lambda valor: tuple(dict.fromkeys(filter(None, map(_texto, _como_lista(valor)))))

_CONVERSOR_POR_CAMPO = {
    "id": _inteiro, "titulo": _texto, "ano": _inteiro, "data_lancamento": _data,
    "generos": _lista, "orcamento": _inteiro, "faturamento": _inteiro,
    "nota": _decimal, "popularidade": _decimal, "duracao": _inteiro,
    "idioma_original": _texto, "classificacao": _texto, "diretor": _texto,
    "elenco": _lista, "paises": _lista, "empresas": _lista, "colecao": _texto,
}
# Na ordem dos campos de Movie; um campo novo sem conversor falha já no import.
_CONVERSORES = tuple(map(_CONVERSOR_POR_CAMPO.__getitem__, Movie._fields))
_CAMPOS_LISTA = frozenset(CAMPOS_LISTA)


# Linha do banco -> tupla de valores (vazia se nem for iterável).
_valores_da_linha = lambda linha: tuple(linha) if isinstance(linha, Iterable) else ()
# A linha só serve se tiver todas as colunas e um id numérico.
_linha_servivel = lambda valores: (
    len(valores) == len(_CONVERSORES) and _numero(valores[0]) is not None
)
# Linha do banco (colunas na ordem de Movie) -> Movie; None se a linha não serve.
linha_para_movie = lambda linha: (
    lambda valores: None if not _linha_servivel(valores)
    else Movie(*map(lambda converter, valor: converter(valor), _CONVERSORES, valores))
)(_valores_da_linha(linha))

# Movie -> linha para o banco (campos-lista viram texto JSON).
filme_para_linha = lambda filme: tuple(
    json.dumps(list(valor), ensure_ascii=False) if campo in _CAMPOS_LISTA else valor
    for campo, valor in zip(Movie._fields, filme)
)

# Linhas -> Movies sob demanda, pulando as inutilizáveis.
para_filmes = lambda linhas: (
    filme for filme in map(linha_para_movie, linhas) if filme is not None
)


# ---- JSON do TMDB -> Movie -------------------------------------------------

_objeto = lambda valor: valor if isinstance(valor, Mapping) else {}
_itens = lambda valor: (
    tuple(item for item in valor if isinstance(item, Mapping))
    if isinstance(valor, (list, tuple)) else ()
)
_nomes = lambda itens: _lista([item.get("name") for item in itens])
_nota_limitada = lambda valor: min(max(_decimal(valor), 0.0), NOTA_MAX)

# Primeiro diretor da equipe técnica; '' se não houver.
_diretor = lambda creditos: next(
    (_texto(pessoa.get("name")) for pessoa in _itens(creditos.get("crew"))
     if pessoa.get("job") == "Director"), "")
# Primeira classificação etária dos EUA; '' se não houver.
_classificacao = lambda release_dates: next(
    (_texto(data.get("certification"))
     for pais in _itens(_objeto(release_dates).get("results"))
     if pais.get("iso_3166_1") == "US"
     for data in _itens(pais.get("release_dates"))
     if _texto(data.get("certification"))), "")

# Um filme só entra na base com id, título e data de lançamento válidos.
_filme_util = lambda detalhe: (
    isinstance(detalhe, Mapping)
    and _inteiro(detalhe.get("id")) > 0
    and bool(_texto(detalhe.get("title")))
    and bool(_data(detalhe.get("release_date")))
)

# JSON de /movie/{id}?append_to_response=credits,release_dates -> Movie | None
_movie_do_json = lambda detalhe: (
    lambda filme_id, titulo, data_lancamento, creditos: Movie(
        id=filme_id,
        titulo=titulo,
        ano=_inteiro(data_lancamento[:4]),
        data_lancamento=data_lancamento,
        generos=_nomes(_itens(detalhe.get("genres"))),
        orcamento=_inteiro(detalhe.get("budget")),
        faturamento=_inteiro(detalhe.get("revenue")),
        nota=_nota_limitada(detalhe.get("vote_average")),
        popularidade=_decimal(detalhe.get("popularity")),
        duracao=_inteiro(detalhe.get("runtime")),
        idioma_original=_texto(detalhe.get("original_language")),
        classificacao=_classificacao(detalhe.get("release_dates")),
        diretor=_diretor(creditos),
        elenco=_lista([item.get("name") for item in _itens(creditos.get("cast"))[:5]]),
        paises=_lista([item.get("iso_3166_1")
                       for item in _itens(detalhe.get("production_countries"))]),
        empresas=_nomes(_itens(detalhe.get("production_companies"))),
        colecao=_texto(_objeto(detalhe.get("belongs_to_collection")).get("name")),
    )
)(_inteiro(detalhe.get("id")), _texto(detalhe.get("title")),
  _data(detalhe.get("release_date")), _objeto(detalhe.get("credits")))

para_movie = lambda detalhe: None if not _filme_util(detalhe) else _movie_do_json(detalhe)


# ---- validação e limpeza ---------------------------------------------------

# Um valor conta como "preenchido" se for número maior que zero ou não vazio.
_presente = lambda valor: (
    valor > 0 if isinstance(valor, (int, float)) and not isinstance(valor, bool)
    else bool(valor)
)
# Predicado "o filme tem o campo preenchido"; ValueError se o campo não existir.
tem_valor = lambda campo: (
    (lambda filme: _presente(getattr(filme, campo))) if campo in Movie._fields
    else _lancar(ValueError(f"campo desconhecido: {campo!r}"))
)

tem_orcamento_valido = lambda filme: filme.orcamento > 0
tem_faturamento_valido = lambda filme: filme.faturamento > 0
tem_financeiro_valido = lambda filme: tem_orcamento_valido(filme) and tem_faturamento_valido(filme)
tem_nota_valida = lambda filme: 0.0 < filme.nota <= NOTA_MAX
tem_ano_valido = lambda filme: ANO_MIN <= filme.ano <= ANO_MAX

# Um filme só é válido para análise se tiver orçamento, faturamento, nota e ano.
REQUISITOS_PADRAO = (tem_orcamento_valido, tem_faturamento_valido, tem_nota_valida, tem_ano_valido)
eh_valido = lambda filme: all(requisito(filme) for requisito in REQUISITOS_PADRAO)

# Limpeza preguiçosa: só os filmes que cumprem TODAS as exigências dadas.
limpar_com = lambda exigencias, filmes: (
    lambda fixas: filter(lambda filme: all(exigencia(filme) for exigencia in fixas), filmes)
)(tuple(exigencias))
limpar = lambda filmes: limpar_com(REQUISITOS_PADRAO, filmes)
com_financeiro_valido = lambda filmes: filter(tem_financeiro_valido, filmes)
com_nota_valida = lambda filmes: filter(tem_nota_valida, filmes)
# Os `n` filmes a partir de `inicio`, sem materializar o resto.
amostra = lambda filmes, n, inicio=0: islice(filmes, inicio, inicio + n)

# ==========================================================================
# 4. MÉTRICAS E DIMENSÕES (puras)
#    MÉTRICA:   Movie -> número ou None   (médias, rankings, correlação)
#    DIMENSÃO:  Movie -> chaves de grupo  (agrupamentos e comparações)
# ==========================================================================

NOMES_METRICAS = ("orcamento", "faturamento", "lucro", "roi", "nota",
                  "popularidade", "duracao", "ano")
NOMES_DIMENSOES = ("genero", "decada", "ano", "mes", "trimestre", "idioma", "classificacao",
                   "diretor", "ator", "pais", "empresa", "colecao", "em_franquia",
                   "faixa_orcamento", "faixa_nota", "faixa_duracao")

decada = lambda filme: (filme.ano // 10) * 10
# Mês (1 a 12) da data de lançamento; None se desconhecido.
mes = lambda filme: (
    None if len(filme.data_lancamento) < 7 or not filme.data_lancamento[5:7].isdecimal()
    else (numero if 1 <= (numero := int(filme.data_lancamento[5:7])) <= 12 else None)
)
trimestre = lambda filme: None if (m := mes(filme)) is None else (m - 1) // 3 + 1
lucro = lambda filme: filme.faturamento - filme.orcamento
# (faturamento - orcamento) / orcamento; None se não houver orçamento.
roi = lambda filme: (
    None if filme.orcamento <= 0 else (filme.faturamento - filme.orcamento) / filme.orcamento
)

# ---- agregações ------------------------------------------------------------

soma = lambda valores: float(reduce(add, valores, 0.0))
# Média em uma passada: o acumulador é o par (soma, quantos valores).
media = lambda valores: (
    lambda soma_e_quantidade: (
        None if soma_e_quantidade[1] == 0
        else soma_e_quantidade[0] / soma_e_quantidade[1]
    )
)(reduce(lambda acumulado, valor: (acumulado[0] + valor, acumulado[1] + 1), valores, (0.0, 0)))
# Mediana de uma lista JÁ ordenada (lista nova: a entrada nunca é alterada).
_mediana_ordenada = lambda ordenados: (
    float(ordenados[len(ordenados) // 2]) if len(ordenados) % 2 == 1
    else (float(ordenados[len(ordenados) // 2 - 1])
          + float(ordenados[len(ordenados) // 2])) / 2
)
mediana = lambda valores: (
    lambda ordenados: _mediana_ordenada(ordenados) if ordenados else None
)(sorted(valores))

# 0 é o "não informado" do TMDB: vira None para não poluir médias e rankings.
_positivo = lambda valor: valor if valor > 0 else None

# Cada métrica vira um seletor Movie -> float | None.
_SELETORES = MappingProxyType({
    "orcamento": lambda filme: _positivo(float(filme.orcamento)),
    "faturamento": lambda filme: _positivo(float(filme.faturamento)),
    "lucro": lambda filme: float(lucro(filme)),
    "roi": roi,
    "nota": lambda filme: _positivo(filme.nota),
    "popularidade": lambda filme: _positivo(filme.popularidade),
    "duracao": lambda filme: _positivo(float(filme.duracao)),
    "ano": lambda filme: _positivo(float(filme.ano)),
})
# Seletor da métrica `nome`; ValueError se desconhecida.
metrica = lambda nome: (
    _SELETORES[nome] if nome in _SELETORES
    else _lancar(ValueError(f"métrica desconhecida: {nome!r}; use uma de {NOMES_METRICAS}"))
)

# Chave de um grupo: tupla de 1 elemento; valor desconhecido (None, '' ou 0) sai.
_chave = lambda valor: () if valor is None or valor == "" or valor == 0 else (valor,)

# Faixas: (limite superior exclusivo, rótulo) + rótulo da última faixa.
FAIXAS_ORCAMENTO = ((10_000_000, "até US$ 10 mi"), (50_000_000, "US$ 10-50 mi"),
                    (100_000_000, "US$ 50-100 mi"))
FAIXA_ORCAMENTO_FINAL = "acima de US$ 100 mi"
FAIXAS_NOTA = ((5.0, "0-5"), (7.0, "5-7"), (8.0, "7-8"))
FAIXA_NOTA_FINAL = "8-10"
FAIXAS_DURACAO = ((90, "até 90 min"), (120, "90-120 min"), (150, "120-150 min"))
FAIXA_DURACAO_FINAL = "150 min ou mais"

# Primeira faixa cujo limite superior é maior que o valor; senão, a última.
# Devolve uma tupla de 1 elemento, como as outras dimensões.
_faixa = lambda valor, faixas, ultima: (
    next((nome for limite, nome in faixas if valor < limite), ultima),)

# Cada dimensão vira um seletor Movie -> tupla de chaves.
_DIMENSOES = MappingProxyType({
    "genero": lambda filme: tuple(filme.generos),
    "decada": lambda filme: _chave(decada(filme)),
    "ano": lambda filme: _chave(filme.ano),
    "mes": lambda filme: _chave(mes(filme)),
    "trimestre": lambda filme: _chave(trimestre(filme)),
    "idioma": lambda filme: _chave(filme.idioma_original),
    "classificacao": lambda filme: _chave(filme.classificacao),
    "diretor": lambda filme: _chave(filme.diretor),
    "ator": lambda filme: tuple(filme.elenco),
    "pais": lambda filme: tuple(filme.paises),
    "empresa": lambda filme: tuple(filme.empresas),
    "colecao": lambda filme: _chave(filme.colecao),
    "em_franquia": lambda filme: ("em franquia" if filme.colecao else "fora de franquia",),
    "faixa_orcamento": lambda filme: (
        () if filme.orcamento <= 0
        else _faixa(filme.orcamento, FAIXAS_ORCAMENTO, FAIXA_ORCAMENTO_FINAL)),
    "faixa_nota": lambda filme: (
        () if filme.nota <= 0 else _faixa(filme.nota, FAIXAS_NOTA, FAIXA_NOTA_FINAL)),
    "faixa_duracao": lambda filme: (
        () if filme.duracao <= 0
        else _faixa(filme.duracao, FAIXAS_DURACAO, FAIXA_DURACAO_FINAL)),
})
# Dimensão `nome`; tupla vazia quando o filme não tem o dado. ValueError se desconhecida.
dimensao = lambda nome: (
    _DIMENSOES[nome] if nome in _DIMENSOES
    else _lancar(ValueError(f"dimensão desconhecida: {nome!r}; use uma de {NOMES_DIMENSOES}"))
)

# ==========================================================================
# 5. FILTROS: funções de alta ordem que fabricam predicados (Movie -> bool)
# ==========================================================================

# Confere o nome do campo e devolve o próprio nome (o erro sobe aqui, não depois).
_exigir_campo = lambda campo, permitidos, tipo: (
    campo if campo in permitidos
    else _lancar(ValueError(f"campo não {tipo}: {campo!r}; use um de {tuple(permitidos)}"))
)

# Gênero entre os do filme (sem diferenciar maiúsculas).
por_genero = lambda genero: (
    lambda alvo: lambda filme: any(item.casefold() == alvo for item in filme.generos)
)(genero.strip().casefold())
# Década informada (1994 -> 1990..1999); ano desconhecido (0) nunca casa.
por_decada = lambda decada_: (
    lambda inicio: lambda filme: filme.ano > 0 and inicio <= filme.ano <= inicio + 9
)((decada_ // 10) * 10)
# Década informada em diante.
a_partir_da_decada = lambda decada_: (
    lambda inicio: lambda filme: filme.ano > 0 and filme.ano >= inicio
)((decada_ // 10) * 10)

# minimo <= campo <= maximo para um campo NUMÉRICO (None = sem limite).
_faixa_de = lambda campo, minimo, maximo: lambda filme: (
    (minimo is None or getattr(filme, campo) >= minimo)
    and (maximo is None or getattr(filme, campo) <= maximo)
)
por_faixa = lambda campo, minimo=None, maximo=None: _faixa_de(
    _exigir_campo(campo, CAMPOS_NUMERICOS, "numérico"), minimo, maximo)
orcamento_minimo = lambda valor: por_faixa("orcamento", minimo=valor)
faturamento_minimo = lambda valor: por_faixa("faturamento", minimo=valor)
nota_minima = lambda valor: por_faixa("nota", minimo=valor)

# Campo de valor único igual a algum dos valores.
_valor_de = lambda campo, valores: (
    lambda alvos: lambda filme: getattr(filme, campo) in alvos
)(frozenset(valores))
por_valor = lambda campo, *valores: _valor_de(
    _exigir_campo(campo, CAMPOS_TEXTO + CAMPOS_NUMERICOS, "de valor único"), valores)

# Campo-LISTA contém algum dos valores (sem diferenciar maiúsculas).
_contendo = lambda campo, valores: (
    lambda alvos: lambda filme: any(item.casefold() in alvos for item in getattr(filme, campo))
)(frozenset(valor.strip().casefold() for valor in valores))
contendo = lambda campo, *valores: _contendo(
    _exigir_campo(campo, CAMPOS_LISTA, "lista"), valores)

# Combinadores: recebem predicados e devolvem predicado.
todos = lambda *predicados: lambda filme: all(predicado(filme) for predicado in predicados)
combinar = lambda *predicados: todos(*predicados)
qualquer = lambda *predicados: lambda filme: any(predicado(filme) for predicado in predicados)
negar = lambda predicado: lambda filme: not predicado(filme)
filtrar = lambda predicado, filmes: filter(predicado, filmes)

# Critérios nomeados aceitos por make_filtro (cada chave vira um predicado).
_fabrica_de_faixa = lambda campo, limite: lambda valor: por_faixa(campo, **{limite: valor})
_FAIXAS = dict(chain(
    map(lambda campo: (f"{campo}_min", _fabrica_de_faixa(campo, "minimo")), CAMPOS_NUMERICOS),
    map(lambda campo: (f"{campo}_max", _fabrica_de_faixa(campo, "maximo")), CAMPOS_NUMERICOS),
))
_CRITERIOS = MappingProxyType({
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

# Predicado pronto a partir de critérios nomeados (combinados com E).
# Ex.: make_filtro(genero='Terror', a_partir_de=2010, nota_min=7)
make_filtro = lambda **criterios: (
    todos(*map(lambda criterio: _CRITERIOS[criterio[0]](criterio[1]), criterios.items()))
    if all(nome in _CRITERIOS for nome in criterios)
    else _lancar(ValueError(
        f"critério desconhecido: {next(nome for nome in criterios if nome not in _CRITERIOS)!r}; "
        f"use um de {tuple(sorted(_CRITERIOS))}"))
)

# ==========================================================================
# 6. ANÁLISES: agrupar e comparar grupos (puras, sem SQL)
# ==========================================================================

# Indicadores calculados por `resumir` (nomes do catálogo de métricas).
INDICADORES_PADRAO = ("roi", "nota", "faturamento")

# Um par (chave, filme) para CADA chave do filme: um filme com 2 gêneros entra
# em 2 grupos; `dict.fromkeys` tira repetições e mantém a ordem.
_pares_chave_filme = lambda dim, filmes: chain.from_iterable(
    map(lambda filme: map(lambda chave: (chave, filme), dict.fromkeys(dim(filme))), filmes))

# Agrupa pelas chaves de uma dimensão. `sorted` é estável e devolve lista nova;
# `groupby` só junta vizinhos, por isso a ordenação por chave antes.
agrupar_por = lambda dim, filmes: dict(
    (chave, tuple(map(itemgetter(1), grupo)))
    for chave, grupo in groupby(
        sorted(_pares_chave_filme(dim, filmes), key=itemgetter(0)), key=itemgetter(0))
)

# quantidade + média de cada indicador (só filmes com dado válido; None se nenhum).
resumir = lambda filmes, indicadores=INDICADORES_PADRAO: (
    lambda base: ResumoGrupo(
        len(base),
        MappingProxyType({
            nome: media(filter(lambda valor: valor is not None, map(metrica(nome), base)))
            for nome in indicadores
        }),
    )
)(tuple(filmes))

comparar_por = lambda dim, filmes: MappingProxyType({
    chave: resumir(grupo) for chave, grupo in agrupar_por(dim, filmes).items()
})
comparar_por_genero = lambda filmes: comparar_por(dimensao("genero"), filmes)
comparar_por_decada = lambda filmes: comparar_por(dimensao("decada"), filmes)

# ---- ANÁLISE PERSONALIZADA: cruzar quaisquer atributos com quaisquer estatísticas ----

# Várias dimensões viram UMA só: a chave ganha uma posição por dimensão.
# Dimensão multivalorada (gênero, ator, país...) entra no produto cartesiano: um
# filme de 2 gêneros numa década gera 2 chaves de 2 posições — ('Ação', 1990) e
# ('Drama', 1990). Se faltar valor em ALGUMA dimensão o filme fica de fora, para
# que nenhuma chave saia menor que as outras.
_unir_dimensoes = lambda *dims: lambda filme: (
    lambda chaves: () if any(not chave for chave in chaves) else tuple(product(*chaves))
)(tuple(dim(filme) for dim in dims))

# Agrupa pelos atributos pedidos e resume cada grupo com as estatísticas pedidas.
# Ex.: analisar(("genero", "decada"), ("roi", "nota"), filmes)
analisar = lambda nomes_dimensoes, nomes_indicadores, filmes: (
    lambda dim, indicadores: MappingProxyType({
        chave: resumir(grupo, indicadores) for chave, grupo in agrupar_por(dim, filmes).items()
    })
)(_unir_dimensoes(*map(dimensao, nomes_dimensoes)), tuple(nomes_indicadores))

# ==========================================================================
# 7. CORRELAÇÃO DE PEARSON (pura)
#    Correlação não implica causalidade: a interpretação é de quem lê.
# ==========================================================================

compor = lambda f, g: lambda x: f(g(x))

# Desvios de cada valor em relação à média da série.
_desvios = lambda valores: (
    lambda media_da_serie: tuple(valor - media_da_serie for valor in valores)
)(soma(valores) / len(valores))

_soma_dos_produtos = lambda xs, ys: soma(map(mul, xs, ys))
_soma_dos_quadrados = lambda xs: soma(map(lambda desvio: desvio * desvio, xs))

# Só dá para correlacionar com 2+ pares e com as duas séries variando.
_da_para_correlacionar = lambda pares: (
    len(pares) >= 2
    and len(frozenset(x for x, _ in pares)) > 1
    and len(frozenset(y for _, y in pares)) > 1
)

# Coeficiente de Pearson: covariância / (desvio padrão x desvio padrão).
# O limitador -1..1 absorve erro de ponto flutuante (ex.: 1.0000000000000002).
_coeficiente = lambda pares: (
    lambda desvios_x, desvios_y: max(-1.0, min(1.0,
        _soma_dos_produtos(desvios_x, desvios_y)
        / math.sqrt(_soma_dos_quadrados(desvios_x) * _soma_dos_quadrados(desvios_y))))
)(_desvios(tuple(x for x, _ in pares)), _desvios(tuple(y for _, y in pares)))

# Coeficiente de Pearson; None se não der para calcular.
pearson = lambda xs, ys: (
    lambda pares: _coeficiente(pares) if _da_para_correlacionar(pares) else None
)(tuple(zip(xs, ys)))

# Pares (x, y) dos filmes em que os DOIS seletores devolvem número.
_pares_de = lambda x, y, filmes: tuple(
    par for par in map(lambda filme: (x(filme), y(filme)), filmes) if None not in par)

# Correlação entre dois seletores, descartando filmes com dado faltando.
correlacionar = lambda x, y, filmes: (
    lambda pares: pearson(tuple(map(itemgetter(0), pares)), tuple(map(itemgetter(1), pares)))
)(_pares_de(x, y, filmes))

# Pares (orçamento, faturamento) válidos, sob demanda.
pares_orcamento_faturamento = lambda filmes: (
    (float(filme.orcamento), float(filme.faturamento))
    for filme in filmes if filme.orcamento > 0 and filme.faturamento > 0
)
# O TMDB usa 0 para "não informado": para análise, zero equivale a ausente.
_positivo_ou_none = lambda valor: valor if valor is not None and valor > 0 else None
_sel_orcamento = compor(_positivo_ou_none, attrgetter("orcamento"))
_sel_faturamento = compor(_positivo_ou_none, attrgetter("faturamento"))
_sel_nota = compor(_positivo_ou_none, attrgetter("nota"))
orcamento_vs_faturamento = lambda filmes: correlacionar(_sel_orcamento, _sel_faturamento, filmes)
orcamento_vs_nota = lambda filmes: correlacionar(_sel_orcamento, _sel_nota, filmes)

# Texto do relatório (devolve str; não imprime). `r` é None quando não calcula.
_relatorio_de = lambda pares, r: "\n".join((
    "Correlação orçamento x faturamento",
    f"  pares usados: {len(pares)}",
    f"  coeficiente de Pearson: {'-' if r is None else f'{r:.3f}'}",
    *(() if r is not None else
      ("  (não calculável: menos de 2 pares ou uma das séries é constante)",)),
    "  Correlação não implica causalidade: um coeficiente alto não prova "
    "que o orçamento causou o faturamento.",
))
relatorio_correlacao = lambda filmes: (
    lambda pares: _relatorio_de(pares, pearson(tuple(map(itemgetter(0), pares)),
                                               tuple(map(itemgetter(1), pares))))
)(tuple(pares_orcamento_faturamento(filmes)))

# ==========================================================================
# 8. RANKING (puro)
# ==========================================================================

# Pares (chave, filme) de quem tem a chave; chave None fica de fora.
_com_chave = lambda chave, filmes: filter(
    lambda par: par[0] is not None, map(lambda filme: (chave(filme), filme), filmes))

# Os n primeiros filmes por uma chave. `sorted` é estável (empates mantêm a
# ordem de entrada); a chave é calculada uma vez por filme; n <= 0 devolve ().
top_filmes = lambda n, chave, filmes, decrescente=True: tuple(islice(
    map(itemgetter(1), sorted(_com_chave(chave, filmes), key=itemgetter(0), reverse=decrescente)),
    max(n, 0)))

# Os n primeiros grupos por um indicador do resumo; indicador None/ausente sai.
top_grupos = lambda n, indicador, grupos, decrescente=True: tuple(islice(
    sorted(filter(lambda par: par[1].indicadores.get(indicador) is not None, grupos.items()),
           key=lambda par: par[1].indicadores[indicador], reverse=decrescente),
    max(n, 0)))

# ==========================================================================
# 9. FORMATAÇÃO: texto para o terminal (as `formatar_*` são puras; só `exibir` escreve)
# ==========================================================================

AVISO_CORRELACAO = "Atenção: correlação não implica causalidade."
LARGURA_TITULO = 34
SEPARADOR_COLUNAS = "  "
_PT_BR = str.maketrans({",": ".", ".": ","})   # troca simultânea: 1,234.5 -> 1.234,5
_FORCAS = ((0.1, "praticamente nula"), (0.3, "fraca"), (0.7, "moderada"))
_FORCA_FINAL = "forte"

# Número no padrão brasileiro: milhar '.' e decimal ','.
_num_br = lambda valor, casas: f"{valor:,.{casas}f}".translate(_PT_BR)
# 1234567 -> 'US$ 1.234.567'; negativo -> '-US$ 1.234.567'.
formatar_moeda = lambda valor: (
    lambda inteiro: f"{'-' if inteiro < 0 else ''}US$ {_num_br(abs(inteiro), 0)}"
)(round(valor))
# 3.0 -> '300,0%'; None -> '-'. O `+ 0.0` troca -0.0 por 0.0 (evita '-0,0%').
formatar_percentual = lambda valor: (
    "-" if valor is None else f"{_num_br(round(valor * 100, 1) + 0.0, 1)}%")
# 7.46 -> '7,5'; None ou 0 (sem avaliações) -> '-'.
formatar_nota = lambda valor: "-" if not valor else _num_br(valor, 1)
_ou_traco = lambda valor, formatador: "-" if not valor else formatador(valor)
_cortar = lambda texto, largura: texto if len(texto) <= largura else texto[: largura - 1] + "…"
# Título com a régua de '=' embaixo.
_bloco = lambda titulo: f"{titulo}\n{'=' * len(titulo)}"

# Uma linha da tabela: cada célula alinhada à esquerda ('<') ou à direita ('>').
_montar = lambda celulas, larguras, alinhamento: SEPARADOR_COLUNAS.join(
    f"{celula:{alinhamento[i]}{largura}}"
    for i, (celula, largura) in enumerate(zip(celulas, larguras)))
# Largura de cada coluna = a do maior texto dela (cabeçalho incluído).
# `zip(cabecalho, *corpo)` transpõe a tabela: cada elemento é uma coluna.
_larguras = lambda cabecalho, corpo: tuple(
    max(len(str(celula)) for celula in coluna) for coluna in zip(cabecalho, *corpo))
# Tabela = cabeçalho + régua de '-' + uma linha por item do corpo.
_tabela = lambda cabecalho, linhas, alinhamento: (
    lambda corpo: (
        lambda larguras: "\n".join((
            _montar(cabecalho, larguras, alinhamento),
            SEPARADOR_COLUNAS.join("-" * largura for largura in larguras),
            *map(lambda linha: _montar(linha, larguras, alinhamento), corpo),
        ))
    )(_larguras(cabecalho, corpo))
)(tuple(linhas))

# ---- tabela de filmes ------------------------------------------------------

_CABECALHO_FILMES = ("Título", "Ano", "Orçamento", "Faturamento", "ROI", "Nota")
_ALINHAMENTO_FILMES = "<>>>>>"

_linha_filme = lambda filme: (
    _cortar(filme.titulo, LARGURA_TITULO),
    str(filme.ano),
    _ou_traco(filme.orcamento, formatar_moeda),
    _ou_traco(filme.faturamento, formatar_moeda),
    formatar_percentual(roi(filme)),
    formatar_nota(filme.nota),
)
formatar_filmes = lambda filmes: (
    lambda lista: "Nenhum filme encontrado." if not lista
    else _tabela(_CABECALHO_FILMES, map(_linha_filme, lista), _ALINHAMENTO_FILMES)
)(tuple(filmes))

# ---- tabela de grupos (comparações) ---------------------------------------

_CABECALHO_GRUPOS = ("Grupo", "Filmes", "ROI médio", "Nota média", "Faturamento médio")
_ALINHAMENTO_GRUPOS = "<>>>>"

# Chave de grupo como texto; chave composta (tupla) vira 'a × b'.
_rotulo = lambda chave: " × ".join(map(str, chave)) if isinstance(chave, tuple) else str(chave)
_linha_grupo = lambda chave, resumo: (
    _rotulo(chave),
    str(resumo.quantidade),
    formatar_percentual(resumo.indicadores.get("roi")),
    formatar_nota(resumo.indicadores.get("nota")),
    _ou_traco(resumo.indicadores.get("faturamento"), formatar_moeda),
)
formatar_comparacao = lambda titulo, grupos: (
    lambda lista, cabecalho: (
        cabecalho + "\nNenhum grupo para comparar." if not lista
        else cabecalho + "\n" + _tabela(_CABECALHO_GRUPOS, starmap(_linha_grupo, lista),
                                        _ALINHAMENTO_GRUPOS)
    )
)(tuple(grupos), _bloco(titulo))

# ---- tabela da análise personalizada (atributos × estatísticas) ------------

ROTULOS_DIMENSOES = MappingProxyType({
    "genero": "Gênero", "decada": "Década", "ano": "Ano", "mes": "Mês",
    "trimestre": "Trimestre", "idioma": "Idioma", "classificacao": "Classificação",
    "diretor": "Diretor", "ator": "Ator", "pais": "País", "empresa": "Empresa",
    "colecao": "Coleção", "em_franquia": "Em franquia",
    "faixa_orcamento": "Faixa de orçamento", "faixa_nota": "Faixa de nota",
    "faixa_duracao": "Faixa de duração",
})
ROTULOS_METRICAS = MappingProxyType({
    "orcamento": "Orçamento médio", "faturamento": "Faturamento médio",
    "lucro": "Lucro médio", "roi": "ROI médio", "nota": "Nota média",
    "popularidade": "Popularidade média", "duracao": "Duração média",
    "ano": "Ano médio",
})
# Como cada estatística vira célula de texto.
_FORMATADORES = MappingProxyType({
    "orcamento": formatar_moeda, "faturamento": formatar_moeda, "lucro": formatar_moeda,
    "roi": formatar_percentual, "nota": formatar_nota,
    "popularidade": lambda valor: _num_br(valor, 1),
    # Ano e duração não levam separador de milhar ("1999", não "1.999").
    "duracao": lambda valor: f"{valor:.0f}",
    "ano": lambda valor: f"{valor:.0f}",
})
# None = o grupo não tem nenhum filme com dado válido para aquela estatística.
_celula_metrica = lambda nome, valor: "-" if valor is None else _FORMATADORES[nome](valor)

_linha_analise = lambda nomes_indicadores, par: (
    _rotulo(par[0]),
    str(par[1].quantidade),
    *map(lambda nome: _celula_metrica(nome, par[1].indicadores.get(nome)), nomes_indicadores),
)
formatar_analise = lambda titulo, subtitulo, nomes_indicadores, grupos: (
    lambda itens, cabecalho: (
        cabecalho + "\nNenhum grupo para mostrar com esses atributos e essa estatística."
        if not itens else cabecalho + "\n" + _tabela(
            ("Grupo", "Filmes", *map(ROTULOS_METRICAS.__getitem__, nomes_indicadores)),
            map(partial(_linha_analise, nomes_indicadores), itens),
            "<" + ">" * (len(nomes_indicadores) + 1))
    )
)(tuple(grupos), _bloco(titulo) + "\n" + subtitulo)

# ---- correlação em texto ---------------------------------------------------

# Força e sentido em palavras (|r| < 0,1 não tem sentido a descrever).
_descrever = lambda r: (
    f"correlação {next((nome for limite, nome in _FORCAS if abs(r) < limite), _FORCA_FINAL)}"
    + ("" if abs(r) < _FORCAS[0][0] else " positiva" if r > 0 else " negativa")
)
formatar_correlacao = lambda rotulo, r: (
    f"{rotulo}: indefinida (dados insuficientes ou sem variação)\n{AVISO_CORRELACAO}"
    if r is None
    else f"{rotulo}: r = {_num_br(r, 3)} ({_descrever(r)})\n{AVISO_CORRELACAO}"
)

# A única função com efeito colateral desta seção.
exibir = lambda texto: print(texto)

# ==========================================================================
# 10. BANCO SQLITE (I/O). O banco é só ARMAZENAMENTO: sem GROUP BY/AVG/SUM.
# ==========================================================================

DB_PADRAO = Path("data") / "cinema.db"
SCHEMA_PATH = Path(__file__).with_name("schema.sql")
_COLUNAS = ", ".join(Movie._fields)
_PLACEHOLDERS = ", ".join("?" * len(Movie._fields))
CONSULTA_FILMES = f"SELECT {_COLUNAS} FROM filmes ORDER BY id"

# Abre (e cria a pasta do banco, se preciso). Aceita ':memory:' nos testes.
conectar = lambda caminho=DB_PADRAO: (
    Path(str(caminho)).parent.mkdir(parents=True, exist_ok=True),
    sqlite3.connect(str(caminho)),
)[-1]
# Lê e executa o schema.sql (idempotente: o script usa CREATE TABLE IF NOT EXISTS).
inicializar_schema = lambda conn: (
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8")), None)[-1]
# Insere ou substitui por id; devolve quantas linhas foram gravadas.
inserir_filmes = lambda conn, filmes: (
    lambda antes: (
        conn.executemany(
            f"INSERT OR REPLACE INTO filmes ({_COLUNAS}) VALUES ({_PLACEHOLDERS})",
            map(filme_para_linha, filmes)),
        conn.commit(),
        conn.total_changes - antes,
    )[-1]
)(conn.total_changes)
# Streaming: o cursor só é aberto na primeira linha pedida (nada de fetchall()).
ler_linhas = lambda conn: iter(conn.execute(CONSULTA_FILMES))
ler_filmes = lambda conn: para_filmes(ler_linhas(conn))

# ==========================================================================
# 11. CLIENTE DA API DO TMDB (I/O: rede). Mensagens nunca incluem o token.
# ==========================================================================

BASE_URL = "https://api.themoviedb.org/3"
TIMEOUT_PADRAO = 10.0          # segundos antes de desistir de uma requisição
TENTATIVAS_RATE_LIMIT = 2      # novas tentativas depois de um 429
ESPERA_RATE_LIMIT = 2.0        # espera padrão (s) quando não há Retry-After
ESPERA_MAXIMA = 10.0           # teto da espera

# Lê TMDB_TOKEN do ambiente/.env; RuntimeError se ausente.
_token_configurado = lambda token: (
    token if token else _lancar(RuntimeError(
        "TMDB_TOKEN não configurado. Copie .env.example para .env e preencha "
        "com o 'Token de Acesso de Leitura da API' "
        "(TMDB > Configurações > API). O .env não deve ser commitado."))
)
carregar_token = lambda: (
    load_dotenv(),
    _token_configurado(os.environ.get("TMDB_TOKEN", "").strip()),
)[-1]
# Bearer token no header: o token nunca vai na URL (evita vazar em log).
_cabecalhos = lambda token: {"Authorization": f"Bearer {token}", "Accept": "application/json"}
# Respeita o `Retry-After` quando o TMDB manda; senão usa o padrão.
_espera_da_resposta = lambda resposta: (
    lambda leitura: min(max(leitura[1], 0.0), ESPERA_MAXIMA) if leitura[0] else ESPERA_RATE_LIMIT
)(_tentar(lambda: float(resposta.headers.get("Retry-After", "")), TypeError, ValueError))

# GET com timeout; falha de rede vira RuntimeError com mensagem clara.
_resposta_ou_erro = lambda leitura, caminho: (
    leitura[1] if leitura[0]
    else _lancar(RuntimeError(
        f"tempo esgotado ao consultar o TMDB ({caminho}) após "
        f"{TIMEOUT_PADRAO:.0f}s. Verifique a conexão e tente de novo."))
    if isinstance(leitura[1], requests.Timeout)
    else _lancar(RuntimeError(
        f"falha de rede ao consultar o TMDB ({caminho}): {type(leitura[1]).__name__}."))
)
_requisitar = lambda token, caminho, parametros: _resposta_ou_erro(
    _tentar(lambda: requests.get(f"{BASE_URL}{caminho}", headers=_cabecalhos(token),
                                 params=parametros, timeout=TIMEOUT_PADRAO),
            requests.RequestException),
    caminho)

# Mensagens dos erros que o usuário precisa saber resolver; o resto vira status.
_MENSAGENS_POR_STATUS = MappingProxyType({
    401: ("token do TMDB recusado (401). Confira TMDB_TOKEN no .env: "
          "ele precisa ser o 'Token de Acesso de Leitura da API' (começa com 'eyJ')."),
    429: ("limite de requisições do TMDB atingido (429). "
          "Aguarde alguns instantes e rode a ingestão novamente."),
})
_mensagem_do_erro = lambda resposta, caminho: _MENSAGENS_POR_STATUS.get(
    resposta.status_code, f"o TMDB respondeu {resposta.status_code} em {caminho}.")

# Resposta -> dados: ok devolve o JSON; 429 com tentativa disponível espera e
# repete; qualquer outro status vira RuntimeError com a mensagem correspondente.
_tratar_resposta = lambda resposta, caminho, tentar_de_novo: (
    resposta.json() if resposta.ok
    else _depois_de_esperar(resposta, tentar_de_novo)
    if resposta.status_code == 429 and tentar_de_novo is not None
    else _lancar(RuntimeError(_mensagem_do_erro(resposta, caminho)))
)

# GET autenticado; a nova tentativa do 429 é uma chamada recursiva.
_obter = lambda token, caminho, parametros, tentativa=0: _tratar_resposta(
    _requisitar(token, caminho, parametros), caminho,
    None if tentativa == TENTATIVAS_RATE_LIMIT
    else partial(_obter, token, caminho, parametros, tentativa + 1))

# Espera o tempo pedido pelo TMDB e então tenta de novo (o sleep vem primeiro).
_depois_de_esperar = lambda resposta, tentar_de_novo: _depois(
    time.sleep(_espera_da_resposta(resposta)), tentar_de_novo())

# Uma página de /discover/movie: maior faturamento primeiro, >= 100 votos, pt-BR.
# Esses critérios definem quais filmes entram na base (viés de amostragem).
descobrir_filmes = lambda token, pagina=1: _obter(
    token, "/discover/movie",
    {"sort_by": "revenue.desc", "vote_count.gte": 100, "language": "pt-BR", "page": pagina})
# /movie/{id} com credits e release_dates (único endpoint com budget e revenue).
detalhar_filme = lambda token, filme_id: _obter(
    token, f"/movie/{filme_id}",
    {"language": "pt-BR", "append_to_response": "credits,release_dates"})
buscar_pagina = lambda pagina=1: list(descobrir_filmes(carregar_token(), pagina).get("results", []))
buscar_detalhes = lambda filme_id: dict(detalhar_filme(carregar_token(), filme_id))

# ==========================================================================
# 12. INGESTÃO: TMDB -> SQLite (I/O: rede + banco)
#     Grava página a página: se a rede cair no meio, o que já foi gravado fica.
# ==========================================================================

POR_PAGINA = 20                # filmes por página do /discover/movie
LIMITE_PADRAO = 1000           # filmes buscados por `python main.py --ingerir`
ResumoIngestao = namedtuple("ResumoIngestao", ("buscados", "gravados", "descartados"))

# Quantas páginas são necessárias para `limite` filmes (mínimo 1).
paginas_para = lambda limite: max(1, -(-limite // POR_PAGINA))
# Ids válidos de uma página do discover (ignora entradas sem id utilizável).
_ids_da_pagina = lambda token, pagina: tuple(
    filme_id for filme_id in (
        item.get("id") for item in descobrir_filmes(token, pagina).get("results", ())
        if isinstance(item, dict))
    if isinstance(filme_id, int) and filme_id > 0)
# (ids encontrados, filmes convertidos) de uma página; `para_movie` rejeita incompletos.
_pagina = lambda token, pagina: (
    lambda ids: (ids, tuple(filter(None, map(para_movie,
                                             (detalhar_filme(token, filme_id) for filme_id in ids)))))
)(_ids_da_pagina(token, pagina))
# Gera (lazy) Movies válidos; cada página só é buscada quando a anterior acabou.
coletar_filmes = lambda token, paginas: (
    filme for pagina in range(1, paginas + 1) for filme in _pagina(token, pagina)[1])

# Acumulador da ingestão (nomes claros em vez de índices de tupla).
_Total = namedtuple("_Total", ("buscados", "convertidos", "gravados"))
# Soma as páginas até o TMDB parar de devolver ids (takewhile) e grava cada uma.
_gravar_paginas = lambda conn, token, paginas: (
    lambda total: ResumoIngestao(total.buscados, total.gravados,
                                 total.buscados - total.convertidos)
)(reduce(
    lambda total, pagina: _Total(total.buscados + len(pagina[0]),
                                 total.convertidos + len(pagina[1]),
                                 total.gravados + inserir_filmes(conn, pagina[1])),
    takewhile(lambda pagina: pagina[0], map(lambda numero: _pagina(token, numero),
                                            range(1, paginas + 1))),
    _Total(0, 0, 0)))
# Abre o banco, grava e FECHA a conexão mesmo se algo falhar (e re-levanta o erro).
_ingerir = lambda token, paginas, caminho_db: (
    lambda conn: _conexao_fechada(
        conn, _tentar(lambda: _depois(inicializar_schema(conn),
                                      _gravar_paginas(conn, token, paginas)), BaseException))
)(conectar(caminho_db))
# `close()` devolve None, então o `or` devolve o resultado depois de fechar.
_conexao_fechada = lambda conn, leitura: (
    conn.close() or (leitura[1] if leitura[0] else _lancar(leitura[1])))
# Cria o schema, coleta e grava; imprime o resumo e devolve quantos foram gravados.
ingerir = lambda paginas=25, caminho_db=DB_PADRAO: (
    lambda resumo: (
        print(f"{caminho_db}: {resumo.buscados} buscados, {resumo.gravados} gravados, "
              f"{resumo.descartados} descartados (sem id, título ou data de lançamento)."),
        resumo.gravados,
    )[-1]
)(_ingerir(carregar_token(), paginas, caminho_db))

# ==========================================================================
# 13. CLI / MENU (I/O: terminal) — Python comum de propósito.
#     O menu só orquestra o núcleo e imprime texto; nenhum cálculo mora aqui.
# ==========================================================================

TOP_N = 10
LIMITE_LISTAGEM = 20
SAIDAS = frozenset({"0", "sair", "s"})
COMANDO_INGESTAO = "python main.py --ingerir"


# ---- carregar a base -------------------------------------------------------

def carregar_filmes(caminho):
    """Lê o banco UMA vez e devolve os filmes válidos como tupla imutável."""
    if not Path(caminho).is_file():
        raise RuntimeError(f"banco não encontrado: {caminho}. "
                           f"Gere a base antes com: {COMANDO_INGESTAO}")
    conn = conectar(caminho)
    try:
        filmes = tuple(limpar(ler_filmes(conn)))
    except sqlite3.DatabaseError as erro:
        raise RuntimeError(f"{caminho} não é um banco válido de filmes ({erro}). "
                           f"Gere a base com: {COMANDO_INGESTAO}") from None
    finally:
        conn.close()
    if not filmes:
        raise RuntimeError(f"{caminho} não tem filmes com orçamento, faturamento, "
                           f"nota e ano válidos.")
    return filmes


# ---- leitura e validação das respostas (sempre (valor, erro)) --------------

def _ler_ano(texto):
    """('', vazio) -> (None, None) = critério não informado."""
    if not texto.strip():
        return None, None
    try:
        return int(texto.strip()), None
    except ValueError:
        return None, f"'{texto.strip()}' não é um ano válido (ex.: 1990)"


def _ler_nota(texto):
    """Aceita vírgula decimal e exige 0 <= nota <= 10 (NaN cai fora da faixa)."""
    if not texto.strip():
        return None, None
    try:
        nota = float(texto.strip().replace(",", "."))
    except ValueError:
        return None, f"'{texto.strip()}' não é um número (ex.: 7,5)"
    if 0 <= nota <= 10:
        return nota, None
    return None, f"a nota mínima deve estar entre 0 e 10 (recebi '{texto.strip()}')"


def _ler_numeros(texto):
    """'1, 3' / '1 3' / '1;3' -> (True, (1, 3)); vazio -> (True, ()); lixo -> (False, erro)."""
    if not texto.strip():
        return True, ()
    try:
        return True, tuple(int(numero) for numero in re.split(r"[,;\s]+", texto.strip()))
    except ValueError:
        return False, f"'{texto.strip()}' não é uma lista de números (ex.: 1,3)"


def _resolver_nomes(leitura, nomes):
    """(nomes escolhidos, erro) a partir da leitura; número fora da lista é erro.

    `dict.fromkeys` tira repetição mantendo a ordem pedida — e a ordem importa:
    a primeira estatística é a que ordena a tabela.
    """
    ok, numeros = leitura
    if not ok:
        return None, numeros
    if not numeros:
        return None, "escolha pelo menos um número"
    fora = tuple(numero for numero in numeros if not 1 <= numero <= len(nomes))
    if fora:
        return None, (f"número(s) fora da lista: {', '.join(map(str, fora))}; "
                      f"use de 1 a {len(nomes)}.")
    return tuple(map(lambda numero: nomes[numero - 1], dict.fromkeys(numeros))), None


def _resolver_limite(texto):
    """(limite, erro): vazio -> padrão; 0 -> todos os grupos; negativo -> erro."""
    if not texto.strip():
        return LIMITE_ANALISE, None
    try:
        limite = int(texto.strip())
    except ValueError:
        return None, f"'{texto.strip()}' não é um número inteiro (ex.: 20)"
    if limite < 0:
        return None, "o limite de grupos não pode ser negativo"
    return limite, None


def _erro_de_entrada(erro):
    return f"Entrada inválida: {erro.rstrip('.')}. Nada foi feito."


# ---- opções do menu (todas: (filmes, perguntar) -> texto) ------------------

def _listar_filtrados(filmes, criterios):
    selecionados = tuple(filtrar(make_filtro(**criterios), filmes))
    maiores = top_filmes(LIMITE_LISTAGEM, metrica("faturamento"), selecionados)
    return (f"{len(selecionados)} filme(s) encontrado(s); "
            f"exibindo os {len(maiores)} de maior faturamento.\n"
            f"{formatar_filmes(maiores)}")


def _filtrar_com(filmes, genero, ano_e, nota_e):
    erros = tuple(filter(None, (ano_e[1], nota_e[1])))
    if erros:
        return "Entrada inválida: " + "; ".join(erros) + ". Nada foi filtrado."
    criterios = dict(filter(
        lambda par: par[1] is not None and par[1] != "",
        (("genero", genero), ("a_partir_de", ano_e[0]), ("nota_min", nota_e[0]))))
    return _listar_filtrados(filmes, criterios)


def _acao_filtrar(filmes, perguntar):
    """Filtrar filmes por gênero, década/ano e nota mínima."""
    genero = perguntar("Gênero (Enter para qualquer um): ")
    ano_e = _ler_ano(perguntar("A partir da década/ano, ex.: 1990 (Enter para qualquer): "))
    nota_e = _ler_nota(perguntar("Nota mínima de 0 a 10, ex.: 7,5 (Enter para qualquer): "))
    return _filtrar_com(filmes, genero.strip(), ano_e, nota_e)


def _mediana(filmes, nome):
    return pipeline(filmes, tem_financeiro_valido, metrica(nome), mediana)


def _acao_indicadores(filmes):
    """Contagem, ROI médio, nota média, faturamento médio e as duas medianas."""
    return "\n".join((
        formatar_comparacao("Indicadores gerais", (("Todos os filmes", resumir(filmes)),)),
        f"Orçamento mediano:   {formatar_moeda(_mediana(filmes, 'orcamento') or 0)}",
        f"Faturamento mediano: {formatar_moeda(_mediana(filmes, 'faturamento') or 0)}",
    ))


def _acao_generos(filmes):
    """Compara gêneros, do maior ROI médio para o menor."""
    grupos = comparar_por_genero(filmes)
    return formatar_comparacao("Comparação por gênero (maior ROI primeiro)",
                               top_grupos(len(grupos), "roi", grupos))


def _acao_decadas(filmes):
    """Compara décadas."""
    return formatar_comparacao(
        "Comparação por década",
        map(lambda par: (f"{par[0]}s", par[1]), comparar_por_decada(filmes).items()))


def _acao_correlacao(filmes):
    """Correlações de Pearson, com o aviso de que não implicam causalidade."""
    return "\n\n".join((
        formatar_correlacao("Orçamento × faturamento", orcamento_vs_faturamento(filmes)),
        formatar_correlacao("Orçamento × nota", orcamento_vs_nota(filmes)),
    ))


def _top_filmes_por(nome, titulo, filmes):
    return f"{titulo}\n{formatar_filmes(top_filmes(TOP_N, metrica(nome), filmes))}"


def _top_grupos_por(nome_dimensao, indicador, titulo, rotulo, filmes):
    grupos = comparar_por(dimensao(nome_dimensao), filmes)
    return formatar_comparacao(
        titulo, map(lambda par: (rotulo(par[0]), par[1]), top_grupos(TOP_N, indicador, grupos)))


RANKINGS = MappingProxyType({
    "1": ("Filmes com maior faturamento",
          partial(_top_filmes_por, "faturamento", f"Top {TOP_N} filmes por faturamento")),
    "2": ("Filmes mais bem avaliados",
          partial(_top_filmes_por, "nota", f"Top {TOP_N} filmes por nota")),
    "3": ("Filmes com maior ROI",
          partial(_top_filmes_por, "roi", f"Top {TOP_N} filmes por ROI")),
    "4": ("Gêneros com maior ROI médio",
          partial(_top_grupos_por, "genero", "roi", "Gêneros por ROI médio", str)),
    "5": ("Décadas com maior nota média",
          partial(_top_grupos_por, "decada", "nota", "Décadas por nota média", "{}s".format)),
})
_OPCOES_RANKING = "\n".join(map(lambda par: f"  {par[0]} - {par[1][0]}", RANKINGS.items()))


def _acao_rankings(filmes, perguntar):
    """Rankings de filmes e de grupos por faturamento, nota ou ROI."""
    escolha = perguntar(f"Rankings disponíveis:\n{_OPCOES_RANKING}\nQual? ").strip()
    if escolha not in RANKINGS:
        return f"Ranking '{escolha}' não existe. Escolha de 1 a {len(RANKINGS)}."
    return RANKINGS[escolha][1](filmes)


# ---- opção 7: montar a análise (atributos × estatísticas) ------------------

LIMITE_ANALISE = 20            # grupos mostrados quando o usuário só dá Enter


def _opcoes_numeradas(nomes, rotulos):
    """Catálogo numerado a partir de NOMES_DIMENSOES / NOMES_METRICAS."""
    return "\n".join(f"  {numero:>2} - {rotulos[nome]}"
                     for numero, nome in enumerate(nomes, start=1))


_OPCOES_ATRIBUTOS = _opcoes_numeradas(NOMES_DIMENSOES, ROTULOS_DIMENSOES)
_OPCOES_ESTATISTICAS = _opcoes_numeradas(NOMES_METRICAS, ROTULOS_METRICAS)


def _mostrar_analise(filmes, atributos, estatisticas, limite):
    """Agrupa pelos atributos, resume pelas estatísticas e ordena pela primeira."""
    grupos = analisar(atributos, estatisticas, filmes)
    mostrados = top_grupos(len(grupos) if limite == 0 else limite, estatisticas[0], grupos)
    return formatar_analise(
        "Análise: " + " × ".join(map(ROTULOS_DIMENSOES.__getitem__, atributos)),
        f"Ordenado por {ROTULOS_METRICAS[estatisticas[0]]} (maior primeiro) · "
        f"mostrando {len(mostrados)} de {len(grupos)} grupo(s)",
        estatisticas, mostrados)


def _acao_analise(filmes, perguntar):
    """Cruzamento livre: atributos × estatísticas (o objetivo do projeto)."""
    atributos, erro_atributos = _resolver_nomes(
        _ler_numeros(perguntar(
            "Atributos para agrupar (um ou mais; dois ou mais cruzam os dados):\n"
            f"{_OPCOES_ATRIBUTOS}\nQuais? (números separados por vírgula, ex.: 1,3) ")),
        NOMES_DIMENSOES)
    estatisticas, erro_estatisticas = _resolver_nomes(
        _ler_numeros(perguntar(
            "Estatísticas para calcular (uma ou mais; a primeira ordena a tabela):\n"
            f"{_OPCOES_ESTATISTICAS}\nQuais? (ex.: 4,5) ")),
        NOMES_METRICAS)
    limite, erro_limite = _resolver_limite(
        perguntar(f"Quantos grupos mostrar? (Enter = {LIMITE_ANALISE}, 0 = todos) "))
    erros = [erro for erro in (erro_atributos, erro_estatisticas, erro_limite) if erro]
    if erros:
        return _erro_de_entrada("; ".join(erros))
    return _mostrar_analise(filmes, atributos, estatisticas, limite)


# ---- registro das opções e laço do menu -----------------------------------

def _sem_perguntas(funcao):
    """Adapta uma ação que não faz perguntas à assinatura do menu."""
    return lambda filmes, _perguntar: funcao(filmes)


ACOES = MappingProxyType({
    "1": ("Filtrar filmes", _acao_filtrar),
    "2": ("Indicadores gerais", _sem_perguntas(_acao_indicadores)),
    "3": ("Comparar gêneros", _sem_perguntas(_acao_generos)),
    "4": ("Comparar décadas", _sem_perguntas(_acao_decadas)),
    "5": ("Correlação orçamento × faturamento", _sem_perguntas(_acao_correlacao)),
    "6": ("Rankings", _acao_rankings),
    "7": ("Montar análise (atributos × estatísticas)", _acao_analise),
})


def pipeline(filmes, selecao, transformacao, agregacao):
    """Seleciona, transforma (descartando None) e agrega — só composição."""
    return agregacao(filter(lambda valor: valor is not None,
                            map(transformacao, filter(selecao, filmes))))


def texto_menu():
    linhas = ["", "MENU"]
    linhas += [f"  {numero} - {descricao}" for numero, (descricao, _) in ACOES.items()]
    linhas += ["  0 - Sair", "Escolha uma opção: "]
    return "\n".join(linhas)


def executar(opcao, filmes, perguntar):
    """Roda a opção e devolve o texto; opção inexistente vira mensagem, não exceção."""
    escolha = opcao.strip()
    if escolha not in ACOES:
        return f"Opção '{escolha}' não existe. Digite um número de 0 a {len(ACOES)}."
    return ACOES[escolha][1](filmes, perguntar)


def _ler(prompt):
    """`input` que trata Ctrl-D (fim da entrada) como 'sair'."""
    try:
        return input(prompt)
    except EOFError:
        return "0"


def _laco(filmes, ler, escrever):
    """Menu em laço: pede a escolha, executa e mostra o texto, até uma saída."""
    while True:
        escolha = ler(texto_menu())
        if escolha.strip().lower() in SAIDAS:
            return
        escrever(executar(escolha, filmes, ler))


# ---- linha de comando ------------------------------------------------------

def _analisador():
    analisador = argparse.ArgumentParser(
        description="Análise de desempenho cinematográfico (menu interativo).")
    analisador.add_argument("--banco", default=str(DB_PADRAO),
                            help=f"caminho do banco (padrão: {DB_PADRAO})")
    analisador.add_argument("--ingerir", action="store_true",
                            help="baixa filmes do TMDB e grava no banco (precisa de TMDB_TOKEN)")
    analisador.add_argument("--limite", type=int, default=LIMITE_PADRAO,
                            help=f"com --ingerir: quantos filmes buscar (padrão: {LIMITE_PADRAO})")
    return analisador


def _menu(argumentos, ler, escrever):
    filmes = carregar_filmes(argumentos.banco)
    escrever(f"Base carregada: {len(filmes)} filmes com dados válidos.")
    _laco(filmes, ler, escrever)
    escrever("Até logo!")
    return 0


def _comando(argumentos, ler, escrever):
    if argumentos.ingerir:
        ingerir(paginas_para(argumentos.limite), argumentos.banco)
        return 0
    return _menu(argumentos, ler, escrever)


def main(argv=None, *, ler=_ler, escrever=exibir):
    """Interpreta os argumentos, executa e devolve o código de saída (0 = sucesso)."""
    argumentos = _analisador().parse_args(argv)
    try:
        return _comando(argumentos, ler, escrever)
    except KeyboardInterrupt:
        escrever("ingestão interrompida; o que já foi gravado está no banco."
                 if argumentos.ingerir else "\nEncerrado.")
        return 130
    except RuntimeError as erro:
        escrever(f"erro: {erro}")
        return 1


if __name__ == "__main__":
    # `reconfigure` garante os acentos no terminal do Windows.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
