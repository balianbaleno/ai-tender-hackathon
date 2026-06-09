from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .analyzer import ParsedDocument, TenderAnalyzer
from .codex_engine import CodexEngine
from .config import Settings
from .models import DocumentResult, LlmUsage, TenderResult
from .parser import DocumentParser
from .prozorro_api import ProzorroClient, is_parseable_document, is_signature_document
from .storage import ResultStorage


class TenderProcessor:
    def __init__(
        self,
        settings: Settings,
        client: ProzorroClient | None = None,
        storage: ResultStorage | None = None,
        parser: DocumentParser | None = None,
        analyzer: TenderAnalyzer | None = None,
    ):
        self.settings = settings
        self.client = client or ProzorroClient(settings)
        self.storage = storage or ResultStorage(settings.db_path)
        self.parser = parser or DocumentParser(settings)
        self.analyzer = analyzer or TenderAnalyzer()

    def process_tender(
        self,
        tender_id: str,
        use_codex: bool = False,
        refresh: bool = False,
    ) -> TenderResult:
        tender = self.client.get_tender(tender_id, refresh=refresh)
        return self.process_tender_payload(tender, use_codex=use_codex)

    def process_tender_payload(self, tender: dict[str, Any], use_codex: bool = False) -> TenderResult:
        summary = self.client.build_summary(tender)
        documents = self.client.collect_documents(tender)
        parsed_documents: list[ParsedDocument] = []
        limitations: list[str] = []

        if not documents:
            limitations.append("У тендері не знайдено публічних документів для аналізу.")

        for document in documents:
            if not is_parseable_document(document):
                if is_signature_document(document):
                    document.status = "підпис, пропущено"
                    document.limitation = None
                else:
                    document.status = "не підтримується"
                    document.limitation = (
                        "Документ має формат, який MVP не аналізує автоматично; потрібна ручна перевірка."
                    )
                parsed_documents.append(ParsedDocument(document=document, text=""))
                continue

            document = self.client.download_document(summary.tender_id, document)
            document, text = self.parser.parse(document)
            if document.limitation:
                limitations.append(f"{document.title}: {document.limitation}")
            parsed_documents.append(ParsedDocument(document=document, text=text))

        if not any(parsed.text for parsed in parsed_documents):
            metadata_text = metadata_fallback_text(tender)
            if metadata_text:
                fallback_doc = DocumentResult(
                    id="metadata",
                    title="Метадані тендера Prozorro",
                    format="application/json",
                    url="",
                    status="опрацьовано",
                    parsed_chars=len(metadata_text),
                )
                parsed_documents.append(
                    ParsedDocument(
                        document=fallback_doc,
                        text=metadata_text,
                    )
                )

        issues, subscores, overall_score = self.analyzer.analyze(parsed_documents)
        llm_engine = "детерміновані правила"
        llm_usage = LlmUsage(
            model=self.settings.codex_cost_model,
            input_usd_per_million=self.settings.codex_input_usd_per_million,
            cached_input_usd_per_million=self.settings.codex_cached_input_usd_per_million,
            output_usd_per_million=self.settings.codex_output_usd_per_million,
        )
        if use_codex:
            issues, codex_limitation, llm_usage = CodexEngine(self.settings).enrich(issues)
            llm_engine = "Codex + детерміновані правила"
            if codex_limitation:
                limitations.append(codex_limitation)

        result = TenderResult(
            summary=summary,
            processed_at=datetime.now(timezone.utc).isoformat(),
            overall_score=overall_score,
            subscores=subscores,
            issues=issues,
            documents=[parsed.document for parsed in parsed_documents],
            limitations=dedupe_strings(limitations),
            llm_engine=llm_engine,
            llm_usage=llm_usage,
        )
        self.storage.save(result)
        return result

    def process_batch(
        self,
        batch_size: int,
        max_pages: int,
        use_codex: bool = False,
        refresh: bool = False,
    ) -> list[TenderResult]:
        processed_ids = self.storage.processed_ids()
        tenders = self.client.select_recent_tenders(
            processed_ids=processed_ids,
            batch_size=batch_size,
            max_pages=max_pages,
        )
        results: list[TenderResult] = []
        for tender in tenders:
            if refresh:
                tender = self.client.get_tender(tender["id"], refresh=True)
            results.append(self.process_tender_payload(tender, use_codex=use_codex))
        return results


def metadata_fallback_text(tender: dict[str, Any]) -> str:
    parts = [
        tender.get("title", ""),
        tender.get("description", ""),
        " ".join(item.get("description", "") for item in tender.get("items", []) or []),
    ]
    return "\n".join(part for part in parts if part)


def dedupe_strings(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result
