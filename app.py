"""SocialNET - aplicação Flask. Inicie com:  python app.py   (ou)   flask run"""
import os

from flask import Flask, g, request, session
from werkzeug.exceptions import HTTPException

import utils
from config import Config
from database import connection, queries

MENSAGENS_HTTP = {
    400: "Requisição inválida.",
    403: "Ação não permitida.",
    404: "Não encontrado.",
    405: "Método não permitido.",
    413: "O envio é grande demais. Reduza o tamanho das imagens.",
}


def create_app(config_class=Config):
    # static_url_path="" mantém as URLs originais da interface (/style.css, /script.js, /img/...)
    app = Flask(__name__, static_folder="static", static_url_path="", template_folder="templates")
    app.config.from_object(config_class)

    if not app.config.get("SECRET_KEY"):
        raise RuntimeError("Defina SECRET_KEY no arquivo .env (veja .env.example).")

    connection.init_app(app)

    # ---------- blueprints ----------
    from routes import auth, comentario, comunidade, curtida, feed, publicacao
    for modulo in (auth, comunidade, publicacao, feed, curtida, comentario):
        app.register_blueprint(modulo.bp)

    # ---------- templates ----------
    app.jinja_env.filters["datahora"] = utils.formatar_datahora
    app.jinja_env.globals.update(csrf_token=utils.csrf_token)

    @app.context_processor
    def contexto_padrao():
        return {
            "usuario": g.get("usuario"),
            "foto_url": utils.foto_url,
            "url_upload": utils.url_upload,
            "imagem_clube_url": utils.imagem_clube_url,
        }

    # ---------- antes de cada requisição ----------
    @app.before_request
    def proteger_e_identificar():
        if request.endpoint == "static":
            return None
        # CSRF: toda requisição que altera dados precisa do token da sessão
        if request.method not in ("GET", "HEAD", "OPTIONS") and not utils.csrf_valido():
            return utils.erro("Sessão expirada ou token inválido. Recarregue a página.", 403)
        # O usuário autenticado vem SEMPRE da sessão do servidor (nunca de IDs enviados pelo frontend)
        g.usuario = None
        id_usuario = session.get("id_usuario")
        if id_usuario:
            g.usuario = queries.buscar_usuario(id_usuario)
            if g.usuario is None:
                session.clear()
        return None

    # ---------- cabeçalhos de segurança ----------
    @app.after_request
    def cabecalhos_seguranca(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "same-origin")
        resp.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src https://fonts.gstatic.com; img-src 'self' data: blob:; "
            "connect-src 'self'; object-src 'none'; base-uri 'self'; "
            "form-action 'self'; frame-ancestors 'none'",
        )
        return resp

    # ---------- erros ----------
    @app.errorhandler(Exception)
    def tratar_erro(e):
        if isinstance(e, HTTPException):
            codigo, mensagem = e.code, MENSAGENS_HTTP.get(e.code, e.description)
        else:
            app.logger.exception("Erro não tratado")
            codigo, mensagem = 500, "Erro interno do servidor."
        if request.path.startswith("/api/"):
            return utils.erro(mensagem, codigo)
        return mensagem, codigo

    return app


if __name__ != "__main__":
    app = create_app()  # usado por "flask run" ou servidores WSGI

if __name__ == "__main__":
    app = create_app()
    app.run(host="127.0.0.1", port=5000, debug=os.environ.get("FLASK_DEBUG") == "1")
