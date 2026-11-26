"""Comentários: listar, comentar e excluir os próprios (sem respostas aninhadas)."""
from flask import Blueprint, g, jsonify, request

from database import queries
from database.connection import commit, consultar_todos, consultar_um, executar
from utils import erro, foto_url, formatar_datahora, login_required, texto_limpo

bp = Blueprint("comentario", __name__)

TEXTO_MAX = 500


def _como_json(c):
    return {
        "id": c["id_comentario"],
        "texto": c["texto"],
        "data": formatar_datahora(c["data_comentario"]),
        "autor": {"username": c["username"], "foto": foto_url(c["foto_perfil"])},
        "meu": c["id_usuario"] == g.usuario["id_usuario"],
    }


_SELECT = """SELECT c.id_comentario, c.id_usuario, c.texto, c.data_comentario, u.username, u.foto_perfil
               FROM tb_comentario c JOIN tb_usuario u ON u.id_usuario = c.id_usuario"""


@bp.get("/api/publicacoes/<int:id_pub>/comentarios")
@login_required
def listar(id_pub):
    if queries.publicacao_existe(id_pub) is None:
        return erro("Publicação não encontrada.", 404)
    linhas = consultar_todos(
        _SELECT + " WHERE c.id_publicacao = %s ORDER BY c.data_comentario, c.id_comentario LIMIT 200",
        (id_pub,))
    return jsonify([_como_json(c) for c in linhas])


@bp.post("/api/publicacoes/<int:id_pub>/comentarios")
@login_required
def comentar(id_pub):
    if queries.publicacao_existe(id_pub) is None:
        return erro("Publicação não encontrada.", 404)
    dados = request.get_json(silent=True) or {}
    texto = texto_limpo(dados.get("texto"))
    if not texto:
        return erro("Escreva um comentário.")
    if len(texto) > TEXTO_MAX:
        return erro(f"O comentário pode ter no máximo {TEXTO_MAX} caracteres.")
    id_com, _ = executar(
        "INSERT INTO tb_comentario (id_publicacao, id_usuario, texto) VALUES (%s, %s, %s)",
        (id_pub, g.usuario["id_usuario"], texto))
    commit()
    novo = consultar_um(_SELECT + " WHERE c.id_comentario = %s", (id_com,))
    total = consultar_um("SELECT COUNT(*) AS t FROM tb_comentario WHERE id_publicacao = %s", (id_pub,))["t"]
    return jsonify({"ok": True, "comentario": _como_json(novo), "total": total}), 201


@bp.delete("/api/comentarios/<int:id_com>")
@login_required
def excluir(id_com):
    com = consultar_um("SELECT id_usuario, id_publicacao FROM tb_comentario WHERE id_comentario = %s", (id_com,))
    if com is None:
        return erro("Comentário não encontrado.", 404)
    if com["id_usuario"] != g.usuario["id_usuario"]:
        return erro("Você só pode excluir os seus próprios comentários.", 403)
    executar("DELETE FROM tb_comentario WHERE id_comentario = %s AND id_usuario = %s",
             (id_com, g.usuario["id_usuario"]))
    commit()
    total = consultar_um("SELECT COUNT(*) AS t FROM tb_comentario WHERE id_publicacao = %s",
                         (com["id_publicacao"],))["t"]
    return jsonify({"ok": True, "total": total})
