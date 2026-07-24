# Domain docs

Este repo é **single-context**. Os documentos de domínio moram em `docs/`, e a definição canônica do padrão mora na raiz.

## Onde está o quê

| Documento | Papel |
| --- | --- |
| `ANATOMY.md` (raiz) | A definição canônica do que é um repo panlabs — três eixos, tipos, invariantes, slots. É o alvo contra o qual o checker mede. |
| `docs/agents/` | Como um agente trabalha **neste** repo. |
| `docs/adr/` | Decisões de arquitetura deste repo, quando houver. |

## Vocabulário

Termos que aparecem em issues, specs e scripts, e que significam algo específico aqui:

- **Frota** — o conjunto de repos da org `panlabs-tech`, derivado da org viva. Nunca uma lista escrita.
- **Superfície** — uma stack presente num repo (node, python, terraform). Um repo pode ter mais de uma, e a variante por stack se aplica **por superfície**, não por repo.
- **Tipo** — a classificação do repo: `app`, `tf-module`, `skills`, `meta`, `dotfiles`.
- **Slot** — item da anatomia que obriga **declaração**, não valor. Um repo declara sua versão de runtime; a anatomia exige que declare, não que declare um número específico.
- **Invariante** — item exigido de todo repo, independentemente de stack ou tipo.
- **Conforme** — o checker passa inteiro. Leitura binária; não existe nível "recomendado".
- **Deriva** — divergência detectada pelo checker. Vira trabalho, nunca bloqueio.
- **Plano** — a saída pura de um script antes de qualquer efeito. Lista de ação, alvo e motivo.
- **Heartbeat** — a tarefa diária no agendador do host que hospeda os passos periódicos da máquina.
- **Esteira** — o caminho `worktree → commit → push → PR automático → merge no verde`.

## Registro histórico

O raciocínio que produziu este padrão está no mapa [panlabs-tech/panlabs#46](https://github.com/panlabs-tech/panlabs/issues/46) e nos seus 21 tickets de decisão, que permanecem lá. Quando uma decisão desta anatomia parecer arbitrária, o porquê provavelmente está num deles.
