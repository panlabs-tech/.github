"""O catálogo é um pacote, e o eixo de um item é o módulo em que ele mora.

O que o endereço carrega é a propriedade guardada aqui: um item de escopo stack
morando no módulo de org mentiria sobre o eixo em que foi avaliado, e é o escopo
que permite auditar o próprio checker.

Estes testes não olham repositório nenhum. Eles olham o catálogo como objeto, e
guardam as três coisas que nenhum teste de planner pegaria: que o eixo do item
bate com o módulo dele, que nenhum id se repete, e que **todo caminho que um item
lê está declarado na observação**. O terceiro é o mais silencioso dos três: um
item que lê um arquivo que ninguém busca não falha -- ele passa, sempre, sobre um
conteúdo que nunca chegou.
"""

from panlabs.checker import catalog
from panlabs.checker.catalog import org, paths, stack, tipo
from panlabs.checker.config import VALID_TYPES, load_read_files


def test_the_catalog_is_the_three_axis_modules_concatenated_in_order():
    assert catalog.DEFAULT_CATALOG == org.ITEMS + stack.ITEMS + tipo.ITEMS


def test_every_item_in_the_org_module_is_scoped_to_the_org_axis():
    assert {item.scope.kind for item in org.ITEMS} == {"org"}


def test_every_item_in_the_stack_module_is_scoped_to_a_named_surface():
    assert {item.scope.kind for item in stack.ITEMS} == {"stack"}
    assert all(item.scope.value for item in stack.ITEMS)


def test_every_item_in_the_type_module_is_scoped_to_a_named_type():
    assert {item.scope.kind for item in tipo.ITEMS} == {"tipo"}
    assert all(item.scope.value for item in tipo.ITEMS)


def test_no_item_is_scoped_to_a_type_that_does_not_exist():
    """Os cinco tipos são nomeados e finitos: um sexto seria invenção."""
    assert {item.scope.value for item in tipo.ITEMS} <= VALID_TYPES


def test_no_item_id_is_declared_twice_across_the_axes():
    """O id é o que aparece na matriz: dois itens homônimos seriam indistinguíveis."""
    ids = [item.id for item in catalog.DEFAULT_CATALOG]

    assert len(ids) == len(set(ids))


def test_every_path_an_item_reads_is_declared_for_observation():
    """Item que lê arquivo não declarado tira veredito do vazio, e sempre passa.

    É o defeito mais silencioso possível do catálogo: nada quebra, nada erra, e a
    linha simplesmente não aparece -- indistinguível de um repositório conforme.
    """
    declared = set(load_read_files())
    read_by_items = {path for item in catalog.DEFAULT_CATALOG for path in item.reads}

    assert read_by_items <= declared


def test_every_shared_path_is_declared_for_observation_too():
    """Os caminhos de `paths.py` entram pela mesma porta, sem exceção."""
    declared = set(load_read_files())
    shared = {paths.PR_CHECKS, *paths.PYTHON_MANIFESTS, *paths.NODE_MANIFESTS}

    assert shared <= declared


def test_the_catalog_covers_the_three_axes_with_more_than_one_item_each():
    """A anatomia tem três eixos, e um eixo com um item só não exercita nada."""
    by_axis = {axis: 0 for axis in ("org", "stack", "tipo")}
    for item in catalog.DEFAULT_CATALOG:
        by_axis[item.scope.kind] += 1

    assert all(count > 1 for count in by_axis.values())
