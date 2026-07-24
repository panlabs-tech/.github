"""Mecanismos que aplicam e verificam o padrao panlabs na org `panlabs-tech`.

Todo script deste repo compartilha o mesmo seam, definido em `panlabs.plan`:

    plan(observed) -> Plan        # puro, testado com fixtures
    apply(Plan)    -> efeitos     # fino, sem teste

Toda decisao vive no planner. Se o applier precisa de um `if`, esse `if` esta
no lugar errado, e o conserto e mover a decisao para cima.
"""
