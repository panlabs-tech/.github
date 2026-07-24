@AGENTS.md

## Específico do Claude Code

- **Skills, subagents e commands são equipamento de máquina**, instalados globalmente em `~/.agents` e symlinkados em `~/.claude`. Este repo **não** versiona nenhum deles — a cópia global é a única (cláusula de zero redundância). Não vendorize.
- **Permissions e statusline** são globais, com override apenas em `settings.local.json` (sempre gitignored). Este repo não versiona lista de permissões.
- **Hooks portáveis** são globais e ativados por *marker file* no repo. Se este repo aderir a algum, o marker é versionado; a lógica do hook, não.
