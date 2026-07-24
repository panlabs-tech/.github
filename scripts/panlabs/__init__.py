"""Mecanismos que aplicam e verificam o padrão panlabs na org `panlabs-tech`.

Todo script deste repo compartilha o mesmo seam, definido em `panlabs.plan`:

    plan(observed, desired) -> Plan   # puro, testado com fixtures
    apply(Plan, efeitos)             # fino, sem teste

Toda decisão vive no planner. Se o applier precisa de um `if`, esse `if` está
no lugar errado, e o conserto é mover a decisão para cima.
"""
