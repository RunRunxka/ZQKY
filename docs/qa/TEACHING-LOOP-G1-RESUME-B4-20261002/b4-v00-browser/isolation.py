"""QA-only isolation, checked before any import of standard app.main."""
import os
import sys
import tempfile
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[4]


def isolated_settings():
    if os.environ.get("ZQKY_ENV") != "test":
        raise RuntimeError("Set the outer environment to test before importing main")
    raw = os.environ.get("ZQKY_DATA_DIR", "")
    data = Path(raw)
    temporary = Path(tempfile.gettempdir()).resolve()
    if not raw or not data.is_absolute():
        raise RuntimeError("Explicit absolute newly-owned temporary data root required")
    data = data.resolve()
    if data == temporary or not data.is_relative_to(temporary) or data.is_relative_to(REPOSITORY) or ".local-data" in [p.lower() for p in data.parts]:
        raise RuntimeError("Refusing formal/repository/non-temporary data")
    if not data.parent.name.startswith("zqky-b4-v00-"):
        raise RuntimeError("Only the fresh B4-V00 root is owned")
    if os.environ.get("ZQKY_QDRANT_URL") != "http://127.0.0.1:16333" or os.environ.get("ZQKY_EMBEDDING_BASE_URL") != "http://127.0.0.1:9":
        raise RuntimeError("Explicit offline endpoints required in outer environment")
    empty = data.parent / "empty-textbooks"
    empty.mkdir(parents=True, exist_ok=True)
    if any(empty.iterdir()):
        raise RuntimeError("The isolated textbook source must be empty")
    sys.path.insert(0, str(REPOSITORY / "apps" / "api"))
    # This settings object has no credential path; the default global import is
    # also fenced by the same outer environment and never enters its lifespan.
    from app.core.config import Settings
    return Settings(env="test", data_dir=data, credentials_file=None,
        host="127.0.0.1", port=8001,
        allowed_origins=frozenset({"http://127.0.0.1:5174"}),
        qdrant_url="http://127.0.0.1:16333", embedding_base_url="http://127.0.0.1:9",
        textbook_source_dir=empty)
