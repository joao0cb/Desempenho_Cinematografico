"""Testes das métricas e dimensões puras (issue #3)."""
import pytest

from dominio import Movie
from metricas import (
    FAIXA_DURACAO_FINAL,
    FAIXA_NOTA_FINAL,
    FAIXA_ORCAMENTO_FINAL,
    NOMES_DIMENSOES,
    NOMES_METRICAS,
    decada,
    dimensao,
    lucro,
    media,
    mediana,
    mes,
    metrica,
    roi,
    soma,
    trimestre,
)

FILME = Movie(
    id=1, titulo="Matrix", ano=1999, data_lancamento="1999-03-31",
    generos=("Ação", "Ficção científica"), orcamento=63_000_000,
    faturamento=463_000_000, nota=8.2, popularidade=60.5, duracao=136,
    idioma_original="en", classificacao="R", diretor="Lana Wachowski",
    elenco=("Keanu Reeves", "Laurence Fishburne"), paises=("US",),
    empresas=("Warner Bros.",), colecao="Matrix",
)


def filme(**campos) -> Movie:
    return FILME._replace(**campos)


# ------------------------------------------------------------------ métricas
def test_decada_arredonda_para_baixo():
    assert decada(filme(ano=1994)) == 1990
    assert decada(filme(ano=2000)) == 2000
    assert decada(filme(ano=0)) == 0


def test_mes_e_trimestre_a_partir_da_data():
    assert mes(FILME) == 3
    assert trimestre(FILME) == 1
    assert mes(filme(data_lancamento="1999-11-05")) == 11
    assert trimestre(filme(data_lancamento="1999-11-05")) == 4


@pytest.mark.parametrize("data", ["", "1999", "1999-13-01", "1999-00-10", "abc"])
def test_mes_e_trimestre_sem_data_valida(data):
    assert mes(filme(data_lancamento=data)) is None
    assert trimestre(filme(data_lancamento=data)) is None


def test_lucro_pode_ser_negativo():
    assert lucro(FILME) == 400_000_000
    assert lucro(filme(faturamento=10, orcamento=100)) == -90


def test_roi():
    assert roi(filme(orcamento=100, faturamento=300)) == 2.0
    assert roi(filme(orcamento=100, faturamento=50)) == -0.5


@pytest.mark.parametrize("orcamento", [0, -1])
def test_roi_sem_orcamento_valido_e_none(orcamento):
    assert roi(filme(orcamento=orcamento)) is None


def test_soma():
    assert soma([]) == 0.0
    assert soma([1, 2, 3.5]) == 6.5
    assert soma(iter([1, 1])) == 2.0


def test_media():
    assert media([]) is None
    assert media([2, 4, 6]) == 4.0
    assert media(iter([1])) == 1.0


def test_mediana():
    assert mediana([]) is None
    assert mediana([3]) == 3.0
    assert mediana([1, 2, 3]) == 2.0
    assert mediana([1, 2, 3, 4]) == 2.5


def test_mediana_nao_altera_a_entrada():
    entrada = [3, 1, 2]
    mediana(entrada)
    assert entrada == [3, 1, 2]


# ---------------------------------------------------------------- catálogo
def test_metrica_devolve_o_seletor_da_funcao():
    assert metrica("roi") is roi
    assert metrica("lucro")(FILME) == 400_000_000.0
    assert metrica("nota")(FILME) == 8.2


@pytest.mark.parametrize("nome", NOMES_METRICAS)
def test_toda_metrica_catalogada_funciona(nome):
    assert isinstance(metrica(nome)(FILME), float)


@pytest.mark.parametrize("campo", ["orcamento", "faturamento", "nota", "duracao", "ano"])
def test_metrica_trata_zero_como_desconhecido(campo):
    assert metrica(campo)(filme(**{campo: 0})) is None


def test_metrica_desconhecida_levanta_value_error():
    with pytest.raises(ValueError):
        metrica("bilheteria")


# --------------------------------------------------------------- dimensões
def test_dimensoes_multivaloradas_entram_em_varios_grupos():
    assert dimensao("genero")(FILME) == ("Ação", "Ficção científica")
    assert dimensao("ator")(FILME) == ("Keanu Reeves", "Laurence Fishburne")
    assert dimensao("pais")(FILME) == ("US",)
    assert dimensao("empresa")(FILME) == ("Warner Bros.",)


def test_dimensoes_de_valor_unico():
    assert dimensao("decada")(FILME) == (1990,)
    assert dimensao("ano")(FILME) == (1999,)
    assert dimensao("diretor")(FILME) == ("Lana Wachowski",)
    assert dimensao("colecao")(FILME) == ("Matrix",)
    assert dimensao("em_franquia")(FILME) == ("em franquia",)
    assert dimensao("em_franquia")(filme(colecao="")) == ("fora de franquia",)


def test_campo_desconhecido_deixa_o_filme_fora_do_agrupamento():
    assert dimensao("diretor")(filme(diretor="")) == ()
    assert dimensao("genero")(filme(generos=())) == ()
    assert dimensao("decada")(filme(ano=0)) == ()


def test_faixas():
    assert dimensao("faixa_orcamento")(FILME) == ("US$ 50-100 mi",)
    assert dimensao("faixa_orcamento")(filme(orcamento=500_000_000)) == (FAIXA_ORCAMENTO_FINAL,)
    assert dimensao("faixa_nota")(FILME) == ("8-10",)
    assert dimensao("faixa_nota")(filme(nota=9.9)) == (FAIXA_NOTA_FINAL,)
    assert dimensao("faixa_duracao")(FILME) == ("120-150 min",)
    assert dimensao("faixa_duracao")(filme(duracao=200)) == (FAIXA_DURACAO_FINAL,)
    assert dimensao("faixa_duracao")(filme(duracao=0)) == ()


@pytest.mark.parametrize("nome", NOMES_DIMENSOES)
def test_toda_dimensao_catalogada_funciona(nome):
    chaves = dimensao(nome)(FILME)
    assert isinstance(chaves, tuple) and chaves


def test_dimensao_desconhecida_levanta_value_error():
    with pytest.raises(ValueError):
        dimensao("bilheteria")


def test_dimensoes_e_metricas_sao_funcoes_puras():
    chamadas = [dimensao(nome)(FILME) for nome in NOMES_DIMENSOES]
    assert chamadas == [dimensao(nome)(FILME) for nome in NOMES_DIMENSOES]
    assert FILME.generos == ("Ação", "Ficção científica")
