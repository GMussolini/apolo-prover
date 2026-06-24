IF OBJECT_ID(N'tb_sessao', N'U') IS NULL
CREATE TABLE tb_sessao (
  id          UNIQUEIDENTIFIER NOT NULL PRIMARY KEY DEFAULT NEWID(),
  usuario_id  INT NOT NULL REFERENCES tb_usuario(id),
  titulo      NVARCHAR(200) NULL,
  canal       NVARCHAR(10) NOT NULL DEFAULT 'texto',
  created_at  DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
  updated_at  DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
  is_deleted  BIT NOT NULL DEFAULT 0
);
GO
IF OBJECT_ID(N'tb_pergunta', N'U') IS NULL
CREATE TABLE tb_pergunta (
  id                       UNIQUEIDENTIFIER NOT NULL PRIMARY KEY DEFAULT NEWID(),
  sessao_id                UNIQUEIDENTIFIER NOT NULL REFERENCES tb_sessao(id) ON DELETE CASCADE,
  usuario_id               INT NOT NULL REFERENCES tb_usuario(id),
  pergunta                 NVARCHAR(MAX) NOT NULL,
  pergunta_reformulada     NVARCHAR(MAX) NULL,
  dominio                  NVARCHAR(100) NULL,
  base_conexao             NVARCHAR(20) NULL,
  confidence_classificacao DECIMAL(3,2) NULL,
  origem                   NVARCHAR(20) NOT NULL DEFAULT 'texto',
  created_at               DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
);
GO
IF OBJECT_ID(N'tb_resposta', N'U') IS NULL
CREATE TABLE tb_resposta (
  id                UNIQUEIDENTIFIER NOT NULL PRIMARY KEY DEFAULT NEWID(),
  pergunta_id       UNIQUEIDENTIFIER NOT NULL REFERENCES tb_pergunta(id) ON DELETE CASCADE,
  resposta_texto    NVARCHAR(MAX) NULL,
  sql_gerado        NVARCHAR(MAX) NULL,
  dados_retornados  NVARCHAR(MAX) NULL,
  grafico_sugerido  NVARCHAR(20) NULL,
  spec_grafico      NVARCHAR(MAX) NULL,
  tokens_input      INT NULL,
  tokens_output     INT NULL,
  custo_estimado    DECIMAL(10,6) NULL,
  latencia_ms       INT NULL,
  erro              NVARCHAR(MAX) NULL,
  created_at        DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'idx_pergunta_sessao')
CREATE INDEX idx_pergunta_sessao ON tb_pergunta (sessao_id, created_at);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'idx_sessao_usuario')
CREATE INDEX idx_sessao_usuario ON tb_sessao (usuario_id, updated_at DESC) WHERE is_deleted = 0;
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'idx_resposta_pergunta')
CREATE INDEX idx_resposta_pergunta ON tb_resposta (pergunta_id);
GO
