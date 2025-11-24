"""Production entry point for running the FastAPI app under Uvicorn."""

from __future__ import annotations

import os

import uvicorn


def main() -> None:
    """Boot the FastAPI app with sensible defaults for containers."""
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    workers = int(os.getenv("UVICORN_WORKERS", "2"))
    log_level = os.getenv("UVICORN_LOG_LEVEL", "info")

    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=False,
        workers=workers,
        log_level=log_level,
    )


if __name__ == "__main__":
    main()
