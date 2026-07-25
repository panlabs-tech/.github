"""Os itens de tipo: cobrados só da categoria que os declara.

Os cinco tipos são nomeados e finitos (`ANATOMY.md`), e o tipo de um repositório
é dado versionado em `config/repo-types.json`, nunca inferência do checker. Um
repositório ainda não classificado não é alcançado por item nenhum daqui, e isso
não é deriva: é o resultado esperado de uma classificação que ninguém fez.
"""

from __future__ import annotations

from panlabs.checker.catalog.item import AnatomyItem, has_file, is_tipo, tipo

__all__ = ["ITEMS"]

ITEMS: tuple[AnatomyItem, ...] = (
    AnatomyItem(
        id="anatomy-doc-exists",
        scope=tipo("meta"),
        applies=is_tipo("meta"),
        satisfied=has_file("ANATOMY.md"),
        motivo=lambda repo: f"{repo.name} é do tipo meta mas não tem ANATOMY.md na raiz",
    ),
)
