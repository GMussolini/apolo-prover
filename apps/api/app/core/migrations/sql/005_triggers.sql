IF OBJECT_ID(N'trg_sessao_updated_at', N'TR') IS NOT NULL
  DROP TRIGGER trg_sessao_updated_at;
GO
CREATE TRIGGER trg_sessao_updated_at ON tb_sessao
AFTER UPDATE AS
BEGIN
  SET NOCOUNT ON;
  UPDATE s SET updated_at = SYSUTCDATETIME()
  FROM tb_sessao s INNER JOIN inserted i ON s.id = i.id;
END;
GO
