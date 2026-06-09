from prozorro_quality.codex_engine import CodexEngine
from prozorro_quality.config import Settings


def test_codex_usage_cost_calculation_uses_cached_input_rate(tmp_path):
    settings = Settings(
        data_dir=tmp_path,
        codex_cost_model="gpt-5.5",
        codex_input_usd_per_million=5.0,
        codex_cached_input_usd_per_million=0.5,
        codex_output_usd_per_million=30.0,
    )
    stdout = """
{"type":"turn.started"}
{"type":"turn.completed","usage":{"input_tokens":1000,"cached_input_tokens":200,"output_tokens":50,"reasoning_output_tokens":30}}
"""

    usage = CodexEngine(settings).usage_from_stdout(stdout)

    assert usage.input_tokens == 1000
    assert usage.cached_input_tokens == 200
    assert usage.billable_input_tokens == 800
    assert usage.output_tokens == 50
    assert usage.total_tokens == 1050
    assert round(usage.total_cost_usd, 6) == 0.0056

