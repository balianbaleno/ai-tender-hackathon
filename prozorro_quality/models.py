from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


SEVERITY_WEIGHT = {
    "висока": 3,
    "середня": 2,
    "низька": 1,
    "немає": 0,
}

PRIORITY_LABELS = {
    "висока": "високий",
    "середня": "середній",
    "низька": "низький",
    "немає": "без сигналів",
}

PRIORITY_CLASSES = {
    "висока": "high",
    "середня": "medium",
    "низька": "low",
    "немає": "none",
}


@dataclass
class DocumentResult:
    id: str
    title: str
    format: str
    url: str
    local_path: str | None = None
    status: str = "не оброблено"
    parsed_chars: int = 0
    limitation: str | None = None


@dataclass
class Issue:
    category: str
    title: str
    severity: str
    evidence_quote: str
    explanation: str
    suggested_rewrite: str
    document_title: str | None = None
    document_id: str | None = None
    source: str = "rules"


@dataclass
class LlmUsage:
    model: str = ""
    input_tokens: int = 0
    cached_input_tokens: int = 0
    billable_input_tokens: int = 0
    output_tokens: int = 0
    reasoning_output_tokens: int = 0
    total_tokens: int = 0
    input_cost_usd: float = 0.0
    cached_input_cost_usd: float = 0.0
    output_cost_usd: float = 0.0
    total_cost_usd: float = 0.0
    input_usd_per_million: float = 0.0
    cached_input_usd_per_million: float = 0.0
    output_usd_per_million: float = 0.0
    source: str = "codex-cli-usage"


@dataclass
class TenderSummary:
    tender_id: str
    tender_code: str
    title: str
    buyer_name: str
    value_amount: float | None
    currency: str | None
    cpv: str | None
    sector: str
    procurement_method_type: str | None
    date_modified: str | None


@dataclass
class TenderResult:
    summary: TenderSummary
    processed_at: str
    overall_score: int
    subscores: dict[str, int]
    issues: list[Issue] = field(default_factory=list)
    documents: list[DocumentResult] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    human_review_notice: str = (
        "Автоматичний аналіз показує потенційні ризики та нечіткі вимоги. "
        "Висновки потребують перевірки людиною і не є твердженням про правові порушення."
    )
    llm_engine: str = "детерміновані правила"
    llm_usage: LlmUsage = field(default_factory=LlmUsage)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TenderResult":
        summary = TenderSummary(**data["summary"])
        issues = [Issue(**item) for item in data.get("issues", [])]
        documents = [DocumentResult(**item) for item in data.get("documents", [])]
        llm_usage = LlmUsage(**data.get("llm_usage", {}))
        return cls(
            summary=summary,
            processed_at=data["processed_at"],
            overall_score=int(data["overall_score"]),
            subscores={k: int(v) for k, v in data.get("subscores", {}).items()},
            issues=issues,
            documents=documents,
            limitations=list(data.get("limitations", [])),
            human_review_notice=data.get(
                "human_review_notice",
                "Автоматичний аналіз потребує перевірки людиною.",
            ),
            llm_engine=data.get("llm_engine", "детерміновані правила"),
            llm_usage=llm_usage,
        )

    @property
    def highest_severity(self) -> str:
        if not self.issues:
            return "немає"
        return max(self.issues, key=lambda issue: SEVERITY_WEIGHT.get(issue.severity, 0)).severity


def priority_label(severity: str) -> str:
    return PRIORITY_LABELS.get(severity, severity)


def priority_class(severity: str) -> str:
    return PRIORITY_CLASSES.get(severity, "none")


def priority_weight(severity: str) -> int:
    return SEVERITY_WEIGHT.get(severity, 0)
