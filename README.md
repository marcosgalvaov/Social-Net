<<<<<<< HEAD
# SocialNET

Rede social simplificada: cadastro/login, clubes (comunidades), postagens com imagem, feeds, curtidas e comentários.
Stack: HTML, CSS, JavaScript, Python, Flask, PyMySQL e MySQL (sem frameworks frontend e sem ORM).

## Estrutura

```
app.py                 aplicação Flask (sessão, CSRF, cabeçalhos de segurança, erros)
config.py              configurações (lê o .env)
init_db.py             cria o banco executando database/init.sql
requirements.txt
.env.example           modelo das credenciais (copie para .env)
database/
  init.sql             tabelas, restrições e os 9 clubes iniciais
  connection.py        conexão PyMySQL + helpers de SQL parametrizado
  queries.py           consultas reutilizadas (feeds, clubes...)
routes/                auth, comunidade, publicacao, feed, curtida, comentario (Blueprints)
utils.py               login_required, CSRF, validação, upload seguro
templates/             as páginas da SUA interface (agora com Jinja) + telaFeed e tela-criar-clube
static/                style.css, script.js, img/  (servidos nas mesmas URLs de antes: /style.css, /img/...)
uploads/               imagens enviadas (fora de static/; só são servidas como imagem)
interface_original/    HTML/CSS exatamente como vieram no ZIP, para comparar
tests/                 test_integracao.py (backend + MySQL) e e2e_navegador.py (navegador real)
```

## Como rodar

1. Python 3.10+ e MySQL 8 (ou MariaDB 10.5+) instalados e ativos.
2. `pip install -r requirements.txt` (de preferência dentro de um venv).
3. Copie `.env.example` para `.env` e preencha `SECRET_KEY` e as credenciais do MySQL.
   Gere uma chave com: `python -c "import secrets; print(secrets.token_hex(32))"`
4. Crie o banco: `python init_db.py` (ou `mysql -u root -p < database/init.sql`).
   **Atenção:** recria as tabelas do zero.
5. Inicie: `python app.py` e acesse http://127.0.0.1:5000

## Rotas principais

Páginas (mesmos nomes de arquivo da interface): `/`, `/telaLogin.html`, `/telaCadastro.html`, `/telaHome.html`,
`/telaClubes.html`, `/tela-desc-clube.html?id=`, `/telaCriar.html`, `/tela-criar-clube.html`,
`/tela-criar-postagem.html`, `/telaFeed.html` (feed principal) e `/telaFeed.html?clube=ID` (feed do clube).

API (JSON): `POST /api/auth/cadastro|login|logout`, `GET /api/auth/me`,
`GET|POST /api/comunidades`, `POST|DELETE /api/comunidades/<id>/participar`, `POST /api/comunidades/<id>/imagem`, `POST /api/auth/foto`,
`POST /api/publicacoes`, `DELETE /api/publicacoes/<id>`, `GET /api/feed[?clube=&pagina=]`,
`POST|DELETE /api/publicacoes/<id>/curtir`, `GET|POST /api/publicacoes/<id>/comentarios`, `DELETE /api/comentarios/<id>`.

## Decisões tomadas

- "Clube" na interface = `tb_comunidade` no banco. Nome do clube é único (sem diferenciar maiúsculas/acentos).
- Todas as páginas, exceto início, login e cadastro, exigem login. Clubes são públicos: qualquer usuário logado vê o feed,
  curte e comenta; **só participantes publicam**.
- Trocar a imagem de um clube: o criador altera o dele; os clubes sem criador (os 9 iniciais) podem ser alterados por qualquer participante. Trocar a foto de perfil: só o próprio usuário. A imagem anterior é apagada do disco.
- A interface tem um único campo de imagem por postagem; o backend e o banco aceitam até 4 (`tb_imagem`).
- Descrição de clube limitada a 200 caracteres para não quebrar o layout posicionado em `tela-desc-clube.html`.
- Segurança: hash de senha (Werkzeug), SQL parametrizado, sessão assinada (HttpOnly, SameSite=Lax), token CSRF em toda
  ação que altera dados, autorização no servidor (usuário sempre vem da sessão), escape automático do Jinja +
  `textContent` no JS, CSP restritiva, upload validado por extensão **e** bytes reais (JPG/PNG/GIF/WEBP, 5 MB, nome gerado
  pelo servidor, SVG proibido).

## Testes

- `python -m unittest tests.test_integracao -v` — usa o banco separado `socialnet_teste` (o usuário do MySQL precisa poder criar bancos).
- `python tests/e2e_navegador.py` — opcional: `pip install playwright && playwright install chromium`, servidor rodando e banco recém-criado.

## Limitações

- Sem limite de tentativas de login, recuperação de senha ou edição de perfil/postagens.
- Servidor de desenvolvimento do Flask; para produção use um servidor WSGI + HTTPS e `SESSION_COOKIE_SECURE=1`.
- Datas usam o fuso do servidor MySQL.
- Não há exclusão/edição de clubes nem moderação.
=======
# Social-Net
>>>>>>> 0a77b836b7ee3f75bd1d1c934dafddb61954d4a9
