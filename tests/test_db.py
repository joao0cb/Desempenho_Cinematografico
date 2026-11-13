from db import conectar, inicializar_schema, inserir_filmes, ler_filmes
from dominio import Movie

FILMES = [
    Movie(1, "A", 1999, "Ação", 100, 300, 7.5),
    Movie(2, "B", 2005, "Comédia", 0, 50, 6.0),
]


def test_roundtrip_preserva_movies():
    conn = conectar(":memory:")
    inicializar_schema(conn)
    assert inserir_filmes(conn, FILMES) == 2
    assert list(ler_filmes(conn)) == FILMES


def test_schema_idempotente_e_upsert_por_id():
    conn = conectar(":memory:")
    inicializar_schema(conn)
    inicializar_schema(conn)
    inserir_filmes(conn, FILMES)
    inserir_filmes(conn, [Movie(1, "A2", 1999, "Ação", 100, 300, 7.5)])
    assert [f.titulo for f in ler_filmes(conn)] == ["A2", "B"]
