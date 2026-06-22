def _format_historico(rows):
    if not rows:
        return "(sem histórico)"
    blocos = []
    for i, (pergunta, resposta) in enumerate(rows, 1):
        resp = (resposta or "").strip()
        if len(resp) > 400:
            resp = resp[:400] + "..."
        blocos.append(f"[{i}] Usuário: {pergunta}\n    APOLO: {resp or '(sem resposta)'}")
    return "\n".join(blocos)


async def run(ctx, deps):
    rows = await deps.store.load_history(ctx.sessao_id, limite=5)
    ctx.historico_txt = _format_historico(rows)
    return
    yield  # async-generator marker
