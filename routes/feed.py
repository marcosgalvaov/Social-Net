"""Home e feeds: feed principal (clubes do usuário) e feed individual de cada clube."""
from flask import Blueprint, abort, current_app, g, jsonify, render_template, request

from database import queries
from utils import (erro, foto_url, formatar_datahora, inteiro_positivo, login_required,
                   url_upload)

bp = Blueprint("feed", __name__)


def _buscar_feed(id_clube_arg, pagina_arg):
    """Devolve (clube ou None, publicações, tem_mais, pagina). Aborta 404 se o clube não existe."""
    pagina = inteiro_positivo(pagina_arg, 1)
    por_pagina = current_app.config["PUBLICACOES_POR_PAGINA"]
    clube = None
    if id_clube_arg not in (None, ""):
        id_clube = inteiro_positivo(id_clube_arg)
        clube = queries.buscar_comunidade(id_clube) if id_clube else None
        if clube is None:
            abort(404)
    publicacoes, tem_mais = queries.listar_publicacoes(
        g.usuario["id_usuario"],
        id_comunidade=clube["id_comunidade"] if clube else None,
        apenas_participando=clube is None,   # sem clube = feed principal
        pagina=pagina, por_pagina=por_pagina,
    )
    return clube, publicacoes, tem_mais, pagina


@bp.get("/telaHome.html")
@login_required
def pagina_home():
    clubes = queries.comunidades_do_usuario(g.usuario["id_usuario"])
    return render_template("telaHome.html", clubes=clubes)


@bp.get("/telaFeed.html")
@login_required
def pagina_feed():
    clube, publicacoes, tem_mais, pagina = _buscar_feed(request.args.get("clube"), request.args.get("pagina"))
    membro = bool(clube) and queries.eh_participante(g.usuario["id_usuario"], clube["id_comunidade"])
    tem_clubes = bool(queries.comunidades_do_usuario(g.usuario["id_usuario"])) if clube is None else True
    return render_template("telaFeed.html", clube=clube, membro=membro, publicacoes=publicacoes,
                           tem_mais=tem_mais, pagina=pagina, tem_clubes=tem_clubes)


@bp.get("/api/feed")
@login_required
def api_feed():
    clube, publicacoes, tem_mais, pagina = _buscar_feed(request.args.get("clube"), request.args.get("pagina"))
    return jsonify({
        "pagina": pagina,
        "tem_mais": tem_mais,
        "publicacoes": [{
            "id": p["id_publicacao"],
            "texto": p["texto"],
            "data": formatar_datahora(p["data_publicacao"]),
            "autor": {"id": p["id_autor"], "username": p["username"], "foto": foto_url(p["foto_perfil"])},
            "comunidade": {"id": p["id_comunidade"], "nome": p["comunidade"]},
            "imagens": [url_upload(c) for c in p["imagens"]],
            "curtidas": p["total_curtidas"],
            "comentarios": p["total_comentarios"],
            "curtiu": p["curtiu"],
            "minha": p["id_autor"] == g.usuario["id_usuario"],
        } for p in publicacoes],
    })
