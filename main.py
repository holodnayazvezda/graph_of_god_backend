from __future__ import annotations

import sys
from pathlib import Path

import uvicorn

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from graph_of_god_backend.app import create_app
from graph_of_god_backend.core.config import AppConfig

app = create_app()


def main() -> None:
    config = AppConfig.from_env()
    uvicorn.run(
        app,
        host=config.api_host,
        port=config.api_port,
        reload=False,
    )


if __name__ == "__main__":
    main()
