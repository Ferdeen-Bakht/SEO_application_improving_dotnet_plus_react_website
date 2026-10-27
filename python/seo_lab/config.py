"""Central configuration. Keep secrets in .env, never commit them."""
import os
from pathlib import Path
from dotenv import load_dotenv

PYTHON_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = PYTHON_DIR.parent
load_dotenv(PYTHON_DIR / ".env")

DOTNET_BASE_URL = os.getenv("DOTNET_BASE_URL", "http://127.0.0.1:5055").rstrip("/")
DOTNET_API_KEY = os.getenv("DOTNET_API_KEY", "local-dev-change-me")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:4b")
DB_PATH_RAW = os.getenv("SEO_DB_PATH", "../data/seo_lab.db")
DB_PATH = (PYTHON_DIR / DB_PATH_RAW).resolve() if not Path(DB_PATH_RAW).is_absolute() else Path(DB_PATH_RAW)
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
