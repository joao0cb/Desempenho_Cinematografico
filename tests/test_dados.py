from itertools import count

import pytest

from dados import (
    amostra,
    eh_valido,
    filme_para_linha,
    limpar,
    limpar_com,
    linha_para_movie,
    para_filmes,
    para_movie,
    tem_ano_valido,
    tem_nota_valida,
    tem_valor,
)
from dominio import Movie

VALIDO = Movie(
    id=1, titulo="Matrix", ano=1999, data_lancamento="1999-03-31",
    generos=("Ação", "Ficção científica"), orcamento=63_000_000, faturamento=463_000_000,
    nota=8.2, popularidade=60.5, duracao=136, idioma_original="en",
    classificacao="R", diretor="Lana Wachowski", elenco=("Keanu Reeves",),
    paises=("US",), empresas=("Warner Bros.",), colecao="Matrix",
)


def filme(**campos) -> Movie:
    return VALIDO._replace(**campos)


def linha(**campos) -> tuple:
    """Linha como vem do banco (listas em JSON), com campos sobrescritos."""
    return filme_para_linha(VALIDO._replace(**campos))


# ---------------------------------------------------------------- conversão

def test_ida_e_volta_filme_linha_filme():
    assert linha_para_movie(filme_para_linha(VALIDO)) == VALIDO


def test_listas_viram_json_na_linha():
    l = filme_para_linha(VALIDO)
    assert l[Movie._fields.index("generos")] == '["Ação", "Ficção científica"]'


def test_numeros_vindos_como_texto():
    l = list(linha())
    for campo, texto in {"ano": "1999", "orcamento": "63000000", "faturamento": "463000000.0",
                         "nota": "8.2", "duracao": "136"}.items():
        l[Movie._fields.index(campo)] = texto
    assert linha_para_movie(tuple(l)) == VALIDO


def test_linha_nula_ou_malformada_vira_none():
    assert linha_para_movie(None) is None
    assert linha_para_movie(()) is None
    assert linha_para_movie((1, "curta")) is None
    assert linha_para_movie(linha()[:-1]) is None  # faltou coluna
    assert linha_para_movie(("abc",) + linha()[1:]) is None  # id ilegível
    assert linha_para_movie((None,) + linha()[1:]) is None  # id ausente


def test_campos_nulos_viram_sentinelas():
    nulos = (7,) + (None,) * (len(Movie._fields) - 1)
    assert linha_para_movie(nulos) == Movie(7, "", 0)


def test_lixo_e_nan_viram_sentinelas():
    l = list(linha())
    l[Movie._fields.index("ano")] = "dois mil"
    l[Movie._fields.index("orcamento")] = "abc"
    l[Movie._fields.index("faturamento")] = float("nan")
    l[Movie._fields.index("nota")] = "n/a"
    convertido = linha_para_movie(tuple(l))
    assert (convertido.ano, convertido.orcamento, convertido.faturamento, convertido.nota) == (0, 0, 0, 0.0)


def test_lista_json_invalida_ou_de_tipo_errado_vira_vazia():
    for ruim in ("isso nao e json", "123", '{"a": 1}', 5, ""):
        l = list(linha())
        l[Movie._fields.index("generos")] = ruim
        assert linha_para_movie(tuple(l)).generos == ()


def test_lista_remove_vazios_e_repeticoes_mantendo_a_ordem():
    l = list(linha())
    l[Movie._fields.index("elenco")] = '["A", "", "B", "A", null, " C "]'
    assert linha_para_movie(tuple(l)).elenco == ("A", "B", "C")


def test_data_invalida_vira_vazia_e_data_com_hora_e_normalizada():
    l = list(linha())
    l[Movie._fields.index("data_lancamento")] = "1999-13-45"
    assert linha_para_movie(tuple(l)).data_lancamento == ""
    l[Movie._fields.index("data_lancamento")] = "1999-03-31T00:00:00"
    assert linha_para_movie(tuple(l)).data_lancamento == "1999-03-31"


def test_para_filmes_pula_linhas_inutilizaveis():
    linhas = [linha(id=1), None, ("x",) + linha()[1:], linha(id=2)]
    assert [f.id for f in para_filmes(linhas)] == [1, 2]


# ------------------------------------------------------------------- limpar

def test_limpar_mantem_filme_valido():
    assert list(limpar([VALIDO])) == [VALIDO]


@pytest.mark.parametrize("orcamento", [0, -5])
def test_descarta_orcamento_zero_ou_negativo(orcamento):
    assert list(limpar([filme(orcamento=orcamento)])) == []


@pytest.mark.parametrize("faturamento", [0, -1])
def test_descarta_faturamento_zero_ou_negativo(faturamento):
    assert list(limpar([filme(faturamento=faturamento)])) == []


@pytest.mark.parametrize("nota", [0.0, -1.0, 10.5])
def test_descarta_nota_ausente_ou_fora_da_faixa(nota):
    assert list(limpar([filme(nota=nota)])) == []


@pytest.mark.parametrize("ano", [0, 1500, 1887, 2101, -1999])
def test_descarta_ano_invalido(ano):
    assert list(limpar([filme(ano=ano)])) == []


def test_limites_validos_sao_aceitos():
    assert tem_ano_valido(filme(ano=1888))
    assert tem_nota_valida(filme(nota=10.0))
    assert eh_valido(filme(orcamento=1, faturamento=1, nota=0.1))


def test_linha_totalmente_nula_nao_sobrevive_a_limpeza():
    nulos = (7,) + (None,) * (len(Movie._fields) - 1)
    assert list(limpar(para_filmes([nulos]))) == []


# ------------------------------------------------- exigências sob medida

def test_tem_valor_por_tipo_de_campo():
    assert tem_valor("diretor")(VALIDO) and not tem_valor("diretor")(filme(diretor=""))
    assert tem_valor("elenco")(VALIDO) and not tem_valor("elenco")(filme(elenco=()))
    assert tem_valor("duracao")(VALIDO) and not tem_valor("duracao")(filme(duracao=0))
    assert not tem_valor("duracao")(filme(duracao=-3))


def test_tem_valor_rejeita_campo_inexistente():
    with pytest.raises(ValueError):
        tem_valor("bilheteria")


def test_limpar_com_exige_so_o_necessario():
    sem_orcamento = filme(orcamento=0, faturamento=0)  # a limpar padrão descartaria
    sem_diretor = filme(diretor="")
    filmes = [VALIDO, sem_orcamento, sem_diretor]
    exigencias = [tem_nota_valida, tem_valor("diretor")]
    assert list(limpar_com(exigencias, filmes)) == [VALIDO, sem_orcamento]
    assert list(limpar(filmes)) == [VALIDO, sem_diretor]


def test_limpar_com_aceita_exigencias_em_gerador():
    exigencias = (e for e in [tem_nota_valida, tem_valor("diretor")])
    assert list(limpar_com(exigencias, [VALIDO])) == [VALIDO]


# --------------------------------------------------- preguiça e imutabilidade

def test_limpar_e_para_filmes_sao_preguicosos():
    puxadas = []

    def fonte():
        for i in count():  # infinita: só termina se alguém parar de puxar
            puxadas.append(i)
            yield linha(id=i)

    filmes = limpar(para_filmes(fonte()))
    assert next(filmes).id == 0
    assert len(puxadas) == 1  # nada foi lido além do necessário


def test_funcoes_devolvem_iteradores_nao_listas():
    for resultado in (
        limpar([VALIDO]), limpar_com([], [VALIDO]), para_filmes([]), amostra([VALIDO], 1),
    ):
        assert iter(resultado) is resultado


def test_entrada_nao_e_mutada():
    entrada = [VALIDO, filme(orcamento=0)]
    copia = list(entrada)
    list(limpar(entrada))
    assert entrada == copia


def test_amostra_usa_islice_sem_consumir_tudo():
    infinita = (filme(id=i) for i in count(1))
    assert [f.id for f in amostra(infinita, 3)] == [1, 2, 3]
    assert [f.id for f in amostra((filme(id=i) for i in count(1)), 2, inicio=5)] == [6, 7]



# ---------------------------------------------------------------- para_movie

DETALHE = {
    "id": 603,
    "title": "Matrix",
    "release_date": "1999-03-31",
    "genres": [{"id": 28, "name": "Ação"}, {"id": 878, "name": "Ficção científica"}],
    "budget": 63_000_000,
    "revenue": 463_000_000,
    "vote_average": 8.2,
    "popularity": 60.5,
    "runtime": 136,
    "original_language": "en",
    "production_countries": [{"iso_3166_1": "US", "name": "United States of America"}],
    "production_companies": [{"id": 1, "name": "Warner Bros."}],
    "belongs_to_collection": {"id": 2344, "name": "Matrix"},
    "credits": {
        "crew": [{"job": "Producer", "name": "Joel Silver"},
                 {"job": "Director", "name": "Lana Wachowski"}],
        "cast": [{"name": "Keanu Reeves"}, {"name": "Laurence Fishburne"},
                 {"name": "Carrie-Anne Moss"}, {"name": "Hugo Weaving"},
                 {"name": "Gloria Foster"}, {"name": "Joe Pantoliano"}],
    },
    "release_dates": {"results": [
        {"iso_3166_1": "BR", "release_dates": [{"certification": "14"}]},
        {"iso_3166_1": "US", "release_dates": [
            {"certification": ""}, {"certification": "R"},
        ]},
    ]},
}


def test_para_movie_mapeia_todos_os_campos():
    convertido = para_movie(DETALHE)
    assert convertido == Movie(
        id=603, titulo="Matrix", ano=1999, data_lancamento="1999-03-31",
        generos=("Ação", "Ficção científica"), orcamento=63_000_000,
        faturamento=463_000_000, nota=8.2, popularidade=60.5, duracao=136,
        idioma_original="en", classificacao="R", diretor="Lana Wachowski",
        elenco=("Keanu Reeves", "Laurence Fishburne", "Carrie-Anne Moss",
                "Hugo Weaving", "Gloria Foster"),
        paises=("US",), empresas=("Warner Bros.",), colecao="Matrix",
    )


def test_para_movie_sem_id_titulo_ou_data_devolve_none():
    assert para_movie({**DETALHE, "id": None}) is None
    assert para_movie({**DETALHE, "id": 0}) is None
    assert para_movie({**DETALHE, "title": ""}) is None
    assert para_movie({**DETALHE, "release_date": ""}) is None
    assert para_movie({**DETALHE, "release_date": "31/03/1999"}) is None


def test_para_movie_com_entrada_que_nao_e_mapping():
    assert para_movie(None) is None
    assert para_movie([1, 2, 3]) is None


def test_para_movie_tolera_campos_ausentes():
    minimo = para_movie({"id": 1, "title": "X", "release_date": "2001-01-02"})
    assert minimo == Movie(id=1, titulo="X", ano=2001, data_lancamento="2001-01-02")


def test_para_movie_com_listas_malformadas():
    estranho = para_movie({
        **DETALHE, "genres": None, "production_countries": "US",
        "credits": {"cast": [{"name": ""}, "nome solto"]},
        "release_dates": [],
    })
    assert estranho.generos == ()
    assert estranho.paises == ()
    assert estranho.elenco == ()
    assert estranho.classificacao == ""
    assert estranho.diretor == ""


def test_para_movie_corta_nota_fora_da_faixa():
    assert para_movie({**DETALHE, "vote_average": 12.5}).nota == 10.0
    assert para_movie({**DETALHE, "vote_average": -1}).nota == 0.0


def test_para_movie_sem_equipe_tecnica():
    sem_creditos = para_movie({**DETALHE, "credits": {}})
    assert sem_creditos.diretor == ""
    assert sem_creditos.elenco == ()


def test_para_movie_usa_a_primeira_classificacao_dos_eua():
    so_br = para_movie({**DETALHE, "release_dates": {"results": [
        {"iso_3166_1": "BR", "release_dates": [{"certification": "14"}]},
        {"iso_3166_1": "US", "release_dates": [{"certification": ""}]},
    ]}})
    assert so_br.classificacao == ""