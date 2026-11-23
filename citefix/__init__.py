"""citefix: check that each citation exists, supports the sentence it is attached to,
and suggest a real paper when it does not."""

import os
from pathlib import Path

__version__ = "0.1.0"


def _load_dotenv(path: Path) -> None:
    """Read KEY=VALUE lines from the project's .env into os.environ, never overriding what is set."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            if value.strip():
                os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


_load_dotenv(Path(__file__).resolve().parents[1] / ".env")
