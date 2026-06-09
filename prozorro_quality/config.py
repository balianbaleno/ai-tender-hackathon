from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    api_base_url: str = "https://public.api.openprocurement.org/api/2.5"
    data_dir: Path = PROJECT_ROOT / "data"
    request_timeout: float = 8.0
    min_value: float = 500_000.0
    max_value: float = 40_000_000.0
    default_batch_size: int = 5
    default_max_pages: int = 12
    documents_per_tender: int = 12
    max_document_bytes: int = 20 * 1024 * 1024
    max_text_chars_per_doc: int = 220_000
    codex_timeout: int = 90
    codex_model: str | None = None
    codex_cost_model: str = "gpt-5.5"
    codex_input_usd_per_million: float = 5.0
    codex_cached_input_usd_per_million: float = 0.5
    codex_output_usd_per_million: float = 30.0

    @property
    def cache_dir(self) -> Path:
        return self.data_dir / "cache"

    @property
    def result_dir(self) -> Path:
        return self.data_dir / "results"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "quality.sqlite3"


def load_settings() -> Settings:
    data_dir = Path(os.getenv("PROZORRO_QUALITY_DATA_DIR", PROJECT_ROOT / "data"))
    codex_model = os.getenv("PROZORRO_CODEX_MODEL") or None
    cost_model = os.getenv("PROZORRO_CODEX_COST_MODEL") or codex_model or default_codex_model()
    default_prices = codex_prices_for_model(cost_model)
    return Settings(
        api_base_url=os.getenv(
            "PROZORRO_API_BASE_URL",
            "https://public.api.openprocurement.org/api/2.5",
        ).rstrip("/"),
        data_dir=data_dir,
        request_timeout=float(os.getenv("PROZORRO_REQUEST_TIMEOUT", "8")),
        min_value=float(os.getenv("PROZORRO_MIN_VALUE", "500000")),
        max_value=float(os.getenv("PROZORRO_MAX_VALUE", "40000000")),
        default_batch_size=int(os.getenv("PROZORRO_BATCH_SIZE", "5")),
        default_max_pages=int(os.getenv("PROZORRO_MAX_PAGES", "12")),
        documents_per_tender=int(os.getenv("PROZORRO_DOCUMENTS_PER_TENDER", "12")),
        max_document_bytes=int(os.getenv("PROZORRO_MAX_DOCUMENT_BYTES", str(20 * 1024 * 1024))),
        max_text_chars_per_doc=int(os.getenv("PROZORRO_MAX_TEXT_CHARS_PER_DOC", "220000")),
        codex_timeout=int(os.getenv("PROZORRO_CODEX_TIMEOUT", "90")),
        codex_model=codex_model,
        codex_cost_model=cost_model,
        codex_input_usd_per_million=float(
            os.getenv("PROZORRO_CODEX_INPUT_USD_PER_M", str(default_prices[0]))
        ),
        codex_cached_input_usd_per_million=float(
            os.getenv("PROZORRO_CODEX_CACHED_INPUT_USD_PER_M", str(default_prices[1]))
        ),
        codex_output_usd_per_million=float(
            os.getenv("PROZORRO_CODEX_OUTPUT_USD_PER_M", str(default_prices[2]))
        ),
    )


def default_codex_model() -> str:
    config_path = Path.home() / ".codex" / "config.toml"
    if not config_path.exists():
        return "gpt-5.5"
    for line in config_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if line.startswith("model "):
            _, value = line.split("=", 1)
            return value.strip().strip('"') or "gpt-5.5"
    return "gpt-5.5"


def codex_prices_for_model(model: str) -> tuple[float, float, float]:
    normalized = model.lower()
    if normalized.startswith("gpt-5.5"):
        return 5.0, 0.5, 30.0
    if normalized.startswith("gpt-5.4"):
        return 2.5, 0.25, 15.0
    if normalized.startswith("gpt-5.3-codex") or normalized.startswith("gpt-5.2-codex"):
        return 1.75, 0.175, 14.0
    if (
        normalized.startswith("gpt-5.1-codex")
        or normalized.startswith("gpt-5-codex")
        or normalized.startswith("gpt-5.1")
        or normalized == "gpt-5"
    ):
        return 1.25, 0.125, 10.0
    return 5.0, 0.5, 30.0
