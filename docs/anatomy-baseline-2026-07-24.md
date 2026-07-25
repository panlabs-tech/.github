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

Gerada pela [issue #27](https://github.com/panlabs-tech/.github/issues/27) com `uv run panlabs-checker --dump-observed tests/fixtures/checker-fleet-2026-07-25.json`, contra o **mesmo catálogo-semente de cinco itens**. Tudo que mudou aqui é observação: a árvore recursiva, o conteúdo do conjunto declarado de arquivos e os metadados de plataforma. Read-only como a primeira, e o retrato está versionado em [`tests/fixtures/checker-fleet-2026-07-25.json`](../tests/fixtures/checker-fleet-2026-07-25.json).

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

**Uma linha que a observação nova conseguiu avaliar e aprovar.** A superfície Node do `tfbox` passou a ser detectada (`web/package.json`, `scripts/package.json`), e o item `node-lockfile-committed` foi avaliado ali pela primeira vez: ele **passa**, porque o repo versiona lockfile junto de cada manifesto. Antes o item não gerava linha por não ser avaliado, o que era indistinguível de aprovado.

**A frota inteira entrou no retrato com o que não mora no working tree.** Descrição, topics, wiki e licença estão no retrato de todos os oito repos, e nenhum item do catálogo-semente os cobra ainda: a #4 é quem decide o que cobrar. O `tfbox` é o único com wiki ligada, e quatro repos não têm licença detectada pela plataforma.

**O conteúdo declarado veio junto.** Os cinco arquivos de `config/checker.json` foram lidos onde existem, e é com esse retrato, sem rede, que o catálogo cheio da #4 pode ser escrito e testado.
