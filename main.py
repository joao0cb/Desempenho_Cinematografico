"""Ponto de entrada (CLI). Orquestra: db.ler_filmes -> núcleo puro -> formatacao.

Módulo com I/O (terminal).
"""
from __future__ import annotations

from typing import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    """Interpreta os argumentos, executa a análise pedida e devolve o código de saída."""
    raise NotImplementedError


if __name__ == "__main__":
    raise SystemExit(main())
