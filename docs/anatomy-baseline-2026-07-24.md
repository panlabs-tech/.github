# A primeira matriz de deriva da frota, 2026-07-24

Gerada por `uv run panlabs-checker --org panlabs-tech`, contra o catálogo-semente de `scripts/panlabs/checker/catalog/` (5 itens, os suficientes para exercitar os três escopos da [`ANATOMY.md`](../ANATOMY.md): org, stack e tipo). Não é o catálogo cheio: esse é o trabalho da [spec de Repo #4](https://github.com/panlabs-tech/.github/issues/4), que esta issue bloqueia.

Read-only: gerar esta matriz não mudou nada em nenhum repo. O retrato observado que a produziu está versionado em [`tests/fixtures/checker-fleet-2026-07-24.json`](../tests/fixtures/checker-fleet-2026-07-24.json).

## A matriz

| Repo | Item | Escopo | Motivo |
| --- | --- | --- | --- |
| `panlabs-tech/.github` | `anatomy-doc-exists` | tipo meta | Não tinha `ANATOMY.md` na raiz no momento da captura. Esta própria issue cria o arquivo; o item cai na próxima corrida depois do merge. |
| `panlabs-tech/life-under-control` | `license-exists` | invariante de org | Sem `LICENSE`. |
| `panlabs-tech/panlabs` | `readme-exists` | invariante de org | Sem `README`. |
| `panlabs-tech/panlabs` | `license-exists` | invariante de org | Sem `LICENSE`. |
| `panlabs-tech/tfbox` | `license-exists` | invariante de org | Sem `LICENSE`. |
| `panlabs-tech/travelmanager` | `license-exists` | invariante de org | Sem `LICENSE`. |

`panlabs-tech/skills` e `panlabs-tech/ethitorial` não aparecem: nenhum item do catálogo-semente encontrou deriva neles. Isso não significa "conformes com a anatomia inteira" (o catálogo-semente é pequeno), só que passam no que já foi avaliado.

## Leitura

Bate com o levantamento já publicado na spec de Repo #4: "quatro dos seis não têm LICENSE". Aqui aparecem quatro (`life-under-control`, `panlabs`, `tfbox`, `travelmanager`), a quinta ausência (`.github` antes desta issue) já não conta porque este repo tem LICENSE desde a sua criação.

**Limitação conhecida do catálogo-semente**, registrada para quem for estender via #4: a detecção de superfície olha só a listagem raiz do repositório, não recursa em subpastas. `panlabs-tech/tfbox` tem `package-lock.json` na raiz mas não `package.json` (que mora numa subpasta do monorepo), então a superfície Node dele não é detectada e o item `node-lockfile-committed` não é avaliado ali. Isso não produz falso positivo (o item simplesmente não se aplica), mas também não avalia o que deveria. Corrigir isso é parte do catálogo cheio da #4, que já nomeia layout de monorepo como uma variação por tipo aplicação.

**Corrigida em 2026-07-25 pela [issue #27](https://github.com/panlabs-tech/.github/issues/27)**, junto com o resto do mecanismo. Ver a segunda matriz, no fim deste documento.

## Este é o inventário de retrofit

As seis linhas acima são o ponto de partida da esteira de convergência: cada uma diverge, e a esteira normal de issues contra o checker (`docs/agents/workflow.md`) fatia o retrofit de cada repo até a matriz sair vazia. Adicionar LICENSE aos quatro repositórios listados é o item mais barato e mais repetido do lote.

## `.github` sujeito ao próprio padrão

Também em 2026-07-24: `panlabs-tech/.github` recebeu o ruleset mínimo de `config/ruleset-dotgithub-required-checks.json` (`uv run panlabs-ruleset --config config/ruleset-dotgithub-required-checks.json --only panlabs-tech/.github --apply`), exigindo os dois required checks do contrato de rollup (`checks`, `security`) na branch default. Foi possível porque as duas condições de bloqueio da issue #8 já estavam resolvidas: a #7 (nomes fixos de check) já tinha mergeado, e o token da máquina já carregava `admin:org`, elevado pelo operador antes desta sessão. O PR desta própria issue (#8) é a primeira prova viva: ele só mergeia depois de passar pelos dois checks exigidos.

Ainda em 2026-07-24, a issue #14 convergiu esse mesmo ruleset para o gate completo da spec de Org #2 (assinatura, squash-only, histórico linear, PR obrigatório com zero aprovações, checks estritos, bypass vazio), e o arquivo de configuração mínima citado acima foi aposentado junto: ele passaria a descrever um estado que ninguém deseja mais, e aplicá-lo desfaria o gate. Quem carrega a configuração desejada agora é `config/ruleset.json`, sozinho.

## A segunda matriz, 2026-07-25: o mecanismo enxergando o repo inteiro

Gerada pela [issue #27](https://github.com/panlabs-tech/.github/issues/27) com `uv run panlabs-checker --dump-observed <arquivo>`, contra o **mesmo catálogo-semente de cinco itens**. Tudo que mudou aqui é observação: a árvore recursiva, o conteúdo do conjunto declarado de arquivos e os metadados de plataforma. Read-only como a primeira, e o retrato está versionado em [`tests/fixtures/checker-fleet-2026-07-25.json`](../tests/fixtures/checker-fleet-2026-07-25.json).

| Repo | Item | Escopo | Motivo |
| --- | --- | --- | --- |
| `panlabs-tech/dotfiles` | `license-exists` | invariante de org | Sem `LICENSE`. Repo novo desde a primeira matriz. |
| `panlabs-tech/ethitorial` | `python-runtime-declared` | stack python | **Novo**: superfície Python em subpasta, invisível antes. |
| `panlabs-tech/life-under-control` | `license-exists` | invariante de org | Sem `LICENSE`. |
| `panlabs-tech/life-under-control` | `python-runtime-declared` | stack python | **Novo**, mesma causa. |
| `panlabs-tech/panlabs` | `readme-exists` | invariante de org | Sem `README`. |
| `panlabs-tech/panlabs` | `license-exists` | invariante de org | Sem `LICENSE`. |
| `panlabs-tech/tfbox` | `license-exists` | invariante de org | Sem `LICENSE`. |
| `panlabs-tech/travelmanager` | `license-exists` | invariante de org | Sem `LICENSE`. |
| `panlabs-tech/travelmanager` | `python-runtime-declared` | stack python | **Novo**, mesma causa. |

`panlabs-tech/.github` e `panlabs-tech/skills` não aparecem: nenhum item do catálogo-semente encontrou deriva neles.

### O que a observação nova encontrou, e o que ela silenciou

**Três linhas novas, todas do mesmo eixo e da mesma causa.** As três aplicações da frota têm superfície Python em subpasta de monorepo, e a listagem da raiz não a via. Nenhuma delas declara versão de runtime na raiz. Não é deriva nova: é deriva que existia e ninguém media.

**Uma linha que a observação nova conseguiu avaliar e aprovar.** A superfície Node do `tfbox` passou a ser detectada (`web/package.json`, `scripts/package.json`), e o item `node-lockfile-committed` foi avaliado ali pela primeira vez: ele **passa**, porque o repo versiona `package-lock.json` na raiz. Antes o item não gerava linha por não ser avaliado, o que era indistinguível de aprovado.

**O que os itens exigem continua igual ao de antes**, e o retrato explica por que mexer nisso seria decisão da #4 e não deste ticket. Os cinco repos com superfície Node usam **dois layouts diferentes**: `ethitorial`, `life-under-control` e `travelmanager` têm workspace de `pnpm`, com um único `pnpm-lock.yaml` na raiz servindo `apps/web/package.json`; o `tfbox` versiona lockfile na raiz **e** ao lado de cada manifesto. Exigir lockfile ao lado de cada manifesto reprovaria os três primeiros, e aceitar lockfile em qualquer lugar aprovaria um repo por causa de um lockfile perdido numa pasta que não é a do manifesto. O item continua pedindo o da raiz, que é o que todos os cinco têm hoje, e a escolha entre as duas regras é do catálogo cheio.

**A frota inteira entrou no retrato com o que não mora no working tree.** Descrição, topics, wiki e licença estão no retrato de todos os oito repos, e nenhum item do catálogo-semente os cobra ainda: a #4 é quem decide o que cobrar. O `tfbox` é o único com wiki ligada, e quatro repos não têm licença detectada pela plataforma.

**O conteúdo declarado veio junto.** Os cinco arquivos de `config/checker.json` foram lidos onde existem, e é com esse retrato, sem rede, que o catálogo cheio da #4 pode ser escrito e testado.

### A fixture não carrega repo privado, e o guarda é o próprio dado

A matriz acima é da frota **inteira**, incluindo `panlabs-tech/dotfiles`, que é privado. A fixture versionada não: **este repo é público**, e uma árvore recursiva mais conteúdo de arquivo é exatamente o retrato que não pode atravessar essa fronteira, porque nome de arquivo de repo privado é informação dele.

Por isso `private` entrou no estado observado junto com descrição, topics, wiki e licença. Ele torna a curadoria reproduzível e o guarda mecânico: a fixture é o retrato cru com `.repos` filtrado por `private == false`, e um teste recusa uma fixture que traga repositório privado dentro. A alternativa seria alguém lembrar quais nomes são privados, que envelhece no primeiro repo novo.

```bash
uv run panlabs-checker --dump-observed /tmp/fleet-cru.json
jq -S '{org, repos: [.repos[] | select(.private | not)]}' /tmp/fleet-cru.json \
  > tests/fixtures/checker-fleet-2026-07-25.json
```

## A terceira matriz, 2026-07-27: o catálogo cheio

Gerada pela [issue #28](https://github.com/panlabs-tech/.github/issues/28), contra o catálogo **cheio**: 39 itens em três eixos (23 invariantes, 9 de stack, 7 de tipo), no lugar dos cinco da semente. O mecanismo é o mesmo da segunda matriz; o que mudou é o que ele cobra. Read-only como as duas anteriores, e o retrato está versionado em [`tests/fixtures/checker-fleet-2026-07-27.json`](../tests/fixtures/checker-fleet-2026-07-27.json), com o mesmo filtro de repositório privado.

**88 linhas em 8 repositórios.** A distribuição importa mais que o total:

| Repo | Linhas | Tipo declarado |
| --- | --- | --- |
| `panlabs-tech/.github` | 2 | meta |
| `panlabs-tech/skills` | 9 | skills |
| `panlabs-tech/dotfiles` | 11 | dotfiles |
| `panlabs-tech/ethitorial` | 12 | aplicação |
| `panlabs-tech/panlabs` | 12 | aplicação |
| `panlabs-tech/life-under-control` | 14 | aplicação |
| `panlabs-tech/tfbox` | 14 | módulo de infraestrutura |
| `panlabs-tech/travelmanager` | 14 | aplicação |

E os itens que mais aparecem, que são o retrofit mais barato por serem repetidos:

| Repos | Item |
| --- | --- |
| 7 | `ci-references-shared-workflows` |
| 6 | `status-rollup-contract` |
| 5 | `license-exists`, `local-commit-gate-exists`, `commit-message-standard-declared`, `no-stale-tool-config`, `no-vendored-agent-equipment`, `node-ci-leg` |
| 4 | `agent-guidance-generic-exists`, `agent-doc-issue-tracker`, `agent-doc-triage-labels`, `agent-doc-domain`, `app-mcp-config-versioned` |

### O que esta matriz diz que as anteriores não diziam

**O repo meta sai com duas linhas, e as duas são verdadeiras.** `panlabs-tech/.github` não tem portão local antes do commit nem configuração mecânica do padrão de mensagem: as duas coisas vivem em prosa no `AGENTS.md`, e prosa não é portão. É o item invariante cobrado do repositório que carrega a definição do padrão, exatamente como a spec pediu, e é a primeira vez que ele aparece na matriz por dívida própria em vez de por um arquivo que a própria issue criava.

**O fóssil da orientação de agente foi encontrado, e é um só.** `panlabs-tech/travelmanager` tem `AGENTS.md` e `CLAUDE.md` com conteúdo **idêntico**, byte a byte, e o genérico começa com o título do específico. É o fóssil que a spec de Repo #4 descreve sem nomear o repositório. Os outros quatro casos de deriva de orientação são de outra natureza: `dotfiles`, `life-under-control`, `panlabs` e `skills` não têm `AGENTS.md` nenhum.

**Os dois resíduos de ferramenta batem com o levantamento.** `.codex/` em quatro repositórios (`ethitorial`, `life-under-control`, `panlabs`, `travelmanager`) e `.serena/` num quinto (`tfbox`). O checker alarma; a remoção tem preflight, e ele é humano.

**Equipamento global vendorizado é o item de maior volume por repositório.** Cinco repositórios versionam `.agents/skills/` ou `.claude/`, de 11 a 95 arquivos cada. A des-vendorização acontece dentro do retrofit de cada um.

**Os condicionais se comportaram como condicionais.** `agent-doc-mcps` aparece em dois repositórios e não nos outros seis; `agent-doc-local-dev` em dois; `agent-doc-design` em três. Nenhum deles aparece onde a condição não vale, e `app-local-services-composition` não apareceu em lugar nenhum: as três aplicações com dependência local com estado declaram composição, e a vitrine, que não tem essa dependência, não é cobrada. Esse é o falso positivo que a spec antecipou por escrito, e ele não aconteceu.

**O módulo de infraestrutura não foi reprovado por regra de aplicação.** `tfbox` usa o gerenciador de pacotes divergente e não recebe `app-package-manager-single`: a regra é de tipo aplicação e não o alcança. Ele recebe, sim, os invariantes e os itens da superfície Node que de fato tem.

**Três itens existem e não foram avaliados**, e a corrida diz isso em voz alta: `license-uniform`, `python-runtime-converged` e `node-runtime-converged` comparam contra valor que ainda não foi decidido em `config/anatomy.json`. Silêncio ali é ausência de pergunta, não aprovação.

### Como reproduzir

```bash
uv run panlabs-checker --dump-observed /tmp/fleet-cru.json
jq -S '{org, repos: [.repos[] | select(.private | not)]}' /tmp/fleet-cru.json \
  > tests/fixtures/checker-fleet-2026-07-27.json
```

O retrato de 2026-07-25 continua versionado como registro da segunda matriz. Ele **não** serve de fixture para o catálogo cheio: foi capturado antes de `config/checker.json` declarar os manifestos e o portão local, então arquivos que existem na árvore vieram sem conteúdo, e um item de conteúdo reprovaria um repositório que está certo. Um teste guarda essa correspondência no retrato em uso, para que fixture velha não seja lida como retrato de hoje.

## O meta conforme, e o inventário de retrofit da frota, 2026-07-27

A terceira matriz acima é o alvo; esta seção é o que a [issue #29](https://github.com/panlabs-tech/.github/issues/29) fez com ele. **Read-only sobre a frota:** nenhum repo além do `.github` foi tocado, e nenhuma convergência de outro repo foi executada.

### Primeiro e sozinho, o meta

As duas linhas do `panlabs-tech/.github` eram a mesma dívida, e ela já era conhecida antes de rodar: o fluxo de trabalho documentado prometia gancho de pre-commit com formatação, verificação e scan de segredos, e não havia configuração nenhuma dele versionada aqui. Prosa não é portão.

| Item | Escopo | Situação |
| --- | --- | --- |
| `local-commit-gate-exists` | invariante de org | Fechada por [`lefthook.yml`](../lefthook.yml). |
| `commit-message-standard-declared` | invariante de org | Fechada por [`commitlint.config.mjs`](../commitlint.config.mjs) mais a chamada no portão. |

Com as duas, a matriz do `.github` sai **vazia**: nenhuma retenção, nenhum item remanescente com motivo escrito. `secret-scan-before-commit` não aparecia porque só se aplica onde há portão local; com o portão existindo, ele passa a ser avaliado e **passa**, porque o portão roda `gitleaks`, o mesmo scanner do portão de CI.

Isso importa mais do que duas linhas sugerem. Sem o repo meta conforme, nem o template nasce conforme, nem o retrofit tem alvo, e o repo que define o padrão vira a primeira exceção a ele.

**Uma dependência de máquina, declarada em vez de escondida:** `lefthook` não está instalado nesta máquina. Ele entrou na classe de binário direto de [`docs/maquina.md`](maquina.md) com justificativa própria, e instalá-lo é convergência de máquina, não de repo. O que o repo versiona é a declaração de adesão, que é o que o checker lê.

### Depois, a frota

Uma issue de retrofit por repo divergente, no tracker **deste** repo, com as linhas daquele repo como checklist e a label `ready-for-agent`. Elas nascem abertas e nada foi executado: esta issue entrega o alvo, e a esteira faz a convergência.

| Repo | Linhas | Issue |
| --- | --- | --- |
| `panlabs-tech/skills` | 9 | [#37](https://github.com/panlabs-tech/.github/issues/37) |
| `panlabs-tech/dotfiles` | 11 | [#33](https://github.com/panlabs-tech/.github/issues/33) |
| `panlabs-tech/ethitorial` | 12 | [#34](https://github.com/panlabs-tech/.github/issues/34) |
| `panlabs-tech/panlabs` | 12 | [#36](https://github.com/panlabs-tech/.github/issues/36) |
| `panlabs-tech/life-under-control` | 14 | [#35](https://github.com/panlabs-tech/.github/issues/35) |
| `panlabs-tech/tfbox` | 14 | [#38](https://github.com/panlabs-tech/.github/issues/38) |
| `panlabs-tech/travelmanager` | 14 | [#39](https://github.com/panlabs-tech/.github/issues/39) |

O corpo de cada uma foi **gerado a partir da matriz**, e não escrito à mão: o checklist de um retrofit é exatamente o que o checker acusou naquele retrato, com o motivo de cada linha junto. Um checklist escrito à mão envelheceria no primeiro item que mudasse de texto.

Elas ficam aqui, e não no tracker de cada repo alvo, por decisão do operador: abrir issue em outro projeto é tocar outro projeto, e o alvo é do meta por natureza. Cada retrofit é **independente dos demais**, em qualquer ordem ou em paralelo.

Três coisas que cada corpo carrega, porque já foram decididas e são caras de redescobrir: o alvo é **uniforme**, e a gradualidade existe só na trajetória; a **des-vendorização das skills acontece dentro** do retrofit de cada repo, com preflight antes de remover resíduo de ferramenta; e o **ruleset de nomes fixos de check só pode ser aplicado num repo depois do retrofit dele**, porque aplicar em massa penduraria todo PR da org esperando um status que ninguém publica.

### O retrato versionado reproduz sete dos oito

`panlabs-tech/dotfiles` é privado, e o filtro que o mantém fora da fixture é o mesmo dado observado (`private == false`). As onze linhas dele estão na matriz e na issue #33, mas o motivo de cada uma só é reproduzível contra a org viva:

```bash
uv run panlabs-checker --json | jq -r '.items[] | select(.target=="panlabs-tech/dotfiles")'
```

Publicar a linha sem publicar a prova dela é a escolha honesta entre as duas: uma árvore recursiva mais conteúdo de arquivo é exatamente o retrato que não atravessa a fronteira do privado para dentro de um repo público.
