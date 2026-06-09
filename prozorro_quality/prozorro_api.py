from __future__ import annotations

import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

from .config import Settings
from .models import DocumentResult, TenderSummary


CPV_SECTORS = {
    "03": "Сільське господарство та продукти",
    "09": "Нафтопродукти, паливо, електроенергія",
    "15": "Харчові продукти",
    "18": "Одяг та взуття",
    "22": "Друкована продукція",
    "24": "Хімічна продукція",
    "30": "Офісна та комп'ютерна техніка",
    "31": "Електричні машини",
    "32": "Радіо-, теле-, комунікаційне обладнання",
    "33": "Медичне обладнання та фармацевтика",
    "34": "Транспортне обладнання",
    "35": "Охоронне та пожежне обладнання",
    "37": "Музичні інструменти, спорттовари та ігри",
    "39": "Меблі та побутова продукція",
    "42": "Промислова техніка",
    "44": "Будівельні матеріали",
    "45": "Будівельні роботи",
    "48": "Програмне забезпечення",
    "50": "Ремонт і технічне обслуговування",
    "51": "Послуги зі встановлення",
    "55": "Готельні та ресторанні послуги",
    "60": "Транспортні послуги",
    "63": "Допоміжні транспортні послуги",
    "64": "Поштові та телекомунікаційні послуги",
    "65": "Комунальні послуги",
    "66": "Фінансові та страхові послуги",
    "70": "Нерухомість",
    "71": "Архітектурні та інженерні послуги",
    "72": "ІТ-послуги",
    "73": "Дослідження та розробки",
    "75": "Адміністративні послуги",
    "77": "Сільськогосподарські та лісові послуги",
    "79": "Ділові послуги",
    "80": "Освітні послуги",
    "85": "Охорона здоров'я та соціальні послуги",
    "90": "Екологічні послуги",
    "92": "Культурні та спортивні послуги",
    "98": "Інші послуги",
}


PARSEABLE_FORMAT_HINTS = (
    "pdf",
    "word",
    "document",
    "msword",
    "rtf",
    "text",
    "html",
    "spreadsheet",
    "excel",
    "sheet",
    "csv",
)


class ProzorroClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.session = requests.Session()
        self.metadata_dir = settings.cache_dir / "metadata"
        self.documents_dir = settings.cache_dir / "documents"
        self.metadata_dir.mkdir(parents=True, exist_ok=True)
        self.documents_dir.mkdir(parents=True, exist_ok=True)

    def _get_json(self, url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                response = self.session.get(url, params=params, timeout=self.settings.request_timeout)
                response.raise_for_status()
                return response.json()
            except Exception as exc:
                last_error = exc
                time.sleep(0.4 * (attempt + 1))
        assert last_error is not None
        raise last_error

    def list_page(self, url: str | None = None, limit: int = 100) -> dict[str, Any]:
        if url:
            return self._get_json(url)
        return self._get_json(
            f"{self.settings.api_base_url}/tenders",
            params={
                "limit": limit,
                "descending": 1,
                "opt_fields": "tenderID,procurementMethodType,procuringEntity",
            },
        )

    def get_tender(self, tender_id: str, refresh: bool = False) -> dict[str, Any]:
        cache_path = self.metadata_dir / f"{tender_id}.json"
        if cache_path.exists() and not refresh:
            return json.loads(cache_path.read_text(encoding="utf-8"))

        payload = self._get_json(f"{self.settings.api_base_url}/tenders/{tender_id}")
        data = payload.get("data", payload)
        cache_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return data

    def build_summary(self, tender: dict[str, Any]) -> TenderSummary:
        buyer = tender.get("procuringEntity") or tender.get("buyer") or {}
        value = tender.get("value") or {}
        cpv = extract_cpv(tender)
        return TenderSummary(
            tender_id=tender.get("id", ""),
            tender_code=tender.get("tenderID", tender.get("id", "")),
            title=clean_space(tender.get("title", "Без назви")),
            buyer_name=clean_space(buyer.get("name", "Невідомий замовник")),
            value_amount=coerce_float(value.get("amount")),
            currency=value.get("currency"),
            cpv=cpv,
            sector=sector_from_cpv(cpv),
            procurement_method_type=tender.get("procurementMethodType"),
            date_modified=tender.get("dateModified"),
        )

    def collect_documents(self, tender: dict[str, Any]) -> list[DocumentResult]:
        docs: list[dict[str, Any]] = []
        seen: set[str] = set()

        def add_many(items: Any) -> None:
            if not isinstance(items, list):
                return
            for doc in items:
                if not isinstance(doc, dict):
                    continue
                doc_id = str(doc.get("id") or doc.get("url") or doc.get("title") or "")
                if not doc_id or doc_id in seen:
                    continue
                if not doc.get("url"):
                    continue
                seen.add(doc_id)
                docs.append(doc)

        add_many(tender.get("documents"))
        for key in ("lots", "items"):
            for item in tender.get(key, []) or []:
                add_many(item.get("documents"))

        results: list[DocumentResult] = []
        for doc in docs[: self.settings.documents_per_tender]:
            results.append(
                DocumentResult(
                    id=str(doc.get("id") or ""),
                    title=clean_space(doc.get("title") or "Документ без назви"),
                    format=clean_space(doc.get("format") or ""),
                    url=str(doc.get("url") or ""),
                )
            )
        return results

    def is_usable_tender(self, tender: dict[str, Any], processed_ids: set[str]) -> bool:
        if tender.get("id") in processed_ids:
            return False
        value = tender.get("value") or {}
        amount = coerce_float(value.get("amount"))
        if value.get("currency") != "UAH" or amount is None:
            return False
        if not (self.settings.min_value <= amount <= self.settings.max_value):
            return False
        documents = self.collect_documents(tender)
        return any(is_parseable_document(doc) for doc in documents)

    def select_recent_tenders(
        self,
        processed_ids: set[str],
        batch_size: int,
        max_pages: int,
        page_limit: int = 100,
    ) -> list[dict[str, Any]]:
        selected: list[dict[str, Any]] = []
        overflow: list[dict[str, Any]] = []
        sector_counts: dict[str, int] = {}
        next_url: str | None = None

        for _page in range(max_pages):
            page = self.list_page(next_url, limit=page_limit)
            candidates = [
                item.get("id")
                for item in page.get("data", [])
                if item.get("id")
                and item.get("id") not in processed_ids
                and item.get("procurementMethodType") != "reporting"
            ]
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = {executor.submit(self.get_tender, tender_id): tender_id for tender_id in candidates}
                for future in as_completed(futures):
                    try:
                        tender = future.result()
                    except Exception:
                        continue
                    if not self.is_usable_tender(tender, processed_ids):
                        continue
                    sector = sector_from_cpv(extract_cpv(tender))
                    if sector_counts.get(sector, 0) < 2:
                        selected.append(tender)
                        sector_counts[sector] = sector_counts.get(sector, 0) + 1
                    else:
                        overflow.append(tender)
                    if len(selected) >= batch_size:
                        return selected
            next_url = (page.get("next_page") or {}).get("uri")
            if not next_url:
                break

        for tender in overflow:
            if len(selected) >= batch_size:
                break
            selected.append(tender)
        return selected

    def download_document(self, tender_id: str, document: DocumentResult) -> DocumentResult:
        tender_dir = self.documents_dir / tender_id
        tender_dir.mkdir(parents=True, exist_ok=True)
        suffix = suffix_for_document(document)
        safe_name = safe_filename(f"{document.id or document.title}{suffix}")
        path = tender_dir / safe_name
        if path.exists() and path.stat().st_size > 0:
            document.local_path = str(path)
            return document

        if not document.url:
            document.status = "не завантажено"
            document.limitation = "Документ не має публічного URL."
            return document

        try:
            with self.session.get(
                document.url,
                timeout=self.settings.request_timeout,
                stream=True,
            ) as response:
                response.raise_for_status()
                total = 0
                with path.open("wb") as fh:
                    for chunk in response.iter_content(chunk_size=64 * 1024):
                        if not chunk:
                            continue
                        total += len(chunk)
                        if total > self.settings.max_document_bytes:
                            document.status = "обмежено"
                            document.limitation = (
                                "Документ завеликий для MVP-аналізу; потрібна ручна перевірка."
                            )
                            break
                        fh.write(chunk)
            if path.exists() and path.stat().st_size > 0 and not document.limitation:
                document.local_path = str(path)
            return document
        except Exception as exc:
            document.status = "помилка завантаження"
            document.limitation = f"Не вдалося завантажити документ: {exc}"
            return document


def clean_space(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def coerce_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def extract_cpv(tender: dict[str, Any]) -> str | None:
    for item in tender.get("items", []) or []:
        classification = item.get("classification") or {}
        if classification.get("id"):
            return str(classification["id"])
    classification = tender.get("classification") or {}
    if classification.get("id"):
        return str(classification["id"])
    return None


def sector_from_cpv(cpv: str | None) -> str:
    if not cpv:
        return "Сектор не визначено"
    return CPV_SECTORS.get(cpv[:2], f"CPV {cpv[:2]}")


def is_parseable_document(document: DocumentResult) -> bool:
    text = f"{document.title} {document.format}".lower()
    if is_signature_document(document):
        return False
    return any(hint in text for hint in PARSEABLE_FORMAT_HINTS)


def is_signature_document(document: DocumentResult) -> bool:
    text = f"{document.title} {document.format}".lower()
    return "pkcs7" in text or text.endswith(".p7s") or "signature" in text or "sign.p7s" in text


def suffix_for_document(document: DocumentResult) -> str:
    title = document.title.lower()
    parsed = urlparse(document.url)
    url_path = Path(parsed.path)
    for source in (title, url_path.name.lower(), document.format.lower()):
        for suffix in (".docx", ".doc", ".pdf", ".xlsx", ".xls", ".csv", ".txt", ".html", ".htm", ".rtf"):
            if suffix in source:
                return suffix
    fmt = document.format.lower()
    if "pdf" in fmt:
        return ".pdf"
    if "wordprocessingml" in fmt:
        return ".docx"
    if "msword" in fmt:
        return ".doc"
    if "spreadsheetml" in fmt or "excel" in fmt:
        return ".xlsx"
    if "html" in fmt:
        return ".html"
    if "rtf" in fmt:
        return ".rtf"
    if "csv" in fmt:
        return ".csv"
    return ".bin"


def safe_filename(value: str) -> str:
    value = re.sub(r"[^\w.\-а-яА-ЯіїєґІЇЄҐ]+", "_", value, flags=re.UNICODE)
    return value.strip("._")[:180] or "document.bin"
