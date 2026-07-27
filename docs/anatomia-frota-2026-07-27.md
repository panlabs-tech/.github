# A frota contra o catálogo cheio, 2026-07-27

A primeira matriz medida contra a anatomia **inteira**: 33 itens nos três eixos, e não mais o catálogo-semente de cinco. As duas matrizes anteriores estão em [`anatomy-baseline-2026-07-24.md`](anatomy-baseline-2026-07-24.md), e valem como registro de um alvo menor, não como comparação item a item.

Gerada por `uv run panlabs-checker --dump-observed <arquivo>`, contra a org viva. **Read-only:** gerar esta matriz não mudou nada em nenhum repo, e nenhuma convergência de repo alheio foi executada por esta issue. O retrato observado que a produziu está versionado em [`tests/fixtures/checker-fleet-2026-07-27.json`](../tests/fixtures/checker-fleet-2026-07-27.json), com os repos privados filtrados pelo próprio dado observado (`private == false`), como as corridas anteriores.

**64 linhas em 8 repos.** Uma delas é do `.github` e as outras 63 são o inventário de retrofit da frota.

## O meta, primeiro e sozinho

| Repo | Item | Escopo | Situação |
| --- | --- | --- | --- |
| `panlabs-tech/.github` | `portao-local-existe` | invariante de org | **Fechada pela issue #29**, no mesmo PR que publica esta matriz. |

Uma linha só, e ela era a lacuna já conhecida antes de rodar: o fluxo de trabalho documentado prometia gancho de pre-commit com formatação, verificação e scan de segredos, e não havia configuração nenhuma dele versionada aqui. [`lefthook.yml`](../lefthook.yml) e [`commitlint.config.mjs`](../commitlint.config.mjs) a fecham, e com eles a matriz do `.github` sai **vazia**: nenhuma retenção, nenhum item remanescente com motivo escrito.

Isso importa mais do que o tamanho sugere. Sem o repo meta conforme, nem o template nasce conforme, nem o retrofit tem alvo, e o repo que define o padrão vira a primeira exceção a ele.

Os outros dois itens de disciplina de versionamento (`padrao-de-mensagem-de-commit` e `scan-de-segredos-antes-do-commit`) não aparecem na matriz porque só se aplicam onde o portão existe: sem o arquivo, o conserto é um só, e a matriz pede um só.

## A frota

| Repo | Item | Escopo |
| --- | --- | --- |
| `panlabs-tech/dotfiles` | `license-exists` | invariante de org |
| `panlabs-tech/dotfiles` | `agent-entrypoint-generico` | invariante de org |
| `panlabs-tech/dotfiles` | `agent-docs-obrigatorios` | invariante de org |
| `panlabs-tech/dotfiles` | `portao-local-existe` | invariante de org |
| `panlabs-tech/dotfiles` | `ci-referencia-workflows-compartilhados` | invariante de org |
| `panlabs-tech/dotfiles` | `topics-declarados` | invariante de org |
| `panlabs-tech/ethitorial` | `agent-docs-obrigatorios` | invariante de org |
| `panlabs-tech/ethitorial` | `sem-configuracao-stale-de-ferramenta` | invariante de org |
| `panlabs-tech/ethitorial` | `sem-equipamento-global-versionado` | invariante de org |
| `panlabs-tech/ethitorial` | `ci-referencia-workflows-compartilhados` | invariante de org |
| `panlabs-tech/ethitorial` | `contrato-de-nomes-de-status` | invariante de org |
| `panlabs-tech/ethitorial` | `python-runtime-declared` | stack python |
| `panlabs-tech/ethitorial` | `python-ci-referencia-perna-compartilhada` | stack python |
| `panlabs-tech/ethitorial` | `node-ci-referencia-perna-compartilhada` | stack node |
| `panlabs-tech/ethitorial` | `aplicacao-mcp-versionado-com-placeholder` | tipo aplicacao |
| `panlabs-tech/life-under-control` | `license-exists` | invariante de org |
| `panlabs-tech/life-under-control` | `agent-entrypoint-generico` | invariante de org |
| `panlabs-tech/life-under-control` | `agent-entrypoint-primario-referencia-generico` | invariante de org |
| `panlabs-tech/life-under-control` | `sem-configuracao-stale-de-ferramenta` | invariante de org |
| `panlabs-tech/life-under-control` | `sem-equipamento-global-versionado` | invariante de org |
| `panlabs-tech/life-under-control` | `portao-local-existe` | invariante de org |
| `panlabs-tech/life-under-control` | `ci-referencia-workflows-compartilhados` | invariante de org |
| `panlabs-tech/life-under-control` | `contrato-de-nomes-de-status` | invariante de org |
| `panlabs-tech/life-under-control` | `python-runtime-declared` | stack python |
| `panlabs-tech/life-under-control` | `python-ci-referencia-perna-compartilhada` | stack python |
| `panlabs-tech/life-under-control` | `node-ci-referencia-perna-compartilhada` | stack node |
| `panlabs-tech/life-under-control` | `aplicacao-mcp-versionado-com-placeholder` | tipo aplicacao |
| `panlabs-tech/panlabs` | `readme-exists` | invariante de org |
| `panlabs-tech/panlabs` | `license-exists` | invariante de org |
| `panlabs-tech/panlabs` | `agent-entrypoint-generico` | invariante de org |
| `panlabs-tech/panlabs` | `agent-entrypoint-primario-referencia-generico` | invariante de org |
| `panlabs-tech/panlabs` | `sem-configuracao-stale-de-ferramenta` | invariante de org |
| `panlabs-tech/panlabs` | `sem-equipamento-global-versionado` | invariante de org |
| `panlabs-tech/panlabs` | `scan-de-segredos-antes-do-commit` | invariante de org |
| `panlabs-tech/panlabs` | `ci-referencia-workflows-compartilhados` | invariante de org |
| `panlabs-tech/panlabs` | `node-ci-referencia-perna-compartilhada` | stack node |
| `panlabs-tech/panlabs` | `aplicacao-gerenciador-de-pacotes-unico` | tipo aplicacao |
| `panlabs-tech/panlabs` | `aplicacao-layout-de-monorepo` | tipo aplicacao |
| `panlabs-tech/panlabs` | `aplicacao-mcp-versionado-com-placeholder` | tipo aplicacao |
| `panlabs-tech/panlabs` | `aplicacao-exemplo-de-variaveis-de-ambiente` | tipo aplicacao |
| `panlabs-tech/skills` | `agent-entrypoint-generico` | invariante de org |
| `panlabs-tech/skills` | `agent-docs-obrigatorios` | invariante de org |
| `panlabs-tech/skills` | `portao-local-existe` | invariante de org |
| `panlabs-tech/skills` | `ci-referencia-workflows-compartilhados` | invariante de org |
| `panlabs-tech/tfbox` | `license-exists` | invariante de org |
| `panlabs-tech/tfbox` | `agent-docs-obrigatorios` | invariante de org |
| `panlabs-tech/tfbox` | `sem-configuracao-stale-de-ferramenta` | invariante de org |
| `panlabs-tech/tfbox` | `sem-equipamento-global-versionado` | invariante de org |
| `panlabs-tech/tfbox` | `portao-local-existe` | invariante de org |
| `panlabs-tech/tfbox` | `ci-referencia-workflows-compartilhados` | invariante de org |
| `panlabs-tech/tfbox` | `node-runtime-declared` | stack node |
| `panlabs-tech/travelmanager` | `license-exists` | invariante de org |
| `panlabs-tech/travelmanager` | `agent-entrypoint-primario-referencia-generico` | invariante de org |
| `panlabs-tech/travelmanager` | `sem-configuracao-stale-de-ferramenta` | invariante de org |
| `panlabs-tech/travelmanager` | `sem-equipamento-global-versionado` | invariante de org |
| `panlabs-tech/travelmanager` | `scan-de-segredos-antes-do-commit` | invariante de org |
| `panlabs-tech/travelmanager` | `ci-referencia-workflows-compartilhados` | invariante de org |
| `panlabs-tech/travelmanager` | `contrato-de-nomes-de-status` | invariante de org |
| `panlabs-tech/travelmanager` | `python-runtime-declared` | stack python |
| `panlabs-tech/travelmanager` | `python-portao-local-declara-ferramenta` | stack python |
| `panlabs-tech/travelmanager` | `python-ci-referencia-perna-compartilhada` | stack python |
| `panlabs-tech/travelmanager` | `node-ci-referencia-perna-compartilhada` | stack node |
| `panlabs-tech/travelmanager` | `aplicacao-mcp-versionado-com-placeholder` | tipo aplicacao |

O motivo de cada linha vive na saída do checker, e não aqui: `uv run panlabs-checker --observed tests/fixtures/checker-fleet-2026-07-27.json` reproduz a matriz inteira, com motivo, sem tocar a rede.

## Leitura

**Nenhum repo da frota está conforme, e nenhum está longe.** A mediana é de oito linhas, e a maioria delas é o mesmo conserto repetido em repos diferentes. Sete dos oito repos falham em `ci-referencia-workflows-compartilhados`, o que confirma o que a spec de Repo já media: os arquivos de CI nasceram copiados um do outro e divergiram entre 48% e 86% em sete semanas. O `.github` é o único que referencia a CI compartilhada, porque é ele quem a publica.

**Cinco repos versionam equipamento global, e cinco versionam configuração stale de ferramenta.** São os dois itens mais repetidos depois da CI, e os dois têm o mesmo formato de conserto: apagar árvore que não pertence ao repo. A des-vendorização das skills acontece **dentro** do retrofit de cada repo, e não como esforço à parte; o resíduo de agente concorrente (`.codex/`, `.github/copilot-instructions.md`) e o de ferramenta de indexação (`.serena/`) saem no mesmo movimento, depois do preflight que pergunta se aquilo é candidato a promoção global.

**Três aplicações não versionam configuração de MCP com placeholder.** O padrão atual é a configuração real sempre gitignorada com segredo literal dentro, e um exemplo versionado ao lado: nunca de fato compartilhada, apesar do nome. Em duas delas isso não é criar arquivo novo, é renomear o exemplo existente e tirá-lo do gitignore.

**A vitrine é o quase-rewrite, e a matriz mostra por quê.** `panlabs` carrega treze linhas, entre elas gerenciador de pacotes divergente e código plano na raiz. A esteira fatia isso em pedaços mergeáveis; o alvo continua uniforme, e a gradualidade existe só na trajetória.

**O módulo de infraestrutura não é cobrado pela regra de gerenciador de pacotes**, e a matriz prova a distinção: `tfbox` usa o gerenciador divergente igual à vitrine, e a linha `aplicacao-gerenciador-de-pacotes-unico` aparece só na vitrine. Ele é variante declarada, não exceção: continua cobrado de todo invariante e da superfície Node que tem.

**Dois repos de stack vazia passam no item que os define.** `skills` e `dotfiles` não têm superfície nenhuma, e nenhum item de stack os alcança. É o fixture que quebra um contrato de required checks ingênuo, e é por isso que o rollup existe sempre.

## O que a matriz não mede, e é declarado

**A convergência de versão maior de runtime está `null` no dado**, e o item existe sem avaliar nada. Os quatro repos com superfície Node declaram 22 e 24, metade e metade; escolher o número da frota é decisão do operador, e um checker que a inventasse estaria cobrando regra que ninguém decidiu. O CLI reporta a dimensão pelo nome a cada corrida, para que o silêncio não seja lido como conformidade.

**A superfície Terraform não tem item nenhum.** Ela existe em um repo só, e a spec de Fundação a deixou fora da CI compartilhada. Não ter item é honesto; inventar um seria cobrar regra que ninguém decidiu.

## Este é o inventário de retrofit

Cada repo divergente tem uma issue de retrofit no tracker **deste** repo, com as linhas dele como checklist e a label `ready-for-agent`. Elas nascem abertas e nada foi executado: esta issue entrega o alvo, e a esteira faz a convergência.

| Repo | Linhas | Issue |
| --- | --- | --- |
| `panlabs-tech/skills` | 4 | [#37](https://github.com/panlabs-tech/.github/issues/37) |
| `panlabs-tech/dotfiles` | 6 | [#33](https://github.com/panlabs-tech/.github/issues/33) |
| `panlabs-tech/tfbox` | 7 | [#38](https://github.com/panlabs-tech/.github/issues/38) |
| `panlabs-tech/ethitorial` | 9 | [#34](https://github.com/panlabs-tech/.github/issues/34) |
| `panlabs-tech/life-under-control` | 12 | [#35](https://github.com/panlabs-tech/.github/issues/35) |
| `panlabs-tech/travelmanager` | 12 | [#39](https://github.com/panlabs-tech/.github/issues/39) |
| `panlabs-tech/panlabs` | 13 | [#36](https://github.com/panlabs-tech/.github/issues/36) |

O corpo de cada uma foi gerado a partir desta matriz, e não escrito à mão: o checklist de um retrofit é exatamente o que o checker acusou naquele retrato, com o motivo junto.

Ficam aqui, e não no tracker de cada repo alvo, por decisão do operador: abrir issue em outro projeto é tocar outro projeto, e o alvo é do meta por natureza. Cada retrofit é independente dos demais, em qualquer ordem ou em paralelo.

**O ruleset com nomes fixos de check só pode ser aplicado num repo depois do retrofit dele.** A frota ainda publica nomes divergentes entre si, e aplicar em massa penduraria todo PR da org esperando um status que ninguém publica. Enquanto a CI de um repo não publica os nomes do contrato, o script de ruleset **retém** aquele repo em vez de convergi-lo, e `--only` é como o operador afirma que o retrofit daquele repo aterrissou.

## Reproduzir

```bash
uv run panlabs-checker --dump-observed /tmp/fleet-cru.json
jq -S '{org, repos: [.repos[] | select(.private | not)]}' /tmp/fleet-cru.json \
  > tests/fixtures/checker-fleet-2026-07-27.json
```
