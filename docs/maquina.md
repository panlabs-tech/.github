# A máquina equipada

A máquina de desenvolvimento é um WSL2 sobre Windows 11 Home. Este documento é a parte **documentada** do padrão de máquina: o que vale para o global, quem instala o quê, e onde estão os limites honestos. A parte **executável** é `uv run panlabs-machine`, cujo plano é a verificação de invariante.

Origem: [spec de Máquina #3](https://github.com/panlabs-tech/.github/issues/3), issue [#20](https://github.com/panlabs-tech/.github/issues/20). O espaço de trabalho é a [issue #21](https://github.com/panlabs-tech/.github/issues/21) e mora em [`docs/espaco-de-trabalho.md`](espaco-de-trabalho.md); o heartbeat é a [#22](https://github.com/panlabs-tech/.github/issues/22). Nenhum dos dois mora aqui.

## Método de instalação, por classe

O ganho de declarar isto é que "como instalo isso" para de ser decisão caso a caso. A classe da ferramenta decide, e não o gosto de quem instala.

| Classe | Método | Por quê | Nesta máquina |
| --- | --- | --- | --- |
| O que já é do sistema | gerenciador de pacotes da distro | quem cuida da atualização é o sistema, e a versão da distro é boa o suficiente | `fdfind`, `batcat`, `rg`, `fzf`, `eza`, `zoxide` |
| Runtime de linguagem | gerenciador de runtime | a versão é do projeto, não da máquina, e mais de uma coexiste | Node, por `mise` |
| Runtime de Python | gerenciador dedicado, **fora** do de runtime | ele resolve ambiente e dependência juntos, e o de runtime não faz isso | `uv` |
| CLI que precisa ficar fresca | binário direto | o release é mais rápido que qualquer distro, e a atualização é do próprio binário | `mise`, `chezmoi`, `gh`, `uv`, `jq`, `gitleaks`, `lefthook` |

`lefthook` entrou nesta classe com o catálogo cheio da anatomia: o portão local virou **invariante de org**, e o binário que executa a declaração versionada de cada repo é equipamento da máquina, não do repo. A justificativa própria dele é essa, e não conveniência: sem ele, todo `lefthook.yml` da frota é declaração que ninguém executa.

**A classificação sozinha não instalava nada.** Esta tabela dizia desde sempre qual é o método, e mesmo assim o `lefthook` passou meses ausente da máquina enquanto três itens da anatomia verificavam um arquivo que nada executava: faltava o dado que o planner lê. A dimensão `tools` de [`config/machine.json`](../config/machine.json) é essa metade, e `uv run panlabs-machine` passa a acusar a ferramenta ausente com o comando exato que a instala. O invariante ali é o **nome resolver em subprocesso**, e não apontar para um endereço escolhido: quem decide onde o binário aterrissa é o instalador dele.

Instalar continua sendo ato do operador, e por decisão: o método é o release do próprio projeto, e um applier que baixasse e descompactasse viraria um instalador caseiro competindo com ele, que é a mesma razão que deixou a promoção de skill com a CLI de distribuição.

**Armar o hook é por clone, e nenhum convergedor de máquina o alcança.** `lefthook install` escreve em `.git/hooks/` de um repositório, e o convergedor de máquina não tem alvo de repositório. Um clone novo da frota nasce com o binário disponível e o hook desarmado, e isso é limite honesto, não omissão.

**Nenhuma ferramenta nova entra sem justificativa própria.** Seis candidatas foram avaliadas e reprovadas durante o mapeamento, e o registro delas fica no [mapa](https://github.com/panlabs-tech/panlabs/issues/46). A regra que sobrevive ao mapa é esta: a máquina não vira coleção.

## Alcançável pelo nome real, em subprocesso

O agente roda em **subprocesso não interativo**. Alias de shell não existe ali. Uma ferramenta que só existe como alias, ou cujo nome um alias captura, está quebrada exatamente do jeito que mais importa, e a medição que revela isso é `env -i sh -c '<nome> --version'`.

O conserto é por link em `~/.local/bin`, e ele é verificado pelo planner. Dois casos concretos:

- `fd` era capturado por um alias do `common-aliases` do oh-my-zsh (`alias fd='find . -type d -name'`). O alias é guardado por `(( $+commands[fd] ))`, então **criar o link aposenta o alias sozinho**, sem editar plugin nenhum.
- `bat` existia apenas como alias para `batcat`. A guarda equivalente foi escrita à mão no arquivo de configuração modular, pelo mesmo motivo e com o mesmo efeito.

### O alvo do link precisa sobreviver ao link

Criar o link não basta, porque **apontar para o alvo pedido não é o mesmo que ser alcançável**. Existe alvo que só funciona no diretório dele: um shim que calcula o que executar a partir de `dirname $0` passa a procurar o que executar ao lado do link, e o nome morre. Foi o que aconteceu com a barra de status, que ficou sem renderizar enquanto a verificação declarava o nome alcançável, porque conferia o alvo imediato e nada mais.

O critério é **relocabilidade**. Shim do gerenciador de runtime é binário e resolve pelo nome com que foi invocado, então sobrevive; shim de pacote npm em `node_modules/.bin` normalmente se ancora no próprio diretório e não sobrevive. O planner mede isso por leitura do alvo, nunca por execução, e reporta o nome inalcançável como item retido: nenhum relink resolve, porque o alvo é o defeito. Quando o binário só existe em forma ancorada, quem precisa dele por caminho fixo aponta para o **endereço real**, e o link em `~/.local/bin` fica para o nome existir em subprocesso.

## O sequenciamento que não pode ser invertido

O `node`, o `npm` e o `npx` vivos da máquina moravam num diretório nomeado por um projeto (`nodeenvs/campfire-context`, 0,84 GB), por link direto. A remoção desse diretório estava decidida, e **só podia rodar depois** da migração: removê-lo antes deixaria a máquina sem runtime.

Isto não é confiado à ordem em que alguém lê o plano. É decisão do planner: a remoção de um diretório fica **retida** enquanto qualquer nome que precisa ser alcançável ainda resolver lá dentro, e o texto da retenção nomeia quem é. Duas rodadas resolvem: a primeira move os links, a segunda encontra o diretório livre.

Este é o tipo de item que um plano bem-intencionado agrupa com as outras remoções, e é por isso que a proteção é mecânica em vez de escrita num comentário.

## O gerenciador de runtime, e o que o agente nunca faz

Node vem do `mise`, e chega por **shim**, não por `mise activate`. Shim funciona em subprocesso sem terminal; ativação por hook de shell não. Não há `eval "$(mise activate zsh)"` no `~/.zshrc`, de propósito.

**A autorização de repositórios no gerenciador de runtime é ato do operador, uma vez só.** O agente nunca a executa, porque ela falha sem terminal interativo. Arquivo de versão simples (`.node-version`) não pede confiança; `mise.toml`, que pode executar tarefa e definir ambiente, pede.

Verificado nesta máquina: um `.node-version` num repo da frota **não** dispara prompt de confiança em subprocesso sem TTY.

## Postura de permissão

A postura agressiva **fica**: é ela que sustenta a autonomia. A mitigação é uma lista de negação de leitura no global.

**Regência: negar sempre o alvo resolvido.** Dois fatos de mecanismo, ambos estabelecidos por teste durante o mapeamento porque a documentação é omissa:

1. A negação **sobrevive** ao modo de contorno de permissões. Logo é mitigação de custo zero.
2. A negação **em caminho com link vaza pelo shell**: ela bloqueia a leitura pela ferramenta e não bloqueia o comando de terminal equivalente, porque o shell fala com o alvo, não com o nome escrito.

Nesta máquina o vazamento é concreto e não hipotético: `~/.aws` é um link para `/mnt/c/Users/panin/.aws`. Negar o nome escrito deixaria o caminho real acessível. O planner por isso resolve o link antes de decidir, e essa resolução é decisão testada, não detalhe do applier.

### O limite honesto

**Isto vale contra descuido, não contra agente hostil.** Um subprocesso arbitrário passa direto: a negação é da ferramenta de leitura, e `cat` não é ela. Quem quiser ler a credencial, lê.

O que a lista compra é real e é modesto: ela impede que uma credencial entre no contexto por acidente, que é o modo como credencial de fato vaza.

**Custo colateral conhecido:** a lista já bloqueou o subagente de uma varredura de inventário legítima. É o preço, e está registrado para não virar surpresa.

**Capacidade preservada:** a CLI da nuvem continua funcionando com o seu diretório de credencial negado. Segurança sem perda de capacidade, verificado.

A lista viva desta máquina carrega, além dos alvos resolvidos, entradas herdadas que nomeiam o **caminho escrito** de `~/.aws` e `~/.azure`. O planner não as gerencia e não as remove: elas não fazem mal, e cobrem a leitura pela ferramenta no caminho com link. O que o invariante garante é o alvo resolvido, que é a metade sem a qual a negação vaza pelo shell. Uma máquina reconstruída do zero recebe só os alvos resolvidos.

## Equipamento de agente

**Skills vivem em um lugar só: o global.** A cláusula operante é **zero redundância**: uma skill candidata a global **não existe em repo nenhum**, e a cópia global é a única. Isso dissolve por construção a inversão de precedência entre níveis, porque elimina colisão de nome.

**A CLI de distribuição é o único mecanismo de instalação**, global ou por projeto. Marketplace nativo, vendoring proposital e travamento por identificador de commit saem de cena: frescor via CLI basta numa frota de uma máquina.

Skill autoral da org mora em [`panlabs-tech/skills`](https://github.com/panlabs-tech/skills), que é a fonte de distribuição. Promover copiando arquivo funcionaria e deixaria a skill global **sem upstream de onde atualizar**, e é por isso que a promoção passa pelo repositório em vez de terminar no diretório global.

**Permissões e barra de status** no global, com override apenas em `.claude/settings.local.json`, sempre fora do git.

A barra de status **não baixa nada por render**. Um comando com `npx …@latest` resolve pacote na rede a cada renderização, e o planner o trata como divergente por si, independentemente de qual pacote seja.

**Hooks portáveis** no global, com adesão por **arquivo marcador** no repo, que é o equivalente, para hooks, da ativação automática por descrição das skills. Sem o marcador, o hook global é inerte.

Hooks **mesclam** em vez de sobrepor. Ao promover um hook, o bloco local precisa ser apagado, senão dispara em dobro. Isso não é teoria: ver a seção de deriva.

## Ordem de bootstrap

Uma máquina perdida volta nesta ordem, e ela importa:

1. **[`panlabs-tech/dotfiles`](https://github.com/panlabs-tech/dotfiles)**, por `chezmoi`. Sem pré-requisito nenhum: o instalador é binário estático e carrega a própria implementação de git, então funciona antes de haver git.
2. **Toolchain**, pelo método por classe da tabela acima.
3. **Equipamento de agente**, pela CLI de distribuição.
4. **Espaço de trabalho** ([`docs/espaco-de-trabalho.md`](espaco-de-trabalho.md)), que é posterior e depende de ferramental já instalado.

Credencial de nuvem e token de CLI ficam **fora** do versionado, porque são segredo ou são regeneráveis. A recuperação deles é manual, e é assim de propósito.

## Onde a realidade divergiu da spec

A spec de Máquina #3 avisa que as suas listas já derivaram uma vez. Derivaram de novo, e o registro fica aqui em vez de a spec ser reescrita:

- **A frota declara dois majors de Node, não um.** A spec justifica o gerenciador de runtime por "treze repositórios que declaram versão e todos querem a mesma". Medido: `.node-version` em 10 diretórios, com major 24 em sete e 22 em três. Contando repositórios distintos e não worktrees, são quatro: `ethitorial` e `travelmanager` em 24, `life-under-control` e `panlabs` em 22. A justificativa fica **mais** forte, não menos: é exatamente para isso que serve um gerenciador de runtime.
- **O `mise` desliga arquivo de versão idiomático por default.** Então hoje todo repo recebe o Node global (24), igual a antes da migração. Ligar a resolução por repo é decisão separada e deliberada, porque pode invalidar módulo nativo já compilado, e não é escopo desta issue.
- **O raio da credencial são dois lugares, e o terceiro é o próprio agente.** `~/.aws` tem 4 entradas e modo 777, num sistema de arquivos que não suporta metadados, então o modo é impossível de corrigir. `~/.ssh` tem 6 entradas e modo 700. `~/.azure` e `~/secrets` estão **vazios**. O token do próprio agente é um terceiro arquivo, de natureza diferente.
- **O bloco local do hook promovido já havia sido apagado, no repositório que importa.** A promoção aconteceu em 2026-07-23 e o commit que a fez removeu o bloco: o working tree de `life-under-control` não tem mais `.claude/settings.json`. Mas **onze** cópias ainda carregam o bloco e disparam em dobro, e todas as onze são **worktree** parada em commit anterior à promoção: uma solta (`life-under-control-mirante`) e dez aninhadas em `life-under-control/.claude/worktrees/`. Nenhuma é o repositório em si. Normalizar e podar worktree é a [issue #21](https://github.com/panlabs-tech/.github/issues/21), não esta.
- **O repositório de dotfiles nasceu privado, e isso tem uma consequência.** Ver abaixo.

## Uma decisão que continua com o operador

`panlabs-tech/dotfiles` foi criado **privado**, porque o conteúdo é configuração de máquina pessoal: nome de usuário do Windows, nome de chave SSH de VPS, caminhos da máquina. Nenhum segredo, mas identificável.

O custo é real e é o critério que escolheu o `chezmoi` em primeiro lugar: **num repositório privado, o bootstrap sem pré-requisito nenhum não funciona.** A implementação de git embutida do `chezmoi` não tem como se autenticar numa distro recém-instalada, onde por definição ainda não há `gh` nem credencial. Numa máquina que já tem a CLI do GitHub autenticada funciona; numa máquina do zero, não.

Tornar público restaura o critério por inteiro, com um comando:

```sh
gh repo edit panlabs-tech/dotfiles --visibility public
```

A escolha é do operador porque é a configuração pessoal dele que fica pública. O padrão escolhido foi o reversível.
