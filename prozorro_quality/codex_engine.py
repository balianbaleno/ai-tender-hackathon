from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from .config import Settings
from .models import Issue, LlmUsage


class CodexEngine:
    """Optional short-snippet enrichment using the local Codex CLI.

    The deterministic rules produce the actual detections and scores. This hook asks Codex only to
    polish Ukrainian explanations and rewrites for already-detected snippets, keeping the prompt
    small and avoiding full-document LLM analysis.
    """

    def __init__(self, settings: Settings):
        self.settings = settings

    def available(self) -> bool:
        return shutil.which("codex") is not None

    def enrich(self, issues: list[Issue]) -> tuple[list[Issue], str | None, LlmUsage]:
        empty_usage = self.empty_usage()
        if not issues:
            return issues, None, empty_usage
        if not self.available():
            return issues, "Codex CLI не знайдено; використано детерміновані пояснення.", empty_usage

        payload = [
            {
                "index": idx,
                "category": issue.category,
                "title": issue.title,
                "severity": issue.severity,
                "evidence_quote": issue.evidence_quote[:700],
                "explanation": issue.explanation,
                "suggested_rewrite": issue.suggested_rewrite,
            }
            for idx, issue in enumerate(issues[:8])
        ]
        schema = {
            "type": "object",
            "properties": {
                "issues": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "index": {"type": "integer"},
                            "explanation": {"type": "string"},
                            "suggested_rewrite": {"type": "string"},
                        },
                        "required": ["index", "explanation", "suggested_rewrite"],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["issues"],
            "additionalProperties": False,
        }
        prompt = (
            "Ти допомагаєш аналізувати тендерну документацію Prozorro. "
            "Не роби юридичних висновків і не стверджуй порушення. "
            "Використовуй обережні формулювання: потенційний ризик, може обмежувати конкуренцію, "
            "потребує перевірки людиною, можлива проблема, нечітка вимога. "
            "Для кожного переданого сигналу поверни природне українське пояснення і коротке "
            "запропоноване переписування. Не додавай нові сигнали. JSON:\n"
            f"{json.dumps(payload, ensure_ascii=False)}"
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            schema_path = Path(tmpdir) / "schema.json"
            output_path = Path(tmpdir) / "codex-output.txt"
            schema_path.write_text(json.dumps(schema, ensure_ascii=False), encoding="utf-8")
            try:
                command = [
                    "codex",
                    "exec",
                    "--json",
                    "--skip-git-repo-check",
                    "--ephemeral",
                    "--sandbox",
                    "read-only",
                    "--output-schema",
                    str(schema_path),
                    "--output-last-message",
                    str(output_path),
                    "-",
                ]
                if self.settings.codex_model:
                    command[2:2] = ["-m", self.settings.codex_model]
                completed = subprocess.run(
                    command,
                    input=prompt,
                    text=True,
                    capture_output=True,
                    timeout=self.settings.codex_timeout,
                    check=True,
                )
                data = json.loads(output_path.read_text(encoding="utf-8"))
                usage = self.usage_from_stdout(completed.stdout)
            except Exception as exc:
                return issues, f"Codex-збагачення не виконано: {exc}", empty_usage

        by_index = {item["index"]: item for item in data.get("issues", [])}
        for idx, issue in enumerate(issues[:8]):
            update = by_index.get(idx)
            if not update:
                continue
            issue.explanation = str(update.get("explanation") or issue.explanation)
            issue.suggested_rewrite = str(update.get("suggested_rewrite") or issue.suggested_rewrite)
            issue.source = "правила+Codex"
        return issues, None, usage

    def empty_usage(self) -> LlmUsage:
        return LlmUsage(
            model=self.settings.codex_cost_model,
            input_usd_per_million=self.settings.codex_input_usd_per_million,
            cached_input_usd_per_million=self.settings.codex_cached_input_usd_per_million,
            output_usd_per_million=self.settings.codex_output_usd_per_million,
        )

    def usage_from_stdout(self, stdout: str) -> LlmUsage:
        usage: dict[str, Any] = {}
        for line in stdout.splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("type") == "turn.completed":
                usage = event.get("usage") or {}
        input_tokens = int(usage.get("input_tokens") or 0)
        cached_input_tokens = int(usage.get("cached_input_tokens") or 0)
        billable_input_tokens = max(0, input_tokens - cached_input_tokens)
        output_tokens = int(usage.get("output_tokens") or 0)
        reasoning_output_tokens = int(usage.get("reasoning_output_tokens") or 0)
        input_cost = billable_input_tokens / 1_000_000 * self.settings.codex_input_usd_per_million
        cached_cost = cached_input_tokens / 1_000_000 * self.settings.codex_cached_input_usd_per_million
        output_cost = output_tokens / 1_000_000 * self.settings.codex_output_usd_per_million
        return LlmUsage(
            model=self.settings.codex_cost_model,
            input_tokens=input_tokens,
            cached_input_tokens=cached_input_tokens,
            billable_input_tokens=billable_input_tokens,
            output_tokens=output_tokens,
            reasoning_output_tokens=reasoning_output_tokens,
            total_tokens=input_tokens + output_tokens,
            input_cost_usd=input_cost,
            cached_input_cost_usd=cached_cost,
            output_cost_usd=output_cost,
            total_cost_usd=input_cost + cached_cost + output_cost,
            input_usd_per_million=self.settings.codex_input_usd_per_million,
            cached_input_usd_per_million=self.settings.codex_cached_input_usd_per_million,
            output_usd_per_million=self.settings.codex_output_usd_per_million,
        )
