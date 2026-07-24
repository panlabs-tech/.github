"""O checker de conformidade: mede a frota contra a anatomia (`ANATOMY.md`).

Instancia o seam de `panlabs.plan` para conformidade, sem `desired`: a
anatomia não é dado configurável por spec de Org, é o catálogo deste pacote.

    fetch_raw(org)  -> observado   # lê a org viva, sem decidir nada
    plan(observed)  -> Plan        # puro, testado com fixtures
    apply(plan, ...)                # aqui, só formatar e notificar

Read-only por construção: não existe efeito que mute nada, e portanto não
existe flag de aplicação neste script.
"""
