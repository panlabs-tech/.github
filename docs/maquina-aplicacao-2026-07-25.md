# A máquina equipada, 2026-07-25

Aplicada por `uv run panlabs-machine --apply`, com a configuração desejada de [`config/machine.json`](../config/machine.json), para a issue [#20](https://github.com/panlabs-tech/.github/issues/20). O padrão documentado está em [`maquina.md`](maquina.md).

**Aplicado em duas rodadas, por construção.** A segunda rodada existe porque a remoção do diretório que hospedava o runtime vivo fica retida até a migração acontecer: não é conveniência, é o sequenciamento que não pode ser invertido. Replanejar depois deixou **0 itens aplicáveis**.

Nenhum retrato observado foi versionado como fixture, e isso é deliberado: ele carrega os caminhos de credencial e a varredura inteira do disco desta máquina. As fixtures do planner são estado de máquina sintético, que é o que a spec pede.

## As duas rodadas

| Rodada | Aplicou | Reteve |
| --- | --- | --- |
| 1ª | 6 links, 2 remoções de fantasma, 1 barra de status | o diretório do runtime, porque `node, npm, npx, pnpm, pnpx` ainda resolviam lá dentro |
| 2ª | a remoção do diretório do runtime, 0,84 GB | nada novo |

O texto da retenção na primeira rodada nomeava os cinco reféns, e é essa frase que torna o item revisável em vez de apenas bloqueado.

As três promoções de skill **não** entram nessa contagem, e a revisão do código é o motivo: elas foram inicialmente aplicadas por cópia de diretório, e a revisão apontou que isso contradiz a própria decisão de a CLI de distribuição ser o único mecanismo, porque uma skill copiada fica sem upstream de onde atualizar. As três foram reinstaladas pela CLI, e promover passou a ser **ação manual**: o plano carrega o comando exato e nenhum applier a realiza.

## O que mudou na máquina

| Dimensão | Antes | Depois |
| --- | --- | --- |
| `node`, `npm`, `npx` | link para `nodeenvs/campfire-context`, diretório nomeado por um projeto | shim do `mise`, `node` v24.18.0 |
| `pnpm`, `pnpx` | mesmo diretório de projeto | shim do `mise`, `pnpm` 11.17.0 |
| Gerenciador de Python | `pyenv` instalado, fora do PATH, 1,68 GB órfãos | `uv`, dedicado, fora do gerenciador de runtime |
| `nvm` | instalado, **nenhuma** versão dentro, 3,7 MB | removido, e as três linhas que o carregavam saíram do `~/.zshrc` |
| `fd` | inalcançável: um alias do oh-my-zsh capturava o nome | link para `/usr/bin/fdfind`, e o alias se aposentou sozinho |
| `bat` | existia **apenas** como alias | link para `/usr/bin/batcat`, alias virou rede de segurança guardada |
| Barra de status | `npx ccstatusline@latest`, ~1163 ms por render, com rede | binário fixado, ~250 ms, sem rede |
| Skills globais | 18 | 21 |
| Negação de leitura | já cobria os alvos resolvidos | inalterada, e agora **verificada** por invariante em vez de suposta |
| `panlabs-tech/dotfiles` | não existia | existe, com os 5 alvos declarados versionados por `chezmoi`. Os artefatos do heartbeat **ainda não**: ver abaixo |
| Clone de `panlabs-tech/skills` | não existia na máquina | existe, e é a fonte de distribuição povoada |

**Espaço recuperado: 2,52 GB** (1,68 do `pyenv`, 0,84 do diretório de runtime, 3,7 MB do `nvm`).

## O runtime nunca faltou

O critério mais duro da issue era negativo: *em nenhum momento a máquina fica sem `node`*. A verificação foi feita em subprocesso limpo (`env -i`, sem arquivo de rc, sem ativação de shell) depois de cada rodada, porque é assim que o agente roda e é ali que a falha apareceria.

Depois da remoção do diretório de 0,84 GB: `node` v24.18.0, `npm` 11.16.0, `pnpm` 11.17.0. Vivos.

## A barra de status, medida

| Comando | Tempo | Rede por render |
| --- | --- | --- |
| `npx ccstatusline@latest` | 1163 ms | sim |
| shim do `mise` | ~600 ms | não |
| binário direto, via `latest` do gerenciador | ~250 ms | não |

O binário direto foi o escolhido, e ele é estável apesar de o caminho conter uma versão: o gerenciador de runtime mantém `latest` como link que ele reaponta a cada upgrade. Foi exatamente esse detalhe que expôs um defeito no planner, descrito abaixo.

## As skills

Três órfãs reais subiram: `caveman`, `frontend-design`, `prompt-engineering-patterns`. Elas existiam versionadas em `panlabs` e **não tinham par no global**, então des-vendorizar sem promover custaria capacidade.

Elas foram para [`panlabs-tech/skills`](https://github.com/panlabs-tech/skills) e de lá instaladas **pela CLI de distribuição**, não por cópia de arquivo. A diferença importa: copiar deixaria três skills globais sem upstream de onde atualizar, e a CLI as registra com origem `panlabs-tech/skills`.

Duas foram **descartadas, não promovidas**, e a verificação foi por comparação de conteúdo:

| Descartada | É revisão anterior de | O que a global ganhou |
| --- | --- | --- |
| `to-prd` | `to-spec` | vocabulário de PRD para spec, e uma frase sobre o número ideal de pontos de teste |
| `to-issues` | `to-tickets` | declaração de dependências entre tickets |

Promovê-las criaria duas globais para o mesmo trabalho, que é a redundância que a cláusula proíbe.

## A varredura, e o que ela achou

A cláusula de zero redundância é verificada por **varredura do disco**, não suposta. Ela encontra hoje **190 cópias de skill global em 12 lugares**.

A varredura desce **dois níveis**, e o limite é deliberado: dois cobrem os dois layouts que existem, repo pessoal no primeiro nível e repo da org sob o diretório que espelha a org, no segundo. Ela não desce até worktree aninhada dentro de um repo, porque a cópia que a worktree carrega é o mesmo arquivo versionado do repo pai, já contado ali; contá-la de novo faria a redundância parecer maior do que é. Também não entra em `node_modules` nem em `.venv`, onde um pacote instalado pode trazer diretório de skill que não é do repo. Medido: contar tudo em qualquer profundidade daria 32 lugares, e os 20 extras são worktree aninhada e virtualenv.

Essas 190 saem no plano **retidas**, todas. Remover arquivo versionado de dentro de um repositório é o retrofit da [spec de Repo #4](https://github.com/panlabs-tech/.github/issues/4), que é onde a spec de Máquina #3 põe essa remoção, no próprio texto de escopo. Elas continuam no plano porque a varredura só vale se for legível por inteiro: esconder a frota faria o plano mentir sobre a redundância que existe.

Boa parte dessas cópias é de worktree solto e de repositório pessoal que a [issue #21](https://github.com/panlabs-tech/.github/issues/21) vai normalizar ou descartar, então o número vai cair sozinho antes de o #4 encostar nele.

## Os defeitos que a máquina viva e a revisão expuseram

Nenhum deles teria aparecido em fixture escrita à mão, e todos viraram teste.

**A promoção instalava por cópia.** O efeito copiava o diretório para o global, o que contradiz a decisão de a CLI de distribuição ser o único mecanismo e deixaria a skill global sem upstream de onde atualizar. Promover virou ação manual, com o comando no plano, e um teste agora garante que toda ação declarada como manual **não** tem efeito registrado e toda outra tem.

**A promoção lia do repositório errado.** O índice de skill vendorizada estava chaveado só por nome, e a mesma skill existe em doze repositórios: a última varrida ganhava. O plano dizia "sobe de `wt-216`" quando o dado declarava `panlabs`. A origem da cópia global passava a depender da ordem alfabética do disco. Corrigido chaveando por repositório **e** nome.

**A comparação de link replanejava para sempre.** O observador comparava o **fim** da cadeia de links com o alvo desejado. Para um alvo que é ele mesmo um link, como o `latest` que o gerenciador de runtime reaponta, o fim da cadeia é a versão concreta, nunca o `latest` pedido, e o plano pediria o mesmo relink em toda rodada. Corrigido separando duas perguntas que são diferentes: `points_to`, o alvo imediato, responde "aponta para onde eu pedi"; `resolved`, o fim da cadeia, responde "onde mora de verdade" e é o que decide se remover um diretório deixaria a máquina sem runtime.

Um terceiro caso não era defeito e sim medição: a CLI de distribuição instala em `~/.claude/skills`, e o observador só conhecia `~/.agents/skills`. As três skills recém-instaladas apareciam como ausentes, e o plano pedia promoção de novo. "Global" passou a significar alcançável globalmente, em qualquer dos dois diretórios, o que é a definição honesta.

## O que continua com o operador

| Item | Por quê |
| --- | --- |
| Autorizar repositórios no gerenciador de runtime | falha sem terminal interativo; é ato manual, uma vez só, e o agente nunca o executa |
| Decidir a visibilidade de `panlabs-tech/dotfiles` | nasceu privado por prudência, e privado custa o bootstrap sem pré-requisito. Ver [`maquina.md`](maquina.md#uma-decisão-que-continua-com-o-operador) |
| Ligar resolução de versão de Node por repo | pode invalidar módulo nativo já compilado; é decisão deliberada e não é escopo desta issue |
| O bloco de hook em onze worktrees | dispara em dobro; todas são worktree parada antes da promoção, e podar worktree é a [issue #21](https://github.com/panlabs-tech/.github/issues/21) |
| Os artefatos do heartbeat | o **endereço** deles é este repositório e está decidido e documentado; os artefatos são construídos pela [issue #22](https://github.com/panlabs-tech/.github/issues/22) |
