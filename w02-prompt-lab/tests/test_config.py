from decimal import Decimal

from promptlab.config import ModelConfig


def test_cost_reproduces_from_token_counts() -> None:
    model = ModelConfig(
        logical_name="test",
        model_id="dated-test-model",
        input_usd_per_million=Decimal("2.00"),
        output_usd_per_million=Decimal("8.00"),
    )
    assert model.cost(500_000, 250_000) == Decimal("3.00")


def test_local_model_has_zero_marginal_provider_cost() -> None:
    model = ModelConfig(logical_name="local", model_id="mistral:7b")
    assert model.cost(20_000, 5_000) == Decimal("0")

