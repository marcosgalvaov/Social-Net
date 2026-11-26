"""Teste ponta a ponta no navegador (Playwright + Chromium) usando a interface real.

Pré-requisitos (opcional, só para este teste):
    pip install playwright && playwright install chromium
Com o servidor rodando (python app.py) e o banco recém-criado (python init_db.py):
    python tests/e2e_navegador.py [URL_BASE]      # padrão: http://127.0.0.1:5000
Cria o usuário "e2e_<número>" no banco; use um banco de desenvolvimento.
"""
import random
import struct
import sys
import tempfile
import zlib
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:5000"
PASTA_FOTOS = Path(tempfile.mkdtemp(prefix="e2e_"))
CAPTURAS = Path("/tmp/capturas")
CAPTURAS.mkdir(exist_ok=True)


def png(caminho, cor, tam=240):
    def bloco(t, d):
        c = t + d
        return struct.pack(">I", len(d)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
    linhas = b"".join(b"\x00" + bytes(cor) * tam for _ in range(tam))
    dados = (b"\x89PNG\r\n\x1a\n" + bloco(b"IHDR", struct.pack(">IIBBBBB", tam, tam, 8, 2, 0, 0, 0))
             + bloco(b"IDAT", zlib.compress(linhas)) + bloco(b"IEND", b""))
    Path(caminho).write_bytes(dados)
    return str(caminho)


FOTO_PERFIL = png(PASTA_FOTOS / "perfil.png", (94, 23, 235))
FOTO_POST = png(PASTA_FOTOS / "post.png", (186, 251, 255), 400)
FOTO_CLUBE = png(PASTA_FOTOS / "clube.png", (255, 200, 120))
USUARIO = f"e2e_{random.randint(1000, 9999)}"
SENHA = "senha-e2e-123"
resultados = []


def ok(descricao):
    resultados.append(descricao)
    print("  OK  ", descricao)


with sync_playwright() as p:
    navegador = p.chromium.launch()
    pagina = navegador.new_page(viewport={"width": 1280, "height": 900})
    erros_console = []
    # fontes do Google ficam bloqueadas no ambiente de teste: não contam como erro da aplicação
    pagina.on("console", lambda m: erros_console.append(m.text) if m.type == "error"
              and "fonts.g" not in m.text and "ERR_" not in m.text
              and "401" not in m.text else None)  # 401 esperado: o teste tenta uma senha errada
    pagina.on("pageerror", lambda e: erros_console.append(str(e)))
    pagina.on("dialog", lambda d: d.accept())

    # --- página inicial -> login
    pagina.goto(BASE + "/")
    pagina.click("#botaoEntrar")
    expect(pagina).to_have_url(f"{BASE}/telaLogin.html?next=%2FtelaHome.html")
    ok("index: botão ENTRAR leva ao login (sem sessão)")

    # --- cadastro com foto
    pagina.click("text=Criar uma conta")
    expect(pagina).to_have_url(BASE + "/telaCadastro.html")
    pagina.fill("#in_username", USUARIO)
    pagina.fill("#in_usersenha", "curta")
    pagina.click("#botaoCriar")
    assert pagina.locator("#in_usersenha").evaluate("e => !e.checkValidity()")
    expect(pagina).to_have_url(BASE + "/telaCadastro.html")
    ok("cadastro: senha curta é barrada pela validação do formulário (não envia)")
    pagina.set_input_files("#in_userfoto", FOTO_PERFIL)
    expect(pagina.locator("#fotoPerfilCadastro")).to_have_attribute("src", __import__("re").compile("^blob:"))
    pagina.fill("#in_usersenha", SENHA)
    pagina.click("#botaoCriar")
    expect(pagina).to_have_url(BASE + "/telaHome.html")
    expect(pagina.locator("#caixaPerfil p")).to_have_text("#" + USUARIO)
    expect(pagina.locator("#imagemPerfil")).to_have_attribute("src", __import__("re").compile("^/uploads/perfis/"))
    ok("cadastro: cria conta com foto, inicia sessão e abre a Home com username e foto")
    foto_antiga = pagina.locator("#imagemPerfil").get_attribute("src")
    pagina.set_input_files("#in_userfotoTroca", FOTO_POST)
    expect(pagina.locator(".aviso")).to_have_text("Foto de perfil atualizada.")
    nova = pagina.locator("#imagemPerfil").get_attribute("src")
    assert nova != foto_antiga and nova.startswith("/uploads/perfis/"), (foto_antiga, nova)
    pagina.reload()
    expect(pagina.locator("#imagemPerfil")).to_have_attribute("src", nova)
    ok("perfil: trocar a foto pela Home atualiza na hora e persiste após recarregar")
    pagina.screenshot(path=str(CAPTURAS / "home_sem_clubes.png"))
    expect(pagina.locator("#listaClubes")).to_contain_text("ainda não participa")

    # --- clubes: busca e entrada
    pagina.click("a.btn:text('CLUBES')")
    expect(pagina.locator(".botaoClube")).to_have_count(9)
    cores = pagina.locator(".botaoClube").evaluate_all("els => els.map(e => getComputedStyle(e).backgroundImage)")
    assert len(set(cores)) >= 8, cores
    pagina.screenshot(path=str(CAPTURAS / "clubes.png"), full_page=True)
    pagina.fill("#campoBusca", "rpg")
    pagina.click("#barraPesquisa button")
    expect(pagina.locator(".botaoClube")).to_have_count(1)
    ok("clubes: 9 clubes vêm do banco e a busca filtra")
    pagina.goto(BASE + "/telaClubes.html")
    pagina.locator(".botaoClube", has_text="MÚSICA").click()
    expect(pagina.locator("#descClubeId h1")).to_have_text("MÚSICA")
    expect(pagina.locator("#descClubeAbsolute")).to_have_text("ENTRAR")
    expect(pagina.locator("#linkAlterarImagem")).to_have_count(0)     # só participantes alteram clubes iniciais
    pagina.screenshot(path=str(CAPTURAS / "desc_clube.png"))
    pagina.click("#descClubeAbsolute")
    expect(pagina).to_have_url(BASE + "/telaFeed.html?clube=1")
    ok("clube: botão ENTRAR registra a participação e abre o feed do clube")

    # --- criar postagem com imagem
    pagina.click("a.pilulaPostar")
    expect(pagina.locator("#escolherClube")).to_have_value("MÚSICA")
    pagina.fill("#escreverPostagem", "Minha primeira postagem <b>sem html</b>")
    pagina.set_input_files("#in_imagem", FOTO_POST)
    expect(pagina.locator("#imagemPostagem")).to_have_attribute("src", __import__("re").compile("^blob:"))
    pagina.screenshot(path=str(CAPTURAS / "criar_postagem.png"))
    pagina.click("#criarPostagemAbsolute")
    expect(pagina).to_have_url(BASE + "/telaFeed.html?clube=1")
    post = pagina.locator(".postagem").first
    expect(post.locator(".postagemTexto")).to_have_text("Minha primeira postagem <b>sem html</b>")
    expect(post.locator(".postagemAutor")).to_have_text(USUARIO)
    assert post.locator(".postagemImagem").evaluate("i => i.complete && i.naturalWidth > 0")
    ok("postagem: texto (escapado) + imagem enviada aparecem no feed do clube")

    # --- curtir
    botao_curtir = post.locator(".botaoCurtir")
    botao_curtir.click()
    expect(post.locator(".contadorCurtidas")).to_have_text("1")
    expect(botao_curtir).to_have_class(__import__("re").compile("curtido"))
    pagina.reload()
    expect(pagina.locator(".postagem").first.locator(".contadorCurtidas")).to_have_text("1")
    ok("curtida: contador e estado visual persistem após recarregar")
    pagina.locator(".postagem").first.locator(".botaoCurtir").click()
    expect(pagina.locator(".postagem").first.locator(".contadorCurtidas")).to_have_text("0")
    ok("curtida: remover curtida atualiza o contador")

    # --- comentários
    post = pagina.locator(".postagem").first
    post.locator(".botaoComentarios").click()
    campo = post.locator(".novoComentario input")
    campo.fill("Ótimo post! <i>teste</i>")
    campo.press("Enter")
    expect(post.locator(".comentarioTexto")).to_have_text("Ótimo post! <i>teste</i>")
    expect(post.locator(".contadorComentarios")).to_have_text("1")
    pagina.reload()
    post = pagina.locator(".postagem").first
    post.locator(".botaoComentarios").click()
    expect(post.locator(".comentario")).to_have_count(1)
    ok("comentário: criar (Enter), exibir autor/data/texto e persistir")
    pagina.screenshot(path=str(CAPTURAS / "feed_clube.png"), full_page=True)
    post.locator("[data-acao='excluir-comentario']").click()
    expect(post.locator(".comentario")).to_have_count(0)
    expect(post.locator(".contadorComentarios")).to_have_text("0")
    ok("comentário: excluir o próprio")

    # --- feed principal e Home
    pagina.goto(BASE + "/telaHome.html")
    expect(pagina.locator("#listaClubes li")).to_have_count(1)
    expect(pagina.locator("text=VER MEU FEED")).to_have_count(0)
    expect(pagina.locator("#listaClubes li img")).to_have_count(1)
    expect(pagina.locator("#listaClubes li span")).to_have_text("MÚSICA")
    pagina.screenshot(path=str(CAPTURAS / "home_com_clube.png"))
    pagina.goto(BASE + "/telaFeed.html")
    expect(pagina.locator(".postagem")).to_have_count(1)
    ok("home/feed principal: sem link de feed, foto+nome do clube em 'Seus Clubes' e a postagem no feed principal")

    # --- excluir postagem
    pagina.locator(".postagem").first.locator("[data-acao='excluir-postagem']").click()
    expect(pagina.locator(".postagem")).to_have_count(0)
    pagina.reload()
    expect(pagina.locator(".postagem")).to_have_count(0)
    ok("postagem: excluir a própria (persiste após recarregar)")

    # --- criar clube pela tela Criar
    pagina.click("a.btn:text('CRIAR')")
    pagina.screenshot(path=str(CAPTURAS / "criar.png"))
    pagina.click("#caixaCriarClube")
    expect(pagina).to_have_url(BASE + "/tela-criar-clube.html")
    pagina.fill("#escreverPostagem", "Fotografia " + USUARIO[-4:])
    pagina.fill("#escolherClube", "Clique, edite e compartilhe.")
    pagina.set_input_files("#in_imagemClube", FOTO_CLUBE)
    pagina.screenshot(path=str(CAPTURAS / "criar_clube.png"))
    pagina.click("#criarPostagemAbsolute")
    expect(pagina).to_have_url(__import__("re").compile(r"/telaFeed\.html\?clube=\d+$"))
    expect(pagina.locator("#menuFeed .pilulaClube")).to_contain_text("FOTOGRAFIA")
    ok("criar clube: cria com imagem e o criador já participa (vê o botão POSTAR)")

    # --- filtro de "Seus Clubes" e sair do clube
    pagina.goto(BASE + "/telaHome.html")
    expect(pagina.locator("#listaClubes li")).to_have_count(2)
    pagina.fill("#filtroClubes", "foto")
    expect(pagina.locator("#listaClubes li:visible")).to_have_count(1)
    ok("home: filtro de 'Seus Clubes' funciona")
    pagina.goto(BASE + "/tela-desc-clube.html?id=1")
    expect(pagina.locator("#descClubeAbsolute")).to_have_text("SAIR")
    img_antiga = pagina.locator("#descClubeId img").get_attribute("src")
    pagina.set_input_files("#in_imagemClubeTroca", FOTO_CLUBE)
    expect(pagina.locator(".aviso")).to_have_text("Imagem do clube atualizada.")
    nova_img = pagina.locator("#descClubeId img").get_attribute("src")
    assert nova_img != img_antiga and nova_img.startswith("/uploads/clubes/"), (img_antiga, nova_img)
    pagina.goto(BASE + "/telaClubes.html")
    expect(pagina.locator(f".botaoClube img[src='{nova_img}']")).to_have_count(1)
    ok("clube: participante troca a imagem de um clube inicial; aparece na lista de clubes")
    pagina.screenshot(path=str(CAPTURAS / "clubes_img_trocada.png"))
    pagina.goto(BASE + "/tela-desc-clube.html?id=1")
    pagina.screenshot(path=str(CAPTURAS / "desc_clube_troca.png"))
    pagina.click("#descClubeAbsolute")
    expect(pagina.locator("#descClubeAbsolute")).to_have_text("ENTRAR")
    pagina.goto(BASE + "/telaHome.html")
    expect(pagina.locator("#listaClubes li")).to_have_count(1)
    ok("clube: botão SAIR remove a participação")

    # --- logout e novo login
    pagina.click("#linkSair")
    expect(pagina).to_have_url(BASE + "/")
    pagina.goto(BASE + "/telaHome.html")
    expect(pagina).to_have_url(__import__("re").compile("/telaLogin.html"))
    ok("logout: encerra a sessão e protege as páginas")
    pagina.fill("#in_username", USUARIO)
    pagina.fill("#in_usersenha", "senha-errada")
    pagina.click("#botaoCriar")
    expect(pagina.locator(".aviso.erro")).to_have_text("Username ou senha inválidos.")
    pagina.screenshot(path=str(CAPTURAS / "login_erro.png"))
    pagina.fill("#in_usersenha", SENHA)
    pagina.click("#botaoCriar")
    expect(pagina).to_have_url(BASE + "/telaHome.html")
    ok("login: senha errada mostra aviso; senha certa entra e respeita o ?next=")

    navegador.close()

print(f"\n{len(resultados)} verificações OK no navegador.")
if erros_console:
    print("ERROS DE CONSOLE/CSP:", *erros_console, sep="\n  - ")
    sys.exit(1)
print("Nenhum erro de console / violação de CSP.")
