"""A configuração versionada que só existe em YAML, lida como ela é entregue.

Nem toda configuração deste repo mora em `config/`: o `dependabot.yml` e os
workflows moram onde o GitHub os procura, no formato que ele exige. Ler o arquivo
entregue é o que faz o teste falar sobre o que a plataforma vai ler, em vez de
sobre uma cópia em Python dele, que divergiria calada.

O que continua **não** sendo testado é o comportamento dos workflows: se o
gitleaks acha segredo, se o CodeQL acha alerta. Isso é exercitado por uso, e o
`.github` é o primeiro consumidor. O que se verifica é a fiação, que é decisão
nossa: quem depende de quem, e quais alvos a configuração declara.
"""

from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"
DEPENDABOT_CONFIG_PATH = REPO_ROOT / ".github" / "dependabot.yml"


def _read(path: Path) -> dict[str, Any]:
    """Lê um YAML entregue, com `on:` de volta ao nome que ele tem no arquivo.

    YAML 1.1 lê `on` como o booleano verdadeiro, e o gatilho do workflow sumiria
    de baixo da chave `"on"` sem esta correção. É pegadinha do formato, não do
    workflow, e cada teste redescobri-la seria pior do que corrigi-la aqui.
    """
    doc: dict[Any, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
    if True in doc:
        doc["on"] = doc.pop(True)
    return doc


def workflow(name: str) -> dict[str, Any]:
    """Um workflow entregue em `.github/workflows/`, pelo nome do arquivo."""
    return _read(WORKFLOWS_DIR / name)


def dependabot_config() -> dict[str, Any]:
    """A configuração de Dependabot version updates entregue por este repo."""
    return _read(DEPENDABOT_CONFIG_PATH)
