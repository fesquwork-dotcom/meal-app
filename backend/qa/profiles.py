"""Deterministic stress-test profile generator."""

from __future__ import annotations

import hashlib
import random
from dataclasses import asdict, dataclass
from typing import Literal

ProfileSource = Literal["generated", "fixtures", "mixed"]

MEAL_TYPE_COMBOS: tuple[tuple[str, ...], ...] = (
    ("breakfast",),
    ("lunch",),
    ("dinner",),
    ("breakfast", "lunch"),
    ("lunch", "dinner"),
    ("breakfast", "dinner"),
    ("breakfast", "lunch", "dinner"),
    ("breakfast", "lunch", "dinner", "snack"),
)

COOKTIME_BY_MINUTES: dict[int, str] = {
    15: "fast",
    20: "fast",
    30: "medium",
    45: "medium",
    60: "slow",
}

GOALS = ("home", "healthy", "weightloss", "muscle", "budget", "restaurant")
PROTEIN_SETS: tuple[tuple[str, ...], ...] = (
    ("any",),
    ("chicken",),
    ("veggie",),
    ("fish",),
    ("chicken", "eggs"),
    ("beef", "pork"),
    ("fish", "seafood"),
)
BUDGET_TIERS: dict[str, tuple[float, float]] = {
    "low": (800.0, 2000.0),
    "medium": (2000.0, 5000.0),
    "high": (5000.0, 15000.0),
}
ALLERGY_OPTIONS = ("нет", "молоко", "глютен", "орехи", "яйца")


@dataclass(frozen=True)
class StressProfile:
    """One generation scenario: profile dict + operational metadata."""

    run_index: int
    seed: int
    profile: dict[str, object]
    persons: int
    budget_tier: str
    cooktime_minutes: int
    dietary_label: str
    source: str

    def summary(self) -> dict[str, object]:
        return {
            "run_index": self.run_index,
            "seed": self.seed,
            "source": self.source,
            "days": self.profile.get("days"),
            "persons": self.persons,
            "meal_types": list(self.profile.get("meal_types") or []),
            "budget": self.profile.get("budget"),
            "budget_tier": self.budget_tier,
            "goal": self.profile.get("goal"),
            "cooktime": self.profile.get("cooktime"),
            "cooktime_minutes": self.cooktime_minutes,
            "proteins": list(self.profile.get("proteins") or []),
            "allergies": self.profile.get("allergies"),
            "dietary_label": self.dietary_label,
        }


def _rng(seed: int, run_index: int) -> random.Random:
    material = f"{seed}:{run_index}".encode("utf-8")
    digest = hashlib.sha256(material).hexdigest()
    return random.Random(int(digest[:16], 16))


def _fixture_profiles() -> list[dict[str, object]]:
    """Small hand-curated set of representative valid profiles."""
    return [
        {
            "goal": "home",
            "days": 3,
            "budget": 2500.0,
            "meal_types": ["breakfast", "lunch", "dinner"],
            "meals_per_day": 3,
            "proteins": ["any"],
            "cooktime": "fast",
            "allergies": "нет",
            "store": "any",
            "persons": 2,
            "_budget_tier": "medium",
            "_cooktime_minutes": 20,
            "_dietary_label": "none",
        },
        {
            "goal": "weightloss",
            "days": 7,
            "budget": 1800.0,
            "meal_types": ["breakfast", "dinner"],
            "meals_per_day": 2,
            "proteins": ["chicken", "eggs"],
            "cooktime": "medium",
            "allergies": "нет",
            "store": "any",
            "persons": 1,
            "_budget_tier": "low",
            "_cooktime_minutes": 30,
            "_dietary_label": "none",
        },
        {
            "goal": "healthy",
            "days": 5,
            "budget": 4500.0,
            "meal_types": ["breakfast", "lunch", "dinner"],
            "meals_per_day": 3,
            "proteins": ["veggie"],
            "cooktime": "medium",
            "allergies": "нет",
            "store": "any",
            "persons": 3,
            "_budget_tier": "medium",
            "_cooktime_minutes": 45,
            "_dietary_label": "vegetarian",
        },
        {
            "goal": "muscle",
            "days": 7,
            "budget": 8000.0,
            "meal_types": ["breakfast", "lunch", "dinner", "snack"],
            "meals_per_day": 4,
            "proteins": ["chicken", "eggs", "fish"],
            "cooktime": "slow",
            "allergies": "нет",
            "store": "any",
            "persons": 2,
            "_budget_tier": "high",
            "_cooktime_minutes": 60,
            "_dietary_label": "none",
        },
        {
            "goal": "budget",
            "days": 3,
            "budget": 1200.0,
            "meal_types": ["lunch", "dinner"],
            "meals_per_day": 2,
            "proteins": ["eggs", "veggie"],
            "cooktime": "fast",
            "allergies": "молоко",
            "store": "any",
            "persons": 4,
            "_budget_tier": "low",
            "_cooktime_minutes": 15,
            "_dietary_label": "allergy",
        },
    ]


def _generate_one(rng: random.Random, run_index: int, seed: int) -> StressProfile:
    days = rng.choice([3, 5, 7])
    persons = rng.randint(1, 6)
    meal_types = list(rng.choice(MEAL_TYPE_COMBOS))
    cooktime_minutes = rng.choice(list(COOKTIME_BY_MINUTES.keys()))
    cooktime = COOKTIME_BY_MINUTES[cooktime_minutes]
    budget_tier = rng.choice(list(BUDGET_TIERS.keys()))
    lo, hi = BUDGET_TIERS[budget_tier]
    # Scale budget roughly with persons and days so profiles stay feasible.
    budget = round(rng.uniform(lo, hi) * (0.6 + 0.15 * persons) * (days / 5.0), 2)
    budget = max(500.0, min(50000.0, budget))
    proteins = list(rng.choice(PROTEIN_SETS))
    goal = rng.choice(GOALS)
    allergies = rng.choice(ALLERGY_OPTIONS)

    if proteins == ["veggie"]:
        dietary_label = "vegetarian"
    elif allergies != "нет":
        dietary_label = "allergy"
    else:
        dietary_label = "none"

    profile: dict[str, object] = {
        "goal": goal,
        "days": days,
        "budget": budget,
        "meal_types": meal_types,
        "meals_per_day": len(meal_types),
        "proteins": proteins,
        "cooktime": cooktime,
        "allergies": allergies,
        "store": "any",
        "persons": persons,
    }
    return StressProfile(
        run_index=run_index,
        seed=seed,
        profile=profile,
        persons=persons,
        budget_tier=budget_tier,
        cooktime_minutes=cooktime_minutes,
        dietary_label=dietary_label,
        source="generated",
    )


def generate_profiles(
    *,
    runs: int,
    seed: int,
    mode: ProfileSource = "generated",
) -> list[StressProfile]:
    """Build `runs` deterministic profiles for the given seed and source mode."""
    if runs < 1:
        raise ValueError("runs must be >= 1")

    fixtures = _fixture_profiles()
    out: list[StressProfile] = []

    for index in range(runs):
        rng = _rng(seed, index)
        if mode == "fixtures":
            raw = dict(fixtures[index % len(fixtures)])
            persons = int(raw.pop("persons", 2))
            budget_tier = str(raw.pop("_budget_tier", "medium"))
            cooktime_minutes = int(raw.pop("_cooktime_minutes", 30))
            dietary_label = str(raw.pop("_dietary_label", "none"))
            out.append(
                StressProfile(
                    run_index=index,
                    seed=seed,
                    profile=raw,
                    persons=persons,
                    budget_tier=budget_tier,
                    cooktime_minutes=cooktime_minutes,
                    dietary_label=dietary_label,
                    source="fixtures",
                )
            )
        elif mode == "mixed":
            if index % 4 == 0:
                # Every 4th run uses a fixture for coverage of known shapes.
                fixture_profiles = generate_profiles(runs=1, seed=seed + index, mode="fixtures")
                base = fixture_profiles[0]
                out.append(
                    StressProfile(
                        run_index=index,
                        seed=seed,
                        profile=dict(base.profile),
                        persons=base.persons,
                        budget_tier=base.budget_tier,
                        cooktime_minutes=base.cooktime_minutes,
                        dietary_label=base.dietary_label,
                        source="mixed-fixture",
                    )
                )
            else:
                generated = _generate_one(rng, index, seed)
                out.append(
                    StressProfile(
                        run_index=generated.run_index,
                        seed=generated.seed,
                        profile=generated.profile,
                        persons=generated.persons,
                        budget_tier=generated.budget_tier,
                        cooktime_minutes=generated.cooktime_minutes,
                        dietary_label=generated.dietary_label,
                        source="mixed-generated",
                    )
                )
        else:
            out.append(_generate_one(rng, index, seed))

    return out


def profile_as_dict(profile: StressProfile) -> dict[str, object]:
    """Serialize stress profile metadata (no secrets)."""
    payload = asdict(profile)
    # asdict nests profile already; ensure JSON-friendly meal_types/proteins.
    nested = payload.get("profile")
    if isinstance(nested, dict):
        for key in ("meal_types", "proteins"):
            value = nested.get(key)
            if isinstance(value, tuple):
                nested[key] = list(value)
    return payload
