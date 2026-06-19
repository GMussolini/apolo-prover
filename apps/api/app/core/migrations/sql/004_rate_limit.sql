CREATE TABLE IF NOT EXISTS tb_rate_limit (
  usuario_id    INT NOT NULL REFERENCES tb_usuario(id),
  bucket        VARCHAR(20) NOT NULL,
  janela_inicio TIMESTAMPTZ NOT NULL,
  contagem      INT NOT NULL DEFAULT 0,
  PRIMARY KEY (usuario_id, bucket, janela_inicio)
);

CREATE INDEX IF NOT EXISTS idx_rate_limpeza ON tb_rate_limit (janela_inicio);
