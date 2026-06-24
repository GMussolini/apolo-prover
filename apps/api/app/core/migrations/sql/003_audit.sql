IF OBJECT_ID(N'tb_audit', N'U') IS NULL
CREATE TABLE tb_audit (
  id          INT IDENTITY(1,1) PRIMARY KEY,
  usuario_id  INT NULL REFERENCES tb_usuario(id),
  acao        NVARCHAR(100) NOT NULL,
  recurso     NVARCHAR(200) NULL,
  payload     NVARCHAR(MAX) NULL,
  ip          NVARCHAR(45) NULL,
  created_at  DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'idx_audit_usuario')
CREATE INDEX idx_audit_usuario ON tb_audit (usuario_id, created_at DESC);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'idx_audit_acao')
CREATE INDEX idx_audit_acao ON tb_audit (acao, created_at DESC);
GO
