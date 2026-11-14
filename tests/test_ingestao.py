"""Testes da ingestão, sem rede e sem banco real: tmdb é falso e o banco é tmp_path."""
from contextlib import closing

import pytest

import ingestao
from db import conectar, ler_filmes

PAGINAS = {1: (1, 2), 2: (3,)}
DETALHES = {
    1: {"id": 1, "title": "A", "release_date": "2000-01-01", "budget": 10, "revenue": 20},
    2: {"id": 2, "title": "B", "release_date": "2001-02-03", "budget": 30, "revenue": 60},
    3: {"id": 3, "title": "C", "release_date": ""},      # sem data -> descartado
}


def instalar(monkeypatch, paginas=PAGINAS, detalhes=DETALHES):
    """Substitui as três funções do cliente que a ingestão usa."""
    consultados: list[int] = []

    monkeypatch.setattr(ingestao.tmdb, "carregar_token", lambda: "tok")
    monkeypatch.setattr(
        ingestao.tmdb,
        "descobrir_filmes",
        lambda token, pagina=1: {"results": [{"id": i} for i in paginas.get(pagina, ())]},
    )

    def detalhar(token, filme_id):
        consultados.append(filme_id)
        valor = detalhes[filme_id]
        if isinstance(valor, Exception):
            raise valor
        return valor

    monkeypatch.setattr(ingestao.tmdb, "detalhar_filme", detalhar)
    return consultados


def filmes_do_banco(caminho):
    with closing(conectar(caminho)) as conn:
        return tuple(ler_filmes(conn))


# ---------------------------------------------------------------- páginas

def test_paginas_para_arredonda_para_cima():
    assert ingestao.paginas_para(400) == 20
    assert ingestao.paginas_para(401) == 21
    assert ingestao.paginas_para(1) == 1
    assert ingestao.paginas_para(0) == 1


# ---------------------------------------------------------------- coleta

def test_coletar_filmes_e_preguicoso(monkeypatch):
    consultados = instalar(monkeypatch)
    filmes = ingestao.coletar_filmes("tok", 2)

    assert consultados == []                    # nada buscado antes de iterar
    assert next(filmes).id == 1
    assert consultados == [1, 2]                # só a primeira página

    assert next(filmes).id == 2
    with pytest.raises(StopIteration):
        next(filmes)                            # página 2 tem só o inválido
    assert consultados == [1, 2, 3]


def test_coletar_filmes_descarta_quem_nao_converte(monkeypatch):
    instalar(monkeypatch)
    assert tuple(f.id for f in ingestao.coletar_filmes("tok", 2)) == (1, 2)


def test_coletar_filmes_respeita_o_numero_de_paginas(monkeypatch):
    consultados = instalar(monkeypatch)
    assert tuple(f.id for f in ingestao.coletar_filmes("tok", 1)) == (1, 2)
    assert consultados == [1, 2]


# ---------------------------------------------------------------- gravação

def test_ingerir_grava_e_devolve_quantos(monkeypatch, tmp_path):
    instalar(monkeypatch)
    banco = tmp_path / "cinema.db"

    assert ingestao.ingerir(paginas=2, caminho_db=banco) == 2
    assert tuple(f.id for f in filmes_do_banco(banco)) == (1, 2)


def test_ingerir_cria_a_pasta_do_banco(monkeypatch, tmp_path):
    instalar(monkeypatch)
    banco = tmp_path / "data" / "cinema.db"

    ingestao.ingerir(paginas=1, caminho_db=banco)

    assert banco.exists()


def test_ingerir_duas_vezes_nao_duplica(monkeypatch, tmp_path):
    instalar(monkeypatch)
    banco = tmp_path / "cinema.db"

    ingestao.ingerir(paginas=2, caminho_db=banco)
    ingestao.ingerir(paginas=2, caminho_db=banco)

    assert len(filmes_do_banco(banco)) == 2


def test_ingerir_imprime_o_resumo(monkeypatch, tmp_path, capsys):
    instalar(monkeypatch)

    ingestao.ingerir(paginas=2, caminho_db=tmp_path / "cinema.db")

    saida = capsys.readouterr().out
    assert "3 buscados" in saida
    assert "2 gravados" in saida
    assert "1 descartados" in saida


def test_falha_no_meio_preserva_o_que_ja_foi_gravado(monkeypatch, tmp_path):
    instalar(monkeypatch, detalhes={**DETALHES, 3: RuntimeError("caiu a rede")})
    banco = tmp_path / "cinema.db"

    with pytest.raises(RuntimeError, match="caiu a rede"):
        ingestao.ingerir(paginas=2, caminho_db=banco)

    assert tuple(f.id for f in filmes_do_banco(banco)) == (1, 2)


def test_pagina_vazia_encerra_a_ingestao(monkeypatch, tmp_path, capsys):
    instalar(monkeypatch)
    banco = tmp_path / "cinema.db"

    assert ingestao.ingerir(paginas=5, caminho_db=banco) == 2
    assert "3 buscados" in capsys.readouterr().out


def test_sem_token_nao_cria_banco(monkeypatch, tmp_path):
    instalar(monkeypatch)

    def sem_token():
        raise RuntimeError("TMDB_TOKEN não configurado.")

    monkeypatch.setattr(ingestao.tmdb, "carregar_token", sem_token)
    banco = tmp_path / "cinema.db"

    with pytest.raises(RuntimeError, match="TMDB_TOKEN"):
        ingestao.ingerir(paginas=1, caminho_db=banco)
    assert not banco.exists()


# ---------------------------------------------------------------- CLI

def test_main_grava_e_devolve_zero(monkeypatch, tmp_path):
    instalar(monkeypatch)
    banco = tmp_path / "cinema.db"

    assert ingestao.main(["--limite", "40", "--banco", str(banco)]) == 0
    assert len(filmes_do_banco(banco)) == 2


def test_main_sem_token_devolve_um(monkeypatch, capsys):
    def sem_token():
        raise RuntimeError("TMDB_TOKEN não configurado. Copie .env.example para .env.")

    monkeypatch.setattr(ingestao.tmdb, "carregar_token", sem_token)

    assert ingestao.main(["--limite", "20"]) == 1
    assert "erro:" in capsys.readouterr().out