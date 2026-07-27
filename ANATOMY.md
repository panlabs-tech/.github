# A anatomia de um repo panlabs

Este documento é a definição canônica do que um repositório da org `panlabs-tech` deve ser. Ele mora ao lado do checker que o mede (`scripts/panlabs/checker/`), no mesmo repo, para que a definição do padrão e o executável que a verifica não possam divergir sem que se note.

Leitura **binária**: um item está obrigatório-no-escopo ou está fora-da-anatomia. Não existe nível "recomendado". Numa org de um mantenedor, recomendação é licença para deriva, e o consumidor deste documento é um agente: só se verifica obrigação.

## Os três eixos

Um denominador comum único seria inútil, e uma regra por repositório não seria padrão. A anatomia usa três eixos:

1. **Invariante de org.** Vale para todo repositório, independentemente de stack ou tipo.
2. **Variante por stack, aplicada por superfície.** Stack indexa superfícies, não repositórios: um mesmo repositório pode ter superfície Node e Python ao mesmo tempo, e cada superfície é avaliada por si. Um repositório com duas linguagens é avaliado nas duas; um repositório de infraestrutura não é avaliado por regra de superfície que ele não tem.
3. **Variante por tipo.** Regras que só fazem sentido para uma categoria de repositório.

Um item de anatomia pertence a exatamente um desses três eixos, e esse eixo é o seu **escopo**. O escopo de um item não é detalhe: é o que permite auditar o próprio checker. "Reprovou por item de stack Node" é revisável; "reprovou" não é.

## Os cinco tipos

O tipo de um repositório é **nomeado e finito**: classificar um repositório novo é escolha entre estes cinco, nunca invenção de um sexto.

A coluna do meio é o valor **declarado** em `config/repo-types.json`, e não enfeite: classificar é escrever esse valor, o checker recusa qualquer outro, e é por ele que o escopo de um item de tipo aparece na matriz.

| Tipo | Valor declarado | O que é |
| --- | --- | --- |
| **Aplicação** | `aplicacao` | Um produto com superfície de código que serve usuário ou operador. |
| **Módulo de infraestrutura** | `modulo-infraestrutura` | Módulos reutilizáveis de infraestrutura como código. Variante declarada, não exceção: verificável como qualquer outro tipo. |
| **Skills** | `skills` | Skills, subagentes e comandos versionados para uso por agentes. Stack vazia. |
| **Meta** | `meta` | O repositório que carrega a própria definição do padrão panlabs, ao lado dos mecanismos que o aplicam e o verificam. Este repositório. |
| **Dotfiles** | `dotfiles` | O source do gerenciador de dotfiles da máquina. Stack vazia; o conteúdo é a árvore-fonte do gerenciador, não código de produto. |

Dois dos cinco (**skills** e **dotfiles**) têm stack vazia por natureza. O tipo **meta** já teve stack vazia, mas deixou de ter: os scripts que este repositório carrega (ruleset e checker) são Python, o que dá a ele superfície própria. Skills e dotfiles continuam sendo o caso real de repositório sem superfície nenhuma, e é por isso que são o fixture mais importante do checker, não um caso de borda.

## Vocabulário

**Invariante.** Um item cujo escopo é a org inteira: toda avaliação o cobra, de todo repositório, independentemente de stack ou tipo.

**Slot.** Um item que obriga a **declaração**, não o **valor**. A anatomia exige que um repositório declare sua versão de runtime; não exige que declare uma versão específica. Um slot preenchido com um valor diferente do de outro repositório passa nos dois; um slot vazio ou não declarado reprova. O vocabulário de labels de triagem é um slot: dialetos diferentes entre repositórios são conformes, desde que cada um declare o seu.

**Condicional.** Um item cujo escopo não alcança um repositório porque a condição que o aciona não se aplica ali. A ausência de um item condicional fora do seu escopo não é deriva: é o resultado esperado. Confundir as duas coisas é o falso positivo que este documento existe para prevenir. Condicional não é opcional: **dentro** da condição, ele é cobrado como qualquer obrigatório.

**Valor decidido.** O oposto do slot: um item que compara contra um valor único, porque a variação ali não é escolha do repositório. O scanner de segredos do portão local é um; o gerenciador de pacotes das aplicações é outro. Quando o valor ainda não foi decidido, ele mora como `null` em `config/anatomy.json` e o item **não é avaliado** -- não decidido não é decidido-como-vazio, e nenhum dos dois é conforme. A corrida do checker diz em qual dimensão a decisão falta, para que o silêncio não seja lido como aprovação.

## O catálogo

O catálogo é um **pacote com um módulo por eixo** (`catalog/org.py`, `catalog/stack.py`, `catalog/tipo.py`), e o endereço de um item carrega o escopo dele. Não é organização: um item de stack morando no módulo de org mentiria sobre o eixo em que foi avaliado, e um teste guarda essa correspondência.

**Item escrito aqui tem veredito lá, e um teste guarda os dois lados.** Um item que existisse só neste documento seria recomendação, e a leitura binária acima não tem nível recomendado; um item que existisse só no checker cobraria uma obrigação que ninguém escreveu. A lista abaixo e `DEFAULT_CATALOG` são o mesmo conjunto, por construção verificada.

Três itens comparam contra um **valor** que ainda não foi decidido (a licença uniforme e as duas séries de runtime). Eles moram no catálogo com o valor em `config/anatomy.json`, hoje `null`. Enquanto for `null`, o item não é avaliado: isso não é conformidade, é ausência de pergunta, e a corrida do checker diz em qual dimensão ela falta. Preencher a linha do dado liga a cobrança na frota inteira sem tocar em código.

### Eixo 1: invariante de org

Cobrado de todo repositório, de todo tipo e de toda stack, **inclusive do meta**, que carrega a definição do padrão e não é a primeira exceção a ele.

| Item | O que cobra | Por quê |
| --- | --- | --- |
| `readme-exists` | README | Núcleo universal observado nas quinze orgs de referência varridas, não convenção inventada. |
| `license-exists` | LICENSE | O outro metade desse núcleo: sob que termos se pode usar aquilo. |
| `license-uniform` | licença igual à decidida | Uniforme é decisão de valor, e o valor ainda é `null`. Só onde há licença: sem ela, a linha a ler é a de cima. |
| `repo-description-declared` | descrição não vazia | Sem ela, a listagem da org é ilegível sem abrir cada repositório. O **texto** continua sendo decisão da spec de Org; a vigia é daqui. |
| `repo-topics-declared` | pelo menos um topic | É por topic que um agente filtra a frota por stack. |
| `wiki-off-unless-declared` | wiki desligado fora das exceções | Superfície vazia que ninguém mantém. A lista de exceções é lida de `config/org.json`, nunca cravada: um repositório cujo wiki é gerado por automação de release está lá. |
| `agent-guidance-generic-exists` | `AGENTS.md` | O arquivo genérico é a fonte-da-verdade da orientação de agente. |
| `agent-guidance-primary-defers-to-generic` | `CLAUDE.md` referencia o genérico e não o duplica | Mata o fóssil medido na frota, onde os dois arquivos têm conteúdo idêntico: um deles para de ser atualizado e passa a descrever um estado que já não é verdade, sem que nada acuse. |
| `agent-doc-issue-tracker` | `docs/agents/issue-tracker.md` | Um dos quatro documentos de nome fixo: o agente encontra a configuração sempre no mesmo lugar. |
| `agent-doc-triage-labels` | `docs/agents/triage-labels.md` | Idem. |
| `agent-doc-workflow` | `docs/agents/workflow.md` | Idem. |
| `agent-doc-domain` | `docs/agents/domain.md` | Idem. |
| `agent-doc-design` | `docs/agents/design.md`, **se** o repositório declara interface | Condicional: sem interface não há design a documentar, e cobrar o documento ali seria o falso positivo que esta anatomia existe para prevenir. |
| `agent-doc-local-dev` | `docs/agents/local-dev.md`, **se** há composição de serviços locais | Condicional pela mesma razão. |
| `agent-doc-mcps` | `docs/agents/mcps.md`, **se** o repositório versiona configuração de MCP | Condicional; e onde a condição vale, ninguém sabe quais MCPs são aqueles sem o documento. |
| `triage-vocabulary-declared` | o documento de labels mapeia os cinco papéis | **Slot**: cobra o mapa, não o label. Os dialetos da frota diferem e ambos passam. Só onde o documento existe: a ausência dele é linha de outro item. |
| `no-stale-tool-config` | nenhuma configuração de ferramenta fora da toolchain decidida | Resíduo medido: diretório de agente concorrente em quatro repositórios, de ferramenta de indexação num quinto. |
| `no-vendored-agent-equipment` | nenhum equipamento global versionado | Skill, subagente, comando, lógica de hook, lista de permissões e barra de status vivem num lugar só. Arquivo marcador **não** entra: marcador é declaração, e a lógica continua fora. |
| `local-commit-gate-exists` | portão local antes do commit | Um dos dois portões; erro barato é pego barato ali. O que ele **roda** por superfície é eixo de stack. |
| `commit-message-standard-declared` | padrão de mensagem de commit em lugar mecânico | Prosa não é portão. Vale por configuração de linter de commit ou por chamada dele no portão local: o item cobra o fato, e a frota o realiza pelos dois caminhos. |
| `secret-scan-before-commit` | o portão local roda o mesmo scanner da CI | Valor decidido, não slot: dois scanners diferentes fariam "passou no local" e "passou na CI" significarem coisas diferentes. Só onde há portão local. |
| `ci-references-shared-workflows` | o caller referencia os workflows compartilhados | Os quatro arquivos de CI da frota nasceram copiados um do outro e divergiram entre 48% e 86% em sete semanas. A forma local vale só no repositório que **publica** os workflows, onde um caller resolve contra o próprio SHA. |
| `status-rollup-contract` | os dois jobs de nome fixo do contrato de status | É o que faz a lista fixa de required checks da org sobreviver a stack variável. Invariante inclusive em repositório sem superfície nenhuma, onde sem ele o merge fica pendurado para sempre esperando um check que ninguém publica. |

### Eixo 2: variante por stack, aplicada por superfície

Cobrado **por superfície**, nunca por repositório. Um repositório sem a superfície não é avaliado pelo item, e a ausência dele ali não é deriva.

| Item | O que cobra | Por quê |
| --- | --- | --- |
| `python-runtime-declared` | `.python-version` na raiz, preenchido | **Slot**: obriga a declaração, não o número. É na raiz que o gerenciador de runtime da máquina lê, e uma homônima enterrada em subpasta não é a mesma declaração. |
| `python-runtime-converged` | a versão dentro da série decidida | O valor ainda é `null`. Declarar é o slot; declarar a **mesma** coisa é este item, e um repositório pode declarar e mesmo assim divergir. Série, e não major: em Python a unidade em que "verde significa o mesmo" é `3.12`. |
| `python-toolchain-declared` | ruff declarado em manifesto | Valor decidido: a toolchain Python da frota é `uv`, `ruff`, `pyright`, `pytest`, e "está limpo" precisa significar o mesmo em qualquer repositório. |
| `python-ci-leg` | a perna `checks-python` no caller | O rollup agrega o que existe, então uma perna que não está lá sai verde sem ter rodado nada. |
| `node-runtime-declared` | `.node-version` na raiz, preenchido | Slot, como o de Python. |
| `node-runtime-converged` | a versão dentro da série decidida | Valor ainda `null`, e a frota hoje declara dois majors. Em Node a série **é** o major: `24` cobre `24.3.0`. |
| `node-lockfile-committed` | lockfile na raiz | A frota usa dois layouts, e o da raiz é o que todos os cinco repositórios com superfície Node têm. |
| `node-toolchain-declared` | ferramenta de formatação e lint declarada em manifesto | **Slot**, não valor: a spec nomeia a toolchain Python e não nomeia a Node, e cravar aqui seria o checker legislando. |
| `node-ci-leg` | a perna `checks-node` no caller | Mesma razão da perna de Python. |

**Terraform tem superfície e não tem item**, e isso é resultado, não esquecimento: Terraform como CI compartilhada está fora do escopo da spec de Repo #4, porque existe num repositório só. A superfície continua sendo detectada, e o dia em que houver o que cobrar dela o item entra sem que nada mais mude.

### Eixo 3: variante por tipo

Cobrado só da categoria que o declara. O tipo é dado versionado em `config/repo-types.json`; um repositório ainda não classificado não é alcançado por item nenhum deste eixo, e isso não é deriva.

| Item | Tipo | O que cobra | Por quê |
| --- | --- | --- | --- |
| `anatomy-doc-exists` | meta | `ANATOMY.md` na raiz | O tipo meta carrega a própria definição do padrão. |
| `app-monorepo-layout` | aplicação | aplicações em subpastas de `apps/` | Navegar entre as aplicações da frota não deve exigir recontextualização. |
| `app-package-manager-single` | aplicação | o gerenciador de pacotes da frota | Só aplicações: o módulo de infraestrutura usa o divergente e continua conforme, porque a regra não o alcança. |
| `app-container-build` | aplicação | arquivo de build de container ao lado de cada aplicação | Toda aplicação implantável do mesmo jeito. Só onde há layout de monorepo: sem ele, a linha a ler é a de cima. |
| `app-mcp-config-versioned` | aplicação | configuração de MCP versionada | Corrige o padrão atual, em que a configuração real fica gitignorada com segredo literal dentro, nunca de fato compartilhada apesar do nome. |
| `app-env-example` | aplicação | arquivo de exemplo de variáveis | Quem chega precisa saber o que preencher sem ler o código. |
| `app-local-services-composition` | aplicação | composição de serviços locais, **se** há dependência local com estado | Condicional de verdade: a vitrine da frota legitimamente não tem, e a ausência lá é o resultado esperado. É o falso positivo que a spec antecipou por escrito. |

**Três dos cinco tipos não declaram item nenhum, e isso é conteúdo.** O módulo de infraestrutura é variante declarada, não exceção: ele é cobrado de todo invariante e de todo item das superfícies que tem, e o que o distingue é ficar fora do escopo da regra de gerenciador de pacotes -- fora **por escopo**, que é revisável na matriz, e não por um `if`, que sumiria no código. `skills` e `dotfiles` têm stack vazia por natureza, e é justamente por não carregarem item de superfície nenhum que são o fixture que importa: é neles que um contrato de required checks ingênuo quebra, e é o item invariante de rollup que os salva.

### O preflight que nenhum script executa

`no-stale-tool-config` alarma; ele não remove. A remoção de um fóssil tem um passo obrigatório antes: **aquilo é candidato a promoção global?** Hoje é operação nula, porque o resíduo mais comum é configuração de MCP, que o mecanismo versionado já cobre. A ordem importa mesmo assim, para que a limpeza não apague capacidade por engano, e ela é procedimento de quem faz o retrofit, não item de catálogo -- um item mede estado, e "alguém perguntou antes de apagar" não é estado.

## O que o checker enxerga

Um item só pode ser escrito sobre o que a observação alcança, e por isso o alcance dela é parte da anatomia e não detalhe de implementação.

| O que | Como | Por quê |
| --- | --- | --- |
| **A árvore inteira** do repositório, em caminho relativo à raiz | uma chamada recursiva por repo | manifesto em subpasta de monorepo é superfície igual à da raiz. Enquanto só a raiz era listada, o item de lockfile de um monorepo **nem chegava a ser avaliado**: não é falso positivo, é um item que ninguém mede e que parece verde |
| O **conteúdo** de um conjunto **declarado** de arquivos | uma consulta por repo, com um apelido por arquivo | slot declarado dentro de um documento, referência à CI compartilhada dentro de um workflow e ferramenta declarada dentro de um manifesto são conteúdo, e nenhum deles se verifica por presença de arquivo. O conjunto é dado (`config/checker.json`), nunca varredura cega, e o custo não cresce com o número de arquivos |
| **Descrição, topics, wiki e licença** | metadados de plataforma | nenhum deles mora no working tree. A fronteira de *decisão* com a spec de Org continua onde está; a de *verificação* atravessa de propósito, porque estes itens ficariam sem vigia nenhum se o checker não os lesse |
| **Visibilidade** (`private`) | metadado de plataforma | a frota tem repositório privado, e o retrato observado vira fixture versionada num repositório **público**. Com o campo, a curadoria é reproduzível e um teste a guarda; sem ele, dependeria de alguém lembrar quais nomes são privados |

Duas propriedades não se negociam. **Ler mais não é escrever nada:** o checker continua read-only, e rodá-lo não muda nada em nenhum repositório, em nenhum momento. E **observação parcial não pode parecer conforme:** uma árvore que a API devolve truncada vira erro de observação daquele repositório, pelo mesmo motivo que o falso-negativo da listagem raiz era grave.

**A superfície é lida da árvore inteira; o que cada item exige é decisão dele.** As duas perguntas são diferentes e não se confundem: "este repositório tem superfície Node?" olha o repositório todo, e "ele declara a versão de runtime que o gerenciador da máquina lê?" olha um caminho exato, na raiz. Os itens de slot de runtime e os de documento perguntam pela raiz; os de ferramenta perguntam pelos manifestos declarados, porque a frota tem mais de um layout e um manifesto em caminho não declarado deixaria aquele item **sem conteúdo para ler**, isto é, sem ser medido. Um teste amarra os dois lados: todo caminho que um item lê está declarado em `config/checker.json`, e layout novo é uma linha a mais no dado, nunca uma mudança de código.

## Quando o checker roda

Como **passo do heartbeat da máquina**, no ramo em que o WSL está de pé, com cadência própria declarada em `config/heartbeat.json`. Ele precisa de rede e do token já autenticado da máquina, que é o oposto do que a poda precisa.

Ele **alarma, não trava**, e o código de saída é a interface: `1` significa deriva, e só deriva; qualquer coisa que impeça a matriz de existir sai como erro. São dois canais de alarme distintos, e é isso que impede um token expirado de chegar ao operador como "toda a frota está fora do padrão".

E ele **nunca é gate de PR**, em repositório nenhum. Anatomia é propriedade do repositório, não do diff: um gate puniria um PR inocente por dívida pré-existente, e metade dos itens nem mora no working tree para o diff poder consertar.

## Onde a anatomia mora

Parte do padrão é **imposta por plataforma**: ruleset e required checks, que um repositório não consegue contornar. Parte é **documentada e checada**: este documento e o checker, que alarmam na deriva sem travar nada. As duas metades moram juntas, com dureza honestamente diferente, e essa diferença é deliberada.
