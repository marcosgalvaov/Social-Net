-- =====================================================================
--  SocialNET - estrutura do banco de dados (MySQL 8+ / MariaDB 10.5+)
--  Executar:  python init_db.py        (ou)   mysql -u root -p < database/init.sql
--  Atenção: recria as tabelas do zero (apaga dados existentes do SocialNET).
-- =====================================================================
CREATE DATABASE IF NOT EXISTS socialnet CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE socialnet;

SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS tb_comentario;
DROP TABLE IF EXISTS tb_curtida;
DROP TABLE IF EXISTS tb_imagem;
DROP TABLE IF EXISTS tb_publicacao;
DROP TABLE IF EXISTS tb_participante;
DROP TABLE IF EXISTS tb_comunidade;
DROP TABLE IF EXISTS tb_usuario;
SET FOREIGN_KEY_CHECKS = 1;

-- Usuários (username único; senha guardada apenas como hash)
CREATE TABLE tb_usuario (
    id_usuario    INT UNSIGNED NOT NULL AUTO_INCREMENT,
    username      VARCHAR(30)  NOT NULL,
    senha_hash    VARCHAR(255) NOT NULL,
    foto_perfil   VARCHAR(255) NULL,
    data_criacao  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id_usuario),
    UNIQUE KEY uq_usuario_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Comunidades (na interface chamadas de "Clubes")
CREATE TABLE tb_comunidade (
    id_comunidade INT UNSIGNED NOT NULL AUTO_INCREMENT,
    nome          VARCHAR(40)  NOT NULL,
    descricao     VARCHAR(200) NOT NULL,
    imagem        VARCHAR(255) NULL,
    id_criador    INT UNSIGNED NULL,
    data_criacao  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id_comunidade),
    UNIQUE KEY uq_comunidade_nome (nome),
    CONSTRAINT fk_comunidade_criador FOREIGN KEY (id_criador)
        REFERENCES tb_usuario (id_usuario) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Participação: a chave primária composta impede participar duas vezes
CREATE TABLE tb_participante (
    id_usuario    INT UNSIGNED NOT NULL,
    id_comunidade INT UNSIGNED NOT NULL,
    data_entrada  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id_usuario, id_comunidade),
    KEY idx_participante_comunidade (id_comunidade),
    CONSTRAINT fk_participante_usuario FOREIGN KEY (id_usuario)
        REFERENCES tb_usuario (id_usuario) ON DELETE CASCADE,
    CONSTRAINT fk_participante_comunidade FOREIGN KEY (id_comunidade)
        REFERENCES tb_comunidade (id_comunidade) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Publicações
CREATE TABLE tb_publicacao (
    id_publicacao   INT UNSIGNED NOT NULL AUTO_INCREMENT,
    id_usuario      INT UNSIGNED NOT NULL,
    id_comunidade   INT UNSIGNED NOT NULL,
    texto           TEXT         NOT NULL,
    data_publicacao DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id_publicacao),
    KEY idx_publicacao_comunidade_data (id_comunidade, data_publicacao),
    KEY idx_publicacao_usuario (id_usuario),
    CONSTRAINT fk_publicacao_usuario FOREIGN KEY (id_usuario)
        REFERENCES tb_usuario (id_usuario) ON DELETE CASCADE,
    CONSTRAINT fk_publicacao_comunidade FOREIGN KEY (id_comunidade)
        REFERENCES tb_comunidade (id_comunidade) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Imagens das publicações (arquivo em disco; aqui só o caminho relativo)
CREATE TABLE tb_imagem (
    id_imagem     INT UNSIGNED NOT NULL AUTO_INCREMENT,
    id_publicacao INT UNSIGNED NOT NULL,
    caminho       VARCHAR(255) NOT NULL,
    ordem         TINYINT UNSIGNED NOT NULL DEFAULT 0,
    PRIMARY KEY (id_imagem),
    KEY idx_imagem_publicacao (id_publicacao),
    CONSTRAINT fk_imagem_publicacao FOREIGN KEY (id_publicacao)
        REFERENCES tb_publicacao (id_publicacao) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Curtidas: chave primária composta impede curtida duplicada
CREATE TABLE tb_curtida (
    id_usuario    INT UNSIGNED NOT NULL,
    id_publicacao INT UNSIGNED NOT NULL,
    data_curtida  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id_usuario, id_publicacao),
    KEY idx_curtida_publicacao (id_publicacao),
    CONSTRAINT fk_curtida_usuario FOREIGN KEY (id_usuario)
        REFERENCES tb_usuario (id_usuario) ON DELETE CASCADE,
    CONSTRAINT fk_curtida_publicacao FOREIGN KEY (id_publicacao)
        REFERENCES tb_publicacao (id_publicacao) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Comentários
CREATE TABLE tb_comentario (
    id_comentario   INT UNSIGNED NOT NULL AUTO_INCREMENT,
    id_publicacao   INT UNSIGNED NOT NULL,
    id_usuario      INT UNSIGNED NOT NULL,
    texto           VARCHAR(500) NOT NULL,
    data_comentario DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id_comentario),
    KEY idx_comentario_publicacao_data (id_publicacao, data_comentario),
    KEY idx_comentario_usuario (id_usuario),
    CONSTRAINT fk_comentario_publicacao FOREIGN KEY (id_publicacao)
        REFERENCES tb_publicacao (id_publicacao) ON DELETE CASCADE,
    CONSTRAINT fk_comentario_usuario FOREIGN KEY (id_usuario)
        REFERENCES tb_usuario (id_usuario) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Dados iniciais: os 9 clubes que já existiam na interface (telaClubes.html).
-- A descrição de MÚSICA é a que estava em tela-desc-clube.html; as demais são exemplos.
INSERT INTO tb_comunidade (nome, descricao) VALUES
('MÚSICA',     'O clube de Música é perfeito para quem é apaixonado por ritmo - Se você não deixa o fone de ouvido de lado nem por um minuto, entre agora!'),
('LIVROS',     'Para quem vive entre páginas: indique leituras, comente histórias e descubra o seu próximo livro favorito.'),
('ESPORTES',   'Treinos, jogos e resultados: compartilhe a sua paixão pelo esporte com quem não perde uma partida.'),
('FILMES',     'Do clássico ao lançamento: conte o que você assistiu e descubra o que vale a pipoca.'),
('ESTUDOS',    'Dicas, resumos e rotinas de estudo para aprender juntos e manter o foco.'),
('RPG',        'Mesas, personagens e aventuras: encontre a sua próxima campanha.'),
('JOGOS',      'Lançamentos, partidas e conquistas: o ponto de encontro de quem joga.'),
('ARTE',       'Desenhos, pinturas e criações: mostre o que você faz e inspire-se no trabalho dos outros.'),
('TECNOLOGIA', 'Novidades, projetos e dúvidas sobre programação, gadgets e tudo que roda em silício.');
