"""Conexão com o MySQL via PyMySQL (uma conexão por requisição) e helpers de SQL.

Todas as consultas usam parâmetros (%s) — nunca concatenar valores do usuário no SQL.
"""
import pymysql
from flask import current_app, g
from pymysql.cursors import DictCursor

ERRO_DUPLICADO = 1062  # código do MySQL para violação de chave única/primária


def get_db():
    if "db" not in g:
        cfg = current_app.config
        g.db = pymysql.connect(
            host=cfg["DB_HOST"], port=cfg["DB_PORT"], user=cfg["DB_USER"],
            password=cfg["DB_PASSWORD"], database=cfg["DB_NAME"],
            charset="utf8mb4", cursorclass=DictCursor, autocommit=False,
        )
    return g.db


def close_db(_erro=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()  # sem commit explícito, a transação pendente é descartada


def init_app(app):
    app.teardown_appcontext(close_db)


def consultar_um(sql, params=()):
    with get_db().cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()


def consultar_todos(sql, params=()):
    with get_db().cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def executar(sql, params=()):
    """Executa INSERT/UPDATE/DELETE. Retorna (último id inserido, linhas afetadas). Não faz commit."""
    with get_db().cursor() as cur:
        cur.execute(sql, params)
        return cur.lastrowid, cur.rowcount


def commit():
    get_db().commit()


def rollback():
    get_db().rollback()


def eh_duplicado(erro):
    """True se a exceção do PyMySQL é uma violação de unicidade."""
    return isinstance(erro, pymysql.err.IntegrityError) and erro.args and erro.args[0] == ERRO_DUPLICADO
