"""Garante o critério de aceite: o núcleo não faz I/O."""
import ast
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
NUCLEO = ["dominio", "dados", "filtros", "metricas", "analises", "correlacao", "ranking"]
IMPORTS_PROIBIDOS = {
    "sqlite3", "requests", "dotenv", "os", "sys", "pathlib", "io",
    "urllib", "http", "socket", "subprocess", "db", "tmdb", "formatacao", "ingestao", "main",
}
CHAMADAS_PROIBIDAS = {"print", "open", "input"}


def _analisar(nome: str):
    return ast.parse((RAIZ / f"{nome}.py").read_text(encoding="utf-8"))


def test_nucleo_nao_importa_modulos_de_io():
    for nome in NUCLEO:
        for no in ast.walk(_analisar(nome)):
            if isinstance(no, ast.Import):
                usados = {a.name.split(".")[0] for a in no.names}
            elif isinstance(no, ast.ImportFrom):
                usados = {(no.module or "").split(".")[0]}
            else:
                continue
            assert not usados & IMPORTS_PROIBIDOS, f"{nome}.py importa {usados & IMPORTS_PROIBIDOS}"


def test_nucleo_nao_chama_print_open_input():
    for nome in NUCLEO:
        for no in ast.walk(_analisar(nome)):
            if isinstance(no, ast.Call) and isinstance(no.func, ast.Name):
                assert no.func.id not in CHAMADAS_PROIBIDAS, f"{nome}.py chama {no.func.id}()"
