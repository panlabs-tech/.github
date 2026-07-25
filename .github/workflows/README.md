# A CI compartilhada

Seis reusable workflows, publicados com `workflow_call` e inputs tipados, para que um repo consumidor referencie a CI em vez de copiar um YAML que vai divergir. Origem: [panlabs-tech/panlabs#59](https://github.com/panlabs-tech/panlabs/issues/59), corrigido e fechado por [panlabs-tech/.github#7](https://github.com/panlabs-tech/.github/issues/7); os dois últimos vieram depois, com [panlabs-tech/.github#15](https://github.com/panlabs-tech/.github/issues/15).

| workflow | o que faz | inputs |
| --- | --- | --- |
| [`security.yml`](security.yml) | scan de segredos com o binário direto do gitleaks (versão e checksum pinados) | nenhum |
| [`checks-python.yml`](checks-python.yml) | `uv sync --frozen` → `ruff format --check` → `ruff check` → `pyright` → `pytest` | `working-directory`, `pytest-args`, `pyright-args` |
| [`checks-node.yml`](checks-node.yml) | instala, depois `<pm> run lint` / `typecheck` / `test`, e `build` se o script existir | `package-manager` (`npm`\|`pnpm`), `working-directory` |
| [`open-pr.yml`](open-pr.yml) | abre o PR da branch de trabalho contra a base, se ainda não existir | `base-branch` |
| [`code-scanning.yml`](code-scanning.yml) | análise estática com CodeQL em modo **advisory**, um job por linguagem, em paralelo | `languages` (array JSON, obrigatório) |
| [`dependabot-auto-merge.yml`](dependabot-auto-merge.yml) | liga auto-merge no PR de bump **minor ou patch** do Dependabot; major nunca | nenhum |

Os dois últimos não são gate, e a diferença é o que os define: os quatro primeiros decidem se um PR pode mergear, e os dois últimos decidem o que aparece no PR e o que aterrissa sozinho. As duas seções no fim explicam por que cada um fica de fora da lista de required checks.

Terraform fica fora: existe em um repo só (`tfbox`), e um reusable workflow de um consumidor é abstração sem retorno.

## O caminho tem `.github` duas vezes

O repo que hospeda estes workflows **se chama** `.github`, e o diretório de workflows de qualquer repo é sempre `.github/workflows/`. Um consumidor externo referencia um destes arquivos assim:

```yaml
jobs:
  security:
    uses: panlabs-tech/.github/.github/workflows/security.yml@v1.0.0
```

O primeiro `.github` é o nome do repo; o segundo é o diretório de workflows dentro dele. Não é erro de digitação, e é a primeira coisa que trava quem escreve um chamador pela primeira vez.

O `.github` consome os próprios workflows por referência **local** (`./.github/workflows/security.yml`), não pela forma externa acima: um caller no mesmo repo resolve contra o próprio commit, o que evita o problema do ovo-e-a-galinha de uma tag ainda não existir no commit que introduz ou muda o próprio workflow. A forma com `@v1.0.0` é para os outros repos da frota, no retrofit de cada um.

São **três** callers, e não um, porque cada um tem um gatilho diferente. Não é organização, é o que impede um de alcançar a conclusão do outro:

| caller | gatilho | chama |
| --- | --- | --- |
| [`pr-checks.yml`](pr-checks.yml) | push nas branches de trabalho | `checks-python`, `security`, `open-pr` |
| [`pr-code-scanning.yml`](pr-code-scanning.yml) | `pull_request`, e push na `main` | `code-scanning` |
| [`pr-dependabot-auto-merge.yml`](pr-dependabot-auto-merge.yml) | `pull_request` | `dependabot-auto-merge` |

Só o primeiro publica required check. Enquanto a análise estática mora no segundo arquivo, não existe `needs` capaz de ligá-la ao rollup sem que alguém mude de arquivo para escrevê-lo.

## Pinning

Toda action de terceiro usada aqui é pinada por SHA, com o comentário de versão ao lado (`actions/checkout@<sha> # v7.0.1`). Isto antecipa a regra de pinning que a org vai ligar (decidida em [panlabs-tech/panlabs#49](https://github.com/panlabs-tech/panlabs/issues/49)) e evita que a própria CI compartilhada seja a primeira reprovada por ela no dia em que ligar. É seguro fazer agora porque o Dependabot já demonstrou (medido em [panlabs-tech/panlabs#64](https://github.com/panlabs-tech/panlabs/issues/64)) que bumpa SHA **e** comentário sozinho, contanto que `dependabot.yml` inclua o ecossistema `github-actions`.

Essa condição deixou de ser promessa: [`../dependabot.yml`](../dependabot.yml) existe e declara esse ecossistema. Sem ele, o pin por SHA viraria dívida no dia um, porque nada mais no mundo atualiza um SHA de action.

## Referência versionada

Uma mudança nestes workflows não pode quebrar todos os repos consumidores ao mesmo tempo sem aviso. A estratégia: este repo corta uma tag semver (`v1.0.0`, `v1.1.0`, ...) a cada mudança publicada em qualquer um deles, e cada repo consumidor pina a tag exata na sua própria referência (`@v1.0.0`, nunca uma tag flutuante tipo `@v1`). Uma tag flutuante reintroduziria exatamente a quebra simultânea que isto existe para evitar.

O mesmo mecanismo de Dependabot que já mantém o pin das actions de terceiro (ecossistema `github-actions`) trata uma referência a reusable workflow por tag do mesmo jeito que trata uma action: quando este repo corta uma tag nova, o Dependabot abre um PR de bump em cada consumidor, no tempo dele. Nenhum consumidor quebra sem passar por um PR revisável primeiro.

## O contrato de nomes de status check

Todo repo consumidor publica **o mesmo conjunto de nomes** de status check, não importa quantas superfícies tem por baixo (Python, Node, nenhuma). Isto é feito por um **job de rollup**, de id fixo `checks`, que declara `needs` sobre as pernas por superfície daquele repo e agrega o resultado explicitamente. Ver o job `checks` em [`pr-checks.yml`](pr-checks.yml) como exemplo de referência para outros consumidores.

Isto corrige um defeito do [panlabs-tech/panlabs#59](https://github.com/panlabs-tech/panlabs/issues/59): um job com `strategy.matrix` não publica o status com o nome do job, publica um status por perna, com os valores da matriz anexados ao nome. Um required check de nome fixo nunca casaria com isso, e um repo sem superfície alguma (o `skills`) pendurava o merge para sempre esperando um check que nunca roda. O rollup existe **sempre**, inclusive sem perna nenhuma, onde passa trivialmente.

O footgun que mata o desenho ingênuo: sem `if: always()` mais checagem explícita de `needs.*.result`, uma perna vermelha faz o rollup ser **pulado**, e pulado não é reprovado. O passo `agregar o resultado das pernas por superfície` em `pr-checks.yml` é essa checagem.

O contrato em si (o conjunto de nomes publicados não varia com a superfície; uma perna reprovada reprova o rollup) é modelado em Python puro e testado sem rodar workflow nenhum: [`scripts/panlabs/ci/rollup.py`](../../scripts/panlabs/ci/rollup.py), exercitado em [`tests/test_ci_rollup.py`](../../tests/test_ci_rollup.py). Os workflows em si não são testados: são exercitados por uso, e o `.github` é o primeiro consumidor.

Consequência decidida junto com o rollup: `open-pr` é padronizado, mas **não** é required. Exigi-lo como condição de merge seria circular, porque é o job que cria o PR. A lista de required checks fica só com `checks` e `security`.

Uma pegadinha adjacente, do próprio GitHub Actions: um job que chama um reusable workflow via `uses:` nunca publica o check só com o nome do job do caller, publica `<job do caller> / <job do workflow chamado>` (não há como suprimir). É por isso que `pr-checks.yml` tem um job `security-scan` que chama `security.yml`, e um job `security` separado, de fachada, que só agrega o resultado de `security-scan` e existe para publicar o nome exato que a spec pede. O rollup `checks` não precisa dessa fachada porque ele mesmo já não chama workflow nenhum via `uses:`.

## A análise estática é advisory, e isso é decisão

[`code-scanning.yml`](code-scanning.yml) roda CodeQL no PR, reporta o que achar, e **nunca** trava merge. A regra de ruleset que exigiria essa análise fica de fora de propósito: ela bloqueia por "análise em andamento" e por "ferramenta não configurada", **sem timeout**. Nenhum dos dois motivos é um alerta, e os dois pendurariam o merge de um PR que não tem nada de errado.

Isso é uma ausência, e ausência não aparece em `config/ruleset.json`: não há como um arquivo carregar a regra que ele não tem. Sem alguém escrever a decisão em algum lugar, ela é indistinguível de esquecimento na próxima leitura. É por isso que ela mora em [`scripts/panlabs/ci/advisory.py`](../../scripts/panlabs/ci/advisory.py) e é verificada em [`tests/test_ci_advisory.py`](../../tests/test_ci_advisory.py) contra o dado entregue, das duas formas possíveis de exigir a análise: a regra dedicada, e um required status check com o nome que a análise publica. A segunda é a que entraria sem ninguém perceber, porque parece só mais um nome na lista.

Consequência que inverte a regra da seção anterior: como nenhum destes nomes é required, este workflow **pode** usar `strategy.matrix`, e usa, com um job por linguagem em paralelo. A perna de matrix entra no nome publicado (`code-scanning / analyze (python)`), que é exatamente o que o rollup existe para evitar num required check e que aqui é inofensivo. Os dois regimes convivem: nome fixo onde o merge depende dele, nome por perna onde não depende.

O `category` por linguagem no passo de análise não é enfeite. Sem ele, a análise de uma linguagem sobrescreve a da outra no mesmo commit, e os alertas da que rodar primeiro somem sem aviso.

## Dependabot com auto-merge no verde, major de fora

[`dependabot-auto-merge.yml`](dependabot-auto-merge.yml) liga auto-merge num PR de bump **minor ou patch** do Dependabot, e nunca num major. O motivo de existir é medido, não estético: sem auto-merge, o aproveitamento na própria org foi de **17%**, com 46 PRs de atualização, 8 mergeados, 28 fechados e 10 parados. Um PR de rotina que espera decisão humana não vira revisão, vira fila.

Três coisas precisam valer juntas, e nenhuma delas é óbvia sozinha:

- **O repositório precisa permitir auto-merge.** É `allow_auto_merge`, configuração de repo, ligada pelo gate da [#14](https://github.com/panlabs-tech/.github/issues/14). Sem ela o GitHub recusa a chamada.
- **O merge pedido é squash**, porque é o único método que o ruleset permite. Não é preferência: sob squash-only quem assina o commit que aterrissa é o GitHub. Um teste amarra as duas pontas, comparando o método pedido com o que `config/ruleset.json` permite.
- **A branch do Dependabot precisa disparar os checks.** O nome dela começa sempre por `dependabot/`, que não é configurável, e [`pr-checks.yml`](pr-checks.yml) lista esse prefixo. Sem essa linha, o PR do bot não dispara checagem nenhuma, os required checks nunca saem, e o auto-merge espera para sempre por um status que ninguém vai publicar. É a falha mais silenciosa deste desenho, porque todo o resto pareceria configurado.

O agrupamento em [`../dependabot.yml`](../dependabot.yml) não é economia de ruído: num PR agrupado, o tipo de bump que a automação lê é o **maior** do grupo. Um grupo que misturasse major com minor chegaria como major e travaria inteiro, levando junto os minors que deveriam ter aterrissado sozinhos. Por isso o grupo carrega minor e patch, e major fica fora dele, num PR por dependência.

A decisão vive em [`scripts/panlabs/ci/dependabot.py`](../../scripts/panlabs/ci/dependabot.py), testada em [`tests/test_ci_dependabot.py`](../../tests/test_ci_dependabot.py), e o YAML a repete. As duas cópias mudam juntas, como as duas cópias da regra de rollup.

## O que `checks-python` deliberadamente não cobre

O `life-under-control` precisa de Postgres e MinIO como `services`, e roda `import-linter`. O bloco `services` de um job não é parametrizável por input num reusable workflow: não existe forma de passar serviços como argumento do `workflow_call`. Esse repo mantém uma perna Python local (fora de `checks-python.yml`) sob o próprio job de rollup, em vez de tentar forçar o encaixe aqui.
