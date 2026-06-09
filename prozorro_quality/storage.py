from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Iterable

from .models import TenderResult


class ResultStorage:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS processed_tenders (
                    tender_id TEXT PRIMARY KEY,
                    tender_code TEXT NOT NULL,
                    title TEXT NOT NULL,
                    buyer_name TEXT,
                    value_amount REAL,
                    currency TEXT,
                    cpv TEXT,
                    sector TEXT,
                    procurement_method_type TEXT,
                    date_modified TEXT,
                    processed_at TEXT NOT NULL,
                    overall_score INTEGER NOT NULL,
                    issue_count INTEGER NOT NULL,
                    highest_severity TEXT NOT NULL,
                    result_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_processed_at ON processed_tenders(processed_at DESC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_score ON processed_tenders(overall_score)"
            )

    def has_tender(self, tender_id: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT tender_id FROM processed_tenders WHERE tender_id = ?",
                (tender_id,),
            ).fetchone()
        return row is not None

    def processed_ids(self) -> set[str]:
        with self._connect() as conn:
            rows = conn.execute("SELECT tender_id FROM processed_tenders").fetchall()
        return {row["tender_id"] for row in rows}

    def save(self, result: TenderResult) -> None:
        payload = json.dumps(result.to_dict(), ensure_ascii=False, indent=2)
        summary = result.summary
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO processed_tenders (
                    tender_id, tender_code, title, buyer_name, value_amount, currency, cpv,
                    sector, procurement_method_type, date_modified, processed_at,
                    overall_score, issue_count, highest_severity, result_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(tender_id) DO UPDATE SET
                    tender_code = excluded.tender_code,
                    title = excluded.title,
                    buyer_name = excluded.buyer_name,
                    value_amount = excluded.value_amount,
                    currency = excluded.currency,
                    cpv = excluded.cpv,
                    sector = excluded.sector,
                    procurement_method_type = excluded.procurement_method_type,
                    date_modified = excluded.date_modified,
                    processed_at = excluded.processed_at,
                    overall_score = excluded.overall_score,
                    issue_count = excluded.issue_count,
                    highest_severity = excluded.highest_severity,
                    result_json = excluded.result_json
                """,
                (
                    summary.tender_id,
                    summary.tender_code,
                    summary.title,
                    summary.buyer_name,
                    summary.value_amount,
                    summary.currency,
                    summary.cpv,
                    summary.sector,
                    summary.procurement_method_type,
                    summary.date_modified,
                    result.processed_at,
                    result.overall_score,
                    len(result.issues),
                    result.highest_severity,
                    payload,
                ),
            )

    def get(self, tender_id: str) -> TenderResult | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT result_json FROM processed_tenders WHERE tender_id = ?",
                (tender_id,),
            ).fetchone()
        if row is None:
            return None
        return TenderResult.from_dict(json.loads(row["result_json"]))

    def list_results(self) -> list[TenderResult]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT result_json FROM processed_tenders ORDER BY processed_at DESC"
            ).fetchall()
        return [TenderResult.from_dict(json.loads(row["result_json"])) for row in rows]

    def aggregate(self) -> dict[str, object]:
        results = self.list_results()
        total = len(results)
        if not results:
            return {
                "total": 0,
                "average_score": 0,
                "issue_count": 0,
                "high_risk_count": 0,
                "total_llm_cost": 0,
                "total_llm_tokens": 0,
                "sectors": [],
            }
        issue_count = sum(len(result.issues) for result in results)
        high_risk_count = sum(
            1 for result in results for issue in result.issues if issue.severity == "висока"
        )
        total_llm_cost = sum(result.llm_usage.total_cost_usd for result in results)
        total_llm_tokens = sum(result.llm_usage.total_tokens for result in results)
        sector_counts: dict[str, int] = {}
        for result in results:
            sector_counts[result.summary.sector] = sector_counts.get(result.summary.sector, 0) + 1
        return {
            "total": total,
            "average_score": round(sum(result.overall_score for result in results) / total, 1),
            "issue_count": issue_count,
            "high_risk_count": high_risk_count,
            "total_llm_cost": total_llm_cost,
            "total_llm_tokens": total_llm_tokens,
            "sectors": sorted(sector_counts.items(), key=lambda item: item[1], reverse=True),
        }


class MemoryProcessedSet:
    def __init__(self, ids: Iterable[str] = ()):
        self.ids = set(ids)

    def has_tender(self, tender_id: str) -> bool:
        return tender_id in self.ids
