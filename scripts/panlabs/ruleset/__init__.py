"""O script de ruleset: converge a protecao de branch da frota para o desejado.

Instancia o seam de `panlabs.plan` para configuracao de repositorio:

    observe(org)            -> Observed   # le a org viva, sem decidir nada
    plan(observed, desired) -> Plan       # puro, testado com fixtures
    apply(plan, effects)    -> efeitos    # tabela de despacho, sem decisao

`desired` e **dado versionado**, nao codigo -- os valores sao decididos pela
spec de Org #2 e moram em `config/ruleset.json`. Um planner que cravasse a
configuracao desejada em codigo quebraria essa fronteira.
"""
