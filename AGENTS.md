# panlabs-tech/.github

Repo **meta** da org `panlabs-tech`. Ele carrega a própria definição do padrão panlabs, ao lado dos mecanismos que o aplicam e o verificam.

Domínio: governança da org no GitHub, ambiente da máquina de desenvolvimento e convenção de repo. **Nenhuma solução de produto mora aqui**: este repo descreve como as outras se organizam.

## O que vive aqui

- **`profile/README.md`**: o perfil da org, a página que um humano de fora vê em 30 segundos.
- **`.github/workflows/`**: os reusable workflows que todos os repos da org referenciam em vez de copiar.
- **`scripts/`**: o script de ruleset (aplica a configuração de proteção repo a repo), o script de org (converge o que não é ruleset: a política de Actions que sustenta a esteira, segurança, vitrine e features desligadas), o checker de conformidade (mede a frota contra a anatomia), o script de máquina (converge o equipamento global da máquina de desenvolvimento), o script de espaço de trabalho (converge o estado estacionário de `~/workspaces`) e o heartbeat (o hospedeiro de passos que a tarefa diária do host dirige).
- **`config/`**: a configuração desejada, como **dado**. Os scripts leem daqui; nenhum deles crava valor em código.
- **`ANATOMY.md`**: a definição canônica do que é um repo panlabs, com o catálogo completo dos itens por eixo. Item escrito lá tem veredito no checker, e um teste amarra os dois lados: item que só existe no documento é recomendação, e a leitura binária da anatomia não tem nível recomendado.
- **[`docs/maquina.md`](docs/maquina.md)**: o padrão da máquina de desenvolvimento, com o método de instalação por classe, a ordem de bootstrap e os limites honestos da postura de permissão.
- **[`docs/espaco-de-trabalho.md`](docs/espaco-de-trabalho.md)**: o estado estacionário do espaço de trabalho, com o invariante aditivo, o critério de descarte sem eixo de tempo e o preflight que preserva o que só existe local.
- **[`docs/heartbeat.md`](docs/heartbeat.md)**: o heartbeat da máquina, com o motivo de o relógio morar no host, o ciclo oportunista, os canais de alarme e a expectativa honesta sobre o que a compactação rende.

Parte do padrão é **imposta por plataforma** (ruleset e required checks); parte é **documentada e checada** (`ANATOMY.md` + checker). As duas metades moram juntas com dureza honestamente diferente.

## Origem

Este repo é resultado do mapa de wayfinding [O padrão panlabs, org, máquina e repo](https://github.com/panlabs-tech/panlabs/issues/46), que travou 21 decisões em três frentes. O mapa e seus tickets de decisão continuam em `panlabs-tech/panlabs` como registro histórico; o **trabalho vivo** mora aqui.

## Convenções

- **Idioma:** pt-BR em prosa, comentários e commits. Identificador de código em inglês.
- **Markdown sem hard-wrap:** uma linha por parágrafo. Quebra só entre parágrafos, ou onde tem semântica (item de lista, linha de tabela, bloco de código).
- **Conventional Commits**, subject minúsculo.
- **Toda decisão vive num planner puro; o applier não decide nada.** Todo script deste repo separa `plan(observed, desired) → Plan` de `apply(Plan)`, com **plano como default** e aplicação sob flag explícita. Cada item de plano carrega ação, alvo e **motivo**. O `desired` entra como segundo argumento porque é dado versionado, não observação. Ver [`docs/agents/workflow.md`](docs/agents/workflow.md).
- **Nenhum script carrega contagem ou lista de repos.** O alvo é sempre derivado da org viva (`gh repo list panlabs-tech`).
- **A configuração desejada é dado, não código.** Ela mora em `config/`, e um valor ainda não decidido é `null`, o que é diferente de decidido-como-vazio. O planner não planeja nada para uma dimensão não decidida.

## Superfície Python

Este repo **tem** superfície Python: os scripts que aplicam e verificam o padrão. O tipo `meta` deixou de ter stack vazia, e a [issue da anatomia](https://github.com/panlabs-tech/.github/issues/8) carrega a emenda. O caso zero-superfície continua real e continua sendo o fixture que importa, via repo `skills`.

Runtime gerido por `uv`, versão declarada em `.python-version`. Toolchain espelhando as `apps/api` da frota:

| | |
| --- | --- |
| `uv run pytest` | **O comando único de teste**: o mesmo que a CI vai chamar. |
| `uv run ruff check` / `uv run ruff format` | Verificação e formatação. |
| `uv run pyright` | Tipos, em modo estrito sobre `scripts/`. |

O pacote vive em `scripts/panlabs/`. O seam compartilhado está em `scripts/panlabs/plan.py`, e cada script o instancia num subpacote: `panlabs.ruleset` (proteção de branch), `panlabs.org` (o resto da configuração de org e repo), `panlabs.checker` (conformidade, read-only), `panlabs.machine` (o equipamento global da máquina), `panlabs.workspace` (o estado estacionário de `~/workspaces`) e `panlabs.heartbeat` (o hospedeiro de passos da tarefa diária).

## Autonomia

O agente opera com autonomia total sobre o escopo deste repo, implementar, mergear PR verde, aplicar configuração de repo próprio.

**Pare e chame o operador em quatro casos:** (1) trancaria o operador para fora (credencial, token de infra); (2) recriaria o substrato; (3) exige segredo de terceiro; (4) tocaria outro projeto sem alvo confirmado.

**Cláusula desta org:** operações que mutam configuração de organização exigem token com escopo `admin:org`, que é elevado pelo operador, não pelo agente.

## Agent skills

### Issue tracker

Issues vivem no GitHub (`panlabs-tech/.github`), via `gh` CLI. PRs externos **não** são superfície de triagem. Ver [`docs/agents/issue-tracker.md`](docs/agents/issue-tracker.md).

### Triage labels

Vocabulário canônico verbatim: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. Ver [`docs/agents/triage-labels.md`](docs/agents/triage-labels.md).

### Domain docs

Single-context; os docs de domínio moram em `docs/`. Ver [`docs/agents/domain.md`](docs/agents/domain.md).

### Fluxo de desenvolvimento

`/to-spec` → `/to-tickets` → `/tdd` → worktree por issue → commit → push → PR → merge autônomo no verde. Ver [`docs/agents/workflow.md`](docs/agents/workflow.md).
