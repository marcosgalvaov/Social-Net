"""Comunidades ("Clubes" na interface): listar, ver, criar, participar e sair."""
import pymysql
from flask import Blueprint, abort, g, jsonify, render_template, request

from database import queries
from database.connection import commit, eh_duplicado, executar
from utils import (erro, imagem_clube_url, inteiro_positivo, login_required,
                   remover_arquivos, salvar_imagem, texto_limpo)

bp = Blueprint("comunidade", __name__)

NOME_MAX, DESCRICAO_MAX = 40, 200


def pode_alterar_imagem(clube, id_usuario):
    """O criador altera a imagem do próprio clube. Clubes sem criador (os iniciais) podem ser
    alterados por qualquer participante."""
    if clube["id_criador"] == id_usuario:
        return True
    return clube["id_criador"] is None and queries.eh_participante(id_usuario, clube["id_comunidade"])


def _resumo(c):
    return {"id": c["id_comunidade"], "nome": c["nome"], "descricao": c["descricao"],
            "imagem": imagem_clube_url(c["imagem"]),
            "participantes": c["total_participantes"]}


# ---------- páginas ----------
@bp.get("/telaClubes.html")
@login_required
def pagina_clubes():
    busca = texto_limpo(request.args.get("q"))[:NOME_MAX]
    return render_template("telaClubes.html", clubes=queries.listar_comunidades(busca), busca=busca)


@bp.get("/tela-desc-clube.html")
@login_required
def pagina_descricao_clube():
    id_clube = inteiro_positivo(request.args.get("id"))
    clube = queries.buscar_comunidade(id_clube) if id_clube else None
    if clube is None:
        abort(404)
    membro = queries.eh_participante(g.usuario["id_usuario"], id_clube)
    return render_template("tela-desc-clube.html", clube=clube, membro=membro,
                           pode_alterar=pode_alterar_imagem(clube, g.usuario["id_usuario"]))


@bp.get("/telaCriar.html")
@login_required
def pagina_criar():
    return render_template("telaCriar.html")


@bp.get("/tela-criar-clube.html")
@login_required
def pagina_criar_clube():
    return render_template("tela-criar-clube.html")


# ---------- API ----------
@bp.get("/api/comunidades")
@login_required
def listar():
    busca = texto_limpo(request.args.get("q"))[:NOME_MAX]
    return jsonify([_resumo(c) for c in queries.listar_comunidades(busca)])


@bp.post("/api/comunidades")
@login_required
def criar():
    nome = texto_limpo(request.form.get("nome"))
    descricao = texto_limpo(request.form.get("descricao"))
    imagem = request.files.get("imagem")

    if len(nome) < 3 or len(nome) > NOME_MAX:
        return erro(f"O nome do clube deve ter de 3 a {NOME_MAX} caracteres.")
    if not descricao or len(descricao) > DESCRICAO_MAX:
        return erro(f"A descrição é obrigatória e deve ter até {DESCRICAO_MAX} caracteres.")
    if queries.buscar_comunidade_por_nome(nome):
        return erro("Já existe um clube com esse nome.", 409)

    caminho = None
    if imagem and imagem.filename:
        try:
            caminho = salvar_imagem(imagem, "clubes")
        except ValueError as e:
            return erro(str(e))

    try:
        id_clube, _ = executar(
            "INSERT INTO tb_comunidade (nome, descricao, imagem, id_criador) VALUES (%s, %s, %s, %s)",
            (nome, descricao, caminho, g.usuario["id_usuario"]),
        )
        # o criador já entra como participante
        executar("INSERT INTO tb_participante (id_usuario, id_comunidade) VALUES (%s, %s)",
                 (g.usuario["id_usuario"], id_clube))
        commit()
    except pymysql.MySQLError as e:
        remover_arquivos([caminho])
        if eh_duplicado(e):
            return erro("Já existe um clube com esse nome.", 409)
        raise
    return jsonify({"ok": True, "id": id_clube, "redirecionar": f"/telaFeed.html?clube={id_clube}"}), 201


@bp.post("/api/comunidades/<int:id_clube>/imagem")
@login_required
def alterar_imagem(id_clube):
    clube = queries.buscar_comunidade(id_clube)
    if clube is None:
        return erro("Clube não encontrado.", 404)
    if not pode_alterar_imagem(clube, g.usuario["id_usuario"]):
        return erro("Você não tem permissão para alterar a imagem deste clube.", 403)
    arquivo = request.files.get("imagem")
    if not arquivo or not arquivo.filename:
        return erro("Selecione uma imagem.")
    try:
        novo = salvar_imagem(arquivo, "clubes")
    except ValueError as e:
        return erro(str(e))
    try:
        executar("UPDATE tb_comunidade SET imagem = %s WHERE id_comunidade = %s", (novo, id_clube))
        commit()
    except pymysql.MySQLError:
        remover_arquivos([novo])
        raise
    remover_arquivos([clube["imagem"]])   # apaga a imagem anterior (se não era a padrão)
    return jsonify({"ok": True, "imagem": imagem_clube_url(novo)})


@bp.post("/api/comunidades/<int:id_clube>/participar")
@login_required
def participar(id_clube):
    if queries.buscar_comunidade(id_clube) is None:
        return erro("Clube não encontrado.", 404)
    try:
        executar("INSERT INTO tb_participante (id_usuario, id_comunidade) VALUES (%s, %s)",
                 (g.usuario["id_usuario"], id_clube))
        commit()
    except pymysql.MySQLError as e:
        if eh_duplicado(e):
            return erro("Você já participa deste clube.", 409)
        raise
    return jsonify({"ok": True, "participa": True, "redirecionar": f"/telaFeed.html?clube={id_clube}"}), 201


@bp.delete("/api/comunidades/<int:id_clube>/participar")
@login_required
def sair(id_clube):
    _, linhas = executar("DELETE FROM tb_participante WHERE id_usuario = %s AND id_comunidade = %s",
                         (g.usuario["id_usuario"], id_clube))
    commit()
    if linhas == 0:
        return erro("Você não participa deste clube.", 404)
    return jsonify({"ok": True, "participa": False})
