from app.core.permissoes import usuario_pode


def test_dominio_aberto_qualquer_um_acessa():
    assert usuario_pode(usuario_permissoes="", dominio_requer=())
    assert usuario_pode(usuario_permissoes="rh", dominio_requer=())


def test_dominio_restrito_exige_permissao():
    assert not usuario_pode(usuario_permissoes="rh", dominio_requer=("coordenador",))
    assert usuario_pode(usuario_permissoes="coordenador,rh", dominio_requer=("coordenador",))


def test_dominio_multipermissao_basta_uma():
    assert usuario_pode(usuario_permissoes="financeiro", dominio_requer=("financeiro", "rh"))


def test_admin_passa_em_tudo():
    assert usuario_pode(usuario_permissoes="", dominio_requer=("coordenador",), is_admin=True)
