from prozorro_quality.analyzer import ParsedDocument, TenderAnalyzer
from prozorro_quality.models import DocumentResult


def doc(text: str) -> ParsedDocument:
    return ParsedDocument(
        document=DocumentResult(
            id="doc1",
            title="Тендерна документація.docx",
            format="docx",
            url="",
            status="опрацьовано",
            parsed_chars=len(text),
        ),
        text=text,
    )


def test_detects_brand_and_authorization_without_legal_claims():
    text = """
    Учасник повинен поставити ноутбук Lenovo ThinkPad модель T14.
    Також надається авторизаційний лист від виробника.
    Строк поставки 10 днів. Оплата протягом 15 банківських днів.
    Проєкт договору містить відповідальність сторін та порядок розірвання.
    """
    issues, subscores, overall = TenderAnalyzer().analyze([doc(text)])
    categories = {issue.category for issue in issues}

    assert "бренд/модель без «або еквівалент»" in categories
    assert "лист виробника" in categories
    assert overall < 100
    assert subscores["конкурентність"] < 100
    combined = " ".join(issue.explanation for issue in issues)
    assert "порушення" not in combined.lower()


def test_equivalent_phrase_reduces_brand_false_positive():
    text = """
    Поставка принтера Canon або еквівалент із ресурсом картриджа не менше 3000 сторінок.
    Фарба Farbmann або аналог, шпаклівка Knauf або аналог.
    Строк поставки 10 днів. Оплата протягом 15 банківських днів.
    Проєкт договору містить відповідальність сторін та порядок розірвання.
    """
    issues, _, _ = TenderAnalyzer().analyze([doc(text)])

    assert "бренд/модель без «або еквівалент»" not in {issue.category for issue in issues}


def test_office_format_and_contact_info_are_not_restrictive_findings():
    text = """
    Файл «Сітка розцінок.xlsx» сумісний з Microsoft Excel 2007 або іншим програмним забезпеченням.
    Довідка містить відомості про учасника: місцезнаходження учасника, телефон, електронна адреса,
    банківські реквізити. Строк поставки 10 днів. Оплата протягом 15 банківських днів.
    Проєкт договору містить відповідальність сторін та порядок розірвання.
    """
    issues, _, _ = TenderAnalyzer().analyze([doc(text)])
    categories = {issue.category for issue in issues}

    assert "бренд/модель без «або еквівалент»" not in categories
    assert "географічне обмеження" not in categories


def test_arma_notary_context_is_not_excessive_document_finding():
    text = """
    Учасник може надати ухвалу суду про передачу активів в управління Національному агентству
    з питань виявлення, розшуку та управління активами або згоду власника активів,
    підпис якої нотаріально завірений. Строк поставки 10 днів. Оплата протягом 15 днів.
    Проєкт договору містить відповідальність сторін та порядок розірвання.
    """
    issues, _, _ = TenderAnalyzer().analyze([doc(text)])

    assert "документальні вимоги" not in {issue.category for issue in issues}


def test_missing_contract_affects_contract_subscore():
    text = "Оплата протягом 10 днів. Поставка за адресою замовника протягом 5 днів."
    issues, subscores, overall = TenderAnalyzer().analyze([doc(text)])

    assert any(issue.category == "проєкт договору" for issue in issues)
    assert subscores["якість проєкту договору"] < 100
    assert overall < 100
