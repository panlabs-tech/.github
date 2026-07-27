# A convergência de org e repo, 2026-07-24

Aplicada por `uv run panlabs-org --apply`, com a configuração desejada de [`config/org.json`](../config/org.json), logo depois do merge da [#17](https://github.com/panlabs-tech/.github/pull/17) (issue [#13](https://github.com/panlabs-tech/.github/issues/13)). Replanejar em seguida deixou só os dois itens retidos abaixo.

**42 itens aplicados, 2 retidos.** O retrato observado que produziu o plano está versionado em [`tests/fixtures/org-fleet-2026-07-24.json`](../tests/fixtures/org-fleet-2026-07-24.json), capturado antes da aplicação.

> Uma emenda, em 2026-07-27, pela [#31](https://github.com/panlabs-tech/.github/issues/31): o retrato ganhou o campo `private` em cada repositório, que a observação passou a exigir. O valor é `false` nos sete, o que era fato naquela data, porque o primeiro repositório privado da org só nasceu no dia 25. Nenhum outro campo mudou, e a frota de sete continua sendo o retrato **divergente** contra o qual o planner é testado; quem carrega o caso do repositório privado é [`org-fleet-2026-07-27.json`](../tests/fixtures/org-fleet-2026-07-27.json).

## O P0 não precisou ser aplicado

A política de organização que permite ao Actions criar e aprovar PR já estava religada quando o script passou a existir, e a primeira corrida confirmou isso do jeito que a issue previu: ela não apareceu no plano. Ela deixa de depender de alguém lembrar, e passa a ser invariante vigiado, `uv run panlabs-org` sem flag é a verificação.

## O que mudou na frota

| Dimensão | Antes | Depois |
| --- | --- | --- |
| Secret scanning | desligado nos 7 repos | ligado nos 7 |
| Push protection | desligada nos 7 repos | ligada nos 7 |
| Dependabot alerts | ligado em 2 dos 7 | ligado nos 7 |
| Dependabot security updates | desligado nos 7 repos | ligado nos 7 |
| Defaults de segurança para repo novo | 5 chaves desligadas na org | as 5 ligadas |
| Descrição da org | prometia "dados e analytics", que nenhum repo sustentava | a tese do perfil |
| Descrição de repo | `panlabs` sem nenhuma | os 7 com a sua |
| Topics | 2 dos 7 tinham, e `ethitorial` usava eixo de conteúdo (`blog`, `learning`) | os 7 com eixo de stack, em inglês |
| Wiki | ligado nos 7, usado em 1 | desligado em 6, mantido em `tfbox` |

`tfbox` é a exceção de wiki, e ela é **dado declarado** em `config/org.json`, não condição embutida no planner: lá o wiki é gerado por automação de release, e desligá-lo quebraria a automação. Um repo declarado como exceção não é avaliado nessa dimensão, e por isso nunca aparece no plano por causa dela.

## O que continua com o operador

Duas dimensões o GitHub não expõe para escrita. Elas ficam no plano, **retidas**: aparecem na leitura, com o motivo da divergência e o motivo da retenção, e o `apply` não as realiza. Vão sumir do plano quando forem resolvidas na web.

| Item | Onde | Por quê não dá por API |
| --- | --- | --- |
| Exigir 2FA na org | Settings > Authentication security | `PATCH /orgs` não aceita `two_factor_requirement_enabled`; o campo é legível e não é escrevível. |
| Fixar os 4 repos no perfil | perfil da org, "Customize pins" | Não há mutação de pinned items, nem em REST nem em GraphQL. A introspecção do schema só devolve `pinIssue`, `pinEnvironment` e afins. |

Os pins desejados, nessa ordem: `travelmanager`, `life-under-control`, `ethitorial`, `skills`. Produtos antes de ferramental. Hoje o perfil fixa `ethitorial`, `life-under-control`, `panlabs`, `tfbox` e `travelmanager`.

**São quatro, e não os seis que a issue #13 pede.** A org tem 7 repos; a #13 tira o meta (`.github`) e o módulo de infraestrutura (`tfbox`), e a [spec de Org #2](https://github.com/panlabs-tech/.github/issues/2) tira também a vitrine (`panlabs`, o site panlabs.tech). Sobram quatro. O número seis vem de quando a org tinha outros repos, e a própria spec proíbe carregar contagem: o que vale é quem entra. Trocar a lista é editar `config/org.json`, não mexer em código.
