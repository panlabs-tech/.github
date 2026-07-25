"""Os itens invariantes: cobrados de todo repositório, de todo tipo e stack.

Um item só mora aqui se a ausência dele é deriva em **qualquer** repositório da
org, sem condição nenhuma. Na dúvida, o item é de stack ou de tipo: um invariante
falso cobra de quem não deve, e é o falso positivo mais caro que existe aqui,
porque ele desgasta a matriz inteira.
"""

from __future__ import annotations

from panlabs.checker.catalog.item import ORG, AnatomyItem, always

__all__ = ["ITEMS"]

ITEMS: tuple[AnatomyItem, ...] = (
    AnatomyItem(
        id="readme-exists",
        scope=ORG,
        applies=always,
        satisfied=lambda repo: repo.has_readme,
        motivo=lambda repo: f"{repo.name} não tem README",
    ),
    AnatomyItem(
        id="license-exists",
        scope=ORG,
        applies=always,
        satisfied=lambda repo: repo.has_license,
        motivo=lambda repo: f"{repo.name} não tem LICENSE",
    ),
)
