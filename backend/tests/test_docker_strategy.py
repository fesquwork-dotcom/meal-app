from pathlib import Path


def test_dockerfile_includes_strategy_package():
    dockerfile = Path(__file__).resolve().parents[1] / "Dockerfile"
    content = dockerfile.read_text(encoding="utf-8")

    assert "COPY strategy ./strategy/" in content


def test_strategy_package_importable():
    from strategy import (
        StrategyBuilder,
        StrategyComplianceError,
        build_strategy_prompt_section,
        validate_menu_against_strategy,
    )
    from strategy.compliance import validate_menu_against_strategy as compliance_fn
    from strategy.prompt import strategy_to_prompt_dict

    assert StrategyBuilder is not None
    assert StrategyComplianceError is not None
    assert build_strategy_prompt_section is not None
    assert validate_menu_against_strategy is compliance_fn
    assert strategy_to_prompt_dict is not None
