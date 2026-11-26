"""Cria/recria o banco do SocialNET executando database/init.sql com o PyMySQL.

Uso:  python init_db.py
(usa as credenciais do arquivo .env; dispensa o cliente de linha de comando 'mysql')
"""
import sys
from pathlib import Path

import pymysql

from config import Config

ARQUIVO_SQL = Path(__file__).resolve().parent / "database" / "init.sql"


def separar_comandos(texto):
    """Divide o script em comandos, ignorando linhas de comentário '--'."""
    linhas = [l for l in texto.splitlines() if not l.strip().startswith("--")]
    return [c.strip() for c in "\n".join(linhas).split(";") if c.strip()]


def executar_script(conexao, caminho=ARQUIVO_SQL, ignorar_create_use=False):
    comandos = separar_comandos(Path(caminho).read_text(encoding="utf-8"))
    with conexao.cursor() as cur:
        for cmd in comandos:
            inicio = cmd.upper().split(None, 1)[0]
            if ignorar_create_use and (cmd.upper().startswith("CREATE DATABASE") or inicio == "USE"):
                continue
            cur.execute(cmd)
    conexao.commit()


def main():
    try:
        conexao = pymysql.connect(
            host=Config.DB_HOST, port=Config.DB_PORT, user=Config.DB_USER,
            password=Config.DB_PASSWORD, charset="utf8mb4",
        )
    except pymysql.MySQLError as e:
        sys.exit(f"Não foi possível conectar ao MySQL: {e}\nConfira o arquivo .env.")
    with conexao:
        executar_script(conexao)
    print("Banco 'socialnet' criado com as tabelas e os clubes iniciais.")


if __name__ == "__main__":
    main()
