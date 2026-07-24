# `.github` — o repo meta da panlabs

Este é o repositório que carrega a **definição do padrão panlabs**, ao lado dos mecanismos que o aplicam e o verificam.

Ele não é um produto. Todo repo da org `panlabs-tech` responde a alguma coisa que está definida aqui.

## O que mora aqui

| | |
| --- | --- |
| **`profile/README.md`** | O perfil da org — a página que um visitante vê antes de abrir qualquer repo. |
| **`.github/workflows/`** | Os *reusable workflows* que os repos da org referenciam em vez de copiar. |
| **`scripts/`** | O script de ruleset, que aplica a configuração de proteção repo a repo, e o checker de conformidade, que mede a frota contra a anatomia. |
| **`ANATOMY.md`** | A definição canônica do que é um repo panlabs: três eixos, quatro tipos, invariantes e slots. |

Parte do padrão é **imposta pela plataforma** — rulesets e required checks, que um repo não consegue contornar. Parte é **documentada e checada** — o `ANATOMY.md` e o checker, que alarmam na deriva sem travar nada. As duas metades moram juntas, com dureza honestamente diferente.

## Princípios de construção

**Toda decisão vive num planner puro.** Os scripts daqui separam `plan(observed) → Plan` de `apply(Plan)`. O plano é o default: rodar sem argumento nunca muda nada. Cada item de plano carrega ação, alvo e **motivo** — plano sem motivo não é revisável.

**Nenhum alvo é hardcoded.** A lista de repos vem sempre da org viva, nunca de uma constante — assim a regra não pode divergir da realidade, e repo novo entra sozinho.

**Conformidade é binária.** Não existe nível "recomendado": numa org de um mantenedor, recomendação é licença para deriva, e o consumidor do padrão é um agente.

## Origem

Este repo é o produto de um mapa de wayfinding — [O padrão panlabs: org, máquina e repo](https://github.com/panlabs-tech/panlabs/issues/46) — que travou 21 decisões em três frentes ao longo de julho de 2026. O mapa e seus tickets de decisão permanecem em `panlabs-tech/panlabs` como registro histórico. Quando algo aqui parecer arbitrário, o porquê provavelmente está lá.

## Licença

MIT. Ver [LICENSE](LICENSE).
