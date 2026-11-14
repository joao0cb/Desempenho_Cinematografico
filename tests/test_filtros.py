import itertools

import pytest

from dominio import Movie
from filtros import (
    a_partir_da_decada,
    qualquer,
    combinar,
    contendo,
    faturamento_minimo,
    filtrar,
    make_filtro,
    negar,
    nota_minima,
    orcamento_minimo,
    por_decada,
    por_faixa,
    por_genero,
    por_valor,
    todos,
)


def filme(**campos) -> Movie:
    base = {"id": 1, "titulo": "X", "ano": 2015}
    return Movie(**{**base, **campos})


# ---------- por_genero ----------

def test_por_genero_ignora_maiusculas():
    terror = filme(generos=("Terror", "Suspense"))
    assert por_genero("terror")(terror)
    assert por_genero("TERROR")(terror)
    assert por_genero("  Terror ")(terror)


def test_por_genero_nao_casa_pedaco_do_nome():
    assert not por_genero("Terro")(filme(generos=("Terror",)))


def test_por_genero_sem_generos_rejeita():
    assert not por_genero("Terror")(filme(generos=()))


# ---------- por_decada ----------

def test_por_decada_pega_todos_os_anos_da_decada():
    assert por_decada(1990)(filme(ano=1990))
    assert por_decada(1990)(filme(ano=1999))
    assert not por_decada(1990)(filme(ano=2000))


def test_por_decada_normaliza_o_ano_recebido():
    assert por_decada(1994)(filme(ano=1995))
    assert not por_decada(1994)(filme(ano=2005))


def test_por_decada_ignora_ano_desconhecido():
    assert not por_decada(0)(filme(ano=0))


def test_a_partir_da_decada_inclui_dali_em_diante():
    filtro = a_partir_da_decada(2010)
    assert filtro(filme(ano=2010))
    assert filtro(filme(ano=2019))
    assert not filtro(filme(ano=2005))
    assert not filtro(filme(ano=0))


def test_a_partir_da_decada_normaliza_o_ano_recebido():
    assert a_partir_da_decada(2017)(filme(ano=2012))


# ---------- por_faixa e atalhos ----------

def test_por_faixa_apenas_minimo():
    filtro = por_faixa("nota", minimo=7)
    assert filtro(filme(nota=7.0))
    assert filtro(filme(nota=9.5))
    assert not filtro(filme(nota=6.9))


def test_por_faixa_apenas_maximo():
    filtro = por_faixa("duracao", maximo=120)
    assert filtro(filme(duracao=90))
    assert filtro(filme(duracao=120))
    assert not filtro(filme(duracao=121))


def test_por_faixa_com_os_dois_limites():
    filtro = por_faixa("duracao", 90, 120)
    assert filtro(filme(duracao=100))
    assert not filtro(filme(duracao=89))
    assert not filtro(filme(duracao=150))


def test_por_faixa_sem_limites_aceita_tudo():
    assert por_faixa("orcamento")(filme(orcamento=0))


def test_atalhos_de_minimo():
    assert orcamento_minimo(1_000_000)(filme(orcamento=2_000_000))
    assert not orcamento_minimo(1_000_000)(filme(orcamento=0))
    assert faturamento_minimo(500)(filme(faturamento=500))
    assert nota_minima(7)(filme(nota=7.0))
    assert not nota_minima(7)(filme(nota=6.99))


def test_por_faixa_com_campo_invalido():
    with pytest.raises(ValueError, match="numérico"):
        por_faixa("generos", minimo=1)


# ---------- por_valor ----------

def test_por_valor_aceita_varios_valores():
    filtro = por_valor("idioma_original", "en", "pt")
    assert filtro(filme(idioma_original="pt"))
    assert filtro(filme(idioma_original="en"))
    assert not filtro(filme(idioma_original="fr"))


def test_por_valor_com_campo_de_lista_e_erro():
    with pytest.raises(ValueError, match="valor único"):
        por_valor("elenco", "Tom Hanks")


# ---------- contendo ----------

def test_contendo_ignora_maiusculas():
    filtro = contendo("elenco", "tom hanks")
    assert filtro(filme(elenco=("Tom Hanks", "Meg Ryan")))
    assert not filtro(filme(elenco=("Meg Ryan",)))


def test_contendo_aceita_varios_valores():
    filtro = contendo("paises", "BR", "AR")
    assert filtro(filme(paises=("AR",)))
    assert not filtro(filme(paises=("US",)))


def test_contendo_lista_vazia_rejeita():
    assert not contendo("empresas", "Pixar")(filme(empresas=()))


def test_contendo_com_campo_numerico_e_erro():
    with pytest.raises(ValueError, match="lista"):
        contendo("nota", "7")


# ---------- combinadores ----------

def test_todos_e_logico():
    filtro = todos(por_genero("Terror"), por_decada(2010))
    assert filtro(filme(ano=2015, generos=("Terror",)))
    assert not filtro(filme(ano=2005, generos=("Terror",)))
    assert not filtro(filme(ano=2015, generos=("Comédia",)))


def test_todos_sem_predicados_aceita_tudo():
    assert todos()(filme())


def test_todos_tem_curto_circuito():
    def explode(_filme: Movie) -> bool:
        raise AssertionError("não deveria ser avaliado")

    filtro = todos(por_decada(2020), explode)
    assert not filtro(filme(ano=1990))     # o segundo predicado nem roda


def test_combinar_e_igual_a_todos():
    importante = filme(ano=2012, generos=("Terror",), nota=8.0)
    assert combinar(por_genero("Terror"), nota_minima(7))(importante)


def test_qualquer_e_ou_logico():
    filtro = qualquer(por_genero("Terror"), nota_minima(9))
    assert filtro(filme(generos=("Terror",), nota=5.0))
    assert filtro(filme(generos=("Comédia",), nota=9.5))
    assert not filtro(filme(generos=("Comédia",), nota=8.0))


def test_qualquer_sem_predicados_rejeita_tudo():
    assert not qualquer()(filme())


def test_negar_inverte():
    assert not negar(por_genero("Terror"))(filme(generos=("Terror",)))
    assert negar(por_genero("Terror"))(filme(generos=("Drama",)))


# ---------- filtrar ----------

def test_filtrar_preserva_ordem():
    filmes = (filme(id=1, nota=5.0), filme(id=2, nota=8.0), filme(id=3, nota=9.0))
    assert tuple(f.id for f in filtrar(nota_minima(7), filmes)) == (2, 3)


def test_filtrar_e_preguicoso_com_gerador_infinito():
    infinito = (filme(id=i, ano=2000 + i) for i in itertools.count())
    primeiros = tuple(f.id for f in filtrar(por_decada(2010), infinito) if False) if False else ()
    primeiros = tuple(f.id for f in itertools.islice(filtrar(por_decada(2010), infinito), 3))
    assert primeiros == (10, 11, 12)


# ---------- make_filtro ----------

def test_make_filtro_combina_criterios():
    filtro = make_filtro(genero="Terror", a_partir_de=2010, nota_min=7)
    assert filtro(filme(ano=2012, generos=("Terror",), nota=7.5))
    assert not filtro(filme(ano=2012, generos=("Terror",), nota=6.9))
    assert not filtro(filme(ano=2001, generos=("Terror",), nota=8.0))
    assert not filtro(filme(ano=2015, generos=("Comédia",), nota=8.0))


def test_make_filtro_usa_faixas_de_campo():
    filtro = make_filtro(orcamento_min=1_000_000, duracao_max=120)
    assert filtro(filme(orcamento=5_000_000, duracao=100))
    assert not filtro(filme(orcamento=500_000, duracao=100))
    assert not filtro(filme(orcamento=5_000_000, duracao=150))


def test_make_filtro_usa_criterios_de_texto_e_lista():
    filtro = make_filtro(idioma="pt", diretor="Fernando Meirelles", pais="BR")
    assert filtro(filme(idioma_original="pt", diretor="Fernando Meirelles", paises=("BR",)))
    assert not filtro(filme(idioma_original="en", diretor="Fernando Meirelles", paises=("BR",)))


def test_make_filtro_sem_criterios_aceita_tudo():
    assert make_filtro()(filme())


def test_make_filtro_com_criterio_desconhecido():
    with pytest.raises(ValueError, match="critério desconhecido"):
        make_filtro(genro="Terror")


def test_make_filtro_com_campo_numerico_inexistente():
    with pytest.raises(ValueError, match="critério desconhecido"):
        make_filtro(bilheteria_min=1)


# ---------- aceite da issue ----------

def test_aceite_terror_e_decada_de_2010_e_nota_maior_ou_igual_a_7():
    filmes = (
        filme(id=1, ano=2012, generos=("Terror",), nota=7.5),    # passa
        filme(id=2, ano=2012, generos=("Terror",), nota=6.9),    # nota baixa
        filme(id=3, ano=2001, generos=("Terror",), nota=8.0),    # década errada
        filme(id=4, ano=2015, generos=("Comédia",), nota=8.0),   # gênero errado
    )
    filtro = todos(por_genero("Terror"), por_decada(2010), nota_minima(7))
    assert [f.id for f in filter(lambda f: filtro(f), filmes)] == [1]

    mesmo_filtro = make_filtro(genero="Terror", decada=2010, nota_min=7)
    assert [f.id for f in filter(lambda f: mesmo_filtro(f), filmes)] == [1]


def test_filtros_nao_alteram_a_entrada():
    filmes = (filme(id=1, ano=2012, generos=("Terror",)), filme(id=2, ano=1990))
    copia = tuple(filmes)
    tuple(filtrar(todos(por_genero("Terror"), a_partir_da_decada(2010)), filmes))
    assert filmes == copia