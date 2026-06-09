from prozorro_quality.config import Settings
from prozorro_quality.models import DocumentResult
from prozorro_quality.prozorro_api import ProzorroClient, suffix_for_document


def tender(tender_id, amount, cpv="30200000-1", docs=True):
    return {
        "id": tender_id,
        "tenderID": f"UA-{tender_id}",
        "title": "Тест",
        "value": {"amount": amount, "currency": "UAH"},
        "items": [{"classification": {"id": cpv}}],
        "documents": [
            {
                "id": f"doc-{tender_id}",
                "title": "Тендерна документація.docx",
                "format": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "url": "https://example.test/doc",
            }
        ]
        if docs
        else [],
    }


class FakeClient(ProzorroClient):
    def __init__(self, settings, tenders):
        super().__init__(settings)
        self.tenders = {item["id"]: item for item in tenders}
        self.pages = [{"data": [{"id": item["id"]} for item in tenders], "next_page": {}}]

    def list_page(self, url=None, limit=100):
        return self.pages[0]

    def get_tender(self, tender_id, refresh=False):
        return self.tenders[tender_id]


def test_select_recent_tenders_filters_value_docs_and_processed(tmp_path):
    settings = Settings(data_dir=tmp_path)
    items = [
        tender("old", 2_000_000),
        tender("too-small", 50_000),
        tender("no-docs", 2_000_000, docs=False),
        tender("ok", 3_000_000, cpv="33100000-1"),
    ]
    client = FakeClient(settings, items)

    selected = client.select_recent_tenders(processed_ids={"old"}, batch_size=5, max_pages=1)

    assert [item["id"] for item in selected] == ["ok"]


def test_collect_documents_skips_audit_yaml_and_suffix_uses_final_extension(tmp_path):
    settings = Settings(data_dir=tmp_path)
    client = ProzorroClient(settings)
    payload = tender("ok", 3_000_000)
    payload["documents"].append(
        {
            "id": "audit",
            "title": "audit_abc.yaml",
            "format": "application/x-yaml",
            "url": "https://example.test/audit.yaml",
        }
    )

    docs = client.collect_documents(payload)

    assert [doc.id for doc in docs] == ["doc-ok"]
    assert (
        suffix_for_document(
            DocumentResult(
                id="pdf",
                title="Додаток 1 - Технічна специфікація.docx.pdf",
                format="application/pdf",
                url="https://example.test/download",
            )
        )
        == ".pdf"
    )
