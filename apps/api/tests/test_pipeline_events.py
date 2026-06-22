from app.pipeline.events import Status, Classification, Sql, Token, Chart, ErrorEvent, Done

def test_eventos_simples():
    assert Status("oi").to_wire() == {"type": "status", "text": "oi"}
    assert Token("ab").to_wire() == {"type": "token", "delta": "ab"}
    assert Sql("SELECT 1").to_wire() == {"type": "sql", "sql": "SELECT 1"}
    assert ErrorEvent("x").to_wire() == {"type": "error", "text": "x"}
    assert Classification("D", 0.9).to_wire() == {"type": "classification", "dominio": "D", "confidence": 0.9}
    assert Chart("bar", {"a": 1}).to_wire() == {"type": "chart", "tipo": "bar", "spec": {"a": 1}}

def test_done_tres_formatos():
    assert Done(10).to_wire() == {"type": "done", "latencia_ms": 10}
    assert Done(10, tokens={"input": 1, "output": 2}).to_wire() == {
        "type": "done", "latencia_ms": 10, "tokens": {"input": 1, "output": 2}}
    assert Done(10, tokens={"input": 1, "output": 2}, custo_usd=0.5).to_wire() == {
        "type": "done", "latencia_ms": 10, "tokens": {"input": 1, "output": 2}, "custo_usd": 0.5}
