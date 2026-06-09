from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from copy import deepcopy
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from prozorro_quality.codex_engine import CodexEngine
from prozorro_quality.config import load_settings
from prozorro_quality.parser import DocumentParser
from prozorro_quality.storage import ResultStorage


OUTPUT_DIR = Path("data/codex_heuristic_mining")
ANALYSES_PATH = OUTPUT_DIR / "tender_analyses.jsonl"
FAILURES_PATH = OUTPUT_DIR / "failures.jsonl"
SYNTHESIS_PATH = OUTPUT_DIR / "heuristics_synthesis.json"
REPORT_PATH = OUTPUT_DIR / "heuristics_report.md"


EXISTING_RULES_SUMMARY = """
Current deterministic rules already cover:
- бренд/модель без «або еквівалент»: explicit brands/models without equivalent/analog guard.
- лист виробника: authorization/manufacturer/distributor letters and authorized partner status.
- географічне обмеження: office/warehouse/service center/local participant location requirements.
- нечітка вимога: vague quality or subjective timing wording.
- кваліфікаційні вимоги: high experience thresholds, especially 3+ years/contracts.
- документальні вимоги: notarized copies, originals of all docs, all passport pages, repeated free-form certificates.
- умови оплати/поставки: unclear delivery/payment wording.
There are also synthetic checks for missing payment, missing delivery, missing contract draft,
missing contract liability terms, and documents that are hard to parse.
""".strip()


TENDER_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "tender_code": {"type": "string"},
        "readability_notes": {"type": "string"},
        "candidates": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "category": {"type": "string"},
                    "signal_title": {"type": "string"},
                    "severity": {"type": "string", "enum": ["висока", "середня", "низька"]},
                    "document_title": {"type": "string"},
                    "evidence_quote": {"type": "string"},
                    "why_it_matters": {"type": "string"},
                    "suggested_rewrite": {"type": "string"},
                    "heuristic_pattern": {"type": "string"},
                    "false_positive_guards": {"type": "string"},
                    "covered_by_existing_rule": {"type": "boolean"},
                    "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                },
                "required": [
                    "category",
                    "signal_title",
                    "severity",
                    "document_title",
                    "evidence_quote",
                    "why_it_matters",
                    "suggested_rewrite",
                    "heuristic_pattern",
                    "false_positive_guards",
                    "covered_by_existing_rule",
                    "confidence",
                ],
                "additionalProperties": False,
            },
        },
    },
    "required": ["tender_code", "readability_notes", "candidates"],
    "additionalProperties": False,
}


SYNTHESIS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "heuristics": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "category": {"type": "string"},
                    "signal_title": {"type": "string"},
                    "recommended_severity": {"type": "string", "enum": ["висока", "середня", "низька"]},
                    "supporting_tender_count": {"type": "integer"},
                    "evidence_phrases": {"type": "array", "items": {"type": "string"}},
                    "detection_pattern": {"type": "string"},
                    "false_positive_guards": {"type": "string"},
                    "why_it_matters": {"type": "string"},
                    "suggested_rewrite": {"type": "string"},
                    "implementation_notes": {"type": "string"},
                    "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                },
                "required": [
                    "category",
                    "signal_title",
                    "recommended_severity",
                    "supporting_tender_count",
                    "evidence_phrases",
                    "detection_pattern",
                    "false_positive_guards",
                    "why_it_matters",
                    "suggested_rewrite",
                    "implementation_notes",
                    "confidence",
                ],
                "additionalProperties": False,
            },
        },
        "existing_rule_refinements": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "existing_category": {"type": "string"},
                    "refinement": {"type": "string"},
                    "why": {"type": "string"},
                },
                "required": ["existing_category", "refinement", "why"],
                "additionalProperties": False,
            },
        },
        "rejected_or_low_signal_patterns": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": ["heuristics", "existing_rule_refinements", "rejected_or_low_signal_patterns"],
    "additionalProperties": False,
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="Maximum tenders to analyze; 0 means all.")
    parser.add_argument("--timeout", type=int, default=240, help="Per-Codex-call timeout in seconds.")
    parser.add_argument("--synthesize", action="store_true", help="Synthesize a final heuristic list after analysis.")
    parser.add_argument("--only-synthesize", action="store_true", help="Skip per-tender analysis and synthesize existing JSONL.")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if not shutil.which("codex"):
        raise RuntimeError("Codex CLI is not available on PATH.")

    if not args.only_synthesize:
        analyze_tenders(limit=args.limit, timeout=args.timeout)
    if args.synthesize or args.only_synthesize:
        synthesize(timeout=args.timeout)


def analyze_tenders(limit: int, timeout: int) -> None:
    settings = replace(load_settings(), max_text_chars_per_doc=2_000_000)
    storage = ResultStorage(settings.db_path)
    doc_parser = DocumentParser(settings)
    completed = completed_tender_ids()
    results = storage.list_results()
    if limit:
        results = results[:limit]

    for index, result in enumerate(results, start=1):
        tender_id = result.summary.tender_id
        if tender_id in completed:
            print(f"skip {index}/{len(results)} {result.summary.tender_code}")
            continue

        try:
            prompt, doc_count, char_count = build_tender_prompt(result, doc_parser)
            print(
                f"codex {index}/{len(results)} {result.summary.tender_code} "
                f"docs={doc_count} chars={char_count}"
            )
            data, usage = run_codex_json(prompt, TENDER_SCHEMA, timeout=timeout)
            record = {
                "tender_id": tender_id,
                "tender_code": result.summary.tender_code,
                "title": result.summary.title,
                "sector": result.summary.sector,
                "cpv": result.summary.cpv,
                "doc_count": doc_count,
                "char_count": char_count,
                "analysis": data,
                "usage": usage,
            }
            append_jsonl(ANALYSES_PATH, record)
            print(
                f"done {result.summary.tender_code} "
                f"candidates={len(data.get('candidates', []))} cost=${usage.get('total_cost_usd', 0):.4f}"
            )
        except Exception as exc:
            append_jsonl(
                FAILURES_PATH,
                {
                    "tender_id": tender_id,
                    "tender_code": result.summary.tender_code,
                    "error": str(exc),
                },
            )
            print(f"fail {result.summary.tender_code}: {exc}")


def build_tender_prompt(result: Any, doc_parser: DocumentParser) -> tuple[str, int, int]:
    docs: list[dict[str, str]] = []
    for document in result.documents:
        local_path = Path(document.local_path) if document.local_path else None
        if not local_path or not local_path.exists():
            docs.append(
                {
                    "title": document.title,
                    "format": document.format or "",
                    "status": "missing_local_file",
                    "text": "",
                    "limitation": document.limitation or "No local file available.",
                }
            )
            continue
        parsed_doc, text = doc_parser.parse(deepcopy(document))
        docs.append(
            {
                "title": parsed_doc.title,
                "format": parsed_doc.format or "",
                "status": parsed_doc.status,
                "text": text,
                "limitation": parsed_doc.limitation or "",
            }
        )

    char_count = sum(len(doc["text"]) for doc in docs)
    doc_count = len(docs)
    docs_text = "\n\n".join(
        (
            f"### DOCUMENT {idx}: {doc['title']}\n"
            f"format: {doc['format']}\n"
            f"status: {doc['status']}\n"
            f"limitation: {doc['limitation']}\n"
            f"FULL EXTRACTED TEXT START\n{doc['text']}\nFULL EXTRACTED TEXT END"
        )
        for idx, doc in enumerate(docs, start=1)
    )

    prompt = f"""
You are mining real-world Prozorro tender documents for additional deterministic heuristics.

Read the tender documents completely. Use the full extracted text between START/END markers.
If a document has no extracted text, note it in readability_notes but do not invent evidence.

Goal:
- Find candidate review signals that are real, repeated, and useful for deterministic detection.
- Prefer heuristics that are missing from the current rule set or meaningful refinements.
- Use cautious Ukrainian wording: potential risk, may restrict competition, needs human review.
- Do not make legal conclusions.
- Return only candidates grounded in direct evidence from these documents.
- Keep evidence_quote short, but quote actual text from the document.

Existing rules to avoid duplicating:
{EXISTING_RULES_SUMMARY}

Tender:
- id: {result.summary.tender_id}
- code: {result.summary.tender_code}
- title: {result.summary.title}
- buyer: {result.summary.buyer_name}
- value: {result.summary.value_amount} {result.summary.currency}
- cpv: {result.summary.cpv}
- sector: {result.summary.sector}

Documents:
{docs_text}
""".strip()
    return prompt, doc_count, char_count


def synthesize(timeout: int) -> None:
    records = read_jsonl(ANALYSES_PATH)
    candidates = []
    for record in records:
        for candidate in record.get("analysis", {}).get("candidates", []):
            item = dict(candidate)
            item["tender_code"] = record.get("tender_code")
            item["sector"] = record.get("sector")
            item["cpv"] = record.get("cpv")
            candidates.append(item)

    prompt = f"""
You are synthesizing Codex-mined heuristic candidates from full-document Prozorro tender analysis.

Use the candidate list below to produce a concise implementation-ready set of deterministic heuristics.
Merge duplicates. Prefer patterns supported by multiple tenders, but keep a strong single-tender heuristic
if it is clearly important and implementable. Separate new heuristics from refinements to current rules.
Reject boilerplate or domain-specific requirements that are not useful as general review signals.

Existing rules:
{EXISTING_RULES_SUMMARY}

Candidates JSON:
{json.dumps(candidates, ensure_ascii=False)}
""".strip()
    data, usage = run_codex_json(prompt, SYNTHESIS_SCHEMA, timeout=timeout)
    payload = {"synthesis": data, "usage": usage, "source_candidate_count": len(candidates)}
    SYNTHESIS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(render_report(payload), encoding="utf-8")
    print(f"synthesis heuristics={len(data.get('heuristics', []))} cost=${usage.get('total_cost_usd', 0):.4f}")
    print(f"report {REPORT_PATH}")


def run_codex_json(prompt: str, schema: dict[str, Any], timeout: int) -> tuple[dict[str, Any], dict[str, Any]]:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        schema_path = tmp / "schema.json"
        output_path = tmp / "output.json"
        schema_path.write_text(json.dumps(schema, ensure_ascii=False), encoding="utf-8")
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
        completed = subprocess.run(
            command,
            input=prompt,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=True,
        )
        data = json.loads(output_path.read_text(encoding="utf-8"))
        usage = asdict(CodexEngine(load_settings()).usage_from_stdout(completed.stdout))
        return data, usage


def render_report(payload: dict[str, Any]) -> str:
    synthesis = payload["synthesis"]
    lines = [
        "# Codex-Heuristic Mining Report",
        "",
        f"Source candidate count: {payload['source_candidate_count']}",
        f"Synthesis LLM cost: ${payload['usage'].get('total_cost_usd', 0):.4f}",
        "",
        "## New Heuristics",
        "",
    ]
    for idx, heuristic in enumerate(synthesis.get("heuristics", []), start=1):
        lines.extend(
            [
                f"### {idx}. {heuristic['category']}: {heuristic['signal_title']}",
                "",
                f"- Severity: {heuristic['recommended_severity']}",
                f"- Support: {heuristic['supporting_tender_count']} tenders",
                f"- Confidence: {heuristic['confidence']}",
                f"- Detection pattern: {heuristic['detection_pattern']}",
                f"- False-positive guards: {heuristic['false_positive_guards']}",
                f"- Why: {heuristic['why_it_matters']}",
                f"- Rewrite: {heuristic['suggested_rewrite']}",
                f"- Implementation: {heuristic['implementation_notes']}",
                "- Evidence phrases:",
            ]
        )
        for phrase in heuristic.get("evidence_phrases", []):
            lines.append(f"  - {phrase}")
        lines.append("")

    lines.extend(["## Existing Rule Refinements", ""])
    for refinement in synthesis.get("existing_rule_refinements", []):
        lines.extend(
            [
                f"- {refinement['existing_category']}: {refinement['refinement']}",
                f"  Reason: {refinement['why']}",
            ]
        )

    lines.extend(["", "## Rejected Or Low-Signal Patterns", ""])
    for pattern in synthesis.get("rejected_or_low_signal_patterns", []):
        lines.append(f"- {pattern}")
    lines.append("")
    return "\n".join(lines)


def append_jsonl(path: Path, item: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(item, ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def completed_tender_ids() -> set[str]:
    return {record["tender_id"] for record in read_jsonl(ANALYSES_PATH)}


if __name__ == "__main__":
    main()
