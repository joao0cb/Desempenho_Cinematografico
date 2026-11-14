"""Preparação dos dados: conversão, validação e limpeza (funções puras).

Este módulo NÃO faz I/O: ele recebe iteráveis (linhas já lidas do banco, filmes)
e devolve iteradores preguiçosos. A leitura do SQLite em streaming fica em
`db.py` (borda de I/O), que usa as funções daqui.

Convenção de ausência (mesma do TMDB e do schema): número 0 = desconhecido,
texto '' = desconhecido, lista () = desconhecido. `linha_para_movie` converte
valores ausentes ou ilegíveis nesses sentinelas; `limpar`/`limpar_com` descartam
quem não tem os campos exigidos pela análise.
"""
from __future__ import annotations

import json
import math
from datetime import date
from itertools import islice
from typing import Any, Callable, Iterable, Iterator, Mapping, Sequence

from dominio import CAMPOS_LISTA, Movie, Predicado

ANO_MIN: int = 1888
"""Primeiro filme da história (Roundhay Garden Scene); antes disso o ano é inválido."""

ANO_MAX: int = 2100
"""Teto de sanidade para o ano de lançamento."""

NOTA_MAX: float = 10.0


# --------------------------------------------------------------------------
# Conversores de valores soltos (tolerantes a nulos e tipos inesperados)
# --------------------------------------------------------------------------

def _numero(valor: object) -> float | None:
    """Converte para float; None se ausente, booleano, ilegível, NaN ou infinito."""
    if valor is None or isinstance(valor, bool):
        return None
    try:
        numero = float(valor)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return numero if math.isfinite(numero) else None


def _inteiro(valor: object) -> int:
    """Converte para int; 0 se ausente ou ilegível (ex.: '63000000.0' -> 63000000)."""
    if isinstance(valor, int) and not isinstance(valor, bool):
        return valor
    numero = _numero(valor)
    return 0 if numero is None else int(numero)


def _decimal(valor: object) -> float:
    """Converte para float; 0.0 se ausente ou ilegível."""
    numero = _numero(valor)
    return 0.0 if numero is None else numero


def _texto(valor: object) -> str:
    """Converte para str sem espaços nas pontas; '' se ausente."""
    return "" if valor is None else str(valor).strip()


def _data(valor: object) -> str:
    """Normaliza para 'AAAA-MM-DD'; '' se ausente ou inválida."""
    try:
        return date.fromisoformat(_texto(valor)[:10]).isoformat()
    except ValueError:
        return ""


def _lista(valor: object) -> tuple[str, ...]:
    """Converte lista JSON (texto) ou sequência em tupla de textos, sem vazios e sem repetição.

    Texto que não é uma lista JSON válida vira () (desconhecido).
    """
    if isinstance(valor, str):
        try:
            itens = json.loads(valor)
        except ValueError:
            return ()
    else:
        itens = valor
    if not isinstance(itens, (list, tuple)):
        return ()
    return tuple(dict.fromkeys(filter(None, map(_texto, itens))))


_CONVERSOR_POR_CAMPO: Mapping[str, Callable[[object], Any]] = {
    "id": _inteiro,
    "titulo": _texto,
    "ano": _inteiro,
    "data_lancamento": _data,
    "generos": _lista,
    "orcamento": _inteiro,
    "faturamento": _inteiro,
    "nota": _decimal,
    "popularidade": _decimal,
    "duracao": _inteiro,
    "idioma_original": _texto,
    "classificacao": _texto,
    "diretor": _texto,
    "elenco": _lista,
    "paises": _lista,
    "empresas": _lista,
    "colecao": _texto,
}

# Na ordem dos campos de Movie; um campo novo sem conversor falha já no import.
_CONVERSORES: tuple[Callable[[object], Any], ...] = tuple(
    _CONVERSOR_POR_CAMPO[campo] for campo in Movie._fields
)

# Campos que viram texto JSON no banco (fonte única: dominio.CAMPOS_LISTA).
_CAMPOS_LISTA: frozenset[str] = frozenset(CAMPOS_LISTA)


# --------------------------------------------------------------------------
# Conversão linha <-> Movie
# --------------------------------------------------------------------------

def linha_para_movie(linha: Sequence[object] | None) -> Movie | None:
    """Converte uma linha do banco (colunas na ordem de `Movie`) em Movie.

    Tolera nulos, números vindos como texto e listas JSON malformadas. Devolve
    None apenas quando a linha não é utilizável (não é uma sequência com todas as
    colunas ou o `id` é ilegível). Campos ausentes viram sentinelas (0, '' ou ()),
    que `limpar` descarta depois conforme a análise.
    """
    try:
        valores = tuple(linha)  # type: ignore[arg-type]
    except TypeError:
        return None
    if len(valores) != len(_CONVERSORES) or _numero(valores[0]) is None:
        return None
    return Movie(*map(lambda converter, valor: converter(valor), _CONVERSORES, valores))


def filme_para_linha(filme: Movie) -> tuple[object, ...]:
    """Converte um Movie em linha para o banco (campos-lista viram texto JSON).

    O que é lista vem de `dominio.CAMPOS_LISTA`, não do tipo do valor em tempo de
    execução: assim uma lista comum (em vez de tupla) também é gravada como JSON,
    em vez de estourar no driver do SQLite.
    """
    return tuple(
        json.dumps(list(valor), ensure_ascii=False) if campo in _CAMPOS_LISTA else valor
        for campo, valor in zip(Movie._fields, filme)
    )


def para_filmes(linhas: Iterable[Sequence[object] | None]) -> Iterator[Movie]:
    """Converte linhas em Movies sob demanda, pulando as linhas inutilizáveis."""
    return (
        filme
        for filme in map(linha_para_movie, linhas)
        if filme is not None
    )


def _objeto(valor: object) -> Mapping[str, Any]:
    """Objeto JSON da resposta; {} quando ausente ou de outro tipo."""
    return valor if isinstance(valor, Mapping) else {}


def _itens(valor: object) -> tuple[Mapping[str, Any], ...]:
    """Lista de objetos JSON da resposta, descartando o que não for objeto."""
    if not isinstance(valor, (list, tuple)):
        return ()
    return tuple(item for item in valor if isinstance(item, Mapping))


def _nota(valor: object) -> float:
    """Nota dentro de 0..NOTA_MAX (o schema tem CHECK); fora da faixa, corta."""
    return min(max(_decimal(valor), 0.0), NOTA_MAX)


def _primeiro_diretor(creditos: Mapping[str, Any]) -> str:
    """Nome do primeiro crédito com job == 'Director'; '' se não houver."""
    return next(
        (
            _texto(pessoa.get("name"))
            for pessoa in _itens(creditos.get("crew"))
            if pessoa.get("job") == "Director"
        ),
        "",
    )


def _classificacao(release_dates: object) -> str:
    """Certificação indicativa dos EUA (primeira não vazia); '' se não houver."""
    for pais in _itens(_objeto(release_dates).get("results")):
        if pais.get("iso_3166_1") != "US":
            continue
        for data in _itens(pais.get("release_dates")):
            certificacao = _texto(data.get("certification"))
            if certificacao:
                return certificacao
    return ""


def para_movie(detalhe: Mapping[str, Any]) -> Movie | None:
    """Converte o JSON de /movie/{id} (com credits e release_dates) em Movie.

    Usada pela ingestão. Requisição: /movie/{id}?append_to_response=credits,release_dates.
    Mapeamento dos campos:

      titulo <- title                   data_lancamento/ano <- release_date
      generos <- genres[].name          orcamento/faturamento <- budget / revenue
      nota/popularidade <- vote_average / popularity
      duracao <- runtime                idioma_original <- original_language
      classificacao <- release_dates (certificação dos EUA)
      diretor <- credits.crew (primeiro com job == 'Director')
      elenco <- credits.cast (os 5 primeiros)
      paises <- production_countries[].iso_3166_1   empresas <- production_companies[].name
      colecao <- belongs_to_collection.name

    Devolve None se faltar `id`, título ou data/ano de lançamento. Campos opcionais
    ausentes viram o valor "desconhecido" (0, '' ou ()).
    """
    if not isinstance(detalhe, Mapping):
        return None

    filme_id = _inteiro(detalhe.get("id"))
    titulo = _texto(detalhe.get("title"))
    data_lancamento = _data(detalhe.get("release_date"))
    if filme_id <= 0 or not titulo or not data_lancamento:
        return None

    creditos = _objeto(detalhe.get("credits"))
    return Movie(
        id=filme_id,
        titulo=titulo,
        ano=_inteiro(data_lancamento[:4]),
        data_lancamento=data_lancamento,
        generos=_lista([item.get("name") for item in _itens(detalhe.get("genres"))]),
        orcamento=_inteiro(detalhe.get("budget")),
        faturamento=_inteiro(detalhe.get("revenue")),
        nota=_nota(detalhe.get("vote_average")),
        popularidade=_decimal(detalhe.get("popularity")),
        duracao=_inteiro(detalhe.get("runtime")),
        idioma_original=_texto(detalhe.get("original_language")),
        classificacao=_classificacao(detalhe.get("release_dates")),
        diretor=_primeiro_diretor(creditos),
        elenco=_lista([item.get("name") for item in _itens(creditos.get("cast"))[:5]]),
        paises=_lista([item.get("iso_3166_1") for item in _itens(detalhe.get("production_countries"))]),
        empresas=_lista([item.get("name") for item in _itens(detalhe.get("production_companies"))]),
        colecao=_texto(_objeto(detalhe.get("belongs_to_collection")).get("name")),
    )


# --------------------------------------------------------------------------
# Validação
# --------------------------------------------------------------------------

def _presente(valor: object) -> bool:
    """Número: > 0. Texto ou lista: não vazio."""
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        return valor > 0
    return bool(valor)


def tem_valor(campo: str) -> Predicado:
    """Predicado: o filme tem o campo preenchido (qualquer campo de Movie).

    Ex.: `tem_valor('diretor')`, `tem_valor('duracao')`, `tem_valor('elenco')`.
    Levanta ValueError se o campo não existir.
    """
    if campo not in Movie._fields:
        raise ValueError(f"campo desconhecido: {campo!r}")
    return lambda filme: _presente(getattr(filme, campo))


def tem_orcamento_valido(filme: Movie) -> bool:
    """True se orcamento > 0 (0 é o 'não sei' do TMDB; requisito para o ROI)."""
    return filme.orcamento > 0


def tem_faturamento_valido(filme: Movie) -> bool:
    """True se faturamento > 0."""
    return filme.faturamento > 0


def tem_financeiro_valido(filme: Movie) -> bool:
    """True se orçamento e faturamento são ambos > 0."""
    return tem_orcamento_valido(filme) and tem_faturamento_valido(filme)


def tem_nota_valida(filme: Movie) -> bool:
    """True se 0 < nota <= 10 (nota 0.0 significa sem avaliações)."""
    return 0.0 < filme.nota <= NOTA_MAX


def tem_ano_valido(filme: Movie) -> bool:
    """True se ANO_MIN <= ano <= ANO_MAX."""
    return ANO_MIN <= filme.ano <= ANO_MAX


REQUISITOS_PADRAO: tuple[Predicado, ...] = (
    tem_orcamento_valido,
    tem_faturamento_valido,
    tem_nota_valida,
    tem_ano_valido,
)
"""Exigências de `limpar`: orçamento, faturamento, nota e ano válidos."""


def eh_valido(filme: Movie) -> bool:
    """True se o filme cumpre todos os REQUISITOS_PADRAO."""
    return all(requisito(filme) for requisito in REQUISITOS_PADRAO)


# --------------------------------------------------------------------------
# Limpeza e amostragem (preguiçosas)
# --------------------------------------------------------------------------

def limpar_com(exigencias: Iterable[Predicado], filmes: Iterable[Movie]) -> Iterator[Movie]:
    """Mantém (lazy) só os filmes que cumprem TODAS as exigências dadas.

    Permite que cada análise exija só os campos de que precisa, aproveitando mais
    filmes. Ex.: nota x diretor -> `limpar_com([tem_nota_valida, tem_valor('diretor')], filmes)`.
    """
    exigencias = tuple(exigencias)
    return filter(lambda filme: all(exigencia(filme) for exigencia in exigencias), filmes)


def limpar(filmes: Iterable[Movie]) -> Iterator[Movie]:
    """Descarta (lazy) filmes com orçamento/faturamento <= 0, nota ausente ou ano inválido."""
    return limpar_com(REQUISITOS_PADRAO, filmes)


def com_financeiro_valido(filmes: Iterable[Movie]) -> Iterator[Movie]:
    """Mantém (lazy) só os filmes com orçamento e faturamento válidos."""
    return filter(tem_financeiro_valido, filmes)


def com_nota_valida(filmes: Iterable[Movie]) -> Iterator[Movie]:
    """Mantém (lazy) só os filmes com nota válida."""
    return filter(tem_nota_valida, filmes)


def amostra(filmes: Iterable[Movie], n: int, inicio: int = 0) -> Iterator[Movie]:
    """Os `n` filmes a partir da posição `inicio`, sem materializar o resto (islice).

    Útil no desenvolvimento: `amostra(limpar(ler_filmes(conn)), 20)`.
    """
    return islice(filmes, inicio, inicio + n)