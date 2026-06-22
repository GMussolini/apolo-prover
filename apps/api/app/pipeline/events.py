from dataclasses import dataclass


@dataclass
class Status:
    text: str
    def to_wire(self): return {"type": "status", "text": self.text}

@dataclass
class Classification:
    dominio: str
    confidence: float
    def to_wire(self): return {"type": "classification", "dominio": self.dominio, "confidence": self.confidence}

@dataclass
class Sql:
    sql: str
    def to_wire(self): return {"type": "sql", "sql": self.sql}

@dataclass
class Token:
    delta: str
    def to_wire(self): return {"type": "token", "delta": self.delta}

@dataclass
class Chart:
    tipo: str
    spec: dict
    def to_wire(self): return {"type": "chart", "tipo": self.tipo, "spec": self.spec}

@dataclass
class ErrorEvent:
    text: str
    def to_wire(self): return {"type": "error", "text": self.text}

@dataclass
class Done:
    latencia_ms: int
    tokens: dict | None = None
    custo_usd: float | None = None
    def to_wire(self):
        d = {"type": "done", "latencia_ms": self.latencia_ms}
        if self.tokens is not None:
            d["tokens"] = self.tokens
        if self.custo_usd is not None:
            d["custo_usd"] = self.custo_usd
        return d
