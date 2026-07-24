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

## Onde a anatomia mora

Parte do padrão é **imposta por plataforma**: ruleset e required checks, que um repositório não consegue contornar. Parte é **documentada e checada**: este documento e o checker, que alarmam na deriva sem travar nada. As duas metades moram juntas, com dureza honestamente diferente, e essa diferença é deliberada: metade dos itens de anatomia (wiki, descrição, topics) nem mora no working tree, e nada aqui é gate de PR. Anatomia é propriedade do repositório, não do diff.
