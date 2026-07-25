# O heartbeat, aplicado em 2026-07-25

Primeira execução real do mecanismo da issue [#22](https://github.com/panlabs-tech/.github/issues/22), pelo caminho inteiro: a tarefa do agendador do host chamando o script do host, que consultou o estado do WSL, entrou nele e deixou o planner de [`config/heartbeat.json`](../config/heartbeat.json) decidir. O padrão documentado está em [`heartbeat.md`](heartbeat.md).

Nenhum retrato observado foi versionado como fixture, pelo mesmo motivo da issue #20: ele carrega a varredura de disco desta máquina. As fixtures do planner são estado sintético.

## O que a poda devolveu

| Alvo | Antes | Depois | Recuperado |
| --- | --- | --- | --- |
| `~/.cache/ms-playwright` | 2,4 GB | 641 MB | **1,80 GB** |
| `~/.cache/pip` | 1,2 GB | 21 MB | **1,18 GB** |
| `~/.npm` | 3,6 GB | 2,7 GB | **0,90 GB** |
| `~/.cache/uv` | 2,2 GB | 1,4 GB | **0,80 GB** |
| `~/.cache/puppeteer` | 1,4 GB | 636 MB | **0,77 GB** |
| store do `pnpm` | 1,7 GB | 1,7 GB | 0 |
| **Total** | | | **5,45 GB** |

O `pnpm store prune` devolver zero **não é falha**: ele é gentil por definição e remove só o inalcançável. Num store em que tudo ainda é referenciado por algum projeto, zero é a resposta certa, e ela custou segundos.

Os dois caches de browser sozinhos devolveram 2,57 GB, e nenhum teste quebrou: as revisões atuais (`chromium-1223` no Playwright, `linux-148.0.7778.97` no Puppeteer) continuam instaladas. Era exatamente a aposta do reenquadramento, e ela pagou.

## O disco do host não subiu, e não era para subir

| | |
| --- | --- |
| `C:` livre antes | 42,06 GB |
| `C:` livre depois | 41,57 GB |

**Liberar 5,45 GB por dentro não devolveu um byte ao host.** Isso não é defeito: o disco virtual é catraca, cresce com uso normal e não encolhe sozinho. O que a poda compra é **preventivo**: ela impede o arquivo de expandir, e expansão é irreversível sem compactação.

E a compactação, medida em julho, devolve 0,28 GiB. Então o número honesto para o operador é este: **o heartbeat não devolve GB ao `C:`; ele impede que o `C:` seja consumido.** Quem esperar a primeira leitura vai se decepcionar com a métrica errada.

## A cadência, observada em vez de suposta

Duas execuções seguidas, com poucos minutos entre elas:

| Execução | O plano continha |
| --- | --- |
| 1ª | os 7 passos do ramo de pé, todos com marca ausente |
| 2ª | **1 passo**: só o `uv-cache`, que havia falhado e por isso não tinha marca |

A segunda execução é a prova viva de "disparo diário não é cadência da ação": seis passos ficaram de fora porque a cadência deles não venceu, e um entrou porque falhar **não** grava marca. Nenhum dos dois comportamentos precisou de caso especial.

## Dois defeitos que só a execução real encontrou

Ambos moram na costura entre os dois lados, que é onde teste nenhum olhava.

**O `uv run` travava o passo que poda o cache do `uv`.** A tarefa chamava o heartbeat por `uv run`, e o `uv` segura o lock de `~/.cache/uv` enquanto o comando roda. O passo `uv cache prune` esperou 300 segundos pelo lock e falhou por timeout, e isso teria acontecido **todo dia, para sempre**. O conserto é a tarefa chamar o console script do ambiente virtual direto.

**O arquivo de marcas tinha dois autores que discordavam sobre codificação.** O PowerShell do Windows grava UTF-8 com marca de ordem de bytes, e o leitor de JSON do Python a recusa. O efeito era silencioso e caro: o lado de dentro lia "primeiro disparo" em toda execução, a cadência de todos os passos zerava, e o alarme de marca velha nunca tocaria. Consertado dos dois lados.

O segundo é o mais instrutivo: ele **não quebrava nada visível**. O plano saía cheio, os passos rodavam, o log ficava bonito. O que estava quebrado era exatamente o mecanismo de silêncio, e um defeito no mecanismo de silêncio não faz barulho.

## A tarefa agendada

Criada como `panlabs-heartbeat`, disparo diário às 03:00, com recuperação de execução perdida ligada. A reconciliação rodou **duas vezes** e o agendador continua com **uma** tarefa.

**Ela ficou sem elevação**, e isso está medido, não presumido: criar tarefa elevada exige que quem cria já esteja elevado, e um processo disparado de dentro do WSL nunca está. A criação com privilégio elevado responde `Access is denied`.

A consequência é exata e pequena: **a poda roda inteira** e só a compactação fica sem efeito, porque só ela precisa de elevação. A reconciliação deixou a definição elevada em `%LOCALAPPDATA%\panlabs\panlabs-heartbeat.xml` e o comando que a promove, para quando o operador quiser.

## O que continua com o operador

1. **`chezmoi apply`**, depois de puxar o [PR dos dotfiles](https://github.com/panlabs-tech/dotfiles). Ele torna versionado o que hoje está no host, e reconcilia tudo idempotentemente.
2. **`uv sync`** no clone principal de `.github`, depois do merge: a tarefa aponta para o console script do ambiente virtual de lá, e ele só existe depois de um sync. Enquanto não existir, o alarme diz exatamente isso.
3. **Armar a compactação**, se quiser os 0,28 GiB, com o comando de uma linha num PowerShell como administrador.

Nenhum dos três é urgente, e o primeiro disparo automático acontece de qualquer jeito.
