"""Curtidas: curtir e remover curtida (a chave primária composta impede duplicidade)."""
import pymysql
from flask import Blueprint, g, jsonify

from database import queries
from database.connection import commit, eh_duplicado, executar
from utils import erro, login_required

bp = Blueprint("curtida", __name__)


def _estado(id_pub, curtiu):
    return jsonify({"ok": True, "curtiu": curtiu, "total": queries.contar_curtidas(id_pub)})


@bp.post("/api/publicacoes/<int:id_pub>/curtir")
@login_required
def curtir(id_pub):
    if queries.publicacao_existe(id_pub) is None:
        return erro("Publicação não encontrada.", 404)
    try:
        executar("INSERT INTO tb_curtida (id_usuario, id_publicacao) VALUES (%s, %s)",
                 (g.usuario["id_usuario"], id_pub))
        commit()
    except pymysql.MySQLError as e:
        if not eh_duplicado(e):   # já curtida: apenas devolve o estado atual (sem duplicar)
            raise
    return _estado(id_pub, True)


@bp.delete("/api/publicacoes/<int:id_pub>/curtir")
@login_required
def descurtir(id_pub):
    if queries.publicacao_existe(id_pub) is None:
        return erro("Publicação não encontrada.", 404)
    executar("DELETE FROM tb_curtida WHERE id_usuario = %s AND id_publicacao = %s",
             (g.usuario["id_usuario"], id_pub))
    commit()
    return _estado(id_pub, False)
