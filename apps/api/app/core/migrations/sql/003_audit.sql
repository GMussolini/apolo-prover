CREATE TABLE IF NOT EXISTS tb_audit (
  id          SERIAL PRIMARY KEY,
  usuario_id  INT REFERENCES tb_usuario(id),
  acao        VARCHAR(100) NOT NULL,
  recurso     VARCHAR(200),
  payload     JSONB,
  ip          VARCHAR(45),
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_usuario ON tb_audit (usuario_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_acao ON tb_audit (acao, created_at DESC);
