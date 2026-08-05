"""Recipe relation index for weekly planning."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from recipes.enums import RelationType
from recipes.models import RecipeRelation


@dataclass
class RelationIndex:
    avoid_consecutive: set[tuple[str, str]] = field(default_factory=set)
    similar_meal: set[tuple[str, str]] = field(default_factory=set)
    shares_ingredients: set[tuple[str, str]] = field(default_factory=set)
    good_pair: set[tuple[str, str]] = field(default_factory=set)
    leftovers_from: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    provides_component: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))

    def related(self, a: str, b: str, bucket: set[tuple[str, str]]) -> bool:
        return (a, b) in bucket or (b, a) in bucket

    def has_avoid_consecutive(self, a: str, b: str) -> bool:
        return self.related(a, b, self.avoid_consecutive)

    def has_similar(self, a: str, b: str) -> bool:
        return self.related(a, b, self.similar_meal)

    def has_shares(self, a: str, b: str) -> bool:
        return self.related(a, b, self.shares_ingredients)

    def has_good_pair(self, a: str, b: str) -> bool:
        return self.related(a, b, self.good_pair)


def build_relation_index(relations: list[RecipeRelation]) -> RelationIndex:
    idx = RelationIndex()
    for rel in relations:
        pair = (rel.source_recipe_id, rel.target_recipe_id)
        rt = rel.relation_type
        if rt == RelationType.AVOID_CONSECUTIVE_DAYS:
            idx.avoid_consecutive.add(pair)
        elif rt == RelationType.SIMILAR_MEAL:
            idx.similar_meal.add(pair)
        elif rt == RelationType.SHARES_INGREDIENTS:
            idx.shares_ingredients.add(pair)
        elif rt == RelationType.GOOD_PAIR:
            idx.good_pair.add(pair)
        elif rt == RelationType.USES_LEFTOVERS_FROM:
            idx.leftovers_from[rel.source_recipe_id].add(rel.target_recipe_id)
        elif rt == RelationType.PROVIDES_COMPONENT_FOR:
            idx.provides_component[rel.source_recipe_id].add(rel.target_recipe_id)
    return idx
