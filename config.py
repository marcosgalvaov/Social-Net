"""Configurações da aplicação. Valores sensíveis vêm de variáveis de ambiente (.env)."""
import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _bool(nome, padrao="0"):
    return os.environ.get(nome, padrao).strip().lower() in ("1", "true", "sim", "yes")


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY")

    # Banco de dados (nunca vão para o frontend nem para o repositório)
    DB_HOST = os.environ.get("DB_HOST", "localhost")
    DB_PORT = int(os.environ.get("DB_PORT", "3306"))
    DB_USER = os.environ.get("DB_USER", "root")
    DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
    DB_NAME = os.environ.get("DB_NAME", "socialnet")

    # Sessão / cookies
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _bool("SESSION_COOKIE_SECURE")
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)

    # Uploads (ficam FORA de static/, em disco; no banco só vai o caminho relativo)
    UPLOAD_FOLDER = BASE_DIR / "uploads"
    MAX_CONTENT_LENGTH = 12 * 1024 * 1024      # tamanho máximo de uma requisição inteira
    MAX_IMAGEM_BYTES = 5 * 1024 * 1024         # tamanho máximo de cada imagem
    MAX_IMAGENS_POR_POSTAGEM = 4
    EXTENSOES_PERMITIDAS = {"jpg", "jpeg", "png", "gif", "webp"}

    # Regras de negócio
    PUBLICACOES_POR_PAGINA = 10
