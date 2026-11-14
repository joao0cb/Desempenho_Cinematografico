"""Testes de agrupamento e comparação de grupos (issue #8)."""
import pytest

from analises import (
    INDICADORES_PADRAO,
    agrupar_por,
    comparar_por,
    comparar_por_decada,
    comparar_por_genero,
    resumir,
)
from dominio import Movie
from metricas import dimensao

BASE = Movie(
    id=1, titulo="X", ano=2015, generos=("Drama",),
    orcamento=10_000_000, faturamento=30_000_000, nota=7.0,
)


def filme(**campos) -> Movie:
    return BASE._replace(**campos)


def ids(filmes) -> tuple[int, ...]:
    return tuple(f.id for f in filmes)


GENERO = dimensao("genero")
DECADA = dimensao("decada")


# ------------------------------------------------------------- agrupar_por
def test_agrupa_por_genero():
    filmes = (filme(id=1, generos=("Terror",)), filme(id=2, generos=("Drama",)),
              filme(id=3, generos=("Terror",)))
    grupos = agrupar_por(GENERO, filmes)
    assert set(grupos) == {"Terror", "Drama"}
    assert ids(grupos["Terror"]) == (1, 3)
    assert ids(grupos["Drama"]) == (2,)


def test_filme_com_varios_generos_entra_em_varios_grupos():
    f = filme(id=1, generos=("Ação", "Aventura"))
    grupos = agrupar_por(GENERO, (f,))
    assert ids(grupos["Ação"]) == (1,) and ids(grupos["Aventura"]) == (1,)


def test_genero_repetido_no_mesmo_filme_nao_duplica():
    grupos = agrupar_por(GENERO, (filme(id=1, generos=("Drama", "Drama")),))
    assert ids(grupos["Drama"]) == (1,)


def test_filme_sem_chave_fica_fora_do_agrupamento():
    filmes = (filme(id=1, generos=()), filme(id=2, generos=("Drama",)))
    grupos = agrupar_por(GENERO, filmes)
    assert set(grupos) == {"Drama"} and ids(grupos["Drama"]) == (2,)


def test_agrupa_por_decada_com_chave_inteira():
    filmes = (filme(id=1, ano=1999), filme(id=2, ano=2000),
              filme(id=3, ano=2009), filme(id=4, ano=2015))
    grupos = agrupar_por(DECADA, filmes)
    assert set(grupos) == {1990, 2000, 2010}
    assert ids(grupos[2000]) == (2, 3)


def test_ordem_de_entrada_se_mantem_dentro_do_grupo():
    filmes = tuple(filme(id=i, generos=("Drama",)) for i in (5, 1, 9, 3))
    assert ids(agrupar_por(GENERO, filmes)["Drama"]) == (5, 1, 9, 3)


def test_entrada_original_inalterada():
    filmes = [filme(id=1, generos=("Terror",)), filme(id=2, generos=("Drama",))]
    copia = list(filmes)
    agrupar_por(GENERO, filmes)
    assert filmes == copia


def test_cada_chamada_devolve_dicionario_novo():
    filmes = (filme(id=1),)
    a, b = agrupar_por(GENERO, filmes), agrupar_por(GENERO, filmes)
    assert a == b and a is not b


def test_base_vazia_devolve_mapa_vazio():
    assert agrupar_por(GENERO, ()) == {}


def test_aceita_gerador():
    filmes = (filme(id=i) for i in (1, 2, 3))
    assert len(agrupar_por(GENERO, filmes)["Drama"]) == 3


def test_grupos_sao_tuplas_imutaveis():
    assert isinstance(agrupar_por(GENERO, (filme(),))["Drama"], tuple)


# ----------------------------------------------------------------- resumir
def test_resumir_quantidade_e_medias():
    filmes = (
        filme(id=1, orcamento=10, faturamento=30, nota=8.0),   # roi 2.0
        filme(id=2, orcamento=10, faturamento=20, nota=6.0),   # roi 1.0
    )
    r = resumir(filmes)
    assert r.quantidade == 2
    assert r.indicadores["roi"] == pytest.approx(1.5)
    assert r.indicadores["nota"] == pytest.approx(7.0)
    assert r.indicadores["faturamento"] == pytest.approx(25.0)


def test_resumir_traz_os_indicadores_padrao():
    assert tuple(resumir((filme(),)).indicadores) == INDICADORES_PADRAO


def test_roi_ignora_filme_sem_orcamento_mas_conta_na_quantidade():
    filmes = (filme(id=1, orcamento=10, faturamento=30),   # roi 2.0
              filme(id=2, orcamento=0, faturamento=500))   # sem orçamento
    r = resumir(filmes)
    assert r.quantidade == 2
    assert r.indicadores["roi"] == pytest.approx(2.0)
    assert r.indicadores["faturamento"] == pytest.approx(265.0)


def test_nota_ignora_filme_sem_nota():
    filmes = (filme(id=1, nota=8.0), filme(id=2, nota=0.0))
    assert resumir(filmes).indicadores["nota"] == pytest.approx(8.0)


def test_indicador_sem_nenhum_dado_valido_e_none():
    r = resumir((filme(id=1, orcamento=0, nota=0.0), filme(id=2, orcamento=0, nota=0.0)))
    assert r.quantidade == 2
    assert r.indicadores["roi"] is None and r.indicadores["nota"] is None


def test_resumir_grupo_vazio():
    r = resumir(())
    assert r.quantidade == 0
    assert all(v is None for v in r.indicadores.values())


def test_resumir_aceita_indicadores_extras():
    r = resumir((filme(duracao=100), filme(id=2, duracao=140)), ("duracao",))
    assert r.indicadores["duracao"] == pytest.approx(120.0)


def test_resumir_indicador_desconhecido_levanta_erro():
    with pytest.raises(ValueError):
        resumir((filme(),), ("inexistente",))


def test_resumo_e_somente_leitura():
    r = resumir((filme(),))
    with pytest.raises(TypeError):
        r.indicadores["roi"] = 99.0


def test_resumir_aceita_gerador_e_nao_altera_entrada():
    filmes = [filme(id=1), filme(id=2)]
    copia = list(filmes)
    resumir(iter(filmes))
    assert filmes == copia


# --------------------------------------------------------------- comparar_*
def test_comparar_por_genero():
    filmes = (
        filme(id=1, generos=("Terror",), orcamento=10, faturamento=40),   # roi 3
        filme(id=2, generos=("Drama",), orcamento=10, faturamento=20),    # roi 1
        filme(id=3, generos=("Terror", "Drama"), orcamento=10, faturamento=20),  # roi 1
    )
    r = comparar_por_genero(filmes)
    assert r["Terror"].quantidade == 2 and r["Drama"].quantidade == 2
    assert r["Terror"].indicadores["roi"] == pytest.approx(2.0)
    assert r["Drama"].indicadores["roi"] == pytest.approx(1.0)


def test_comparar_por_decada_usa_chave_inteira():
    filmes = (filme(id=1, ano=1995), filme(id=2, ano=1999), filme(id=3, ano=2012))
    r = comparar_por_decada(filmes)
    assert set(r) == {1990, 2010}
    assert r[1990].quantidade == 2 and r[2010].quantidade == 1


def test_grupo_sem_roi_nao_quebra_a_comparacao():
    filmes = (filme(id=1, generos=("Doc",), orcamento=0),
              filme(id=2, generos=("Drama",)))
    r = comparar_por_genero(filmes)
    assert r["Doc"].indicadores["roi"] is None
    assert r["Drama"].indicadores["roi"] is not None


def test_comparar_por_funciona_com_qualquer_dimensao():
    r = comparar_por(dimensao("faixa_nota"), (filme(nota=9.0), filme(id=2, nota=3.0)))
    assert set(r) == {"8-10", "0-5"}


def test_comparacao_e_somente_leitura():
    r = comparar_por_genero((filme(),))
    with pytest.raises(TypeError):
        r["Drama"] = None


def test_base_vazia_devolve_comparacao_vazia():
    assert dict(comparar_por_genero(())) == {} and dict(comparar_por_decada(())) == {}