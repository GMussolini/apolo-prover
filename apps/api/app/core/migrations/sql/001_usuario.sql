IF OBJECT_ID(N'tb_usuario', N'U') IS NULL
CREATE TABLE tb_usuario (
  id            INT IDENTITY(1,1) PRIMARY KEY,
  email         NVARCHAR(200) NOT NULL UNIQUE,
  nome          NVARCHAR(200) NOT NULL,
  senha_hash    NVARCHAR(255) NOT NULL,
  permissoes    NVARCHAR(500) NOT NULL DEFAULT '',
  is_admin      BIT NOT NULL DEFAULT 0,
  ativo         BIT NOT NULL DEFAULT 1,
  created_at    DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
  ultimo_login  DATETIME2 NULL
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'idx_usuario_email')
CREATE INDEX idx_usuario_email ON tb_usuario (email) WHERE ativo = 1;
GO
