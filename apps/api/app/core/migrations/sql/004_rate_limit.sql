IF OBJECT_ID(N'tb_rate_limit', N'U') IS NULL
CREATE TABLE tb_rate_limit (
  usuario_id    INT NOT NULL REFERENCES tb_usuario(id),
  bucket        NVARCHAR(20) NOT NULL,
  janela_inicio DATETIME2 NOT NULL,
  contagem      INT NOT NULL DEFAULT 0,
  PRIMARY KEY (usuario_id, bucket, janela_inicio)
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'idx_rate_limpeza')
CREATE INDEX idx_rate_limpeza ON tb_rate_limit (janela_inicio);
GO
