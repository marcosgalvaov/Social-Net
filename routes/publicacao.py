"""Publicações: criar (texto + imagens), excluir e servir os arquivos enviados."""
import pymysql
from flask import Blueprint, abort, current_app, g, jsonify, render_template, request, send_from_directory

from database import queries
from database.connection import commit, consultar_todos, executar
from utils import erro, inteiro_positivo, login_required, remover_arquivos, salvar_imagem, texto_limpo

bp = Blueprint("publicacao", __name__)

TEXTO_MAX = 1000


@bp.get("/tela-criar-postagem.html")
@login_required
def pagina_criar_postagem():
    meus_clubes = queries.comunidades_do_usuario(g.usuario["id_usuario"])
    # pré-preenche o clube quando vem de um feed (?clube=ID) e o usuário participa dele
    id_clube = inteiro_positivo(request.args.get("clube"))
    clube_inicial = next((c["nome"] for c in meus_clubes if c["id_comunidade"] == id_clube), "")
    return render_template("tela-criar-postagem.html", meus_clubes=meus_clubes, clube_inicial=clube_inicial)


@bp.post("/api/publicacoes")
@login_required
def criar():
    cfg = current_app.config
    texto = texto_limpo(request.form.get("texto"))
    arquivos = [a for a in request.files.getlist("imagens") if a and a.filename]

    if len(texto) > TEXTO_MAX:
        return erro(f"O texto pode ter no máximo {TEXTO_MAX} caracteres.")
    if not texto and not arquivos:
        return erro("Escreva algo ou selecione uma imagem para publicar.")
    if len(arquivos) > cfg["MAX_IMAGENS_POR_POSTAGEM"]:
        return erro(f"Envie no máximo {cfg['MAX_IMAGENS_POR_POSTAGEM']} imagens por postagem.")

    # clube informado por id ou pelo nome (campo "Escolher Clube" da interface)
    id_clube = inteiro_positivo(request.form.get("id_comunidade"))
    if id_clube:
        clube = queries.buscar_comunidade(id_clube)
    else:
        nome = texto_limpo(request.form.get("clube"))
        if not nome:
            return erro("Escolha o clube em que deseja publicar.")
        clube = queries.buscar_comunidade_por_nome(nome)
    if clube is None:
        return erro("Clube não encontrado.", 404)
    if not queries.eh_participante(g.usuario["id_usuario"], clube["id_comunidade"]):
        return erro("Você precisa participar do clube para publicar nele.", 403)

    caminhos = []
    try:
        for arquivo in arquivos:
            caminhos.append(salvar_imagem(arquivo, "posts"))
        id_pub, _ = executar(
            "INSERT INTO tb_publicacao (id_usuario, id_comunidade, texto) VALUES (%s, %s, %s)",
            (g.usuario["id_usuario"], clube["id_comunidade"], texto),
        )
        for ordem, caminho in enumerate(caminhos):
            executar("INSERT INTO tb_imagem (id_publicacao, caminho, ordem) VALUES (%s, %s, %s)",
                     (id_pub, caminho, ordem))
        commit()
    except ValueError as e:
        remover_arquivos(caminhos)
        return erro(str(e))
    except pymysql.MySQLError:
        remover_arquivos(caminhos)
        raise
    return jsonify({"ok": True, "id": id_pub,
                    "redirecionar": f"/telaFeed.html?clube={clube['id_comunidade']}"}), 201


@bp.delete("/api/publicacoes/<int:id_pub>")
@login_required
def excluir(id_pub):
    pub = queries.publicacao_existe(id_pub)
    if pub is None:
        return erro("Publicação não encontrada.", 404)
    if pub["id_usuario"] != g.usuario["id_usuario"]:
        return erro("Você só pode excluir as suas próprias publicações.", 403)
    caminhos = [l["caminho"] for l in consultar_todos(
        "SELECT caminho FROM tb_imagem WHERE id_publicacao = %s", (id_pub,))]
    # imagens, curtidas e comentários saem junto (ON DELETE CASCADE)
    executar("DELETE FROM tb_publicacao WHERE id_publicacao = %s AND id_usuario = %s",
             (id_pub, g.usuario["id_usuario"]))
    commit()
    remover_arquivos(caminhos)
    return jsonify({"ok": True})


@bp.get("/uploads/<path:caminho>")
def arquivo_enviado(caminho):
    """Serve apenas imagens enviadas. Nunca executa nada: só devolve bytes com tipo de imagem."""
    extensao = caminho.rsplit(".", 1)[-1].lower() if "." in caminho else ""
    if extensao not in current_app.config["EXTENSOES_PERMITIDAS"]:
        abort(404)
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], caminho)
