# `.github`: o repo meta da panlabs

Este é o repositório que carrega a **definição do padrão panlabs**, ao lado dos mecanismos que o aplicam e o verificam.

Ele não é um produto. Todo repo da org `panlabs-tech` responde a alguma coisa que está definida aqui.

## O que mora aqui

| | |
| --- | --- |
| **`profile/README.md`** | O perfil da org: a página que um visitante vê antes de abrir qualquer repo. |
| **`.github/workflows/`** | Os *reusable workflows* que os repos da org referenciam em vez de copiar. Ver [`.github/workflows/README.md`](.github/workflows/README.md). |
| **`.github/dependabot.yml`** | Quais atualizações de dependência o bot abre, e quais delas aterrissam sozinhas no verde. |
| **`scripts/`** | O script de ruleset, que aplica a configuração de proteção repo a repo; o de org, que converge o que não é ruleset (a esteira, segurança e vitrine); o checker de conformidade, que mede a frota contra a anatomia; o de máquina, que converge o equipamento global; o de espaço de trabalho, que converge o estado estacionário de `~/workspaces`; e o heartbeat, o hospedeiro de passos que a tarefa diária do host dirige. |
| **`config/`** | A configuração desejada, como dado versionado. Os scripts leem daqui. |
| **`ANATOMY.md`** | A definição canônica do que é um repo panlabs: três eixos, cinco tipos, invariantes e slots. |
| **`lefthook.yml`** | O portão 1, local: formatação e verificação da superfície Python, scan de segredos e padrão de mensagem de commit, antes do commit. O portão 2 continua sendo a CI, no PR. |

Parte do padrão é **imposta pela plataforma**: rulesets e required checks, que um repo não consegue contornar. Parte é **documentada e checada**: o `ANATOMY.md` e o checker, que alarmam na deriva sem travar nada. As duas metades moram juntas, com dureza honestamente diferente.

## Princípios de construção

**Toda decisão vive num planner puro.** Os scripts daqui separam `plan(observed) → Plan` de `apply(Plan)`. O plano é o default: rodar sem argumento nunca muda nada. Cada item de plano carrega ação, alvo e **motivo**: plano sem motivo não é revisável.

**Nenhum alvo é hardcoded.** A lista de repos vem sempre da org viva, nunca de uma constante. Assim a regra não pode divergir da realidade, e repo novo entra sozinho.

**Um item pode ser planejado e retido.** Quando aplicar uma convergência hoje quebraria o repo que ela deveria proteger, o item entra no plano marcado como *retido*: aparece na leitura, com o motivo, e o `apply` não o executa. Sumir com ele faria o plano mentir sobre a deriva; aplicá-lo faria o script quebrar o que veio consertar.

**Conformidade é binária.** Não existe nível "recomendado": numa org de um mantenedor, recomendação é licença para deriva, e o consumidor do padrão é um agente.

**A configuração desejada é dado, não código.** Ela mora em `config/`, separada do mecanismo que a aplica. Um valor `null` ali significa *ainda não decidido*, e o planner não planeja nada para uma dimensão não decidida, o que é diferente de decidida-como-vazia.

## Rodando os scripts

Os scripts são Python gerido por [`uv`](https://docs.astral.sh/uv/), e usam o `gh` já autenticado da máquina. Nenhuma credencial é guardada em lugar nenhum.

```bash
uv sync                                  # prepara o ambiente

uv run panlabs-ruleset                   # o plano de proteção da org viva
uv run panlabs-ruleset --json            # o mesmo plano, serializado
uv run panlabs-ruleset --apply           # aplica  (exige `admin:org` no token)
uv run panlabs-ruleset --only ORG/REPO   # restringe o plano a um repo (repetível)

uv run panlabs-org                       # o plano de org e repo que não é ruleset
uv run panlabs-org --json                # o mesmo plano, serializado
uv run panlabs-org --apply               # aplica  (exige `admin:org` no token)

uv run panlabs-checker                   # a matriz de deriva da org viva (read-only)
uv run panlabs-checker --json            # a mesma matriz, serializada

uv run panlabs-machine                   # o plano do equipamento global desta máquina
uv run panlabs-machine --json            # o mesmo plano, serializado
uv run panlabs-machine --apply           # aplica  (não usa token nenhum)

uv run panlabs-workspace                 # o plano do espaço de trabalho desta máquina
uv run panlabs-workspace --json          # o mesmo plano, serializado
uv run panlabs-workspace --only PATH     # recorta o plano a um caminho (repetível)
uv run panlabs-workspace --apply         # aplica  (nenhum descarte, veja abaixo)
uv run panlabs-workspace --discard PATH --apply   # autoriza um descarte, um a um

uv run panlabs-heartbeat                 # o plano do heartbeat desta máquina agora
uv run panlabs-heartbeat --json          # o mesmo plano, serializado
uv run panlabs-heartbeat --apply         # roda os passos cuja cadência venceu
```

**Rodar sem argumento nunca muda nada.** Aplicar exige `--apply`, explícito, e só contra a org viva: aplicar a partir de um retrato salvo agiria sobre um estado que já pode ter mudado. O checker não tem `--apply`: ele não tem efeito que mute nada, então a flag não existe.

**Rodar contra a org inteira é seguro por construção.** O ruleset desejado exige nomes fixos de status check, e um repo cuja CI ainda não publica esses nomes penduraria todo PR esperando um status que nunca sai. Por isso o planner **retém** esses repos: a divergência deles aparece no plano, com o motivo, e a aplicação é adiada até o retrofit de CI de cada um. O critério é o nome de check que o repo já exige hoje, que é o melhor proxy do que a CI dele publica.

`--only` restringe o plano a um subconjunto explícito da frota **e** afirma que a CI dos repos nomeados já publica os nomes fixos, levantando o portão para eles. É assim que um repo entra no gate logo depois do retrofit, sem esperar a próxima rodada da frota.

A configuração desejada cobre duas superfícies, porque são dois recursos na API e uma decisão só: o **ruleset** da branch default e a **configuração do repositório** (método de merge, deleção de branch no merge, auto-merge). Exigir commit assinado sem restringir o merge a squash quebraria o merge autônomo na hora, já que o commit local do agente não é assinado e quem assina o commit final é o GitHub, no squash via API. As duas metades aterrissam juntas, nesta ordem, e nunca uma sem a outra.

`panlabs-org` cobre as dimensões que não são proteção de branch: a política de Actions que cria e aprova PR (a que sustenta a esteira), secret scanning, push protection, Dependabot, os defaults de segurança para repo novo, 2FA, descrição da org e dos repos, topics, pins e wiki. Rodá-lo **sem aplicar é a verificação** desses invariantes: a política que quebrou a esteira em julho de 2026 passou oito dias caída porque não existia nada olhando.

Duas dessas dimensões o GitHub não expõe para escrita: a exigência de 2FA (`PATCH /orgs` não a aceita) e os repos fixados no perfil (não há mutação em REST nem em GraphQL). Elas aparecem no plano como itens **manuais**, com o motivo dizendo onde resolver, e o `--apply` não finge aplicá-las.

`panlabs-machine` é o único que não fala com a org: o alvo dele é o **global desta máquina**, e ele não usa token nenhum. Ele cobre os nomes que precisam ser alcançáveis em subprocesso, os diretórios cuja remoção está decidida, a negação de leitura sobre credencial e a cláusula de zero redundância das skills. Duas decisões dele valem a leitura: a negação vale sempre sobre o **alvo resolvido**, porque negar um caminho com link deixa o comando de terminal equivalente passar; e a remoção de um diretório fica **retida** enquanto algo que precisa ser alcançável ainda resolver lá dentro, que é o que impedia a máquina de ficar sem `node` no meio da migração. Ver [`docs/maquina.md`](docs/maquina.md).

`panlabs-workspace` também não fala com a org para escrever: ele lê a listagem viva e converge o **espaço de trabalho** desta máquina. Todo repo da org tem clone sob o diretório que espelha a org, com o remote canônico; o que só existe local é commitado e pushado antes de qualquer faxina; e o que não é da org, tem remote e está pushado aparece como **sugestão** de descarte. Nenhum diretório é apagado sem o operador nomear o alvo em `--discard`, um a um: elegibilidade é sugestão do critério, e a decisão irreversível continua humana. Duas decisões dele valem a leitura: o critério de descarte **não tem eixo de tempo**, e o descarte de worktree é decidido por comparação de **conteúdo**, nunca por identificador de commit, que o squash-merge faz divergir. Ver [`docs/espaco-de-trabalho.md`](docs/espaco-de-trabalho.md).

`panlabs-checker` mede a frota contra a [`ANATOMY.md`](ANATOMY.md) e emite a matriz repo x item. Ele enxerga a **árvore inteira** de cada repo (um manifesto em subpasta de monorepo é superfície igual à da raiz), o **conteúdo** de um conjunto declarado de arquivos em `config/checker.json` (slot dentro de documento e referência à CI compartilhada são conteúdo, não presença de arquivo) e os metadados que **não moram no working tree**: descrição, topics, wiki e licença. Ler mais não é escrever nada: ele é read-only, e não tem `--apply`. O código de saída é a interface de alarme: `1` significa deriva e só deriva, e qualquer coisa que impeça a matriz de existir sai como erro, porque um token expirado não pode virar "toda a frota está fora do padrão". Ele roda **agendado**, como passo do heartbeat, e nunca como gate de PR.

`panlabs-heartbeat` é o **hospedeiro de passos** que a tarefa diária do agendador do host dirige. Ele não é um script de higiene: é o lugar onde um passo declara em qual ramo roda (WSL de pé ou parado), qual é a cadência dele e qual canal de alarme ele usa, e é essa forma que permitiu o checker de conformidade entrar como passo sem que a tarefa fosse reescrita, trazendo o quarto canal junto. A promessa original era mais larga do que o que fechou, e a correção está registrada: passo cujo **corpo já existe** entra só como dado; o checker precisou de um corpo novo, que traduz código de saída em canal, e corpo novo é capacidade nova. Três decisões dele valem a leitura: **disparo diário não é cadência da ação**, e um passo cujo prazo não venceu não entra no plano; o estado do WSL é **tri-estado**, porque tratar não consultado como parado mandaria a compactação para cima de um disco vivo; e o ramo parado atravessa a fronteira como **ordem permanente**, emitida de véspera, porque ele só é executável exatamente quando o planner é inalcançável. Ver [`docs/heartbeat.md`](docs/heartbeat.md).

Operações que mutam configuração de organização exigem token com escopo `admin:org`. Quem eleva o escopo é o operador, com `gh auth refresh -h github.com -s admin:org`. Metade das dimensões de `panlabs-org` também **se lê** com esse escopo: sem ele o GitHub omite os campos em vez de negar a resposta, e por isso um campo omitido vira erro alto, nunca "está desligado".

Testes, verificação e tipos:

```bash
uv run pytest                            # o comando único de teste
uv run ruff check && uv run ruff format  # verificação e formatação
uv run pyright                           # tipos
```

O que é testado é o **planner**: uma função pura de estado observado para plano, exercitada com fixtures capturadas da própria frota. O applier não é testado: ele é uma tabela de despacho, uma chamada de API por ação. Se algum dia ele precisar de um `if`, a decisão vazou para dentro dele, e o conserto é movê-la para o planner.

Junto com o planner, testa-se a **configuração entregue**, incluindo a parte dela que só existe em YAML porque o GitHub exige esse formato. O comportamento dos workflows continua fora: se o gitleaks acha segredo ou se o CodeQL acha alerta são perguntas para o uso, não para o teste. O que se verifica é a fiação, que é decisão nossa: quem depende de quem, e quais alvos a configuração declara.

## Origem

Este repo é o produto de um mapa de wayfinding, [O padrão panlabs: org, máquina e repo](https://github.com/panlabs-tech/panlabs/issues/46), que travou 21 decisões em três frentes ao longo de julho de 2026. O mapa e seus tickets de decisão permanecem em `panlabs-tech/panlabs` como registro histórico. Quando algo aqui parecer arbitrário, o porquê provavelmente está lá.

## Licença

MIT. Ver [LICENSE](LICENSE).
