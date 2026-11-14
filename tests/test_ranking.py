
"""Testes dos rankings de filmes e de grupos (issue #4)."""
from types import MappingProxyType
 
from dominio import Movie, ResumoGrupo
from metricas import metrica
from ranking import top_filmes, top_grupos
 
BASE = Movie(
    id=1, titulo="X", ano=2015, orcamento=10_000_000,
    faturamento=30_000_000, nota=7.0, duracao=100,
)
 
 
def filme(**campos) -> Movie:
    return BASE._replace(**campos)
 
 
def ids(filmes) -> tuple[int, ...]:
    return tuple(f.id for f in filmes)
 
 
FILMES = (
    filme(id=1, faturamento=100, orcamento=50, nota=6.0),   # roi 1.0
    filme(id=2, faturamento=300, orcamento=100, nota=9.0),  # roi 2.0
    filme(id=3, faturamento=200, orcamento=200, nota=8.0),  # roi 0.0
    filme(id=4, faturamento=50, orcamento=0, nota=0.0),     # sem roi, sem nota
)
 
 
# --------------------------------------------------------------- top_filmes
def test_top_por_faturamento_decrescente():
    assert ids(top_filmes(3, metrica("faturamento"), FILMES)) == (2, 3, 1)
 
 
def test_top_crescente():
    assert ids(top_filmes(2, metrica("faturamento"), FILMES, decrescente=False)) == (4, 1)
 
 
def test_top_funciona_com_qualquer_metrica():
    assert ids(top_filmes(1, metrica("nota"), FILMES)) == (2,)
    assert ids(top_filmes(1, metrica("roi"), FILMES)) == (2,)
    assert ids(top_filmes(1, lambda f: float(f.duracao), (filme(id=7, duracao=200),))) == (7,)
 
 
def test_chave_none_fica_de_fora():
    assert ids(top_filmes(10, metrica("roi"), FILMES)) == (2, 1, 3)   # id 4 sem orçamento
    assert ids(top_filmes(10, metrica("nota"), FILMES)) == (2, 3, 1)  # id 4 sem nota
 
 
def test_n_maior_que_o_total_devolve_todos_com_dado():
    assert len(top_filmes(999, metrica("faturamento"), FILMES)) == 4
 
 
def test_n_zero_ou_negativo_devolve_vazio():
    assert top_filmes(0, metrica("faturamento"), FILMES) == ()
    assert top_filmes(-3, metrica("faturamento"), FILMES) == ()
 
 
def test_base_vazia():
    assert top_filmes(5, metrica("faturamento"), ()) == ()
 
 
def test_empates_mantem_a_ordem_de_entrada():
    empatados = tuple(filme(id=i, faturamento=100) for i in (5, 1, 9))
    assert ids(top_filmes(3, metrica("faturamento"), empatados)) == (5, 1, 9)
    assert ids(top_filmes(3, metrica("faturamento"), empatados, decrescente=False)) == (5, 1, 9)
 
 
def test_chave_e_calculada_uma_vez_por_filme():
    chamadas = []
    def chave(f):
        chamadas.append(f.id)
        return float(f.faturamento)
    top_filmes(2, chave, FILMES)
    assert sorted(chamadas) == [1, 2, 3, 4]
 
 
def test_aceita_gerador():
    assert ids(top_filmes(2, metrica("faturamento"), (f for f in FILMES))) == (2, 3)
 
 
def test_devolve_tupla_e_nao_altera_a_entrada():
    entrada = list(FILMES)
    copia = list(entrada)
    resultado = top_filmes(3, metrica("faturamento"), entrada)
    assert isinstance(resultado, tuple) and entrada == copia
 
 
# -------------------------------------------------------------- top_grupos
def resumo(quantidade: int, **indicadores) -> ResumoGrupo:
    return ResumoGrupo(quantidade, MappingProxyType(indicadores))
 
 
GRUPOS = {
    "Drama": resumo(10, roi=1.5, nota=7.5),
    "Terror": resumo(4, roi=3.0, nota=6.0),
    "Ação": resumo(7, roi=0.5, nota=7.0),
    "Doc": resumo(2, roi=None, nota=8.0),
}
 
 
def chaves(pares) -> tuple:
    return tuple(c for c, _ in pares)
 
 
def test_top_grupos_por_roi_decrescente():
    assert chaves(top_grupos(2, "roi", GRUPOS)) == ("Terror", "Drama")
 
 
def test_top_grupos_crescente():
    assert chaves(top_grupos(2, "roi", GRUPOS, decrescente=False)) == ("Ação", "Drama")
 
 
def test_grupo_com_indicador_none_fica_de_fora():
    assert "Doc" not in chaves(top_grupos(10, "roi", GRUPOS))
    assert "Doc" in chaves(top_grupos(10, "nota", GRUPOS))
 
 
def test_top_grupos_devolve_chave_e_resumo():
    (chave, r), = top_grupos(1, "nota", GRUPOS)
    assert chave == "Doc" and r is GRUPOS["Doc"]
 
 
def test_indicador_inexistente_nao_quebra_e_devolve_vazio():
    assert top_grupos(3, "lucro", GRUPOS) == ()
 
 
def test_top_grupos_n_zero_negativo_e_vazio():
    assert top_grupos(0, "roi", GRUPOS) == ()
    assert top_grupos(-1, "roi", GRUPOS) == ()
    assert top_grupos(3, "roi", {}) == ()
 
 
def test_chaves_inteiras_e_tuplas_funcionam():
    decadas = {1990: resumo(3, nota=6.0), 2000: resumo(5, nota=8.0)}
    assert chaves(top_grupos(1, "nota", decadas)) == (2000,)
    combinadas = {("Ação", 1990): resumo(1, nota=9.0), ("Drama", 2000): resumo(1, nota=5.0)}
    assert chaves(top_grupos(1, "nota", combinadas)) == (("Ação", 1990),)
 
 
def test_empate_de_grupos_mantem_a_ordem_do_mapeamento():
    empate = {"B": resumo(1, roi=1.0), "A": resumo(1, roi=1.0)}
    assert chaves(top_grupos(2, "roi", empate)) == ("B", "A")
 
 
def test_top_grupos_nao_altera_a_entrada():
    copia = dict(GRUPOS)
    top_grupos(2, "roi", GRUPOS)
    assert GRUPOS == copia
 