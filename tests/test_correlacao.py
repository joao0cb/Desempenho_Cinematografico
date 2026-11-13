import pytest

from correlacao import (
    correlacionar,
    orcamento_vs_faturamento,
    orcamento_vs_nota,
    pearson,
)
from dominio import Movie

# Movie tem 17 campos: gêneros vêm em tupla e o resto tem valor padrão.
BASE = Movie(id=1, titulo="X", ano=2015, generos=("Drama",),
             orcamento=10, faturamento=30, nota=7.0)


def filme(**campos) -> Movie:
    return BASE._replace(**campos)


# ---------- pearson ----------

def test_correlacao_perfeita_positiva():
    assert pearson((1, 2, 3), (2, 4, 6)) == pytest.approx(1.0)


def test_correlacao_perfeita_negativa():
    assert pearson((1, 2, 3), (6, 4, 2)) == pytest.approx(-1.0)


def test_correlacao_zero():
    assert pearson((-1, 0, 1), (1, 0, 1)) == pytest.approx(0.0)


def test_serie_constante_devolve_none():
    assert pearson((5, 5, 5), (1, 2, 3)) is None
    assert pearson((1, 2, 3), (5, 5, 5)) is None


def test_menos_de_dois_pares_devolve_none():
    assert pearson((1,), (2,)) is None
    assert pearson((), ()) is None


def test_pearson_aceita_listas_e_tuplas():
    assert pearson([1, 2, 3], [2, 4, 6]) == pytest.approx(1.0)


# ---------- correlacionar ----------

def test_correlacionar_usa_os_seletores():
    filmes = (filme(id=1, ano=2000, nota=1.0),
              filme(id=2, ano=2010, nota=2.0),
              filme(id=3, ano=2020, nota=3.0))
    assert correlacionar(lambda f: f.ano, lambda f: f.nota, filmes) == pytest.approx(1.0)


def test_correlacionar_descarta_filmes_com_seletor_none():
    filmes = (filme(id=1, orcamento=1, faturamento=2),
              filme(id=2, orcamento=2, faturamento=4),
              filme(id=3, orcamento=3, faturamento=6),
              filme(id=4, orcamento=100, faturamento=1))   # será descartado

    def seletor_orcamento(filme: Movie) -> float | None:
        return filme.orcamento if filme.id != 4 else None

    assert correlacionar(seletor_orcamento, lambda f: f.faturamento, filmes) == pytest.approx(1.0)


def test_correlacionar_aceita_gerador():
    filmes = (filme(id=i, orcamento=i, faturamento=2 * i) for i in (1, 2, 3))
    assert correlacionar(lambda f: f.orcamento, lambda f: f.faturamento, filmes) == pytest.approx(1.0)


# ---------- orcamento_vs_faturamento ----------

def test_orcamento_vs_faturamento_correlacao_perfeita():
    filmes = tuple(filme(id=i, orcamento=i, faturamento=3 * i) for i in (1, 2, 3))
    assert orcamento_vs_faturamento(filmes) == pytest.approx(1.0)


def test_orcamento_vs_faturamento_ignora_zero_como_desconhecido():
    validos = tuple(filme(id=i, orcamento=i, faturamento=3 * i) for i in (1, 2, 3))
    sem_orcamento = filme(id=9, orcamento=0, faturamento=999)
    sem_faturamento = filme(id=10, orcamento=50, faturamento=0)
    assert orcamento_vs_faturamento(validos + (sem_orcamento, sem_faturamento)) == pytest.approx(1.0)


def test_base_vazia_devolve_none():
    assert orcamento_vs_faturamento(()) is None
    assert orcamento_vs_nota(()) is None


def test_todos_sem_dados_validos_devolve_none():
    filmes = (filme(id=1, orcamento=0), filme(id=2, orcamento=0))
    assert orcamento_vs_faturamento(filmes) is None


def test_um_unico_filme_devolve_none():
    assert orcamento_vs_faturamento((filme(),)) is None


# ---------- orcamento_vs_nota ----------

def test_orcamento_vs_nota_negativa():
    filmes = (filme(id=1, orcamento=1, nota=9.0),
              filme(id=2, orcamento=2, nota=6.0),
              filme(id=3, orcamento=3, nota=3.0))
    assert orcamento_vs_nota(filmes) == pytest.approx(-1.0)


def test_orcamento_vs_nota_ignora_nota_zero():
    validos = (filme(id=1, orcamento=1, nota=9.0),
               filme(id=2, orcamento=2, nota=6.0),
               filme(id=3, orcamento=3, nota=3.0))
    sem_nota = filme(id=9, orcamento=500, nota=0.0)
    assert orcamento_vs_nota(validos + (sem_nota,)) == pytest.approx(-1.0)


# ---------- pureza ----------

def test_entrada_nao_e_alterada():
    filmes = (filme(id=1), filme(id=2, orcamento=20, faturamento=70))
    copia = tuple(filmes)
    orcamento_vs_faturamento(filmes)
    orcamento_vs_nota(filmes)
    assert filmes == copia