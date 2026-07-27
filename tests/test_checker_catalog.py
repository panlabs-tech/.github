"""O catálogo é um pacote, e o eixo de um item é o módulo em que ele mora.

O prefactor não muda comportamento: os itens-semente só mudam de endereço, e a
matriz que sai deles continua a mesma (os testes do planner são quem prova isso).
O que o endereço passa a carregar é a propriedade guardada aqui: um item de
escopo stack morando no módulo de org mentiria sobre o eixo em que foi avaliado,
e é o escopo que permite auditar o próprio checker.
"""

from panlabs.checker import catalog
from panlabs.checker.catalog import org, stack, tipo


def test_the_seed_catalog_is_the_three_axis_modules_concatenated_in_order():
    assert catalog.DEFAULT_CATALOG == org.ITEMS + stack.ITEMS + tipo.ITEMS


def test_every_item_in_the_org_module_is_scoped_to_the_org_axis():
    assert {item.scope.kind for item in org.ITEMS} == {"org"}


def test_every_item_in_the_stack_module_is_scoped_to_a_named_surface():
    assert {item.scope.kind for item in stack.ITEMS} == {"stack"}
    assert all(item.scope.value for item in stack.ITEMS)


def test_every_item_in_the_type_module_is_scoped_to_a_named_type():
    assert {item.scope.kind for item in tipo.ITEMS} == {"tipo"}
    assert all(item.scope.value for item in tipo.ITEMS)


def test_no_item_id_is_declared_twice_across_the_axes():
    """O id é o que aparece na matriz: dois itens homônimos seriam indistinguíveis."""
    ids = [item.id for item in catalog.DEFAULT_CATALOG]

    assert len(ids) == len(set(ids))


def test_the_seed_catalog_still_carries_the_five_items_it_had_before_the_split():
    assert [item.id for item in catalog.DEFAULT_CATALOG] == [
        "readme-exists",
        "license-exists",
        "python-runtime-declared",
        "node-lockfile-committed",
        "anatomy-doc-exists",
    ]
