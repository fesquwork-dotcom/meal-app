"""API models for strategy compare (Sprint 5.24)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from decision.user_explanation import DecisionExplanationChange
from strategy.preview_models import StrategyPreviewResponse
from strategy.settings_diff_models import StrategySettingsDiff


class StrategyCompareResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    preview: StrategyPreviewResponse | None = None
    diff: StrategySettingsDiff | None = None
    decision_changes: list[DecisionExplanationChange] | None = None
