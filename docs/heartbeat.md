# O heartbeat da máquina

Esta máquina **não tinha execução periódica nenhuma**. O init do sistema está desabilitado, não há daemon de agendamento rodando, os hooks globais do agente estão vazios. Foi assim que o disco do host chegou a 99% de ocupação, com 8,1 GB livres, hospedando trabalho não commitado de cinco repositórios.

O heartbeat é o mecanismo que conserta isso. Este documento é a parte **documentada**; a parte executável é `uv run panlabs-heartbeat`, cujo plano é a verificação de invariante.

Origem: [spec de Máquina #3](https://github.com/panlabs-tech/.github/issues/3), issue [#22](https://github.com/panlabs-tech/.github/issues/22). O equipamento da máquina é a [`maquina.md`](maquina.md); o espaço de trabalho é a [issue #21](https://github.com/panlabs-tech/.github/issues/21).

## Por que o relógio mora no host

De dentro do WSL **não é possível medir a pressão que importa.** O disco virtual é *thin-provisioned*, declara um teto de 1 TB, e o sistema de dentro reporta 913 GB livres que fisicamente não existem: eles teriam que ser esculpidos do que sobra no `C:`. Não é que boa parte seja espaço do Windows; é que **boa parte não é espaço de ninguém**.

Não há alarme possível construído de dentro. Por isso o mecanismo é o Agendador de Tarefas do Windows, e não um timer de dentro:

| | Agendador do host | timer do init | agendador da distro |
| --- | --- | --- | --- |
| Roda com o WSL desligado | **sim** | não | não |
| Recupera execução perdida | **sim**, nativo | sim | não |
| Enxerga o `C:` livre real | **sim** | não | não |
| Pode compactar o disco virtual | **sim** | não | não |
| Raio de explosão na distro | **zero** | alto | baixo |

**O init do sistema não será habilitado.** Ele seria decisão consequente por si só, e a justificativa nunca apareceu porque o mecanismo escolhido não precisa dele. Decisão consequente evitada de graça.

## Oportunista: faz o que for seguro agora

```
tarefa dispara (diariamente)
     │
     └─ consulta quem está de pé          (não boota; não desliga)
          │
          ├─ WSL DE PÉ  → poda por dentro        (você está usando; risco zero)
          │
          └─ WSL PARADO → compacta o disco       (ninguém usando; risco zero)

  nunca executa: desligamento    |    nunca executa: boot forçado
```

O ciclo completo forçado (bootar, podar, desligar, compactar) foi **rejeitado**: um desligamento agendado pode matar sessão de trabalho no meio, e há repositórios com trabalho não commitado morando lá dentro.

Existe um terceiro estado, e ele não é "parado": **não consultado**. Tratá-lo como parado mandaria a compactação para cima de um disco vivo, que é o único desastre que este desenho tem como causar. Sem resposta, nenhum passo roda e o operador é notificado.

## Disparo diário não é cadência da ação

O disparo é diário por um motivo específico, e não é porque a ação precise ser diária: ele dá **cerca de trinta chances por mês** de encontrar o WSL no estado certo. Uma cadência mensal única daria uma só, e numa máquina que fica ligada a compactação poderia nunca acontecer.

Cada passo carrega a **cadência dele**:

| Passo | Ramo | Cadência | Rende |
| --- | --- | --- | --- |
| `npm cache verify` | de pé | 7 dias | 3,6 GB em `~/.npm` |
| `pnpm store prune` | de pé | 7 dias | 1,7 GB no store, 0,5 no cache |
| `uv cache prune` | de pé | 7 dias | até 2,2 GB |
| revisões velhas de browser (dois caches) | de pé | 7 dias | 2,4 GB medidos |
| arquivo de instalação órfão | de pé | 7 dias | 0,2 GB |
| `pip cache purge` | de pé | **30 dias** | 1,2 GB |
| compactação do disco virtual | parado | 30 dias | ver abaixo |

A taxa de acréscimo medida é de **3 a 4 GB por mês**, com 0,22 GB nos últimos 7 dias. Uma execução semanal de tudo colheria esses 0,22 GB e jogaria fora uma semana de cache quente. Quase toda poda aqui é **gentil** (remove só o inalcançável), e por isso cabe em sete dias; a única que é wipe de verdade espera trinta.

## O que poda, e o que explicitamente não poda

Os comandos nativos de limpeza de cada ferramenta, mais **versões obsoletas de browser de teste**, mais arquivos órfãos.

O reenquadramento que faz isso funcionar: **o desperdício não é browser, é versão velha de browser.** O cache do Playwright guardava três revisões de chromium e só a mais nova é a atual; as duas velhas somavam 1,7 dos 2,4 GB. Apagar todos os browsers renderia pouco mais e quebraria o próximo teste de ponta a ponta. Manter a mais nova custa quase nada e não quebra ninguém.

**Varredura genérica por idade foi rejeitada por mérito, não por gosto.** Dois motivos, ambos medidos:

1. Os dois maiores consumidores, `~/.npm` (3,6 GB) e o store do `pnpm` (1,7 GB), **não moram em `~/.cache`**. Uma varredura do diretório de cache erraria justamente os 5,3 GB maiores.
2. Ela poderia apagar o browser **atual** de quem não roda teste de ponta a ponta há um mês.

A rejeição é de mérito e não de viabilidade: `atime` funciona nesta máquina, com granularidade de cerca de um dia.

**`docker builder prune` não está na lista, e a ausência é decidida.** Ele é o passo de maior retorno conhecido (18,4 GB de build cache medidos) e precisa do daemon de pé, que é uma dimensão que este heartbeat não observa. Um passo que só falha quando o Docker Desktop está parado alarmaria todo dia até alguém subi-lo, e treinar o operador a ignorar o canal de falha custa mais do que os 18 GB valem. Ele entra quando chegar com a observação que o guarda.

## A compactação, com expectativa honesta

Ela usa o **único caminho disponível nesta edição do Windows**: a ferramenta usual exige um recurso que a edição Home não tem e não pode instalar. Exige elevação, e o agendador roda elevado sem prompt, o que torna a compactação automatizável **apenas** por este mecanismo.

**Ela rende pouco.** Uma execução medida devolveu **0,28 GiB** contra os cerca de 12 GB previstos: o arquivo foi de 51,51 para 51,23 GiB. A causa é mecânica: a compactação só recupera bloco **zerado**, e a raiz do WSL está montada com `discard`, então o descarte online já devolve bloco liberado continuamente. Não existe poça de lixo para drenar. A diferença entre o usado por dentro e o tamanho do arquivo no host é **alocação real do sistema de arquivos** (metadados, journal, blocos reservados), e ela não encolhe por compactação.

**O resultado real vem da poda.** O ramo de compactação fica porque é oportunista e de custo praticamente zero. Se algum dia a folga do disco for contada como "o agendador me devolve X GB por mês", esse X vem da poda.

### A ordem permanente

O ramo parado tem uma propriedade incômoda e inescapável: **ele só é executável exatamente quando o planner é inalcançável.** Entrar no WSL para planejar seria ligá-lo, que é a única coisa que este desenho promete nunca fazer.

A saída não é duplicar a decisão do outro lado da fronteira. É emitir a ordem **de véspera**, do mesmo planner puro: em toda execução com o WSL de pé, o plano do ramo parado é serializado em `standing-order.json`. Quando o host encontra o WSL parado, ele realiza aquela ordem e a **apaga**: uma ordem vale uma vez, e quem a reemite é o planner, no disparo seguinte. Se o passo não vence mais, a ordem some sozinha, e o host não precisa julgar idade de nada.

Um plano já é artefato serializável neste repo. A ordem permanente é o próprio plano atravessando uma fronteira de plataforma.

## Silencioso quando saudável

A poda não quebra nada, então não há o que pedir: ela **age**. O que sobra é como o operador fica sabendo, e o histórico desta máquina torna isso a parte mais importante do desenho, porque o disco chegou a 99% precisamente por não haver sinal.

| Estado | Saída |
| --- | --- |
| Tudo ok | só linha de log |
| Um passo falhou | notificação, no canal **daquele passo** |
| Disco do host abaixo do piso | notificação, no canal do disco |
| Marca de execução mais velha que 3 dias | notificação, no canal da marca |
| Uma dimensão não pôde ser observada | notificação, no canal de falha |

**O piso é de 25 GB**, e dá cerca de dois meses de folga na taxa medida. Ele é generoso de propósito: a razão registrada pelo operador é agir cedo e longe do teto, em vez de reagir colado nele.

### Por que os canais são separados

Cada passo declara o canal dele. **Falha de rede num passo não pode se disfarçar de alarme de disco**, porque o alarme de disco é o único vigia de uma métrica que não se enxerga de dentro do WSL, e gastá-lo com ruído o transformaria em algo que se ignora.

É essa separação que permite o checker de conformidade da spec de Repo #4 entrar como passo: ele traz um quarto canal, de natureza diferente, e um token expirado dele nunca vai parecer disco cheio.

Uma dimensão que **não pôde ser medida** sai no canal de falha, e não no canal do disco, mesmo quando o que faltou medir foi o disco: um alarme de piso que na verdade significa "ninguém mediu" gastaria o canal errado.

### O limite honesto dos alarmes

**Com o WSL parado, o piso do disco não é verificado.** O piso é decisão do planner, e o planner mora do lado de dentro; consultá-lo exigiria ligar o WSL. A verificação volta no primeiro disparo que o encontrar de pé.

Isso é menos grave do que parece, e a razão é estrutural: a pressão que este mecanismo vigia é o **crescimento do lado do WSL**, e ele não cresce enquanto está parado. O disco do host cresce por conta do lado Windows, que a spec de Máquina #3 põe explicitamente fora de escopo.

### O vigia de homem-morto

A tarefa **não tem como avisar da própria morte**. Se um update do Windows a desabilitar, o silêncio dela fica indistinguível de "está tudo bem", que é exatamente o modo de falha que este mecanismo existe para eliminar.

Por isso a marca da execução é lida no startup do shell, e ela grita quando envelhece. O custo é irrisório perto do tempo de startup já medido.

A marca da própria execução é gravada **sempre**, inclusive quando o plano sai vazio. Uma máquina saudável que não escrevesse marca ficaria indistinguível de uma tarefa morta.

## O hospedeiro de passos

O heartbeat é construído como **hospedeiro de passos plugáveis**, e não como script monolítico. Um passo declara três coisas, todas como dado em [`config/heartbeat.json`](../config/heartbeat.json):

- **em qual ramo roda**: com o WSL de pé, ou com ele parado;
- **qual é a cadência dele**;
- **qual canal de alarme ele usa**.

Isso existe porque a spec de Repo #4 determina que o checker de conformidade da frota rode como passo desta tarefa diária, e as premissas não batem: o checker precisa do WSL de pé, de rede e de token autenticado, e a poda não precisa de nada disso.

**Consequência de ordem: esta issue entrega o hospedeiro antes de a spec de Repo poder plugar o checker.** É uma dependência `repo -> máquina` que o handoff do mapa não declarava.

Plugar o checker é acrescentar um canal e um passo ao dado, e **nenhuma linha de código muda**. Um teste prova exatamente isso.

Expectativa honesta: no ramo "WSL de pé", o checker roda nas ocasiões em que a tarefa encontrar o WSL rodando. Para um alarme de deriva de anatomia isso basta; não é garantia diária.

### Os quatro corpos de um passo

| Corpo | O que faz | Por quê |
| --- | --- | --- |
| `run` | roda um comando nativo de limpeza | é o que o próprio tooling declara descartável |
| `keep_newest` | mantém as revisões novas de cada família de um cache versionado | o desperdício é versão velha, não o produto |
| `drop_matching` | remove arquivo pela **forma do nome** | órfão de instalação, reconhecido por forma e nunca por idade |
| `on_host` | o ato é do host | no ramo parado não existe WSL onde rodar nada |

Um passo tem exatamente um corpo. Nenhum é um passo que nunca age; dois é um passo cuja ordem ninguém escreveu. A leitura recusa os dois casos.

**O ramo parado obriga `on_host`**, e a leitura recusa o contrário: um passo do ramo parado que declarasse um comando de dentro só poderia ser realizado ligando o WSL. Recusar o dado é mais barato do que descobrir isso no host, elevado.

### Alcançável em subprocesso

O executável de um passo é declarado por **caminho absoluto**. O passo roda em subprocesso não interativo, disparado do agendador do host: ali não há arquivo de rc, e o PATH é o mínimo do sistema. `npm`, `pnpm` e `uv` moram em `~/.local/bin`, que não está nesse PATH.

Um nome nu funcionaria no terminal e falharia na tarefa. É a mesma classe de erro que a [issue #20](https://github.com/panlabs-tech/.github/issues/20) consertou ao exigir que todo nome seja alcançável pelo nome real, e ela reaparece aqui pelo mesmo motivo.

## Onde os artefatos moram

Os quatro artefatos são **versionados e recriáveis por script idempotente**, e o endereço é [`panlabs-tech/dotfiles`](https://github.com/panlabs-tech/dotfiles):

| Artefato | Onde | Como |
| --- | --- | --- |
| O planner e os passos | este repo | `uv run panlabs-heartbeat` |
| O script do host | dotfiles | arquivo versionado, copiado para o lado do host na reconciliação |
| A tarefa agendada | **não se versiona** | recriada pelo script de reconciliação idempotente |
| O vigia de homem-morto | dotfiles | fragmento no startup do shell |
| Marcas e log | **não se versionam** | estado de runtime, do lado do host |

A tarefa agendada é estado no registro do host: não se versiona, só se recria. Rodar a recriação duas vezes **não cria duas tarefas**, porque a criação sobrescreve por nome.

### A elevação, que a reconciliação não consegue conceder sozinha

Criar uma tarefa **elevada** exige que quem a cria já esteja elevado, e um processo disparado de dentro do WSL nunca está. Medido nesta máquina: a criação com privilégio elevado responde `Access is denied`.

A reconciliação então cria a tarefa **sem elevação**, e diz isso em voz alta em vez de falhar. A consequência é exata e pequena: a **poda roda inteira**, e só a compactação fica sem efeito, porque só ela precisa de elevação. Ela é o ramo que rende 0,28 GiB medidos.

Para armar a compactação, a reconciliação deixa a definição elevada em disco e o comando pronto. Num PowerShell **como administrador**:

```powershell
schtasks /Create /TN panlabs-heartbeat /XML "$env:LOCALAPPDATA\panlabs\panlabs-heartbeat.xml" /F
```

É uma decisão do operador porque é a conta dele que concede a elevação, e o padrão escolhido foi o que funciona sem pedir nada.

**As marcas moram do lado do host** porque é o único lado que as enxerga com o WSL parado, que é justamente o estado em que o ramo de compactação existe. De dentro do WSL elas são alcançadas por um caminho estável de estado, que a reconciliação aponta para o lado de lá; assim nada precisa descobrir o nome de usuário do Windows a cada execução, e o vigia no shell lê a marca por um caminho barato.

## Duas coisas que só a execução real revelou

Ambas eram invisíveis para o teste, porque as duas moram exatamente na costura entre os dois lados. Estão registradas aqui e em comentário no código porque são o tipo de defeito que volta.

**O heartbeat não pode rodar sob `uv run`.** Um dos passos poda o cache do próprio `uv`, e `uv run` segura o lock desse cache enquanto o passo roda. O passo espera cinco minutos e falha por timeout, todo dia, para sempre. A tarefa do host chama o console script do ambiente virtual direto, e o conflito dissolve porque nenhum processo do `uv` fica vivo.

**O arquivo de marcas tem dois autores, e eles não concordavam sobre codificação.** O PowerShell do Windows grava UTF-8 **com** marca de ordem de bytes, e o leitor de JSON do Python a recusa. O efeito era silencioso e caro: o lado de dentro lia "primeiro disparo" em toda execução, a cadência de todos os passos zerava, e o alarme de marca velha nunca tocaria. Consertado dos dois lados, porque cada metade está certa por si: o host grava sem a marca, e a leitura tolera encontrá-la.

## O substrato: o que este mecanismo explicitamente não faz

**Nenhum arquivo de configuração do WSL é criado.** Nenhuma chave sobreviveu ao escrutínio: as de dimensionamento ficam no default proporcional e nenhum número medido é melhor; a de recuperação de memória já está no valor desejado; a de tamanho de disco só afeta distro nova.

A opção de disco esparso continua **descartada**, e não por conservadorismo: o próprio fornecedor a desabilitou por corrupção de dados, e só se força com uma flag que se declara insegura.

**Expectativa honesta de teto:** o WSL inteiro é cerca de um quinto do disco usado do host. O resto é lado Windows, fora do alcance deste esforço.
