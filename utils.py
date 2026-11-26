"""Funções auxiliares compartilhadas: respostas JSON, autenticação, CSRF, validação e uploads."""
import re
import secrets
import uuid
from datetime import datetime
from functools import wraps
from pathlib import Path
from urllib.parse import quote

from flask import current_app, g, jsonify, redirect, request, session

USERNAME_RE = re.compile(r"^[A-Za-z0-9_.]{3,30}$")


# ---------- respostas ----------
def erro(mensagem, status=400):
    return jsonify({"erro": mensagem}), status


# ---------- autenticação ----------
def login_required(func):
    """Exige usuário autenticado. APIs respondem 401; páginas redirecionam ao login."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        if g.get("usuario") is None:
            if request.path.startswith("/api/"):
                return erro("É necessário estar autenticado.", 401)
            destino = request.full_path.rstrip("?")
            return redirect("/telaLogin.html?next=" + quote(destino, safe=""))
        return func(*args, **kwargs)
    return wrapper


def destino_seguro(url, padrao="/telaHome.html"):
    """Aceita apenas caminhos locais (evita open redirect)."""
    if (isinstance(url, str) and url.startswith("/") and not url.startswith("//")
            and "\\" not in url and url.isprintable()):
        return url
    return padrao


# ---------- CSRF ----------
def csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    return session["csrf_token"]


def csrf_valido():
    enviado = request.headers.get("X-CSRF-Token", "")
    esperado = session.get("csrf_token", "")
    return bool(esperado) and secrets.compare_digest(enviado.encode(), esperado.encode())


# ---------- validação / formatação ----------
def texto_limpo(valor):
    """Remove bytes nulos e espaços nas pontas. Valores que não são texto viram ''."""
    if not isinstance(valor, str):
        return ""
    return valor.replace("\x00", "").strip()


def formatar_datahora(valor):
    if isinstance(valor, datetime):
        return valor.strftime("%d/%m/%Y %H:%M")
    return str(valor or "")


def inteiro_positivo(valor, padrao=None):
    try:
        n = int(valor)
    except (TypeError, ValueError):
        return padrao
    return n if n > 0 else padrao


# ---------- URLs de arquivos ----------
def url_upload(caminho):
    return f"/uploads/{caminho}"


def foto_url(caminho):
    return url_upload(caminho) if caminho else "/img/usuarioSemFoto.jpg"


def imagem_clube_url(caminho):
    return url_upload(caminho) if caminho else "/img/imgclube1.jpg"


# ---------- uploads de imagem ----------
def _detectar_tipo_imagem(dados):
    """Identifica o formato pelos primeiros bytes (não confia no nome nem no Content-Type)."""
    if dados.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if dados.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if dados[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    if dados[:4] == b"RIFF" and dados[8:12] == b"WEBP":
        return "webp"
    return None


def salvar_imagem(arquivo, subpasta):
    """Valida e grava a imagem. Devolve o caminho relativo (ex.: 'posts/ab12.jpg').

    Levanta ValueError com mensagem amigável se o arquivo for inválido.
    O nome final é gerado pelo servidor (uuid + extensão detectada).
    """
    cfg = current_app.config
    nome = arquivo.filename or ""
    extensao = nome.rsplit(".", 1)[-1].lower() if "." in nome else ""
    if extensao not in cfg["EXTENSOES_PERMITIDAS"]:
        raise ValueError("Formato de imagem não permitido. Use JPG, PNG, GIF ou WEBP.")

    limite = cfg["MAX_IMAGEM_BYTES"]
    dados = arquivo.stream.read(limite + 1)
    if not dados:
        raise ValueError("O arquivo de imagem está vazio.")
    if len(dados) > limite:
        raise ValueError(f"A imagem excede o limite de {limite // (1024 * 1024)} MB.")
    tipo = _detectar_tipo_imagem(dados)
    if tipo is None:
        raise ValueError("O arquivo enviado não é uma imagem válida.")

    pasta = Path(cfg["UPLOAD_FOLDER"]) / subpasta
    pasta.mkdir(parents=True, exist_ok=True)
    nome_seguro = f"{uuid.uuid4().hex}.{tipo}"
    (pasta / nome_seguro).write_bytes(dados)
    return f"{subpasta}/{nome_seguro}"


def remover_arquivos(caminhos):
    """Apaga arquivos de upload (somente dentro da pasta de uploads)."""
    base = Path(current_app.config["UPLOAD_FOLDER"]).resolve()
    for caminho in caminhos:
        if not caminho:
            continue
        alvo = (base / caminho).resolve()
        if base in alvo.parents and alvo.is_file():
            try:
                alvo.unlink()
            except OSError:
                pass
