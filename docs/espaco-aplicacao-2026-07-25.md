# O espaço de trabalho reconciliado, 2026-07-25

Aplicado por `uv run panlabs-workspace --apply`, com a configuração desejada de [`config/workspace.json`](../config/workspace.json), para a issue [#21](https://github.com/panlabs-tech/.github/issues/21). O padrão documentado está em [`espaco-de-trabalho.md`](espaco-de-trabalho.md).

**Aplicado em recortes, e não de uma vez.** O espaço de trabalho é da máquina inteira, e `--only` existe justamente para isso: uma árvore de trabalho com sessão viva em cima teria o trabalho em voo commitado no meio. Havia uma, da issue [#22](https://github.com/panlabs-tech/.github/issues/22), e ela ficou de fora até fechar sozinha.

Nenhum retrato observado foi versionado como fixture, pelo mesmo motivo do script de máquina: ele carrega a varredura inteira do disco. As fixtures do planner são estado sintético, que é o que a spec pede.

## O que o plano encontrou, e o que foi feito

O plano saiu com **77 itens em 42 alvos**. Depois da aplicação sobraram 43, e os 12 aplicáveis que restam são preflight de repositório pessoal e o push desta própria branch.

| Metade | Itens | Estado |
| --- | --- | --- |
| Aditiva: clone do que faltava | 1 | aplicado |
| Remotes que mentiam por redirect | 4 | aplicado |
| Layout: repos da org sob o diretório da org | 5 | aplicado |
| Layout: reparo de vínculo de worktree | 17 | aplicado |
| Preflight de repositório da org | 8 | aplicado |
| Preflight de repositório pessoal | 12 | **continua com o operador** |
| Subtrativa: descarte | 31 | **retido, por construção** |

## O que mudou no espaço de trabalho

| Dimensão | Antes | Depois |
| --- | --- | --- |
| Repos da org com clone | 7 de 8; `dotfiles` ausente | 8 de 8, todos sob `~/workspaces/panlabs-tech/` |
| Repos da org fora do diretório da org | 5, planos na raiz | 0 |
| Remotes apontando para a conta antiga | 10, funcionando por redirect | 0 |
| Vínculos de worktree quebrados pela movimentação | seriam 17 | 0, reparados dos dois lados |
| Branches que só existiam neste disco | 6 | 0 nas da org |

**Os dez remotes stale colapsaram em quatro reescritas**, como a spec previa, e agora está medido em vez de suposto: `ethitorial`, `life-under-control`, `tfbox` e `travelmanager`. Os seis worktrees pendurados neles compartilham o `.git` do pai, e portanto o remote.

**O repo de nome com ponto e o `dotfiles` entraram sem caso especial.** O alvo é a listagem da org, e ela não filtra oculto.

## O que a execução na máquina viva ensinou

Dois defeitos reais, os dois encontrados por rodar o plano e ler o que ele dizia. Nenhum dos dois apareceria em fixture, porque os dois nascem de estado que só a máquina produz.

**O worktree solto de um pai que anda quebra parado.** A primeira versão só planejava reparo para quem mudava de endereço. Um worktree solto fica exatamente onde estava quando o pai se move, e ainda assim para de funcionar, porque o `.git` dele nomeia um `.git` de pai que deixou de existir naquele caminho. Eram seis nesta máquina, e todos os seis teriam quebrado em silêncio. O reparo passou a ser planejado quando **qualquer um dos dois lados** muda de endereço.

**Um worktree aninhado não é trabalho a preservar.** O `panlabs` não ignora `.claude/worktrees/`, então a árvore aninhada aparecia como diretório não rastreado e o preflight a lia como trabalho local a commitar. Commitá-la enfiaria um repositório dentro do outro: é dano, não preservação. O repo meta da org ignora esse caminho, e por isso nunca teria visto o caso.

## O que continua com o operador

**Os 31 descartes, retidos por construção.** Elegibilidade é sugestão do critério; a decisão irreversível continua humana, alvo por alvo:

- 6 diretórios: três vazios (`.agents`, `.git`, `luc-wt`) e três repositórios pessoais pushados (`aidriven-resources`, `b3stocks`, `hashnode-backup`);
- 25 worktrees cujo conteúdo já está inteiro em algum remote.

```sh
uv run panlabs-workspace --discard ~/workspaces/luc-wt --apply
```

**O preflight dos quatro repositórios pessoais**, que commitaria e empurraria o que só existe neste disco em `ThiagoPanini`, `callisto`, `campfire` e `engineering-golden-case`, e descartaria três stashes órfãos do `campfire`.

Ele não foi aplicado de propósito. O preflight existe para proteger um descarte, e com todos os descartes retidos ele escreveria commit em quatro repositórios pessoais e apagaria três stashes sem proteger nada hoje. Quando o operador autorizar a faxina, o mesmo comando faz as duas coisas na ordem certa, que é o que "o preflight precede a faxina, num fluxo só" quer dizer.

**Uma segunda rodada não desfaz nada.** Nenhum item de clone, reescrita, movimentação ou reparo sobrou, e nenhum repositório pessoal apagado é re-clonado: os alvos de clonagem saem só da listagem viva da org.
