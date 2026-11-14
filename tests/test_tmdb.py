"""Testes do cliente do TMDB, sem rede: `requests.get` é substituído por um fake."""
import pytest
import requests

import tmdb


class Resposta:
    """Resposta mínima no formato do requests, para teste offline."""

    def __init__(self, status: int = 200, corpo: dict | None = None,
                 headers: dict | None = None) -> None:
        self.status_code = status
        self._corpo = {} if corpo is None else corpo
        self.headers = {} if headers is None else headers

    @property
    def ok(self) -> bool:
        return self.status_code < 400

    def json(self) -> dict:
        return self._corpo


@pytest.fixture(autouse=True)
def sem_dotenv(monkeypatch):
    """Impede que o .env da máquina interfira nos testes."""
    monkeypatch.setattr(tmdb, "load_dotenv", lambda *args, **kwargs: None)


def instalar(monkeypatch, *respostas) -> list[dict]:
    """Substitui `requests.get` por uma fila de respostas e registra as chamadas."""
    fila = list(respostas)
    registro: list[dict] = []

    def falso_get(url, headers=None, params=None, timeout=None):
        registro.append({"url": url, "headers": headers, "params": params, "timeout": timeout})
        if not fila:
            raise AssertionError("chamada inesperada ao TMDB")
        item = fila.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    monkeypatch.setattr(tmdb.requests, "get", falso_get)
    return registro


# ---------------------------------------------------------------- token

def test_carregar_token_le_do_ambiente(monkeypatch):
    monkeypatch.setenv("TMDB_TOKEN", "  eyJabc  ")
    assert tmdb.carregar_token() == "eyJabc"


def test_carregar_token_ausente_explica_como_configurar(monkeypatch):
    monkeypatch.delenv("TMDB_TOKEN", raising=False)
    with pytest.raises(RuntimeError, match=r"\.env"):
        tmdb.carregar_token()


# ---------------------------------------------------------------- requisições

def test_descobrir_filmes_monta_cabecalho_e_parametros(monkeypatch):
    registro = instalar(monkeypatch, Resposta(200, {"page": 2, "results": [{"id": 603}]}))

    corpo = tmdb.descobrir_filmes("tok", pagina=2)

    assert corpo["results"] == [{"id": 603}]
    chamada = registro[0]
    assert chamada["url"] == "https://api.themoviedb.org/3/discover/movie"
    assert chamada["headers"]["Authorization"] == "Bearer tok"
    assert chamada["timeout"] == tmdb.TIMEOUT_PADRAO
    assert chamada["params"] == {
        "sort_by": "revenue.desc",
        "vote_count.gte": 100,
        "language": "pt-BR",
        "page": 2,
    }


def test_detalhar_filme_pede_creditos_e_release_dates(monkeypatch):
    registro = instalar(monkeypatch, Resposta(200, {"id": 603}))

    assert tmdb.detalhar_filme("tok", 603) == {"id": 603}

    chamada = registro[0]
    assert chamada["url"] == "https://api.themoviedb.org/3/movie/603"
    assert chamada["params"]["language"] == "pt-BR"
    assert chamada["params"]["append_to_response"] == "credits,release_dates"


def test_token_nao_vai_na_url(monkeypatch):
    registro = instalar(monkeypatch, Resposta(200, {}))
    tmdb.descobrir_filmes("tok-secreto")
    assert "tok-secreto" not in registro[0]["url"]
    assert "tok-secreto" not in str(registro[0]["params"])


# ---------------------------------------------------------------- erros

def test_token_recusado_nao_vaza_o_token(monkeypatch):
    instalar(monkeypatch, Resposta(401))
    with pytest.raises(RuntimeError) as erro:
        tmdb.detalhar_filme("segredo-do-token", 603)

    mensagem = str(erro.value)
    assert "401" in mensagem
    assert ".env" in mensagem
    assert "segredo-do-token" not in mensagem


def test_rate_limit_espera_e_tenta_de_novo(monkeypatch):
    esperas: list[float] = []
    monkeypatch.setattr(tmdb.time, "sleep", lambda segundos: esperas.append(segundos))
    instalar(monkeypatch, Resposta(429, headers={"Retry-After": "1"}), Resposta(200, {"ok": True}))

    assert tmdb.descobrir_filmes("tok") == {"ok": True}
    assert esperas == [1.0]


def test_rate_limit_persistente_desiste_com_mensagem(monkeypatch):
    monkeypatch.setattr(tmdb.time, "sleep", lambda segundos: None)
    instalar(monkeypatch, *[Resposta(429) for _ in range(tmdb.TENTATIVAS_RATE_LIMIT + 1)])

    with pytest.raises(RuntimeError, match="429"):
        tmdb.descobrir_filmes("tok")


def test_timeout_tem_mensagem_clara(monkeypatch):
    instalar(monkeypatch, requests.Timeout())
    with pytest.raises(RuntimeError, match="tempo esgotado"):
        tmdb.descobrir_filmes("tok")


def test_falha_de_rede_tem_mensagem_clara(monkeypatch):
    instalar(monkeypatch, requests.ConnectionError("sem rede"))
    with pytest.raises(RuntimeError, match="rede"):
        tmdb.descobrir_filmes("tok")


def test_outro_erro_http_informa_o_status(monkeypatch):
    instalar(monkeypatch, Resposta(500))
    with pytest.raises(RuntimeError, match="500"):
        tmdb.descobrir_filmes("tok")


# ---------------------------------------------------------------- atalhos

def test_buscar_pagina_usa_o_token_do_ambiente(monkeypatch):
    monkeypatch.setenv("TMDB_TOKEN", "tok")
    registro = instalar(monkeypatch, Resposta(200, {"results": [{"id": 1}, {"id": 2}]}))

    assert tmdb.buscar_pagina(3) == [{"id": 1}, {"id": 2}]
    assert registro[0]["params"]["page"] == 3
    assert registro[0]["headers"]["Authorization"] == "Bearer tok"


def test_buscar_pagina_sem_resultados_devolve_lista_vazia(monkeypatch):
    monkeypatch.setenv("TMDB_TOKEN", "tok")
    instalar(monkeypatch, Resposta(200, {}))
    assert tmdb.buscar_pagina() == []


def test_buscar_detalhes_devolve_dict(monkeypatch):
    monkeypatch.setenv("TMDB_TOKEN", "tok")
    instalar(monkeypatch, Resposta(200, {"id": 603, "title": "Matrix"}))
    assert tmdb.buscar_detalhes(603) == {"id": 603, "title": "Matrix"}