CREATE TABLE IF NOT EXISTS tb_sessao (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  usuario_id  INT NOT NULL REFERENCES tb_usuario(id),
  titulo      VARCHAR(200),
  canal       VARCHAR(10) NOT NULL DEFAULT 'texto',
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  is_deleted  BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS tb_pergunta (
  id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  sessao_id                UUID NOT NULL REFERENCES tb_sessao(id) ON DELETE CASCADE,
  usuario_id               INT NOT NULL REFERENCES tb_usuario(id),
  pergunta                 TEXT NOT NULL,
  pergunta_reformulada     TEXT,
  dominio                  VARCHAR(100),
  base_conexao             VARCHAR(20),
  confidence_classificacao DECIMAL(3,2),
  origem                   VARCHAR(20) NOT NULL DEFAULT 'texto',
  created_at               TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS tb_resposta (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  pergunta_id       UUID NOT NULL REFERENCES tb_pergunta(id) ON DELETE CASCADE,
  resposta_texto    TEXT,
  sql_gerado        TEXT,
  dados_retornados  JSONB,
  grafico_sugerido  VARCHAR(20),
  spec_grafico      JSONB,
  tokens_input      INT,
  tokens_output     INT,
  custo_estimado    DECIMAL(10,6),
  latencia_ms       INT,
  erro              TEXT,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pergunta_sessao ON tb_pergunta (sessao_id, created_at);
CREATE INDEX IF NOT EXISTS idx_sessao_usuario ON tb_sessao (usuario_id, updated_at DESC) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_resposta_pergunta ON tb_resposta (pergunta_id);
