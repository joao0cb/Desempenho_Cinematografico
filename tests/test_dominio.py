import pytest

from dominio import CAMPOS_LISTA, CAMPOS_NUMERICOS, CAMPOS_TEXTO, Movie


def test_movie_e_imutavel():
    filme = Movie(1, "Titanic", 1997)
    with pytest.raises(AttributeError):
        filme.titulo = "Outro"  # type: ignore[misc]


def test_so_id_titulo_e_ano_sao_obrigatorios_e_o_resto_e_desconhecido():
    filme = Movie(1, "Titanic", 1997)
    assert filme.orcamento == 0 and filme.nota == 0.0
    assert filme.diretor == "" and filme.generos == () and filme.elenco == ()


def test_campos_na_ordem_do_schema():
    assert Movie._fields[:3] == ("id", "titulo", "ano")
    assert len(Movie._fields) == 17


def test_classificacao_de_campos_cobre_todos_menos_id():
    classificados = CAMPOS_NUMERICOS + CAMPOS_TEXTO + CAMPOS_LISTA
    assert len(classificados) == len(set(classificados))
    assert set(classificados) == set(Movie._fields) - {"id"}