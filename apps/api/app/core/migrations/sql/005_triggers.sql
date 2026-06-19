CREATE OR REPLACE FUNCTION trg_updated_at() RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_sessao_updated_at ON tb_sessao;
CREATE TRIGGER trg_sessao_updated_at
  BEFORE UPDATE ON tb_sessao
  FOR EACH ROW EXECUTE FUNCTION trg_updated_at();
