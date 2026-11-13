import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# Database configuration
DATABASE_PATH = Path(
    os.getenv("DATABASE_PATH", str(BASE_DIR / "data" / "sankalit.db"))
)

# Ollama configuration
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:1.7b")
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")

# Security and JWT configuration
# Minimum 32-character key for HS256 to prevent InsecureKeyLengthWarning
DEFAULT_SECRET_KEY = "sankalit-intelligence-secure-offline-jwt-secret-key-32bytes"
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", DEFAULT_SECRET_KEY)
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

# Account security & rate limiting
MAX_LOGIN_ATTEMPTS = int(os.getenv("MAX_LOGIN_ATTEMPTS", "5"))
LOCKOUT_DURATION_MINUTES = int(os.getenv("LOCKOUT_DURATION_MINUTES", "15"))

# Registration policy: If true, allows public user self-registration as EMPLOYEE.
# If false, only SUPER_ADMIN / ADMIN can create accounts (except bootstrap first user).
ALLOW_OPEN_REGISTRATION = os.getenv("ALLOW_OPEN_REGISTRATION", "false").lower() in ("true", "1", "yes")

# Upload limits
MAX_UPLOAD_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB

