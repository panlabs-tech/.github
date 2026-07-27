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

Este documento entrega o **esqueleto**: os três eixos, os cinco tipos e o vocabulário. O **conteúdo do catálogo**, isto é, a lista completa de itens por eixo (quais documentos são invariantes, quais ferramentas cada stack exige, o que cada tipo carrega) é decidido pela [spec de Repo #4](https://github.com/panlabs-tech/.github/issues/4), que esta issue bloqueia.

O checker (`scripts/panlabs/checker/`) já opera sobre este esqueleto com um **catálogo-semente**: itens suficientes para exercitar os três escopos de verdade, não para cobrir a frota inteira. Onde o catálogo-semente e o catálogo final da #4 divergirem, a #4 é quem decide o item; este documento continua descrevendo a forma.

O catálogo é um **pacote com um módulo por eixo** (`catalog/org.py`, `catalog/stack.py`, `catalog/tipo.py`), e o endereço de um item carrega o escopo dele. Não é organização: um item de stack morando no módulo de org mentiria sobre o eixo em que foi avaliado, e um teste guarda essa correspondência.

## O que o checker enxerga

Um item só pode ser escrito sobre o que a observação alcança, e por isso o alcance dela é parte da anatomia e não detalhe de implementação.

| O que | Como | Por quê |
| --- | --- | --- |
| **A árvore inteira** do repositório, em caminho relativo à raiz | uma chamada recursiva por repo | manifesto em subpasta de monorepo é superfície igual à da raiz. Enquanto só a raiz era listada, o item de lockfile de um monorepo **nem chegava a ser avaliado**: não é falso positivo, é um item que ninguém mede e que parece verde |
| O **conteúdo** de um conjunto **declarado** de arquivos | uma consulta por repo, com um apelido por arquivo | slot declarado dentro de um documento, referência à CI compartilhada dentro de um workflow e ferramenta declarada dentro de um manifesto são conteúdo, e nenhum deles se verifica por presença de arquivo. O conjunto é dado (`config/checker.json`), nunca varredura cega, e o custo não cresce com o número de arquivos |
| **Descrição, topics, wiki e licença** | metadados de plataforma | nenhum deles mora no working tree. A fronteira de *decisão* com a spec de Org continua onde está; a de *verificação* atravessa de propósito, porque estes itens ficariam sem vigia nenhum se o checker não os lesse |
| **Visibilidade** (`private`) | metadado de plataforma | a frota tem repositório privado, e o retrato observado vira fixture versionada num repositório **público**. Com o campo, a curadoria é reproduzível e um teste a guarda; sem ele, dependeria de alguém lembrar quais nomes são privados |

Duas propriedades não se negociam. **Ler mais não é escrever nada:** o checker continua read-only, e rodá-lo não muda nada em nenhum repositório, em nenhum momento. E **observação parcial não pode parecer conforme:** uma árvore que a API devolve truncada vira erro de observação daquele repositório, pelo mesmo motivo que o falso-negativo da listagem raiz era grave.

**A superfície é lida da árvore inteira; o que cada item exige é decisão dele.** As duas perguntas são diferentes e não se confundem: "este repositório tem superfície Node?" olha o repositório todo, e "ele declara a versão de runtime que o gerenciador da máquina lê?" olha um caminho exato, na raiz. O catálogo-semente pergunta pela raiz nos três itens que perguntam por arquivo; se algum item do catálogo cheio precisar da outra pergunta, ela é escolha dele, e o escopo continua revisável.

## Quando o checker roda

Como **passo do heartbeat da máquina**, no ramo em que o WSL está de pé, com cadência própria declarada em `config/heartbeat.json`. Ele precisa de rede e do token já autenticado da máquina, que é o oposto do que a poda precisa.

Ele **alarma, não trava**, e o código de saída é a interface: `1` significa deriva, e só deriva; qualquer coisa que impeça a matriz de existir sai como erro. São dois canais de alarme distintos, e é isso que impede um token expirado de chegar ao operador como "toda a frota está fora do padrão".

E ele **nunca é gate de PR**, em repositório nenhum. Anatomia é propriedade do repositório, não do diff: um gate puniria um PR inocente por dívida pré-existente, e metade dos itens nem mora no working tree para o diff poder consertar.

## Onde a anatomia mora

Parte do padrão é **imposta por plataforma**: ruleset e required checks, que um repositório não consegue contornar. Parte é **documentada e checada**: este documento e o checker, que alarmam na deriva sem travar nada. As duas metades moram juntas, com dureza honestamente diferente, e essa diferença é deliberada.
