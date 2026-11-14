"""Configuração comum dos testes.

A suíte precisa rodar verde **sem internet** (inclusive na apresentação). A
fixture abaixo bloqueia conexões de saída: se algum teste tentar falar com o
TMDB de verdade, ele falha com uma mensagem dizendo o que substituir.
"""
import socket

import pytest


@pytest.fixture(autouse=True)
def sem_rede(monkeypatch):
    """Impede qualquer conexão de rede durante os testes."""

    def bloqueado(*args, **kwargs):
        raise AssertionError(
            "teste tentou acessar a rede. Substitua tmdb.descobrir_filmes / "
            "tmdb.detalhar_filme com monkeypatch em vez de chamar a API."
        )

    monkeypatch.setattr(socket, "create_connection", bloqueado)
    monkeypatch.setattr(socket.socket, "connect", bloqueado)
    monkeypatch.setattr(socket.socket, "connect_ex", bloqueado)