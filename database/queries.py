"""Consultas SQL reutilizadas por várias rotas (todas parametrizadas)."""
from database.connection import consultar_todos, consultar_um


# ---------- usuários ----------
def buscar_usuario(id_usuario):
    return consultar_um(
        "SELECT id_usuario, username, foto_perfil FROM tb_usuario WHERE id_usuario = %s",
        (id_usuario,),
    )


# ---------- comunidades ----------
def _escapar_like(texto):
    return texto.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def listar_comunidades(busca=None, limite=100):
    sql = """SELECT c.id_comunidade, c.nome, c.descricao, c.imagem, c.data_criacao,
                    (SELECT COUNT(*) FROM tb_participante pa
                      WHERE pa.id_comunidade = c.id_comunidade) AS total_participantes
               FROM tb_comunidade c"""
    params = []
    if busca:
        sql += " WHERE c.nome LIKE %s"
        params.append("%" + _escapar_like(busca) + "%")
    sql += " ORDER BY c.id_comunidade LIMIT %s"
    params.append(limite)
    return consultar_todos(sql, params)


def buscar_comunidade(id_comunidade):
    return consultar_um(
        """SELECT c.id_comunidade, c.nome, c.descricao, c.imagem, c.id_criador, c.data_criacao,
                  (SELECT COUNT(*) FROM tb_participante pa
                    WHERE pa.id_comunidade = c.id_comunidade) AS total_participantes
             FROM tb_comunidade c WHERE c.id_comunidade = %s""",
        (id_comunidade,),
    )


def buscar_comunidade_por_nome(nome):
    return consultar_um(
        "SELECT id_comunidade, nome FROM tb_comunidade WHERE nome = %s", (nome,)
    )


def comunidades_do_usuario(id_usuario):
    return consultar_todos(
        """SELECT c.id_comunidade, c.nome, c.imagem
             FROM tb_participante p
             JOIN tb_comunidade c ON c.id_comunidade = p.id_comunidade
            WHERE p.id_usuario = %s
            ORDER BY c.nome""",
        (id_usuario,),
    )


def eh_participante(id_usuario, id_comunidade):
    return consultar_um(
        "SELECT 1 AS ok FROM tb_participante WHERE id_usuario = %s AND id_comunidade = %s",
        (id_usuario, id_comunidade),
    ) is not None


# ---------- publicações / feeds ----------
def listar_publicacoes(id_usuario, id_comunidade=None, apenas_participando=False,
                       pagina=1, por_pagina=10):
    """Feed em ordem cronológica inversa.

    - id_comunidade: feed de uma comunidade específica.
    - apenas_participando: feed principal (só comunidades das quais o usuário participa).
    Retorna (lista de publicações, existe_proxima_pagina).
    """
    sql = """
        SELECT p.id_publicacao, p.texto, p.data_publicacao, p.id_usuario AS id_autor,
               u.username, u.foto_perfil,
               c.id_comunidade, c.nome AS comunidade,
               (SELECT COUNT(*) FROM tb_curtida cu
                 WHERE cu.id_publicacao = p.id_publicacao) AS total_curtidas,
               (SELECT COUNT(*) FROM tb_comentario co
                 WHERE co.id_publicacao = p.id_publicacao) AS total_comentarios,
               EXISTS(SELECT 1 FROM tb_curtida cm
                       WHERE cm.id_publicacao = p.id_publicacao
                         AND cm.id_usuario = %s) AS curtiu
          FROM tb_publicacao p
          JOIN tb_usuario u    ON u.id_usuario = p.id_usuario
          JOIN tb_comunidade c ON c.id_comunidade = p.id_comunidade
    """
    params = [id_usuario]
    if apenas_participando:
        sql += " JOIN tb_participante pa ON pa.id_comunidade = p.id_comunidade AND pa.id_usuario = %s"
        params.append(id_usuario)
    if id_comunidade is not None:
        sql += " WHERE p.id_comunidade = %s"
        params.append(id_comunidade)
    sql += " ORDER BY p.data_publicacao DESC, p.id_publicacao DESC LIMIT %s OFFSET %s"
    params += [por_pagina + 1, (pagina - 1) * por_pagina]

    linhas = list(consultar_todos(sql, params))
    tem_mais = len(linhas) > por_pagina
    linhas = linhas[:por_pagina]

    imagens = _imagens_das_publicacoes([l["id_publicacao"] for l in linhas])
    for l in linhas:
        l["curtiu"] = bool(l["curtiu"])
        l["imagens"] = imagens.get(l["id_publicacao"], [])
    return linhas, tem_mais


def _imagens_das_publicacoes(ids):
    if not ids:
        return {}
    marcadores = ", ".join(["%s"] * len(ids))  # só gera "%s, %s, ..."; os valores vão como parâmetros
    linhas = consultar_todos(
        f"SELECT id_publicacao, caminho FROM tb_imagem WHERE id_publicacao IN ({marcadores}) "
        "ORDER BY id_publicacao, ordem, id_imagem",
        ids,
    )
    resultado = {}
    for l in linhas:
        resultado.setdefault(l["id_publicacao"], []).append(l["caminho"])
    return resultado


def publicacao_existe(id_publicacao):
    return consultar_um(
        "SELECT id_publicacao, id_usuario FROM tb_publicacao WHERE id_publicacao = %s",
        (id_publicacao,),
    )


def contar_curtidas(id_publicacao):
    return consultar_um(
        "SELECT COUNT(*) AS total FROM tb_curtida WHERE id_publicacao = %s", (id_publicacao,)
    )["total"]
