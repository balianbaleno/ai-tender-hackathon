from prozorro_quality.models import Issue, TenderResult, TenderSummary
from prozorro_quality.storage import ResultStorage


def sample_result() -> TenderResult:
    return TenderResult(
        summary=TenderSummary(
            tender_id="abc",
            tender_code="UA-TEST",
            title="Тестовий тендер",
            buyer_name="Замовник",
            value_amount=1_500_000,
            currency="UAH",
            cpv="30200000-1",
            sector="Офісна та комп'ютерна техніка",
            procurement_method_type="aboveThreshold",
            date_modified="2026-06-09T00:00:00+03:00",
        ),
        processed_at="2026-06-09T01:00:00+00:00",
        overall_score=82,
        subscores={
            "повнота": 90,
            "зрозумілість": 90,
            "конкурентність": 80,
            "технічна нейтральність": 70,
            "якість проєкту договору": 90,
        },
        issues=[
            Issue(
                category="бренд/модель",
                title="Можлива прив'язка",
                severity="висока",
                evidence_quote="Lenovo",
                explanation="Потенційний ризик.",
                suggested_rewrite="Додайте або еквівалент.",
            )
        ],
    )


def test_storage_roundtrip(tmp_path):
    storage = ResultStorage(tmp_path / "db.sqlite3")
    result = sample_result()

    storage.save(result)
    loaded = storage.get("abc")

    assert loaded is not None
    assert loaded.summary.tender_code == "UA-TEST"
    assert loaded.highest_severity == "висока"
    assert storage.has_tender("abc")
    assert storage.aggregate()["total"] == 1

