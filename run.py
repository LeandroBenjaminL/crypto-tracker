"""
Lanzador — arranca la API y el dashboard juntos.

Uso:
    python run.py

Esto levanta:
  - FastAPI en http://localhost:8000 (docs en /docs)
  - Streamlit en http://localhost:8501
"""

from __future__ import annotations

import atexit
import subprocess
import sys
import time

_API_PORT = 8000
_STREAMLIT_PORT = 8501

procs: list[subprocess.Popen] = []


def _cleanup() -> None:
    for p in procs:
        p.terminate()
        try:
            p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            p.kill()


atexit.register(_cleanup)


def _wait_for_api(timeout: float = 15.0) -> bool:
    """Espera hasta timeout segundos a que la API responda."""
    import urllib.request

    start = time.monotonic()
    while time.monotonic() - start < timeout:
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{_API_PORT}/api/health", timeout=1
            ):
                return True
        except Exception:
            time.sleep(0.3)
    return False


def main() -> None:
    print("🚀 Arrancando Crypto Tracker...\n")

    # 1. FastAPI
    print(f"  • API  → http://localhost:{_API_PORT}")
    print(f"           http://localhost:{_API_PORT}/docs (OpenAPI)")
    api = subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn",
            "src.api.server:app",
            "--host", "127.0.0.1",
            "--port", str(_API_PORT),
            "--log-level", "warning",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    procs.append(api)

    if not _wait_for_api():
        print("❌ La API no arrancó. Revisá que fastapi/uvicorn estén instalados:")
        print("   pip install -e '.[dev]'")
        _cleanup()
        sys.exit(1)

    print(f"  ✓ API lista\n")

    # 2. Streamlit
    print(f"  • Dashboard → http://localhost:{_STREAMLIT_PORT}")
    streamlit_proc = subprocess.Popen(
        [
            sys.executable, "-m", "streamlit", "run", "app.py",
            "--server.port", str(_STREAMLIT_PORT),
            "--server.headless", "true",
        ],
    )
    procs.append(streamlit_proc)
    streamlit_proc.wait()  # bloquea hasta que Streamlit termine


if __name__ == "__main__":
    main()
