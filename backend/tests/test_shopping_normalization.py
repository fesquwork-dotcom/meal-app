import pytest

from shopping.normalization import canonical_ingredient_name, are_merge_compatible


def test_canonical_trim_and_yo():
    assert canonical_ingredient_name("  Помидоры  ") == "помидор"


def test_alias_normalization():
    assert canonical_ingredient_name("Томаты") == "помидор"
    assert canonical_ingredient_name("Куриное филе") == "куриная грудка"


def test_qualifiers_preserved():
    left = canonical_ingredient_name("Сливки 10%")
    right = canonical_ingredient_name("Сливки 33%")
    assert left != right
    assert not are_merge_compatible("Сливки 10%", "Сливки 33%")


def test_incompatible_products_not_merged():
    assert canonical_ingredient_name("Рис") != canonical_ingredient_name("Рисовая мука")
