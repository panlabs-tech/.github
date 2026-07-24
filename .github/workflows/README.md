# A CI compartilhada

Quatro reusable workflows, publicados com `workflow_call` e inputs tipados, para que um repo consumidor referencie a CI em vez de copiar um YAML que vai divergir. Origem: [panlabs-tech/panlabs#59](https://github.com/panlabs-tech/panlabs/issues/59), corrigido e fechado por [panlabs-tech/.github#7](https://github.com/panlabs-tech/.github/issues/7).

| workflow | o que faz | inputs |
| --- | --- | --- |
| [`security.yml`](security.yml) | scan de segredos com o binário direto do gitleaks (versão e checksum pinados) | nenhum |
| [`checks-python.yml`](checks-python.yml) | `uv sync --frozen` → `ruff format --check` → `ruff check` → `pyright` → `pytest` | `working-directory`, `pytest-args`, `pyright-args` |
| [`checks-node.yml`](checks-node.yml) | instala, depois `<pm> run lint` / `typecheck` / `test`, e `build` se o script existir | `package-manager` (`npm`\|`pnpm`), `working-directory` |
| [`open-pr.yml`](open-pr.yml) | abre o PR da branch de trabalho contra a base, se ainda não existir | `base-branch` |

Terraform fica fora: existe em um repo só (`tfbox`), e um reusable workflow de um consumidor é abstração sem retorno.

## O caminho tem `.github` duas vezes

O repo que hospeda estes workflows **se chama** `.github`, e o diretório de workflows de qualquer repo é sempre `.github/workflows/`. Um consumidor externo referencia um destes arquivos assim:

```yaml
jobs:
  security:
    uses: panlabs-tech/.github/.github/workflows/security.yml@v1.0.0
```

O primeiro `.github` é o nome do repo; o segundo é o diretório de workflows dentro dele. Não é erro de digitação, e é a primeira coisa que trava quem escreve um chamador pela primeira vez.

O `.github` consome os próprios quatro workflows em [`pr-checks.yml`](pr-checks.yml), mas por referência **local** (`./.github/workflows/security.yml`), não pela forma externa acima: um caller no mesmo repo resolve contra o próprio commit, o que evita o problema do ovo-e-a-galinha de uma tag ainda não existir no commit que introduz ou muda o próprio workflow. A forma com `@v1.0.0` é para os outros repos da frota, no retrofit de cada um.

## Pinning

Toda action de terceiro usada aqui é pinada por SHA, com o comentário de versão ao lado (`actions/checkout@<sha> # v7.0.1`). Isto antecipa a regra de pinning que a org vai ligar (decidida em [panlabs-tech/panlabs#49](https://github.com/panlabs-tech/panlabs/issues/49)) e evita que a própria CI compartilhada seja a primeira reprovada por ela no dia em que ligar. É seguro fazer agora porque o Dependabot já demonstrou (medido em [panlabs-tech/panlabs#64](https://github.com/panlabs-tech/panlabs/issues/64)) que bumpa SHA **e** comentário sozinho, contanto que `dependabot.yml` inclua o ecossistema `github-actions`.

## Referência versionada

Uma mudança nestes workflows não pode quebrar todos os repos consumidores ao mesmo tempo sem aviso. A estratégia: este repo corta uma tag semver (`v1.0.0`, `v1.1.0`, ...) a cada mudança publicada nos quatro workflows, e cada repo consumidor pina a tag exata na sua própria referência (`@v1.0.0`, nunca uma tag flutuante tipo `@v1`). Uma tag flutuante reintroduziria exatamente a quebra simultânea que isto existe para evitar.

O mesmo mecanismo de Dependabot que já mantém o pin das actions de terceiro (ecossistema `github-actions`) trata uma referência a reusable workflow por tag do mesmo jeito que trata uma action: quando este repo corta uma tag nova, o Dependabot abre um PR de bump em cada consumidor, no tempo dele. Nenhum consumidor quebra sem passar por um PR revisável primeiro.

## O contrato de nomes de status check

Todo repo consumidor publica **o mesmo conjunto de nomes** de status check, não importa quantas superfícies tem por baixo (Python, Node, nenhuma). Isto é feito por um **job de rollup**, de id fixo `checks`, que declara `needs` sobre as pernas por superfície daquele repo e agrega o resultado explicitamente. Ver o job `checks` em [`pr-checks.yml`](pr-checks.yml) como exemplo de referência para outros consumidores.

Isto corrige um defeito do [panlabs-tech/panlabs#59](https://github.com/panlabs-tech/panlabs/issues/59): um job com `strategy.matrix` não publica o status com o nome do job, publica um status por perna, com os valores da matriz anexados ao nome. Um required check de nome fixo nunca casaria com isso, e um repo sem superfície alguma (o `skills`) pendurava o merge para sempre esperando um check que nunca roda. O rollup existe **sempre**, inclusive sem perna nenhuma, onde passa trivialmente.

O footgun que mata o desenho ingênuo: sem `if: always()` mais checagem explícita de `needs.*.result`, uma perna vermelha faz o rollup ser **pulado**, e pulado não é reprovado. O passo `agregar o resultado das pernas por superfície` em `pr-checks.yml` é essa checagem.

O contrato em si (o conjunto de nomes publicados não varia com a superfície; uma perna reprovada reprova o rollup) é modelado em Python puro e testado sem rodar workflow nenhum: [`scripts/panlabs/ci/rollup.py`](../../scripts/panlabs/ci/rollup.py), exercitado em [`tests/test_ci_rollup.py`](../../tests/test_ci_rollup.py). Os workflows em si não são testados: são exercitados por uso, e o `.github` é o primeiro consumidor.

Consequência decidida junto com o rollup: `open-pr` é padronizado, mas **não** é required. Exigi-lo como condição de merge seria circular, porque é o job que cria o PR. A lista de required checks fica só com `checks` e `security`.

Uma pegadinha adjacente, do próprio GitHub Actions: um job que chama um reusable workflow via `uses:` nunca publica o check só com o nome do job do caller, publica `<job do caller> / <job do workflow chamado>` (não há como suprimir). É por isso que `pr-checks.yml` tem um job `security-scan` que chama `security.yml`, e um job `security` separado, de fachada, que só agrega o resultado de `security-scan` e existe para publicar o nome exato que a spec pede. O rollup `checks` não precisa dessa fachada porque ele mesmo já não chama workflow nenhum via `uses:`.

## O que `checks-python` deliberadamente não cobre

O `life-under-control` precisa de Postgres e MinIO como `services`, e roda `import-linter`. O bloco `services` de um job não é parametrizável por input num reusable workflow: não existe forma de passar serviços como argumento do `workflow_call`. Esse repo mantém uma perna Python local (fora de `checks-python.yml`) sob o próprio job de rollup, em vez de tentar forçar o encaixe aqui.
