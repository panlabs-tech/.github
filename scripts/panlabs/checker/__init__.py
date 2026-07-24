"""O checker de conformidade: mede a frota contra a anatomia (`ANATOMY.md`).

Instancia o seam de `panlabs.plan` para conformidade, sem `desired`: a
anatomia não é dado configurável por spec de Org, é o catálogo deste pacote.

    fetch_raw(org)  -> observado   # lê a org viva, sem decidir nada
    plan(observed)  -> Plan        # puro, testado com fixtures

Read-only por construção: não existe `apply` neste pacote, porque não existe
efeito que mute nada. "Aplicar" aqui é só o CLI formatando e imprimindo o
`Plan` -- por isso não existe flag de aplicação neste script.
"""
