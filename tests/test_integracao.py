"""Testes de integração do SocialNET (Flask test client + MySQL real).

Usa um banco SEPARADO (socialnet_teste) e uma pasta de uploads temporária:
nunca toca nos dados do banco 'socialnet'.

Executar na raiz do projeto:   python -m unittest tests.test_integracao -v
(usa as credenciais do .env; o usuário do MySQL precisa poder criar/apagar bancos)
"""
import io
import os
import re
import shutil
import struct
import tempfile
import unittest
import warnings
import zlib
from pathlib import Path

os.environ.setdefault("SECRET_KEY", "chave-somente-para-testes")
warnings.simplefilter("ignore", ResourceWarning)  # o test client do Flask não fecha respostas de arquivos

import pymysql  # noqa: E402

from app import create_app  # noqa: E402
from config import Config  # noqa: E402
from init_db import executar_script  # noqa: E402

BANCO_TESTE = "socialnet_teste"
PASTA_UPLOADS = Path(tempfile.mkdtemp(prefix="socialnet_uploads_"))


class ConfigTeste(Config):
    TESTING = True
    DB_NAME = BANCO_TESTE
    UPLOAD_FOLDER = PASTA_UPLOADS


def png_valido():
    """PNG 1x1 mínimo e válido, gerado na hora."""
    def bloco(tipo, dados):
        corpo = tipo + dados
        return struct.pack(">I", len(dados)) + corpo + struct.pack(">I", zlib.crc32(corpo) & 0xFFFFFFFF)
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    idat = zlib.compress(b"\x00\xff\x00\x00")
    return b"\x89PNG\r\n\x1a\n" + bloco(b"IHDR", ihdr) + bloco(b"IDAT", idat) + bloco(b"IEND", b"")


class Cliente:
    """Cliente de teste que cuida do token CSRF e da sessão."""

    def __init__(self, app):
        self.c = app.test_client()

    def token(self):
        with self.c.session_transaction() as s:
            t = s.get("csrf_token")
        if not t:
            r = self.c.get("/telaLogin.html")
            if r.status_code != 200:               # já logado: a página de login redireciona
                self.c.get("/telaCriar.html")
            with self.c.session_transaction() as s:
                t = s.get("csrf_token")
        return t

    def get(self, url, **kw):
        return self.c.get(url, **kw)

    def post(self, url, json=None, data=None, csrf=True):
        h = {"X-CSRF-Token": self.token()} if csrf else {}
        return self.c.post(url, json=json, data=data, headers=h)

    def delete(self, url, csrf=True):
        h = {"X-CSRF-Token": self.token()} if csrf else {}
        return self.c.delete(url, headers=h)

    def cadastrar(self, username, senha="senha12345", foto=None):
        data = {"username": username, "senha": senha}
        if foto:
            data["foto"] = foto
        return self.post("/api/auth/cadastro", data=data)

    def login(self, username, senha="senha12345", next_=None):
        corpo = {"username": username, "senha": senha}
        if next_:
            corpo["next"] = next_
        return self.post("/api/auth/login", json=corpo)


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        con = pymysql.connect(host=Config.DB_HOST, port=Config.DB_PORT, user=Config.DB_USER,
                              password=Config.DB_PASSWORD, charset="utf8mb4")
        with con.cursor() as cur:
            cur.execute(f"CREATE DATABASE IF NOT EXISTS {BANCO_TESTE} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        con.commit()
        con.close()
        cls.app = create_app(ConfigTeste)

    @classmethod
    def tearDownClass(cls):
        con = pymysql.connect(host=Config.DB_HOST, port=Config.DB_PORT, user=Config.DB_USER,
                              password=Config.DB_PASSWORD, charset="utf8mb4")
        with con.cursor() as cur:
            cur.execute(f"DROP DATABASE IF EXISTS {BANCO_TESTE}")
        con.commit()
        con.close()
        shutil.rmtree(PASTA_UPLOADS, ignore_errors=True)

    def setUp(self):
        # esquema limpo + clubes iniciais a cada teste
        self.db = pymysql.connect(host=Config.DB_HOST, port=Config.DB_PORT, user=Config.DB_USER,
                                  password=Config.DB_PASSWORD, database=BANCO_TESTE,
                                  charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor)
        executar_script(self.db, ignorar_create_use=True)
        for sub in ("posts", "perfis", "clubes"):
            shutil.rmtree(PASTA_UPLOADS / sub, ignore_errors=True)

    def tearDown(self):
        self.db.close()

    # ---- ajudantes ----
    def sql(self, consulta, params=()):
        with self.db.cursor() as cur:
            cur.execute(consulta, params)
            linhas = cur.fetchall()
        self.db.commit()
        return linhas

    def novo_usuario(self, nome="ana"):
        cli = Cliente(self.app)
        r = cli.cadastrar(nome)
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        return cli

    def entrar_no_clube(self, cli, id_clube):
        r = cli.post(f"/api/comunidades/{id_clube}/participar")
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))

    def publicar(self, cli, texto="olá", clube="MÚSICA", imagens=None):
        data = {"texto": texto, "clube": clube}
        if imagens:
            data["imagens"] = imagens
        return cli.post("/api/publicacoes", data=data)

    def img(self, nome="foto.png"):
        return (io.BytesIO(png_valido()), nome)


# ======================================================================
class TestPaginasEEstaticos(Base):
    def test_arquivos_estaticos_da_interface_continuam_nas_mesmas_urls(self):
        c = Cliente(self.app)
        for url, tipo in (("/style.css", "text/css"), ("/script.js", "javascript"),
                          ("/img/logoHeader.png", "image/png"), ("/img/usuarioSemFoto.jpg", "image/jpeg")):
            r = c.get(url)
            self.assertEqual(r.status_code, 200, url)
            self.assertIn(tipo, r.content_type, url)

    def test_paginas_publicas_abrem(self):
        c = Cliente(self.app)
        for url in ("/", "/index.html", "/telaLogin.html", "/telaCadastro.html"):
            self.assertEqual(c.get(url).status_code, 200, url)

    def test_paginas_protegidas_redirecionam_para_o_login(self):
        c = Cliente(self.app)
        for url in ("/telaHome.html", "/telaClubes.html", "/telaFeed.html", "/telaCriar.html",
                    "/tela-criar-postagem.html", "/tela-criar-clube.html", "/tela-desc-clube.html?id=1"):
            r = c.get(url)
            self.assertEqual(r.status_code, 302, url)
            self.assertIn("/telaLogin.html", r.headers["Location"], url)

    def test_todas_as_paginas_abrem_logado(self):
        cli = self.novo_usuario()
        for url in ("/telaHome.html", "/telaClubes.html", "/tela-desc-clube.html?id=1", "/telaCriar.html",
                    "/tela-criar-postagem.html", "/tela-criar-clube.html", "/telaFeed.html", "/telaFeed.html?clube=1"):
            r = cli.get(url)
            self.assertEqual(r.status_code, 200, url)
            self.assertIn("csrf-token", r.get_data(as_text=True), url)
        self.assertEqual(cli.get("/tela-desc-clube.html?id=9999").status_code, 404)
        self.assertEqual(cli.get("/telaFeed.html?clube=9999").status_code, 404)

    def test_cabecalhos_de_seguranca(self):
        r = Cliente(self.app).get("/telaLogin.html")
        self.assertEqual(r.headers["X-Content-Type-Options"], "nosniff")
        self.assertIn("script-src 'self'", r.headers["Content-Security-Policy"])
        self.assertEqual(r.headers["X-Frame-Options"], "DENY")


class TestAutenticacao(Base):
    def test_cadastro_valida_dados(self):
        c = Cliente(self.app)
        self.assertEqual(c.cadastrar("ab").status_code, 400)               # username curto
        self.assertEqual(c.cadastrar("nome com espaço").status_code, 400)  # caracteres inválidos
        self.assertEqual(c.cadastrar("valido", senha="curta").status_code, 400)

    def test_cadastro_guarda_hash_e_nao_senha(self):
        self.novo_usuario("maria")
        linha = self.sql("SELECT senha_hash FROM tb_usuario WHERE username='maria'")[0]
        self.assertNotIn("senha12345", linha["senha_hash"])
        self.assertTrue(linha["senha_hash"].startswith(("scrypt:", "pbkdf2:")))

    def test_username_duplicado_retorna_409_inclusive_com_outra_caixa(self):
        self.novo_usuario("maria")
        self.assertEqual(Cliente(self.app).cadastrar("maria").status_code, 409)
        self.assertEqual(Cliente(self.app).cadastrar("MARIA").status_code, 409)

    def test_cadastro_ja_inicia_a_sessao_e_logout_encerra(self):
        cli = self.novo_usuario("ana")
        self.assertEqual(cli.get("/api/auth/me").get_json()["username"], "ana")
        self.assertEqual(cli.get("/telaHome.html").status_code, 200)
        self.assertEqual(cli.post("/api/auth/logout").status_code, 200)
        self.assertEqual(cli.get("/api/auth/me").status_code, 401)
        self.assertEqual(cli.get("/telaHome.html").status_code, 302)

    def test_login_certo_e_errado(self):
        self.novo_usuario("ana")
        c = Cliente(self.app)
        self.assertEqual(c.login("ana", "senha-errada").status_code, 401)
        self.assertEqual(c.login("naoexiste").status_code, 401)
        r = c.login("ana")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["redirecionar"], "/telaHome.html")
        self.assertEqual(c.get("/api/auth/me").status_code, 200)

    def test_login_nao_aceita_redirecionamento_externo(self):
        self.novo_usuario("ana")
        for malicioso in ("//evil.com", "https://evil.com", "\\\\evil.com"):
            r = Cliente(self.app).login("ana", next_=malicioso)
            self.assertEqual(r.get_json()["redirecionar"], "/telaHome.html", malicioso)
        r = Cliente(self.app).login("ana", next_="/telaClubes.html")
        self.assertEqual(r.get_json()["redirecionar"], "/telaClubes.html")

    def test_sql_injection_no_login_nao_funciona(self):
        self.novo_usuario("ana")
        c = Cliente(self.app)
        self.assertEqual(c.login("' OR '1'='1' -- ", "' OR '1'='1").status_code, 401)
        self.assertEqual(c.login("ana' -- ", "x").status_code, 401)
        self.assertEqual(c.get("/api/auth/me").status_code, 401)

    def test_csrf_bloqueia_acoes_sem_token(self):
        cli = self.novo_usuario("ana")
        self.assertEqual(cli.post("/api/comunidades/1/participar", csrf=False).status_code, 403)
        self.assertEqual(self.sql("SELECT COUNT(*) AS n FROM tb_participante")[0]["n"], 0)

    def test_api_exige_autenticacao(self):
        c = Cliente(self.app)
        c.token()
        self.assertEqual(c.post("/api/comunidades/1/participar").status_code, 401)
        self.assertEqual(c.post("/api/publicacoes", data={"texto": "x", "clube": "MÚSICA"}).status_code, 401)
        self.assertEqual(c.post("/api/publicacoes/1/curtir").status_code, 401)
        self.assertEqual(c.post("/api/publicacoes/1/comentarios", json={"texto": "x"}).status_code, 401)
        self.assertEqual(c.delete("/api/publicacoes/1").status_code, 401)

    def test_foto_de_perfil_no_cadastro(self):
        cli = Cliente(self.app)
        r = cli.cadastrar("fotografo", foto=self.img("eu.png"))
        self.assertEqual(r.status_code, 201)
        caminho = self.sql("SELECT foto_perfil FROM tb_usuario WHERE username='fotografo'")[0]["foto_perfil"]
        self.assertTrue(caminho.startswith("perfis/") and caminho.endswith(".png"))
        self.assertTrue((PASTA_UPLOADS / caminho).is_file())
        self.assertIn(caminho, cli.get("/telaHome.html").get_data(as_text=True))


class TestApresentacao(Base):
    def test_home_nao_tem_link_do_feed_e_mostra_foto_do_clube_com_nome(self):
        cli = self.novo_usuario()
        self.entrar_no_clube(cli, 1)
        html = cli.get("/telaHome.html").get_data(as_text=True)
        self.assertNotIn("VER MEU FEED", html)
        self.assertNotIn('href="/telaFeed.html"', html)
        self.assertRegex(html, r'<a href="/telaFeed\.html\?clube=1"[^>]*>\s*<img src="/img/imgclube1\.jpg"[^>]*>\s*<span>MÚSICA</span>')

    def test_botoes_de_clube_tem_cores_diferentes(self):
        cli = self.novo_usuario()
        html = cli.get("/telaClubes.html").get_data(as_text=True)
        cores = re.findall(r'class="botaoClube (cor-\d)"', html)
        self.assertEqual(len(cores), 9)
        self.assertEqual(len(set(cores)), 8)             # 8 cores na paleta; o 9º clube recomeça a paleta
        self.assertEqual(cores[:3], ["cor-0", "cor-1", "cor-2"])


class TestTrocaDeImagens(Base):
    def caminho_foto(self, username):
        return self.sql("SELECT foto_perfil FROM tb_usuario WHERE username=%s", (username,))[0]["foto_perfil"]

    def caminho_clube(self, id_clube):
        return self.sql("SELECT imagem FROM tb_comunidade WHERE id_comunidade=%s", (id_clube,))[0]["imagem"]

    def test_trocar_foto_de_perfil_apaga_a_anterior(self):
        cli = Cliente(self.app)
        cli.cadastrar("ana", foto=self.img("a.png"))
        antiga = self.caminho_foto("ana")
        self.assertTrue((PASTA_UPLOADS / antiga).is_file())
        r = cli.post("/api/auth/foto", data={"foto": self.img("b.png")})
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        nova = self.caminho_foto("ana")
        self.assertNotEqual(nova, antiga)
        self.assertEqual(r.get_json()["foto"], "/uploads/" + nova)
        self.assertTrue((PASTA_UPLOADS / nova).is_file())
        self.assertFalse((PASTA_UPLOADS / antiga).exists())
        self.assertIn("/uploads/" + nova, cli.get("/telaHome.html").get_data(as_text=True))

    def test_trocar_foto_de_perfil_sem_foto_anterior_e_validacoes(self):
        cli = self.novo_usuario("ana")                      # cadastro sem foto
        self.assertIsNone(self.caminho_foto("ana"))
        self.assertEqual(cli.post("/api/auth/foto", data={"foto": self.img()}).status_code, 200)
        self.assertEqual(cli.post("/api/auth/foto", data={}).status_code, 400)
        for nome, arq in {"php": (io.BytesIO(b"<?php ?>"), "x.php"), "falso": (io.BytesIO(b"texto"), "x.png"),
                          "svg": (io.BytesIO(b"<svg onload=alert(1)/>"), "x.svg")}.items():
            self.assertEqual(cli.post("/api/auth/foto", data={"foto": arq}).status_code, 400, nome)
        grande = png_valido() + b"0" * (5 * 1024 * 1024)
        self.assertEqual(cli.post("/api/auth/foto", data={"foto": (io.BytesIO(grande), "g.png")}).status_code, 400)
        self.assertEqual(len(list((PASTA_UPLOADS / "perfis").glob("*"))), 1)   # só a foto válida ficou

    def test_trocar_foto_exige_login_e_csrf(self):
        c = Cliente(self.app)
        c.token()
        self.assertEqual(c.post("/api/auth/foto", data={"foto": self.img()}).status_code, 401)
        cli = self.novo_usuario("ana")
        self.assertEqual(cli.post("/api/auth/foto", data={"foto": self.img()}, csrf=False).status_code, 403)

    def test_clube_inicial_qualquer_participante_troca_a_imagem(self):
        a, b = self.novo_usuario("ana"), self.novo_usuario("bia")
        self.assertNotIn("linkAlterarImagem", a.get("/tela-desc-clube.html?id=1").get_data(as_text=True))
        r = a.post("/api/comunidades/1/imagem", data={"imagem": self.img()})        # ainda não participa
        self.assertEqual(r.status_code, 403)
        self.assertIsNone(self.caminho_clube(1))
        self.entrar_no_clube(a, 1)
        self.entrar_no_clube(b, 1)
        self.assertIn("linkAlterarImagem", a.get("/tela-desc-clube.html?id=1").get_data(as_text=True))
        r = a.post("/api/comunidades/1/imagem", data={"imagem": self.img("um.png")})
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        primeira = self.caminho_clube(1)
        self.assertTrue(primeira.startswith("clubes/") and (PASTA_UPLOADS / primeira).is_file())
        self.assertEqual(r.get_json()["imagem"], "/uploads/" + primeira)
        # outro participante troca de novo: a imagem anterior some do disco
        self.assertEqual(b.post("/api/comunidades/1/imagem", data={"imagem": self.img("dois.png")}).status_code, 200)
        segunda = self.caminho_clube(1)
        self.assertNotEqual(primeira, segunda)
        self.assertFalse((PASTA_UPLOADS / primeira).exists())
        self.assertIn("/uploads/" + segunda, b.get("/telaClubes.html").get_data(as_text=True))
        self.assertIsNone(self.caminho_clube(2))                                     # outros clubes intactos

    def test_clube_criado_por_usuario_so_o_criador_troca_a_imagem(self):
        a, b = self.novo_usuario("ana"), self.novo_usuario("bia")
        id_clube = a.post("/api/comunidades", data={"nome": "Fotografia", "descricao": "Fotos."}).get_json()["id"]
        self.entrar_no_clube(b, id_clube)
        self.assertEqual(b.post(f"/api/comunidades/{id_clube}/imagem", data={"imagem": self.img()}).status_code, 403)
        self.assertNotIn("linkAlterarImagem", b.get(f"/tela-desc-clube.html?id={id_clube}").get_data(as_text=True))
        self.assertIn("linkAlterarImagem", a.get(f"/tela-desc-clube.html?id={id_clube}").get_data(as_text=True))
        self.assertEqual(a.post(f"/api/comunidades/{id_clube}/imagem", data={"imagem": self.img()}).status_code, 200)

    def test_trocar_imagem_do_clube_validacoes(self):
        a = self.novo_usuario("ana")
        self.entrar_no_clube(a, 1)
        self.assertEqual(a.post("/api/comunidades/999/imagem", data={"imagem": self.img()}).status_code, 404)
        self.assertEqual(a.post("/api/comunidades/1/imagem", data={}).status_code, 400)
        self.assertEqual(a.post("/api/comunidades/1/imagem", data={"imagem": (io.BytesIO(b"<?php ?>"), "x.php")}).status_code, 400)
        self.assertEqual(a.post("/api/comunidades/1/imagem", data={"imagem": (io.BytesIO(b"nao e imagem"), "x.png")}).status_code, 400)
        self.assertEqual(a.post("/api/comunidades/1/imagem", data={"imagem": self.img()}, csrf=False).status_code, 403)
        self.assertIsNone(self.caminho_clube(1))
        c = Cliente(self.app); c.token()
        self.assertEqual(c.post("/api/comunidades/1/imagem", data={"imagem": self.img()}).status_code, 401)


class TestComunidades(Base):
    def test_listar_e_buscar(self):
        cli = self.novo_usuario()
        todas = cli.get("/api/comunidades").get_json()
        self.assertEqual([c["nome"] for c in todas][:3], ["MÚSICA", "LIVROS", "ESPORTES"])
        self.assertEqual(len(todas), 9)
        self.assertEqual([c["nome"] for c in cli.get("/api/comunidades?q=liv").get_json()], ["LIVROS"])
        self.assertEqual(cli.get("/api/comunidades?q=%25").get_json(), [])         # '%' é literal, não curinga
        self.assertEqual(cli.get("/api/comunidades?q=' OR 1=1 --").get_json(), [])
        html = cli.get("/telaClubes.html?q=rpg").get_data(as_text=True)
        self.assertIn("RPG", html)
        self.assertNotIn("LIVROS", html)

    def test_participar_sair_e_bloqueio_de_duplicidade(self):
        cli = self.novo_usuario()
        self.entrar_no_clube(cli, 1)
        r = cli.post("/api/comunidades/1/participar")
        self.assertEqual(r.status_code, 409)
        self.assertEqual(self.sql("SELECT COUNT(*) AS n FROM tb_participante")[0]["n"], 1)
        self.assertIn("SAIR", cli.get("/tela-desc-clube.html?id=1").get_data(as_text=True))
        self.assertIn("MÚSICA", cli.get("/telaHome.html").get_data(as_text=True))   # aparece em "Seus Clubes"
        self.assertEqual(cli.delete("/api/comunidades/1/participar").status_code, 200)
        self.assertEqual(cli.delete("/api/comunidades/1/participar").status_code, 404)
        self.assertIn("ENTRAR", cli.get("/tela-desc-clube.html?id=1").get_data(as_text=True))
        self.assertEqual(cli.post("/api/comunidades/9999/participar").status_code, 404)

    def test_restricao_unica_do_banco_tambem_impede_duplicidade(self):
        cli = self.novo_usuario()
        self.entrar_no_clube(cli, 1)
        with self.assertRaises(pymysql.err.IntegrityError):
            self.sql("INSERT INTO tb_participante (id_usuario, id_comunidade) VALUES (1, 1)")

    def test_criar_clube_com_imagem_e_criador_vira_participante(self):
        cli = self.novo_usuario()
        r = cli.post("/api/comunidades", data={"nome": "Fotografia", "descricao": "Clique e compartilhe.",
                                               "imagem": self.img("capa.png")})
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        id_clube = r.get_json()["id"]
        self.assertEqual(self.sql("SELECT COUNT(*) AS n FROM tb_participante WHERE id_comunidade=%s", (id_clube,))[0]["n"], 1)
        imagem = self.sql("SELECT imagem FROM tb_comunidade WHERE id_comunidade=%s", (id_clube,))[0]["imagem"]
        self.assertTrue((PASTA_UPLOADS / imagem).is_file())
        self.assertIn("FOTOGRAFIA", cli.get("/telaClubes.html").get_data(as_text=True))

    def test_criar_clube_valida_dados(self):
        cli = self.novo_usuario()
        self.assertEqual(cli.post("/api/comunidades", data={"nome": "x", "descricao": "d"}).status_code, 400)
        self.assertEqual(cli.post("/api/comunidades", data={"nome": "Valido", "descricao": ""}).status_code, 400)
        self.assertEqual(cli.post("/api/comunidades", data={"nome": "Valido", "descricao": "d" * 201}).status_code, 400)
        self.assertEqual(cli.post("/api/comunidades", data={"nome": "música", "descricao": "d"}).status_code, 409)


class TestPublicacoesEUploads(Base):
    def test_nao_participante_nao_publica(self):
        cli = self.novo_usuario()
        r = self.publicar(cli)
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.sql("SELECT COUNT(*) AS n FROM tb_publicacao")[0]["n"], 0)

    def test_publicar_texto_e_validacoes(self):
        cli = self.novo_usuario()
        self.entrar_no_clube(cli, 1)
        r = self.publicar(cli, "Primeira postagem")
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        self.assertEqual(self.publicar(cli, "").status_code, 400)                    # vazio
        self.assertEqual(self.publicar(cli, "x" * 1001).status_code, 400)            # longo demais
        self.assertEqual(self.publicar(cli, "x", clube="NaoExiste").status_code, 404)
        self.assertEqual(self.publicar(cli, "x", clube="").status_code, 400)

    def test_usuario_vem_da_sessao_e_nao_do_formulario(self):
        a = self.novo_usuario("ana")
        b = self.novo_usuario("bia")
        self.entrar_no_clube(a, 1)
        r = a.post("/api/publicacoes", data={"texto": "tentando me passar pela bia", "clube": "MÚSICA", "id_usuario": "2"})
        self.assertEqual(r.status_code, 201)
        autor = self.sql("SELECT u.username FROM tb_publicacao p JOIN tb_usuario u ON u.id_usuario=p.id_usuario")[0]
        self.assertEqual(autor["username"], "ana")

    def test_upload_de_imagem_valida(self):
        cli = self.novo_usuario()
        self.entrar_no_clube(cli, 1)
        r = self.publicar(cli, "com foto", imagens=self.img("Minha Foto (1).PNG"))
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        caminho = self.sql("SELECT caminho FROM tb_imagem")[0]["caminho"]
        self.assertTrue(re.fullmatch(r"posts/[0-9a-f]{32}\.png", caminho), caminho)   # nome gerado pelo servidor
        self.assertTrue((PASTA_UPLOADS / caminho).is_file())
        resp = cli.get("/uploads/" + caminho)
        self.assertEqual((resp.status_code, resp.content_type), (200, "image/png"))
        self.assertIn("/uploads/" + caminho, cli.get("/telaFeed.html?clube=1").get_data(as_text=True))

    def test_upload_rejeita_arquivos_perigosos_ou_invalidos(self):
        cli = self.novo_usuario()
        self.entrar_no_clube(cli, 1)
        casos = {
            "script php": (io.BytesIO(b"<?php system($_GET['c']); ?>"), "shell.php"),
            "html": (io.BytesIO(b"<script>alert(1)</script>"), "x.html"),
            "svg": (io.BytesIO(b"<svg onload=alert(1)></svg>"), "x.svg"),
            "php disfarçado de png": (io.BytesIO(b"<?php echo 1; ?>"), "falso.png"),
            "texto com extensão jpg": (io.BytesIO(b"isso nao e imagem"), "x.jpg"),
            "arquivo vazio": (io.BytesIO(b""), "vazio.png"),
            "dupla extensão": (io.BytesIO(b"<?php ?>"), "x.php.png"),
        }
        for nome, arq in casos.items():
            r = self.publicar(cli, "teste", imagens=arq)
            self.assertEqual(r.status_code, 400, f"{nome}: {r.get_data(as_text=True)}")
        self.assertEqual(self.sql("SELECT COUNT(*) AS n FROM tb_publicacao")[0]["n"], 0)
        self.assertEqual(list((PASTA_UPLOADS / "posts").glob("*")) if (PASTA_UPLOADS / "posts").exists() else [], [])

    def test_upload_limite_de_tamanho(self):
        cli = self.novo_usuario()
        self.entrar_no_clube(cli, 1)
        grande = png_valido() + b"0" * (5 * 1024 * 1024)          # > 5 MB
        r = self.publicar(cli, "grande", imagens=(io.BytesIO(grande), "g.png"))
        self.assertEqual(r.status_code, 400)
        self.assertIn("limite", r.get_json()["erro"])
        enorme = b"0" * (13 * 1024 * 1024)                        # > limite da requisição
        r = self.publicar(cli, "enorme", imagens=(io.BytesIO(enorme), "e.png"))
        self.assertEqual(r.status_code, 413)

    def test_limite_de_imagens_por_postagem(self):
        cli = self.novo_usuario()
        self.entrar_no_clube(cli, 1)
        data = {"texto": "muitas", "clube": "MÚSICA",
                "imagens": [(io.BytesIO(png_valido()), f"{i}.png") for i in range(5)]}
        self.assertEqual(cli.post("/api/publicacoes", data=data).status_code, 400)
        data["imagens"] = data["imagens"][:2]
        data["imagens"] = [(io.BytesIO(png_valido()), f"{i}.png") for i in range(2)]
        self.assertEqual(cli.post("/api/publicacoes", data=data).status_code, 201)
        self.assertEqual(self.sql("SELECT COUNT(*) AS n FROM tb_imagem")[0]["n"], 2)

    def test_servir_uploads_nao_permite_fugir_da_pasta_nem_executar_nada(self):
        cli = self.novo_usuario()
        self.assertEqual(cli.get("/uploads/../config.py").status_code, 404)
        self.assertEqual(cli.get("/uploads/%2e%2e/config.py").status_code, 404)
        self.assertEqual(cli.get("/uploads/posts/qualquer.py").status_code, 404)
        self.assertEqual(cli.get("/uploads/posts/nao-existe.png").status_code, 404)

    def test_excluir_publicacao_propria_remove_arquivos_curtidas_e_comentarios(self):
        a = self.novo_usuario("ana")
        self.entrar_no_clube(a, 1)
        self.publicar(a, "para apagar", imagens=self.img())
        caminho = self.sql("SELECT caminho FROM tb_imagem")[0]["caminho"]
        a.post("/api/publicacoes/1/curtir")
        a.post("/api/publicacoes/1/comentarios", json={"texto": "oi"})
        self.assertTrue((PASTA_UPLOADS / caminho).is_file())
        self.assertEqual(a.delete("/api/publicacoes/1").status_code, 200)
        for tabela in ("tb_publicacao", "tb_imagem", "tb_curtida", "tb_comentario"):
            self.assertEqual(self.sql(f"SELECT COUNT(*) AS n FROM {tabela}")[0]["n"], 0, tabela)
        self.assertFalse((PASTA_UPLOADS / caminho).exists())
        self.assertEqual(a.delete("/api/publicacoes/1").status_code, 404)

    def test_nao_exclui_publicacao_de_outro_usuario(self):
        a, b = self.novo_usuario("ana"), self.novo_usuario("bia")
        self.entrar_no_clube(a, 1)
        self.publicar(a, "da ana")
        self.assertEqual(b.delete("/api/publicacoes/1").status_code, 403)
        self.assertEqual(self.sql("SELECT COUNT(*) AS n FROM tb_publicacao")[0]["n"], 1)

    def test_xss_texto_da_postagem_e_escapado_no_html(self):
        cli = self.novo_usuario()
        self.entrar_no_clube(cli, 1)
        self.publicar(cli, '<script>alert("xss")</script><img src=x onerror=alert(1)>')
        html = cli.get("/telaFeed.html?clube=1").get_data(as_text=True)
        self.assertNotIn("<script>alert", html)
        self.assertNotIn("<img src=x", html)
        self.assertIn("&lt;script&gt;", html)


class TestFeeds(Base):
    def test_feed_principal_so_mostra_clubes_do_usuario_e_ordena_do_mais_recente(self):
        a, b = self.novo_usuario("ana"), self.novo_usuario("bia")
        for clube in (1, 2, 3):
            self.entrar_no_clube(b, clube)
        self.entrar_no_clube(a, 1)
        self.entrar_no_clube(a, 2)
        self.publicar(b, "musica-antiga", clube="MÚSICA")
        self.publicar(b, "livros-nova", clube="LIVROS")
        self.publicar(b, "esportes-invisivel", clube="ESPORTES")   # ana não participa
        # a "musica-antiga" ganha data mais velha mesmo tendo id menor/maior: ordenação é por data
        self.sql("UPDATE tb_publicacao SET data_publicacao = NOW() - INTERVAL 2 DAY WHERE texto='musica-antiga'")
        self.sql("UPDATE tb_publicacao SET data_publicacao = NOW() - INTERVAL 1 DAY WHERE texto='livros-nova'")
        html = a.get("/telaFeed.html").get_data(as_text=True)
        self.assertIn("livros-nova", html)
        self.assertIn("musica-antiga", html)
        self.assertNotIn("esportes-invisivel", html)
        self.assertLess(html.index("livros-nova"), html.index("musica-antiga"))
        pubs = a.get("/api/feed").get_json()["publicacoes"]
        self.assertEqual([p["texto"] for p in pubs], ["livros-nova", "musica-antiga"])

    def test_feed_de_um_clube_mostra_so_aquele_clube(self):
        a = self.novo_usuario("ana")
        self.entrar_no_clube(a, 1)
        self.entrar_no_clube(a, 2)
        self.publicar(a, "so-musica", clube="MÚSICA")
        self.publicar(a, "so-livros", clube="LIVROS")
        html = a.get("/telaFeed.html?clube=1").get_data(as_text=True)
        self.assertIn("so-musica", html)
        self.assertNotIn("so-livros", html)
        self.assertEqual([p["texto"] for p in a.get("/api/feed?clube=2").get_json()["publicacoes"]], ["so-livros"])

    def test_nao_participante_ve_feed_do_clube_mas_nao_ve_botao_de_nova_postagem(self):
        a, b = self.novo_usuario("ana"), self.novo_usuario("bia")
        self.entrar_no_clube(a, 1)
        self.publicar(a, "publica")
        html = b.get("/telaFeed.html?clube=1").get_data(as_text=True)
        self.assertIn("publica", html)
        self.assertNotIn("pilulaPostar", html)
        self.assertIn("pilulaPostar", a.get("/telaFeed.html?clube=1").get_data(as_text=True))

    def test_feed_principal_vazio_sem_clubes(self):
        cli = self.novo_usuario()
        self.assertIn("ainda não participa de nenhum clube", cli.get("/telaFeed.html").get_data(as_text=True))

    def test_paginacao(self):
        cli = self.novo_usuario()
        self.entrar_no_clube(cli, 1)
        for i in range(12):
            self.sql("INSERT INTO tb_publicacao (id_usuario, id_comunidade, texto, data_publicacao) "
                     "VALUES (1, 1, %s, NOW() - INTERVAL %s MINUTE)", (f"post-{i}", i))
        p1 = cli.get("/api/feed").get_json()
        self.assertEqual((len(p1["publicacoes"]), p1["tem_mais"]), (10, True))
        self.assertEqual(p1["publicacoes"][0]["texto"], "post-0")
        p2 = cli.get("/api/feed?pagina=2").get_json()
        self.assertEqual((len(p2["publicacoes"]), p2["tem_mais"]), (2, False))
        self.assertIn("VER MAIS", cli.get("/telaFeed.html").get_data(as_text=True))


class TestCurtidasEComentarios(Base):
    def preparar(self):
        a, b = self.novo_usuario("ana"), self.novo_usuario("bia")
        self.entrar_no_clube(a, 1)
        self.publicar(a, "post da ana")
        return a, b

    def test_curtir_descurtir_e_sem_duplicidade(self):
        a, b = self.preparar()
        r = b.post("/api/publicacoes/1/curtir")
        self.assertEqual(r.get_json(), {"ok": True, "curtiu": True, "total": 1})
        self.assertEqual(b.post("/api/publicacoes/1/curtir").get_json()["total"], 1)      # repetir não duplica
        self.assertEqual(a.post("/api/publicacoes/1/curtir").get_json()["total"], 2)       # outro usuário soma
        self.assertEqual(self.sql("SELECT COUNT(*) AS n FROM tb_curtida")[0]["n"], 2)
        with self.assertRaises(pymysql.err.IntegrityError):                                # e o banco também impede
            self.sql("INSERT INTO tb_curtida (id_usuario, id_publicacao) VALUES (1, 1)")
        feed = b.get("/api/feed?clube=1").get_json()["publicacoes"][0]
        self.assertEqual((feed["curtiu"], feed["curtidas"]), (True, 2))
        self.assertIn("botaoCurtir curtido", b.get("/telaFeed.html?clube=1").get_data(as_text=True))
        r = b.delete("/api/publicacoes/1/curtir")
        self.assertEqual(r.get_json(), {"ok": True, "curtiu": False, "total": 1})
        self.assertEqual(b.delete("/api/publicacoes/1/curtir").get_json()["total"], 1)     # idempotente
        self.assertFalse(b.get("/api/feed?clube=1").get_json()["publicacoes"][0]["curtiu"])
        self.assertEqual(b.post("/api/publicacoes/999/curtir").status_code, 404)

    def test_comentarios_criar_listar_e_excluir_somente_os_proprios(self):
        a, b = self.preparar()
        r = b.post("/api/publicacoes/1/comentarios", json={"texto": "  Muito bom!  "})
        self.assertEqual(r.status_code, 201)
        corpo = r.get_json()
        self.assertEqual((corpo["comentario"]["texto"], corpo["total"], corpo["comentario"]["meu"]), ("Muito bom!", 1, True))
        self.assertEqual(corpo["comentario"]["autor"]["username"], "bia")
        a.post("/api/publicacoes/1/comentarios", json={"texto": "Obrigada!"})
        lista = a.get("/api/publicacoes/1/comentarios").get_json()
        self.assertEqual([c["texto"] for c in lista], ["Muito bom!", "Obrigada!"])
        self.assertEqual([c["meu"] for c in lista], [False, True])
        self.assertTrue(all(c["data"] for c in lista))
        id_bia = lista[0]["id"]
        self.assertEqual(a.delete(f"/api/comentarios/{id_bia}").status_code, 403)          # não é dela
        self.assertEqual(self.sql("SELECT COUNT(*) AS n FROM tb_comentario")[0]["n"], 2)
        r = b.delete(f"/api/comentarios/{id_bia}")
        self.assertEqual((r.status_code, r.get_json()["total"]), (200, 1))
        self.assertEqual(b.delete(f"/api/comentarios/{id_bia}").status_code, 404)
        self.assertEqual(a.get("/api/feed?clube=1").get_json()["publicacoes"][0]["comentarios"], 1)

    def test_comentarios_validacao_e_xss(self):
        a, b = self.preparar()
        self.assertEqual(b.post("/api/publicacoes/1/comentarios", json={"texto": "   "}).status_code, 400)
        self.assertEqual(b.post("/api/publicacoes/1/comentarios", json={"texto": "x" * 501}).status_code, 400)
        self.assertEqual(b.post("/api/publicacoes/1/comentarios", json={"texto": 123}).status_code, 400)
        self.assertEqual(b.post("/api/publicacoes/999/comentarios", json={"texto": "oi"}).status_code, 404)
        # texto malicioso é guardado como texto puro e devolvido como JSON (o JS usa textContent)
        r = b.post("/api/publicacoes/1/comentarios", json={"texto": "<img src=x onerror=alert(1)>"})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.content_type, "application/json")


class TestPersistenciaEPermissoes(Base):
    def test_dados_persistem_apos_novo_login(self):
        a = self.novo_usuario("ana")
        self.entrar_no_clube(a, 1)
        self.publicar(a, "persistente", imagens=self.img())
        a.post("/api/publicacoes/1/curtir")
        a.post("/api/publicacoes/1/comentarios", json={"texto": "guardado"})
        a.post("/api/auth/logout")
        # sessão totalmente nova, só com username e senha
        nova = Cliente(self.app)
        self.assertEqual(nova.login("ana").status_code, 200)
        post = nova.get("/api/feed").get_json()["publicacoes"][0]
        self.assertEqual((post["texto"], post["curtiu"], post["curtidas"], post["comentarios"], len(post["imagens"])),
                         ("persistente", True, 1, 1, 1))
        self.assertIn("#ana", nova.get("/telaHome.html").get_data(as_text=True))

    def test_usuario_removido_perde_a_sessao(self):
        a = self.novo_usuario("ana")
        self.sql("DELETE FROM tb_usuario")
        self.assertEqual(a.get("/telaHome.html").status_code, 302)
        self.assertEqual(a.get("/api/auth/me").status_code, 401)


if __name__ == "__main__":
    unittest.main(verbosity=2)
