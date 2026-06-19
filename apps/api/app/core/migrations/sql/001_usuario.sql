CREATE TABLE IF NOT EXISTS tb_usuario (
  id            SERIAL PRIMARY KEY,
  email         VARCHAR(200) UNIQUE NOT NULL,
  nome          VARCHAR(200) NOT NULL,
  senha_hash    VARCHAR(255) NOT NULL,
  permissoes    VARCHAR(500) NOT NULL DEFAULT '',
  is_admin      BOOLEAN NOT NULL DEFAULT FALSE,
  ativo         BOOLEAN NOT NULL DEFAULT TRUE,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  ultimo_login  TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_usuario_email ON tb_usuario (email) WHERE ativo = TRUE;
