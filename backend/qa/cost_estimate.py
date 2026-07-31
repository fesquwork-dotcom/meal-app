"""Cost / volume estimation before real Claude stress runs."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CostEstimate:
    expected_api_calls_min: int
    expected_api_calls_max: int
    expected_input_tokens: int | None
    expected_output_tokens: int | None
    cost_usd: float | None
    note: str

    def to_dict(self) -> dict[str, object]:
        return {
            "expected_api_calls_min": self.expected_api_calls_min,
            "expected_api_calls_max": self.expected_api_calls_max,
            "expected_input_tokens": self.expected_input_tokens,
            "expected_output_tokens": self.expected_output_tokens,
            "cost_usd": self.cost_usd if self.cost_usd is not None else "unknown",
            "note": self.note,
        }


def estimate_run_cost(
    *,
    runs: int,
    avg_attempts: float = 1.4,
    avg_input_tokens: int = 12000,
    avg_output_tokens: int = 10000,
    input_usd_per_mtok: float | None = None,
    output_usd_per_mtok: float | None = None,
) -> CostEstimate:
    """Rough volume estimate. Price is unknown unless rates are configured."""
    calls_min = runs
    calls_max = int(runs * max(1.0, avg_attempts) + 0.999)
    input_total = int(calls_max * avg_input_tokens)
    output_total = int(calls_max * avg_output_tokens)
    cost = None
    note = "cost_estimate=unknown (set input/output USD per million tokens to price the run)"
    if input_usd_per_mtok is not None and output_usd_per_mtok is not None:
        cost = (input_total / 1_000_000.0) * input_usd_per_mtok + (
            output_total / 1_000_000.0
        ) * output_usd_per_mtok
        note = "estimate uses configured per-million-token rates"
    return CostEstimate(
        expected_api_calls_min=calls_min,
        expected_api_calls_max=calls_max,
        expected_input_tokens=input_total,
        expected_output_tokens=output_total,
        cost_usd=cost,
        note=note,
    )


def confirm_real_run(*, estimate: CostEstimate, assume_yes: bool) -> bool:
    if assume_yes:
        return True
    print("Real Claude stress test estimate:")
    for key, value in estimate.to_dict().items():
        print(f"  {key}: {value}")
    answer = input("Continue real API stress test? [y/N] ").strip().lower()
    return answer in {"y", "yes"}
