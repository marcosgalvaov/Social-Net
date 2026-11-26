"""Cadastro, login, logout e verificação de sessão."""
import pymysql
from flask import Blueprint, g, jsonify, redirect, render_template, request, session
from werkzeug.security import check_password_hash, generate_password_hash

from database.connection import commit, consultar_um, eh_duplicado, executar
from utils import (USERNAME_RE, destino_seguro, erro, foto_url, login_required,
                   remover_arquivos, salvar_imagem, texto_limpo)

bp = Blueprint("auth", __name__)

# Hash fictício: comparado quando o username não existe, para o tempo de resposta não revelar isso
_HASH_FALSO = generate_password_hash("senha-ficticia-para-igualar-o-tempo")


def _iniciar_sessao(id_usuario):
    session.clear()  # evita fixação de sessão
    session["id_usuario"] = id_usuario
    session.permanent = True


# ---------- páginas ----------
@bp.get("/")
@bp.get("/index.html")
def pagina_inicial():
    return render_template("index.html")


@bp.get("/telaLogin.html")
def pagina_login():
    if g.usuario:
        return redirect("/telaHome.html")
    return render_template("telaLogin.html", next=destino_seguro(request.args.get("next")))


@bp.get("/telaCadastro.html")
def pagina_cadastro():
    if g.usuario:
        return redirect("/telaHome.html")
    return render_template("telaCadastro.html")


# ---------- API ----------
@bp.post("/api/auth/cadastro")
def cadastro():
    username = texto_limpo(request.form.get("username"))
    senha = request.form.get("senha") or ""
    foto = request.files.get("foto")

    if not USERNAME_RE.match(username):
        return erro("O username deve ter de 3 a 30 caracteres: letras, números, ponto ou _.")
    if len(senha) < 8:
        return erro("A senha deve ter pelo menos 8 caracteres.")
    if len(senha) > 128:
        return erro("A senha deve ter no máximo 128 caracteres.")
    if consultar_um("SELECT 1 AS ok FROM tb_usuario WHERE username = %s", (username,)):
        return erro("Este username já está em uso.", 409)

    caminho_foto = None
    if foto and foto.filename:
        try:
            caminho_foto = salvar_imagem(foto, "perfis")
        except ValueError as e:
            return erro(str(e))

    try:
        id_usuario, _ = executar(
            "INSERT INTO tb_usuario (username, senha_hash, foto_perfil) VALUES (%s, %s, %s)",
            (username, generate_password_hash(senha), caminho_foto),
        )
        commit()
    except pymysql.MySQLError as e:
        remover_arquivos([caminho_foto])
        if eh_duplicado(e):
            return erro("Este username já está em uso.", 409)
        raise

    _iniciar_sessao(id_usuario)
    return jsonify({"ok": True, "redirecionar": "/telaHome.html"}), 201


@bp.post("/api/auth/login")
def login():
    dados = request.get_json(silent=True) or {}
    username = texto_limpo(dados.get("username"))
    senha = dados.get("senha") if isinstance(dados.get("senha"), str) else ""

    usuario = consultar_um(
        "SELECT id_usuario, senha_hash FROM tb_usuario WHERE username = %s", (username,)
    )
    senha_ok = check_password_hash(usuario["senha_hash"] if usuario else _HASH_FALSO, senha)
    if not usuario or not senha_ok:
        return erro("Username ou senha inválidos.", 401)

    _iniciar_sessao(usuario["id_usuario"])
    return jsonify({"ok": True, "redirecionar": destino_seguro(dados.get("next"))})


@bp.post("/api/auth/logout")
def logout():
    session.clear()
    return jsonify({"ok": True, "redirecionar": "/"})


@bp.post("/api/auth/foto")
@login_required
def alterar_foto():
    arquivo = request.files.get("foto")
    if not arquivo or not arquivo.filename:
        return erro("Selecione uma imagem.")
    try:
        nova = salvar_imagem(arquivo, "perfis")
    except ValueError as e:
        return erro(str(e))
    antiga = g.usuario["foto_perfil"]
    try:
        executar("UPDATE tb_usuario SET foto_perfil = %s WHERE id_usuario = %s",
                 (nova, g.usuario["id_usuario"]))
        commit()
    except pymysql.MySQLError:
        remover_arquivos([nova])
        raise
    remover_arquivos([antiga])
    return jsonify({"ok": True, "foto": foto_url(nova)})


@bp.get("/api/auth/me")
def me():
    if not g.usuario:
        return erro("Não autenticado.", 401)
    return jsonify({
        "id_usuario": g.usuario["id_usuario"],
        "username": g.usuario["username"],
        "foto": foto_url(g.usuario["foto_perfil"]),
    })
