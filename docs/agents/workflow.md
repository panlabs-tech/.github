# Fluxo de desenvolvimento

## Do problema à execução

```
/grilling ou /wayfinder  →  /to-spec  →  /to-tickets  →  /tdd  →  worktree  →  PR  →  merge no verde
```

Uma decisão grande demais para uma sessão vira **mapa** de wayfinding, resolvido um ticket de decisão por vez. Um mapa fechado vira **spec** por frente. Uma spec vira **tickets** com arestas de bloqueio declaradas.

## Modo de implementação autônoma

Disparado por "implementa as issues" ou equivalente:

1. Colete as issues `ready-for-agent` abertas, sem bloqueio pendente.
2. Um **git worktree por issue**, aninhado no próprio repo.
3. `/tdd`: RED → GREEN → refactor.
4. Commit (Conventional Commits) e push.
5. A esteira abre o PR.
6. **Mergeie no verde** e encadeie até as issues acabarem.

## Portões

- **Portão 1, local:** `lefthook` antes do commit, com formatação, verificação, scan de segredos e padrão de mensagem de commit. Neste repo ele mora em [`lefthook.yml`](../../lefthook.yml) e em [`commitlint.config.mjs`](../../commitlint.config.mjs), e a anatomia o cobra em três itens: `local-commit-gate-exists`, `commit-message-standard-declared` e `secret-scan-before-commit`. O scanner é `gitleaks` e não outro por decisão, não por gosto: é o mesmo que o portão 2 roda, e dois scanners fariam "passou no local" e "passou na CI" significarem coisas diferentes.
- **Portão 2, CI:** o workflow de checks no PR.

As ferramentas do portão 1 (`lefthook`, `gitleaks`, o runtime que serve o `npx`) são **equipamento da máquina**, provisionado globalmente ([`docs/maquina.md`](../maquina.md)); o que o repo versiona é a **declaração** de adesão. Um repo aberto numa máquina sem equipamento provisionado perde capacidade por design, e não por omissão.

Todo repo da org expõe os **mesmos nomes de status check**, independentemente de quantas superfícies tem. Isso é feito por um **job de rollup** de id fixo, que declara dependência das pernas por superfície e reporta um status único. O rollup existe **sempre**: inclusive em repo sem superfície nenhuma, onde passa trivialmente.

Sem o rollup, um required check de nome fixo nunca casaria com os status de uma matriz (que saem com os valores anexados ao nome), e um repo sem superfície penduraria o merge para sempre esperando um check que não roda.

O ruleset da org exige exatamente esses nomes, sem exceção por tipo de repo. Enquanto a CI de um repo não os publica, o script de ruleset **retém** aquele repo em vez de convergi-lo: o portão é o nome de check que ele já exige hoje, e `--only` é como o operador afirma que o retrofit daquele repo aterrissou.

## Merge autônomo sob assinatura

A branch default exige **commit assinado**, e o repositório permite **squash como único método de merge**. As duas coisas são uma decisão só: quem assina o commit que aterrissa na branch é o GitHub, no squash via API, e por isso o commit local do agente nunca precisa ser assinado. Ligar a exigência sem restringir o merge quebraria a esteira na hora, porque sob merge-commit ou rebase o commit local não assinado chegaria na branch e reprovaria a regra.

## Forma dos scripts

Todo script deste repo separa decisão de efeito:

```
plan(observed) -> Plan       # puro, testado com fixtures
apply(Plan)    -> efeitos    # fino, sem teste
```

- **Plano é o default.** Rodar sem argumento nunca muda nada; aplicar exige flag explícita.
- Cada item do plano carrega **ação, alvo e motivo**. Plano sem motivo não é revisável.
- **Nenhum alvo é hardcoded.** A lista de repos vem sempre da org viva.
- Um item pode ser **retido**: planejado, mostrado com o motivo da retenção, e não aplicado. É o que permite planejar a frota inteira sem quebrar quem ainda não pode receber a convergência.

Se o `apply` precisa de um `if`, esse `if` está no lugar errado. Item retido não é exceção a isso: o `apply` percorre `plan.applicable`, e quem decidiu reter foi o planner, que escreveu o motivo no próprio item. A tabela de despacho continua sem ramificação.

**A configuração desejada entra como segundo argumento**, `plan(observed, desired)`, porque ela é *dado versionado* e não observação: ela mora em `config/`, não no código. O seam continua sendo o mesmo: uma função pura de estado para plano, e acima dela só a chamada real de API. Um valor `null` no dado significa **ainda não decidido**, e o planner não planeja nada para essa dimensão; isso é diferente de decidido-como-vazio, e quem lê um plano vazio precisa saber qual dos dois é.

**Do outro lado do seam existe a ausência oposta, e ela leva ao lugar contrário.** Uma dimensão que a plataforma se recusa a mostrar é `Unobservable`, um terceiro valor entre observado-ligado e observado-desligado. Ela nunca vira `False`, nunca some do plano e nunca derruba a corrida: vira **item retido**, com o motivo citando o que a plataforma respondeu. Nada é planejado para o que ninguém decidiu; é planejado e retido o que ninguém conseguiu medir. Um repositório privado num plano que não oferece rulesets é o caso vivo: ele não tem ruleset desligado, ele tem ruleset que este observador não alcança, e um plano da frota que morre por causa dele é pior do que um plano parcial. A recusa **por plano** é a única que vira retenção; um 403 de permissão continua sendo erro alto, porque esse tem conserto pelo operador e engoli-lo esconderia o conserto.

O vocabulário vive em `scripts/panlabs/plan.py`, e é **um só**: o mesmo formato serve ao ruleset, ao checker, ao reconcile de workspaces e à poda do heartbeat.

## Conformidade

O checker de conformidade é **read-only**, roda **agendado** como passo do heartbeat da máquina, **alarma na deriva** e **nunca é gate de PR**: anatomia é propriedade do repo, não do diff, e metade dela nem mora no working tree. Um teste guarda a última metade dessa frase: nenhum workflow entregue aqui invoca o checker, e é esta a CI que os outros repos referenciam.

Falha de rede ou de credencial do checker é reportada como **erro**, distinguível de não-conformidade. Um token expirado não pode virar "toda a frota está fora do padrão". A distinção é o **código de saída**, e ele é contrato: `1` é deriva e só deriva, `2` é qualquer coisa que impeça a matriz de existir. O passo do heartbeat mapeia os dois para canais de alarme diferentes.

## Credencial

Operações que mutam configuração de **organização** (ruleset, políticas, features de org) exigem token com escopo `admin:org`. O agente não eleva escopo de token, quem faz isso é o operador, com `gh auth refresh`.

Operações de **leitura** de frota, incluindo o checker, funcionam com o escopo de leitura padrão.
