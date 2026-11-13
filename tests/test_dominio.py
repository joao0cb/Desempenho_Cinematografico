import pytest

from dominio import Movie


def test_movie_e_imutavel():
    filme = Movie(1, "Titanic", 1997, "Drama", 200_000_000, 2_200_000_000, 7.9)
    with pytest.raises(AttributeError):
        filme.titulo = "Outro"  # type: ignore[misc]


def test_movie_campos_na_ordem_do_schema():
    assert Movie._fields == (
        "id", "titulo", "ano", "genero", "orcamento", "faturamento", "nota",
    )
