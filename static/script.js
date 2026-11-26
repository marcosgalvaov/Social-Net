(function () {
    "use strict";

    var TIPOS_IMAGEM = ["image/jpeg", "image/png", "image/gif", "image/webp"];
    var MAX_IMAGEM = 5 * 1024 * 1024;

    function $(seletor, raiz) { return (raiz || document).querySelector(seletor); }

    function csrf() {
        var meta = $('meta[name="csrf-token"]');
        return meta ? meta.content : "";
    }

    function avisar(texto, tipo) {
        var antigo = $(".aviso");
        if (antigo) { antigo.remove(); }
        var el = document.createElement("div");
        el.className = "aviso" + (tipo === "erro" ? " erro" : "");
        el.setAttribute("role", "alert");
        el.textContent = texto;
        document.body.appendChild(el);
        setTimeout(function () { el.remove(); }, 4000);
    }

    function api(url, opcoes) {
        opcoes = opcoes || {};
        var config = {
            method: opcoes.method || "GET",
            credentials: "same-origin",
            headers: { "X-CSRF-Token": csrf() }
        };
        if (opcoes.json !== undefined) {
            config.headers["Content-Type"] = "application/json";
            config.body = JSON.stringify(opcoes.json);
        } else if (opcoes.form) {
            config.body = opcoes.form; //
        }
        return fetch(url, config).then(function (resp) {
            return resp.json().catch(function () { return {}; }).then(function (dados) {
                if (resp.status === 401 && !/^\/api\/auth\/login/.test(url)) {
                    window.location.href = "/telaLogin.html?next=" +
                        encodeURIComponent(window.location.pathname + window.location.search);
                    throw new Error("Sessão expirada. Faça login novamente.");
                }
                if (!resp.ok) { throw new Error(dados.erro || "Algo deu errado. Tente novamente."); }
                return dados;
            });
        }, function () {
            throw new Error("Não foi possível conectar ao servidor.");
        });
    }

    function ligarSeletorImagem(areaClicavel, inputArquivo, imgPrevia) {
        areaClicavel.forEach(function (el) {
            el.addEventListener("click", function () { inputArquivo.click(); });
        });
        inputArquivo.addEventListener("change", function () {
            var arquivo = inputArquivo.files[0];
            if (!arquivo) { return; }
            if (TIPOS_IMAGEM.indexOf(arquivo.type) === -1) {
                avisar("Formato não permitido. Use JPG, PNG, GIF ou WEBP.", "erro");
                inputArquivo.value = "";
                return;
            }
            if (arquivo.size > MAX_IMAGEM) {
                avisar("A imagem excede o limite de 5 MB.", "erro");
                inputArquivo.value = "";
                return;
            }
            imgPrevia.src = URL.createObjectURL(arquivo);
        });
    }

    function irPara(url) { window.location.href = url; }

    function iniciarSair() {
        var link = $("#linkSair");
        if (!link) { return; }
        link.addEventListener("click", function (e) {
            e.preventDefault();
            api("/api/auth/logout", { method: "POST" })
                .then(function (d) { irPara(d.redirecionar || "/"); })
                .catch(function (err) { avisar(err.message, "erro"); });
        });
    }

    // elementos clicaveis
    function iniciarLinksPorData() {
        document.querySelectorAll("[data-href]").forEach(function (el) {
            if (el.tagName !== "BUTTON") {
                el.setAttribute("role", "link");
                el.setAttribute("tabindex", "0");
                el.addEventListener("keydown", function (e) {
                    if (e.key === "Enter") { irPara(el.dataset.href); }
                });
            }
            el.addEventListener("click", function () { irPara(el.dataset.href); });
        });
    }

    /*  index */
    function iniciarIndex() {
        var botao = $("#botaoEntrar");
        if (botao) { botao.addEventListener("click", function () { irPara("/telaHome.html"); }); }
    }

    /*  login  */
    function iniciarLogin() {
        var form = $("#formLogin");
        if (!form) { return; }
        form.addEventListener("submit", function (e) {
            e.preventDefault();
            var botao = $("#botaoCriar", form);
            botao.disabled = true;
            api("/api/auth/login", {
                method: "POST",
                json: {
                    username: $("#in_username").value,
                    senha: $("#in_usersenha").value,
                    next: form.dataset.next
                }
            }).then(function (d) { irPara(d.redirecionar); })
              .catch(function (err) { avisar(err.message, "erro"); botao.disabled = false; });
        });
    }

    /*  cadastro */
    function iniciarCadastro() {
        var form = $("#formCadastro");
        if (!form) { return; }
        var foto = $("#in_userfoto");
        var img = $("#fotoPerfilCadastro");
        ligarSeletorImagem([img], foto, img);

        form.addEventListener("submit", function (e) {
            e.preventDefault();
            var dados = new FormData();
            dados.append("username", $("#in_username").value);
            dados.append("senha", $("#in_usersenha").value);
            if (foto.files[0]) { dados.append("foto", foto.files[0]); }
            var botao = $("#botaoCriar", form);
            botao.disabled = true;
            api("/api/auth/cadastro", { method: "POST", form: dados })
                .then(function (d) { irPara(d.redirecionar); })
                .catch(function (err) { avisar(err.message, "erro"); botao.disabled = false; });
        });
    }

    /*  home  */
    function iniciarHome() {
        var filtro = $("#filtroClubes");
        if (!filtro) { return; }
        filtro.addEventListener("input", function () {
            var termo = filtro.value.trim().toLowerCase();
            document.querySelectorAll("#listaClubes li:not(.semClubes)").forEach(function (li) {
                li.style.display = li.textContent.toLowerCase().indexOf(termo) === -1 ? "none" : "";
            });
        });
    }

    /*  lista de clubes (busca)  */
    function iniciarBuscaClubes() {
        var campo = $("#campoBusca");
        if (!campo) { return; }
        function buscar() {
            var termo = campo.value.trim();
            irPara("/telaClubes.html" + (termo ? "?q=" + encodeURIComponent(termo) : ""));
        }
        $("#barraPesquisa button").addEventListener("click", buscar);
        campo.addEventListener("keydown", function (e) { if (e.key === "Enter") { buscar(); } });
    }

    /*  descrição do clube (entrar / sair)  */
    function iniciarDescricaoClube() {
        var botao = $("#descClubeAbsolute");
        if (!botao || !botao.dataset.id) { return; }
        botao.addEventListener("click", function () {
            var membro = botao.dataset.membro === "1";
            botao.disabled = true;
            api("/api/comunidades/" + encodeURIComponent(botao.dataset.id) + "/participar",
                { method: membro ? "DELETE" : "POST" })
                .then(function (d) {
                    if (membro) {
                        botao.dataset.membro = "0";
                        botao.textContent = "ENTRAR";
                        avisar("Você saiu do clube.");
                    } else {
                        irPara(d.redirecionar);
                        return;
                    }
                    botao.disabled = false;
                })
                .catch(function (err) { avisar(err.message, "erro"); botao.disabled = false; });
        });
    }

    /* ---------- trocar a foto de perfil e a imagem de um clube ---------- */
    function ligarTrocaDeImagem(cfg) {
        var link = $(cfg.link);
        var input = $(cfg.input);
        if (!link || !input) { return; }
        var img = $(cfg.img);
        var gatilhos = [link];
        if (cfg.clicarNaImagem && img) { gatilhos.push(img); }
        gatilhos.forEach(function (el) {
            el.addEventListener("click", function (e) { e.preventDefault(); input.click(); });
        });
        input.addEventListener("change", function () {
            var arquivo = input.files[0];
            if (!arquivo) { return; }
            if (TIPOS_IMAGEM.indexOf(arquivo.type) === -1) {
                avisar("Formato não permitido. Use JPG, PNG, GIF ou WEBP.", "erro");
                input.value = "";
                return;
            }
            if (arquivo.size > MAX_IMAGEM) {
                avisar("A imagem excede o limite de 5 MB.", "erro");
                input.value = "";
                return;
            }
            var dados = new FormData();
            dados.append(cfg.campo, arquivo);
            api(cfg.url(link), { method: "POST", form: dados })
                .then(function (d) {
                    img.src = d[cfg.resposta];
                    avisar(cfg.mensagem);
                })
                .catch(function (err) { avisar(err.message, "erro"); })
                .then(function () { input.value = ""; });
        });
    }

    function iniciarTrocaDeImagens() {
        ligarTrocaDeImagem({
            link: "#linkAlterarFoto", input: "#in_userfotoTroca", img: "#imagemPerfil",
            clicarNaImagem: true, campo: "foto", resposta: "foto",
            url: function () { return "/api/auth/foto"; },
            mensagem: "Foto de perfil atualizada."
        });
        ligarTrocaDeImagem({
            link: "#linkAlterarImagem", input: "#in_imagemClubeTroca", img: "#descClubeId img",
            clicarNaImagem: true, campo: "imagem", resposta: "imagem",
            url: function (link) { return "/api/comunidades/" + encodeURIComponent(link.dataset.id) + "/imagem"; },
            mensagem: "Imagem do clube atualizada."
        });
    }

    /*  criar clube / criar postagem (mesmo layout) */
    function iniciarCriarClube() {
        var botao = $("#criarPostagemAbsolute[data-tipo='clube']");
        if (!botao) { return; }
        var arquivo = $("#in_imagemClube");
        var img = $("#imagemClube");
        ligarSeletorImagem([img, $("#criarPostagemId h1")], arquivo, img);

        botao.addEventListener("click", function () {
            var dados = new FormData();
            dados.append("nome", $("#escreverPostagem").value);
            dados.append("descricao", $("#escolherClube").value);
            if (arquivo.files[0]) { dados.append("imagem", arquivo.files[0]); }
            botao.disabled = true;
            api("/api/comunidades", { method: "POST", form: dados })
                .then(function (d) { irPara(d.redirecionar); })
                .catch(function (err) { avisar(err.message, "erro"); botao.disabled = false; });
        });
    }

    function iniciarCriarPostagem() {
        var botao = $("#criarPostagemAbsolute");
        var arquivo = $("#in_imagem");
        if (!botao || !arquivo) { return; }
        var img = $("#imagemPostagem");
        ligarSeletorImagem([img, $("#criarPostagemId h1")], arquivo, img);

        botao.addEventListener("click", function () {
            var dados = new FormData();
            dados.append("texto", $("#escreverPostagem").value);
            dados.append("clube", $("#escolherClube").value);
            if (arquivo.files[0]) { dados.append("imagens", arquivo.files[0]); }
            botao.disabled = true;
            api("/api/publicacoes", { method: "POST", form: dados })
                .then(function (d) { irPara(d.redirecionar); })
                .catch(function (err) { avisar(err.message, "erro"); botao.disabled = false; });
        });
    }

    /* ---------- feed: curtidas, comentários e exclusão ---------- */
    function montarComentario(c) {
        var li = document.createElement("li");
        li.className = "comentario";
        li.dataset.id = c.id;

        var cab = document.createElement("div");
        cab.className = "comentarioCabecalho";
        var autor = document.createElement("span");
        autor.className = "comentarioAutor";
        autor.textContent = "#" + c.autor.username;
        var data = document.createElement("span");
        data.className = "comentarioData";
        data.textContent = c.data;
        cab.appendChild(autor);
        cab.appendChild(data);
        if (c.meu) {
            var excluir = document.createElement("button");
            excluir.className = "botaoExcluirComentario";
            excluir.dataset.acao = "excluir-comentario";
            excluir.textContent = "EXCLUIR";
            cab.appendChild(excluir);
        }

        var texto = document.createElement("p");
        texto.className = "comentarioTexto";
        texto.textContent = c.texto; // textContent: proteção contra XSS
        li.appendChild(cab);
        li.appendChild(texto);
        return li;
    }

    function carregarComentarios(post) {
        var lista = $(".listaComentarios", post);
        return api("/api/publicacoes/" + post.dataset.id + "/comentarios").then(function (comentarios) {
            lista.textContent = "";
            comentarios.forEach(function (c) { lista.appendChild(montarComentario(c)); });
            post.dataset.carregado = "1";
        });
    }

    function enviarComentario(post) {
        var campo = $(".novoComentario input", post);
        var texto = campo.value.trim();
        if (!texto) { return; }
        api("/api/publicacoes/" + post.dataset.id + "/comentarios", { method: "POST", json: { texto: texto } })
            .then(function (d) {
                $(".listaComentarios", post).appendChild(montarComentario(d.comentario));
                $(".contadorComentarios", post).textContent = d.total;
                campo.value = "";
            })
            .catch(function (err) { avisar(err.message, "erro"); });
    }

    function alternarCurtida(post, botao) {
        var curtido = botao.classList.contains("curtido");
        botao.disabled = true;
        api("/api/publicacoes/" + post.dataset.id + "/curtir", { method: curtido ? "DELETE" : "POST" })
            .then(function (d) {
                botao.classList.toggle("curtido", d.curtiu);
                botao.setAttribute("aria-pressed", d.curtiu ? "true" : "false");
                $(".contadorCurtidas", botao).textContent = d.total;
            })
            .catch(function (err) { avisar(err.message, "erro"); })
            .then(function () { botao.disabled = false; });
    }

    function iniciarFeed() {
        var lista = $("#listaPostagens");
        if (!lista) { return; }

        lista.addEventListener("click", function (e) {
            var botao = e.target.closest("[data-acao]");
            var post = e.target.closest(".postagem");
            if (!botao || !post) { return; }

            switch (botao.dataset.acao) {
                case "curtir":
                    alternarCurtida(post, botao);
                    break;
                case "comentarios":
                    var area = $(".postagemComentarios", post);
                    area.hidden = !area.hidden;
                    if (!area.hidden && !post.dataset.carregado) {
                        carregarComentarios(post).catch(function (err) { avisar(err.message, "erro"); });
                    }
                    break;
                case "enviar-comentario":
                    enviarComentario(post);
                    break;
                case "excluir-comentario":
                    var item = botao.closest(".comentario");
                    if (!window.confirm("Excluir este comentário?")) { return; }
                    api("/api/comentarios/" + item.dataset.id, { method: "DELETE" })
                        .then(function (d) {
                            item.remove();
                            $(".contadorComentarios", post).textContent = d.total;
                        })
                        .catch(function (err) { avisar(err.message, "erro"); });
                    break;
                case "excluir-postagem":
                    if (!window.confirm("Excluir esta postagem?")) { return; }
                    api("/api/publicacoes/" + post.dataset.id, { method: "DELETE" })
                        .then(function () { post.remove(); avisar("Postagem excluída."); })
                        .catch(function (err) { avisar(err.message, "erro"); });
                    break;
            }
        });

        // Enter no campo de comentário envia
        lista.addEventListener("keydown", function (e) {
            if (e.key === "Enter" && e.target.matches(".novoComentario input")) {
                e.preventDefault();
                enviarComentario(e.target.closest(".postagem"));
            }
        });
    }

    /* ---------- inicialização ---------- */
    iniciarSair();
    iniciarLinksPorData();
    iniciarIndex();
    iniciarLogin();
    iniciarCadastro();
    iniciarHome();
    iniciarBuscaClubes();
    iniciarDescricaoClube();
    iniciarTrocaDeImagens();
    iniciarCriarClube();
    iniciarCriarPostagem();
    iniciarFeed();
})();
