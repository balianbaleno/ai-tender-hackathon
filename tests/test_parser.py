import zipfile

from prozorro_quality.config import Settings
from prozorro_quality.models import DocumentResult
from prozorro_quality.parser import DocumentParser


def test_zip_parser_extracts_supported_members(tmp_path):
    archive_path = tmp_path / "docs.zip"
    tender_text = "Тендерна документація. " + "Оплата протягом 15 днів. " * 20
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("td.txt", tender_text)
        archive.writestr("audit.yaml", "service metadata")

    document = DocumentResult(
        id="zip",
        title="Тендерна документація.docx.zip",
        format="application/zip",
        url="",
        local_path=str(archive_path),
    )

    parsed, text = DocumentParser(Settings(data_dir=tmp_path)).parse(document)

    assert parsed.status == "опрацьовано"
    assert "Документ в архіві: td.txt" in text
    assert "Оплата протягом 15 днів" in text
    assert "service metadata" not in text
