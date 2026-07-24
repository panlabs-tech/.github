"""O script de ruleset: converge a proteção de branch da frota para o desejado.

Instancia o seam de `panlabs.plan` para configuração de repositório:

    fetch_raw(org)          -> observado   # lê a org viva, sem decidir nada
    plan(observed, desired) -> Plan        # puro, testado com fixtures
    apply(plan, effects)                   # tabela de despacho, sem decisão

`desired` é **dado versionado**, não código: os valores são decididos pela
spec de Org #2 e moram em `config/ruleset.json`. Um planner que cravasse a
configuração desejada em código quebraria essa fronteira.
"""
