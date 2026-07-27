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

| Tipo | O que é |
| --- | --- |
| **Aplicação** | Um produto com superfície de código que serve usuário ou operador. |
| **Módulo de infraestrutura** | Módulos reutilizáveis de infraestrutura como código. Variante declarada, não exceção: verificável como qualquer outro tipo. |
| **Skills** | Skills, subagentes e comandos versionados para uso por agentes. Stack vazia. |
| **Meta** | O repositório que carrega a própria definição do padrão panlabs, ao lado dos mecanismos que o aplicam e o verificam. Este repositório. |
| **Dotfiles** | O source do gerenciador de dotfiles da máquina. Stack vazia; o conteúdo é a árvore-fonte do gerenciador, não código de produto. |

Dois dos cinco (**skills** e **dotfiles**) têm stack vazia por natureza. O tipo **meta** já teve stack vazia, mas deixou de ter: os scripts que este repositório carrega (ruleset e checker) são Python, o que dá a ele superfície própria. Skills e dotfiles continuam sendo o caso real de repositório sem superfície nenhuma, e é por isso que são o fixture mais importante do checker, não um caso de borda.

## Vocabulário

**Invariante.** Um item cujo escopo é a org inteira: toda avaliação o cobra, de todo repositório, independentemente de stack ou tipo.

**Slot.** Um item que obriga a **declaração**, não o **valor**. A anatomia exige que um repositório declare sua versão de runtime; não exige que declare uma versão específica. Um slot preenchido com um valor diferente do de outro repositório passa nos dois; um slot vazio ou não declarado reprova. O vocabulário de labels de triagem é um slot: dialetos diferentes entre repositórios são conformes, desde que cada um declare o seu.

**Condicional.** Um item cujo escopo não alcança um repositório porque a condição que o aciona não se aplica ali. A ausência de um item condicional fora do seu escopo não é deriva: é o resultado esperado. Confundir as duas coisas é o falso positivo que este documento existe para prevenir.

## O catálogo

Este é o catálogo cheio, decidido pela [spec de Repo #4](https://github.com/panlabs-tech/.github/issues/4) e escrito pela [issue #28](https://github.com/panlabs-tech/.github/issues/28). Item escrito aqui que não vira veredito seria recomendação, e a leitura binária proíbe recomendação: **um teste amarra esta tabela ao catálogo executável**, e escrever um item aqui sem implementá-lo (ou o contrário) reprova.

O catálogo é um **pacote com um módulo por eixo** (`catalog/org.py`, `catalog/stack.py`, `catalog/tipo.py`), e o endereço de um item carrega o escopo dele. Não é organização: um item de stack morando no módulo de org mentiria sobre o eixo em que foi avaliado, e um teste guarda essa correspondência.

O que cada item **exige** é dado, e mora em [`config/anatomy.json`](config/anatomy.json). A separação é a mesma que rege o resto do repo: o catálogo decide *que item existe e em que eixo ele é avaliado*, e o dado carrega *qual valor ele cobra*. Uma dimensão `null` está ainda não decidida, e o item que depende dela não gera veredito nenhum, o que o CLI anuncia em voz alta para que silêncio não seja lido como conformidade.

### Invariante de org

| Item | O que cobra |
| --- | --- |
| `readme-exists` | README em todo repo. |
| `license-exists` | LICENSE em todo repo. |
| `license-uniform` | A licença é a mesma na org toda. Só cobra de quem já tem alguma: cobrar uniformidade de quem não tem licença nenhuma daria duas linhas para o mesmo conserto. |
| `agent-entrypoint-generico` | O arquivo genérico de orientação do agente existe, e é a fonte-da-verdade. |
| `agent-entrypoint-primario-referencia-generico` | O arquivo do agente primário **referencia** o genérico, mais o que é genuinamente específico dele. É a amarra que mata o fóssil de um genérico que já não corresponde ao conteúdo real. |
| `agent-docs-obrigatorios` | Os quatro documentos de nome fixo: tracker de issues, vocabulário de labels, fluxo de trabalho e domínio. O motivo nomeia quais faltam. |
| `triage-labels-slot-declarado` | O vocabulário de labels é **slot**: o documento diz alguma coisa e nomeia ao menos uma label. Qual label é do repo, e nenhum dialeto está cravado no código. |
| `sem-configuracao-stale-de-ferramenta` | Nada versionado fora da toolchain decidida na spec de Máquina. Preflight antes de remover: aquilo é candidato a promoção global? |
| `sem-equipamento-global-versionado` | Skills, subagentes, comandos, hooks portáveis, lista de permissões e barra de status ficam de fora **por design, não por omissão**. |
| `portao-local-existe` | O portão 1 existe, antes do commit. |
| `padrao-de-mensagem-de-commit` | O portão local verifica a mensagem de commit. |
| `scan-de-segredos-antes-do-commit` | O portão local verifica segredos antes do commit, e não depois de já estarem no histórico. |
| `ci-referencia-workflows-compartilhados` | A CI referencia os reusable workflows publicados aqui, e ninguém copia YAML. O repo que os publica os referencia por caminho local, e essa exceção é dado declarado. |
| `contrato-de-nomes-de-status` | O rollup de id fixo e o job de segurança existem, com zero, uma ou duas superfícies. |
| `descricao-declarada` | Descrição, comparada com o declarado em `config/org.json`; sem texto governado, só se cobra que exista alguma. |
| `topics-declarados` | Topics, pelo mesmo critério da descrição. |
| `wiki-conforme-decidido` | Wiki como a org decidiu, com as exceções declaradas em `config/org.json`. |

**Dois itens que a prosa da spec listou sob stack e que moram aqui.** O contrato de nomes de status e a referência à CI compartilhada valem para **todo** repositório, inclusive o de stack vazia, onde o rollup passa trivialmente e é justamente esse o ponto. Um item de eixo stack precisa de um valor de stack para aparecer na matriz, e um repositório sem superfície nenhuma não tem nenhum: escrevê-los como item de stack os deixaria sem escopo exatamente no repositório que eles existem para servir.

### Variante por stack, aplicada por superfície

Os itens são **gerados a partir do dado**, um conjunto por superfície declarada. Uma superfície nova entra no catálogo pelo dado, com o mesmo conjunto de cobranças, em vez de alguém precisar lembrar de escrever quatro itens à mão e esquecer um.

| Item | O que cobra |
| --- | --- |
| `python-runtime-declared` | A superfície Python declara a versão de runtime na raiz. **Slot**: obriga a declaração, não o número. |
| `python-portao-local-declara-ferramenta` | O portão local roda a ferramenta de formatação e verificação daquela superfície. |
| `python-ci-referencia-perna-compartilhada` | A perna de CI daquela superfície vem do workflow compartilhado. |
| `node-runtime-declared` | Idem, para a superfície Node. |
| `node-lockfile-committed` | A superfície Node versiona lockfile na raiz. |
| `node-portao-local-declara-ferramenta` | Idem. |
| `node-ci-referencia-perna-compartilhada` | Idem. |

Existe um item de convergência de versão maior por superfície, `<superfície>-runtime-major-convergido`, e ele **não aparece na tabela porque não está ativo**: `runtime_major` é `null` no dado. Os quatro repos com superfície Node declaram 22 e 24, metade e metade, e escolher o número da frota é decisão do operador. Enquanto for `null`, o item não avalia nada e o CLI reporta a dimensão como não decidida.

**A superfície Terraform não tem item, e a ausência é deliberada.** Ela existe em um repo só, e a spec de Fundação a deixou fora da CI compartilhada porque um reusable workflow de um consumidor é abstração sem retorno. Sem CI compartilhada e sem ferramenta decidida, não ter item é honesto; inventar um seria cobrar regra que ninguém decidiu.

### Variante por tipo

| Item | O que cobra |
| --- | --- |
| `anatomy-doc-exists` | O tipo **meta** carrega a própria definição do padrão, ao lado do checker que a mede. |
| `aplicacao-gerenciador-de-pacotes-unico` | Gerenciador de pacotes único. Valor fixo, não slot: dois gerenciadores são exatamente a recontextualização que a regra existe para matar. |
| `aplicacao-layout-de-monorepo` | Aplicações em subpastas, e não código plano na raiz. |
| `aplicacao-build-de-container-por-app` | Arquivo de build de container por aplicação, morando junto de cada uma. Só cobra de quem já tem o layout. |
| `aplicacao-composicao-de-servicos-locais` | **Condicional**: existe se e somente se a aplicação tem dependência local com estado. Sem esse rastro na árvore, o item não se aplica, e a ausência **não é** deriva. |
| `aplicacao-mcp-versionado-com-placeholder` | Configuração de MCP versionada, com placeholder de variável de ambiente em vez de segredo literal gitignorado. |
| `aplicacao-exemplo-de-variaveis-de-ambiente` | Arquivo de exemplo de variáveis, sem o qual o placeholder não diz o que preencher. |
| `skills-sem-superficie` | Stack vazia por natureza. Superfície ali é código de produto, que não é o conteúdo do tipo. |
| `dotfiles-sem-superficie` | Idem. |

**O módulo de infraestrutura não tem item próprio, e isso é a definição dele.** Ele é variante *declarada*, não exceção: a diferença é que ele é verificável como qualquer outro, cobrado de todo invariante e de todo item das superfícies que ele tem. O que não o alcança é a regra de convergência de gerenciador de pacotes, que é do tipo aplicação. Isso importa porque são **dois** os repos com o gerenciador divergente, e não um: a vitrine, que a regra alcança, e o de infraestrutura, que ela não alcança.

**Skills e dotfiles são o fixture mais importante do checker, não caso de borda.** É neles que um contrato de required checks ingênuo quebra, e é por isso que o rollup existe sempre.

## O que o checker enxerga

Um item só pode ser escrito sobre o que a observação alcança, e por isso o alcance dela é parte da anatomia e não detalhe de implementação.

| O que | Como | Por quê |
| --- | --- | --- |
| **A árvore inteira** do repositório, em caminho relativo à raiz | uma chamada recursiva por repo | manifesto em subpasta de monorepo é superfície igual à da raiz. Enquanto só a raiz era listada, o item de lockfile de um monorepo **nem chegava a ser avaliado**: não é falso positivo, é um item que ninguém mede e que parece verde |
| O **conteúdo** de um conjunto **declarado** de arquivos | uma consulta por repo, com um apelido por arquivo | slot declarado dentro de um documento, referência à CI compartilhada dentro de um workflow e ferramenta declarada dentro de um manifesto são conteúdo, e nenhum deles se verifica por presença de arquivo. O conjunto é dado (`config/checker.json`), nunca varredura cega, e o custo não cresce com o número de arquivos |
| **Descrição, topics, wiki e licença** | metadados de plataforma | nenhum deles mora no working tree. A fronteira de *decisão* com a spec de Org continua onde está; a de *verificação* atravessa de propósito, porque estes itens ficariam sem vigia nenhum se o checker não os lesse |
| **Visibilidade** (`private`) | metadado de plataforma | a frota tem repositório privado, e o retrato observado vira fixture versionada num repositório **público**. Com o campo, a curadoria é reproduzível e um teste a guarda; sem ele, dependeria de alguém lembrar quais nomes são privados |

Duas propriedades não se negociam. **Ler mais não é escrever nada:** o checker continua read-only, e rodá-lo não muda nada em nenhum repositório, em nenhum momento. E **observação parcial não pode parecer conforme:** uma árvore que a API devolve truncada vira erro de observação daquele repositório, pelo mesmo motivo que o falso-negativo da listagem raiz era grave.

**A superfície é lida da árvore inteira; o que cada item exige é decisão dele.** As duas perguntas são diferentes e não se confundem: "este repositório tem superfície Node?" olha o repositório todo, e "ele declara a versão de runtime que o gerenciador da máquina lê?" olha um caminho exato, na raiz. Os itens de slot e de portão perguntam pela raiz, porque é lá que o gerenciador da máquina e o `git` leem; os de layout de monorepo e de build de container perguntam por caminho relativo à aplicação, porque é lá que aquilo mora. A escolha é de cada item, e o escopo continua revisável.

## Quando o checker roda

Como **passo do heartbeat da máquina**, no ramo em que o WSL está de pé, com cadência própria declarada em `config/heartbeat.json`. Ele precisa de rede e do token já autenticado da máquina, que é o oposto do que a poda precisa.

Ele **alarma, não trava**, e o código de saída é a interface: `1` significa deriva, e só deriva; qualquer coisa que impeça a matriz de existir sai como erro. São dois canais de alarme distintos, e é isso que impede um token expirado de chegar ao operador como "toda a frota está fora do padrão".

E ele **nunca é gate de PR**, em repositório nenhum. Anatomia é propriedade do repositório, não do diff: um gate puniria um PR inocente por dívida pré-existente, e metade dos itens nem mora no working tree para o diff poder consertar.

## Onde a anatomia mora

Parte do padrão é **imposta por plataforma**: ruleset e required checks, que um repositório não consegue contornar. Parte é **documentada e checada**: este documento e o checker, que alarmam na deriva sem travar nada. As duas metades moram juntas, com dureza honestamente diferente, e essa diferença é deliberada.
