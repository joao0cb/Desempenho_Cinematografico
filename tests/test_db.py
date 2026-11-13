import re

from dados import amostra, limpar
from db import CONSULTA_FILMES, conectar, inicializar_schema, inserir_filmes, ler_filmes, ler_linhas
from dominio import Movie

COMPLETO = Movie(
    id=1, titulo="Titanic", ano=1997, data_lancamento="1997-12-19",
    generos=("Drama", "Romance"), orcamento=200_000_000, faturamento=2_200_000_000,
    nota=7.9, popularidade=80.1, duracao=194, idioma_original="en",
    classificacao="PG-13", diretor="James Cameron", elenco=("Leonardo DiCaprio", "Kate Winslet"),
    paises=("US",), empresas=("Paramount Pictures", "20th Century Fox"), colecao="",
)
MINIMO = Movie(2, "Filme sem dados", 2005)
FILMES = [COMPLETO, MINIMO]


def _banco(filmes):
    conn = conectar(":memory:")
    inicializar_schema(conn)
    inserir_filmes(conn, filmes)
    return conn


def test_colunas_do_schema_seguem_a_ordem_de_movie():
    conn = conectar(":memory:")
    inicializar_schema(conn)
    colunas = tuple(linha[1] for linha in conn.execute("PRAGMA table_info(filmes)"))
    assert colunas == Movie._fields


def test_roundtrip_preserva_todos_os_campos_inclusive_listas_e_acentos():
    conn = _banco(FILMES)
    assert list(ler_filmes(conn)) == FILMES


def test_inserir_devolve_quantidade():
    conn = conectar(":memory:")
    inicializar_schema(conn)
    assert inserir_filmes(conn, FILMES) == 2


def test_schema_idempotente_e_upsert_por_id():
    conn = _banco(FILMES)
    inicializar_schema(conn)
    inserir_filmes(conn, [COMPLETO._replace(titulo="Titanic (reedição)")])
    assert [f.titulo for f in ler_filmes(conn)] == ["Titanic (reedição)", "Filme sem dados"]


def test_consulta_nao_tem_agregacao():
    assert not re.search(
        r"\b(GROUP\s+BY|HAVING|AVG|SUM|COUNT|MIN|MAX|DISTINCT)\b", CONSULTA_FILMES, re.IGNORECASE
    )


def test_leitura_e_streaming_nao_lista():
    conn = _banco(FILMES)
    for fluxo in (ler_linhas(conn), ler_filmes(conn)):
        assert iter(fluxo) is fluxo  # iterador, não lista
    assert next(ler_filmes(conn)) == COMPLETO


def test_banco_para_limpar_para_amostra():
    ruins = [
        COMPLETO._replace(id=3, orcamento=0),
        COMPLETO._replace(id=4, nota=0.0),
        COMPLETO._replace(id=5, ano=0),
    ]
    conn = _banco(FILMES + ruins)
    assert list(limpar(ler_filmes(conn))) == [COMPLETO]
    assert [f.id for f in amostra(ler_filmes(conn), 2)] == [1, 2]