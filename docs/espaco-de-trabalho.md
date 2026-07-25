# O estado estacionário do espaço de trabalho

O espaço de trabalho da máquina tem um **estado estacionário declarado**, e a máquina viva converge para ele. Este documento é a parte documentada; a parte executável é `uv run panlabs-workspace`, cujo plano é a verificação do invariante.

Origem: [spec de Máquina #3](https://github.com/panlabs-tech/.github/issues/3), issue [#21](https://github.com/panlabs-tech/.github/issues/21). O equipamento global da máquina é a [#20](https://github.com/panlabs-tech/.github/issues/20) e mora em [`docs/maquina.md`](maquina.md); o heartbeat é a [#22](https://github.com/panlabs-tech/.github/issues/22).

## Plano por default, e por que aqui isso não é conveniência

Este é o script que apaga diretório, move repositório e reescreve remote. Rodar sem argumento nunca muda nada, e nenhum descarte é aplicável sem o operador nomear o alvo, um a um.

Cada item do plano carrega ação, alvo e **motivo**. Um item que diz "apagar X" sem dizer por que X é elegível não é revisável, e revisão humana é parte do desenho do critério de descarte, não um extra.

## A metade aditiva: o que entra

**Invariante declarativo:** todo repositório da org tem clone num diretório que espelha o nome da org, com o remote canônico da org. Uniforme, sem exceção.

A fonte é a **listagem da org viva**, não um manifesto estático. Assim a regra não pode divergir da realidade, e repo novo entra sozinho. Clonagem preguiçosa sob demanda foi recusada porque falha exatamente no furo real: o repo de skills estava ausente e é a fonte de distribuição do equipamento de agente. Só uma regra que afirma "isto **tem** que existir" o pega.

"Clone" significa **só fonte**. Instalação de dependências fica fora, sob demanda: a frota inteira é menos de um giga de fonte, e o peso está nos artefatos reproduzíveis.

**Nenhuma afirmação aditiva sobre o que não é da org.** Repositório pessoal apagado nunca é re-clonado. Sem essa cláusula, a regra aditiva desfaria a faxina em toda rodada.

### O repo de nome com ponto

O repo meta da org começa com ponto, então o clone dele é um **diretório oculto**. No lado aditivo ele não é caso especial nenhum, e é justamente por isso: o alvo é a listagem da org, e ela não filtra oculto. Quem o perderia para sempre é um glob de disco, e por isso o alvo não é o disco. Na varredura, onde o disco **é** a fonte, a leitura é por `iterdir`, que também não filtra.

## Remotes: o redirect que mente

Os remotes que apontam para a conta pessoal e se referem a repos já migrados são reescritos para a org. Eles ainda funcionam, por redirect, e é exatamente esse o problema: eles mentem para quem lê o remote como dado, e já enganaram pelo menos duas análises.

**A reescrita é do repositório, nunca do worktree.** Worktree compartilha o `.git` do pai, e portanto o remote: dez remotes stale colapsam em quatro reescritas. Verificado, não suposto.

Repos genuinamente pessoais ficam intocados. O invariante é só da org, e quem responde "este diretório é da org?" é o **remote**, não o nome do diretório.

## O layout

| | |
| --- | --- |
| Repo da org | sob o diretório que espelha a org |
| Repo pessoal | plano na raiz, como alvo de faxina |
| Worktree que carrega trabalho | aninhado no próprio repositório pai |
| Worktree que já aterrissou por inteiro | fica onde está, e é proposto para descarte |

A última linha é a única exceção, e ela é deliberada: a regra de layout existe para tornar visível a relação entre worktree e pai, e um worktree que não carrega mais nada que só exista nele é descartável, não organizável. Mover antes de descartar seria trabalho jogado fora. Se ele voltar a carregar trabalho, volta a ser movido.

**Mover um worktree quebra o vínculo com o pai**, porque o ponteiro de volta é caminho absoluto dos dois lados. Reparar esse vínculo é passo obrigatório do plano, não detalhe: sem ele, worktrees que hoje funcionam param de funcionar em silêncio.

O caso que só se enxerga olhando o pai: um worktree **solto**, de um repositório que anda, fica exatamente onde estava e ainda assim quebra, porque o `.git` dele nomeia um `.git` de pai que deixou de existir naquele caminho. Nenhuma comparação sobre o endereço do próprio worktree o pegaria. Por isso o reparo é planejado quando **qualquer um dos dois lados** muda de endereço.

Um worktree aninhado num pai que anda **anda junto**, sem item de movimentação próprio, e mesmo assim precisa do reparo. O planner calcula o endereço final de cada diretório uma vez, antes de qualquer item, para que as duas coisas não divirjam.

## A metade subtrativa: o que sai

**Critério de elegibilidade:** não pertence à org **e** tem remote **e** está pushado. Diretório vazio é **sempre** elegível.

**Sem eixo de recência**, e isso é decisão consciente: um projeto parado há um ano não é um projeto morto. Não é promessa de comentário: o modelo observado **não tem campo de data**, então um critério com eixo de tempo não teria de onde tirá-la. O teste que prova isso compara o motivo de um repo parado há muito tempo com o de qualquer outro, e exige que sejam o mesmo texto.

**Elegibilidade é sugestão. A decisão de apagar continua humana**, alvo por alvo. Todo item de descarte nasce **retido**: ele aparece no plano, com o motivo à vista, e o `apply` não encosta nele. Só um alvo nomeado em `--discard` vira aplicável. Um caminho que o critério não considera elegível é **erro**, e não silêncio: um plano sem aquele descarte se leria como "não era elegível" quando na verdade foi erro de digitação.

O caminho a nomear é o que o plano mostra, que é o endereço **final**: o descarte é o último item do plano, então quando ele roda o diretório já está onde o layout o pôs. Um worktree de um repositório que se move é autorizado pelo endereço para onde ele vai, e não pelo de hoje.

O predicado que veta o descarte é deliberadamente mais largo que o que reconhece um clone da org: aqui basta o **nome** estar na listagem viva para o diretório nunca correr risco. Nas duas metades o erro seguro é para o lado de preservar.

## Conteúdo decide, identificador nunca

**Descarte de worktree só por comparação de conteúdo.** Sob squash-merge os identificadores divergem enquanto o conteúdo é idêntico. Foi assim que uma varredura anterior gerou alarme falso de 30 commits em 22 branches supostamente ausentes de todo remote, todas na verdade idênticas ao que já estava lá.

A medição é de **árvore**: o que os remotes alcançam entra em dois conjuntos, o dos identificadores e o das árvores, e só o segundo decide. O commit que aterrissa num squash tem outro identificador e a mesma árvore da branch que o originou, e é por isso que a árvore é a medida que sobrevive ao merge.

O identificador continua sendo medido, e continua não sendo usado. Ele existe no modelo para o plano poder dizer que **não** o usou.

O limite é honesto e declarado: a varredura cobre os últimos vinte mil commits de remote. Uma branch que aterrissou antes disso aparece como não pushada, o que erra para o lado de preservar.

## O preflight

**Regra única:** commita e pusha o que só existe local, depois apaga o diretório. Sem tarball, sem arquivo fora do git. Preservar tudo custa kilobytes.

**Detecção por conteúdo**, porque os dois defaults do git mentem em direções opostas:

- `git status` colapsa diretório não rastreado num item só e **subconta** o que se perderia. A leitura é sempre com todos os arquivos expandidos, e o plano nomeia quantos são.
- comparar branch com remote por identificador **superconta** sob squash-merge, como acima.

**Não protege o que o git já ignora.** É a cláusula que faz o eixo terminar em vez de virar arqueologia infinita.

**Derivado da máquina, não de uma lista.** A lista original nomeava três repos; quatro dias depois um quarto, este da própria org, apareceu com dezenas de arquivos sujos. A decisão continua válida; a lista, não.

**Stashes órfãos**, de branch que não existe mais nem local nem em remote nenhum, são descartados: eles não se aplicam a nada. Os vivos sobem como branch, porque a regra única é preservar o que só existe local, e stash é exatamente isso. Stash de repositório que **fica** na máquina não está em risco e não entra no preflight.

O descarte de stash sai em ordem decrescente de índice, porque descartar um stash desloca os de baixo. Isso é decisão de plano, não do applier: quem percorre a tabela de despacho não pode precisar saber disso.

**O preflight precede a faxina em vez de bloqueá-la:** é um fluxo só. As duas metades operam sobre conjuntos disjuntos, o que entra é da org e o que sai não é, então a ordem entre elas é indiferente por construção. O preflight antes do descarte é o único sequenciamento obrigatório, e ele é ordem de plano, que é a mesma ordem de aplicação.

A ordem inteira, e o porquê de cada aresta:

1. **reescrita de remote**, antes de qualquer coisa empurrar por ele, para que o trabalho preservado não viaje por um redirect;
2. **clone** do que falta;
3. **preflight**: commit, push, stash;
4. **layout**: primeiro os pais, depois os worktrees, e só então os reparos, porque reparar um vínculo antes de o pai chegar ao endereço final o gravaria apontando para onde o pai não está mais;
5. **descarte**, sempre por último.

## O recorte de invocação

O espaço de trabalho é da máquina inteira, e nem todo alvo dela está pronto para receber a convergência na mesma hora. Uma árvore de trabalho com sessão viva em cima teria o trabalho em voo commitado no meio pelo preflight.

`--only PATH` restringe o plano a um caminho e ao que mora sob ele. O recorte é do **plano**, e não do observado: recortar o observado produziria um plano diferente, e errado, porque um worktree sem o pai à vista perderia a movimentação do pai que muda o endereço dele, e um repo da org escondido da listagem viraria clone duplicado. O planner continua enxergando o espaço inteiro, e o que ficou fora do recorte é reportado em vez de sumir.

## Nenhum componente agendado

E explicitamente **sem pegar carona no heartbeat**. A estrutura fica verdadeira sozinha: remote não deriva, e a org quase nunca cresce. Quando crescer, o reconcile idempotente roda na mão.

## Como se roda

```sh
uv run panlabs-workspace                              # o plano do espaço vivo
uv run panlabs-workspace --json                       # o mesmo plano, serializado
uv run panlabs-workspace --show-observed              # o retrato antes do plano
uv run panlabs-workspace --only ~/workspaces/campfire # recorta o plano
uv run panlabs-workspace --apply                      # aplica o que é aplicável
uv run panlabs-workspace --discard PATH --apply       # autoriza um alvo, um a um
```

`--apply` não aceita `--observed`: aplicar a partir de um retrato salvo agiria sobre um estado que pode já ter mudado, e aqui isso apagaria diretório.
