"""
Regression guard for the Streamlit/FastAPI import decoupling (branch
``fix/streamlit-fastapi-decouple``).

The outage this protects against: ``app/main.py`` on Python 3.14 crashed because
it transitively imported ``fastapi`` / ``pydantic`` / ``starlette`` / ``jose`` /
``openai`` through ``src.api.*``. The fix moved the framework-free helpers into
``src.passwords`` / ``src.user_sessions`` and made ``openai`` a lazy import in
``src.rag``.

If any of these tests fail, the Streamlit app has regained a hard dependency on
the FastAPI stack and will crash on a machine where that stack does not import.

Each check runs in a clean subprocess interpreter: the pytest process itself has
FastAPI loaded (``conftest.py`` does ``from src.api.main import app``), so an
in-process ``sys.modules`` check would be meaningless.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Modules ``app/main.py`` imports from ``src/``. None of them may pull in the
# FastAPI/Pydantic/OpenAI stack at import time.
STREAMLIT_SRC_IMPORTS = [
    "src.passwords",
    "src.user_sessions",
    "src.vocab_export",
    "src.dictionary",
    "src.rag",
    "src.models",
]

# Heavy / framework modules that must NOT be imported as a side effect.
FORBIDDEN = ["fastapi", "pydantic", "starlette", "jose", "openai"]


def _run_import_probe(import_lines: str, check_modules: list[str]) -> list[str]:
    """
    Import ``import_lines`` in a fresh interpreter and return which of
    ``check_modules`` ended up in ``sys.modules``.

    Args:
        import_lines: Python source executed after a clean start.
        check_modules: Top-level module names to look for afterwards.

    Returns:
        The subset of ``check_modules`` present in the child's ``sys.modules``.
    """
    probe = (
        "import sys\n"
        f"{import_lines}\n"
        f"found = [m for m in {check_modules!r} if m in sys.modules]\n"
        'print(",".join(found))\n'
    )
    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, (
        f"import probe failed:\nstdout={result.stdout}\nstderr={result.stderr}"
    )
    line = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else ""
    return [m for m in line.split(",") if m]


def test_streamlit_src_imports_do_not_pull_in_fastapi_stack() -> None:
    """If this fails, the Streamlit app crashes on any environment where the
    FastAPI/Pydantic/OpenAI stack does not import (the Python 3.14 outage)."""
    import_lines = "\n".join(f"import {mod}" for mod in STREAMLIT_SRC_IMPORTS)
    leaked = _run_import_probe(import_lines, FORBIDDEN)
    assert leaked == [], f"Streamlit src imports leaked heavy modules: {leaked}"


def test_rag_imports_without_openai() -> None:
    """``src.rag`` is imported on every Streamlit page load for
    ``is_semantic_search_available``; ``openai`` must stay a lazy import inside
    ``get_client()`` so the page does not pay for (or crash on) the SDK."""
    leaked = _run_import_probe("import src.rag", ["openai"])
    assert leaked == [], "src.rag imported openai at module load time"


def test_passwords_module_is_framework_free() -> None:
    """``src.passwords`` is the Streamlit login/register hashing path; importing
    it must not drag in FastAPI or Pydantic."""
    leaked = _run_import_probe("import src.passwords", FORBIDDEN)
    assert leaked == [], f"src.passwords leaked: {leaked}"


def test_user_sessions_module_is_framework_free() -> None:
    """``src.user_sessions`` resolves anonymous sessions for the Streamlit app;
    importing it must not drag in the FastAPI request stack."""
    leaked = _run_import_probe("import src.user_sessions", FORBIDDEN)
    assert leaked == [], f"src.user_sessions leaked: {leaked}"
