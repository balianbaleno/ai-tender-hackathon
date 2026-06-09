from __future__ import annotations

import re
from dataclasses import dataclass

from .models import DocumentResult, Issue


SUBSCORE_NAMES = [
    "повнота",
    "зрозумілість",
    "конкурентність",
    "технічна нейтральність",
    "якість проєкту договору",
]


@dataclass(frozen=True)
class ParsedDocument:
    document: DocumentResult
    text: str


@dataclass(frozen=True)
class Rule:
    category: str
    title: str
    severity: str
    pattern: re.Pattern[str]
    explanation: str
    suggested_rewrite: str
    subscores: tuple[str, ...]


RULES = [
    Rule(
        category="бренд/модель без «або еквівалент»",
        title="Можлива прив'язка до бренду або моделі без еквіваленту",
        severity="висока",
        pattern=re.compile(
            r"(?i:\b(?:hp|hewlett|canon|epson|xerox|samsung|lenovo|dell|apple|bosch|makita|cisco|intel|amd|microsoft)\b)|"
            r"(?i:(?:модель|model)\s+)[A-Z0-9][A-Za-z0-9\-_/]{2,}|"
            r"(?i:(?:торговельна|торгова)\s+марка\s+)[A-ZА-ЯІЇЄҐ0-9][A-Za-zА-Яа-яІіЇїЄєҐґ0-9\-_/]{2,}",
            re.UNICODE,
        ),
        explanation=(
            "Формулювання може обмежувати конкуренцію, якщо конкретний бренд або модель "
            "використані без функціонального опису і без можливості еквіваленту."
        ),
        suggested_rewrite=(
            "Опишіть функціональні та технічні характеристики предмета закупівлі і додайте "
            "формулювання «або еквівалент» для сумісних рішень."
        ),
        subscores=("конкурентність", "технічна нейтральність"),
    ),
    Rule(
        category="лист виробника",
        title="Залежність від листа виробника або авторизованого партнера",
        severity="висока",
        pattern=re.compile(
            r"(?:авторизаційн(?:ий|ого)\s+лист|лист(?:а)?\s+(?:від\s+)?виробника|лист(?:а)?\s+(?:від\s+)?офіційн(?:ого|им)\s+дистриб|"
            r"сертифікат\s+партнера|статус\s+авторизованого\s+партнера)",
            re.IGNORECASE | re.UNICODE,
        ),
        explanation=(
            "Вимога може створювати потенційний ризик залежності учасника від виробника "
            "або дистриб'ютора і потребує перевірки людиною."
        ),
        suggested_rewrite=(
            "Замініть вимогу листа виробника на підтвердження законного походження товару, "
            "гарантійних зобов'язань і можливості постачання без прив'язки до конкретного каналу."
        ),
        subscores=("конкурентність",),
    ),
    Rule(
        category="географічне обмеження",
        title="Можливе географічне обмеження для учасників",
        severity="середня",
        pattern=re.compile(
            r"(?:наявн(?:ість|ий)\s+(?:склад|офіс|сервісн(?:ий|ого)\s+центр)|місцезнаходження\s+учасника|"
            r"розташован(?:ий|ого)\s+у\s+(?:м\.|місті|області)|на\s+території\s+(?:міста|області))",
            re.IGNORECASE | re.UNICODE,
        ),
        explanation=(
            "Локальна вимога може обмежувати конкуренцію, якщо вона не обґрунтована предметом закупівлі "
            "або строками виконання."
        ),
        suggested_rewrite=(
            "Сформулюйте вимогу через строк реагування, строк доставки або рівень сервісу, "
            "не вимагаючи постійного місцезнаходження в конкретному населеному пункті."
        ),
        subscores=("конкурентність",),
    ),
    Rule(
        category="нечітка вимога",
        title="Нечітке або оціночне формулювання",
        severity="середня",
        pattern=re.compile(
            r"(?:висок(?:а|ої)\s+якість|\bналежн(?:а|ої)\s+якість|найкращ(?:ий|а)|за\s+першою\s+вимогою|"
            r"у\s+найкоротш(?:ий|і)\s+строк|повністю\s+відповідати\s+вимогам\s+замовника)",
            re.IGNORECASE | re.UNICODE,
        ),
        explanation=(
            "Оціночне формулювання ускладнює однакове розуміння вимоги учасниками та замовником."
        ),
        suggested_rewrite=(
            "Задайте вимірюваний критерій: числовий показник, стандарт, граничне значення, "
            "строк або перелік документів для підтвердження."
        ),
        subscores=("зрозумілість",),
    ),
    Rule(
        category="кваліфікаційні вимоги",
        title="Можливо надмірна кваліфікаційна вимога",
        severity="середня",
        pattern=re.compile(
            r"(?:досвід\s+роботи\s+не\s+менше\s+[3-9]|не\s+менше\s+[3-9]\s+(?:рок|аналогічн)|"
            r"(?:аналогічн(?:их|ого)\s+договор(?:ів|у)).{0,80}(?:не\s+менше\s+[3-9]|за\s+останні\s+[5-9]))",
            re.IGNORECASE | re.UNICODE | re.DOTALL,
        ),
        explanation=(
            "Вимога може бути надмірною для частини учасників, якщо кількість договорів або років "
            "не пов'язана прямо з предметом закупівлі."
        ),
        suggested_rewrite=(
            "Залиште пропорційне підтвердження досвіду, наприклад один релевантний договір "
            "або інший документ, який показує спроможність виконати закупівлю."
        ),
        subscores=("конкурентність", "повнота"),
    ),
    Rule(
        category="документальні вимоги",
        title="Можливо надмірна документальна вимога",
        severity="середня",
        pattern=re.compile(
            r"(?:нотаріально\s+завірен|оригінал(?:и)?\s+усіх|усі\s+сторінки\s+паспорта|"
            r"довідк(?:а|и)\s+у\s+довільній\s+формі.{0,80}довідк(?:а|и)\s+у\s+довільній\s+формі)",
            re.IGNORECASE | re.UNICODE | re.DOTALL,
        ),
        explanation=(
            "Надмірний перелік або форма документів може ускладнювати участь без очевидної користі "
            "для оцінки пропозиції."
        ),
        suggested_rewrite=(
            "Залиште лише документи, які прямо підтверджують вимоги закупівлі, і дозволяйте "
            "електронні копії, якщо оригінал не є необхідним."
        ),
        subscores=("повнота", "конкурентність"),
    ),
    Rule(
        category="умови оплати/поставки",
        title="Нечіткі умови поставки або оплати",
        severity="середня",
        pattern=re.compile(
            r"(?:строк\s+поставки\s*[:\-]?\s*(?:за\s+заявк|протягом\s+невизначен)|"
            r"оплата\s+здійснюється\s+за\s+наявності\s+фінансування|умови\s+оплати\s+уточнюються)",
            re.IGNORECASE | re.UNICODE,
        ),
        explanation=(
            "Нечіткі строки або умови оплати можуть впливати на ціну пропозицій і потребують "
            "уточнення перед поданням."
        ),
        suggested_rewrite=(
            "Вкажіть конкретний строк поставки, місце поставки, порядок приймання, строк оплати "
            "та умови відстрочки або авансу."
        ),
        subscores=("повнота", "зрозумілість", "якість проєкту договору"),
    ),
]


EQUIVALENT_RE = re.compile(r"або\s+еквівалент|чи\s+еквівалент|еквівалентн|або\s+аналог|чи\s+аналог", re.IGNORECASE)
PAYMENT_RE = re.compile(r"оплат|післяоплат|аванс|розрахунк", re.IGNORECASE)
DELIVERY_RE = re.compile(r"поставк|доставк|місце\s+передач|строк\s+виконан", re.IGNORECASE)
CONTRACT_RE = re.compile(r"догов|проєкт\s+договор|проект\s+договор", re.IGNORECASE)
CONTRACT_TERMS_RE = re.compile(r"відповідальн|штраф|пеня|неустойк|розірван|зміни\s+до\s+договор", re.IGNORECASE)
SIGNATURE_RE = re.compile(r"pkcs7|sign\.p7s|signature|електронн(?:ий|ого)\s+підпис", re.IGNORECASE)
GENERIC_PRODUCER_RE = re.compile(
    r"учасник.{0,100}(?:зазнач|пропону)|змінив\s+предмет.{0,100}(?:марк|модел)",
    re.IGNORECASE | re.DOTALL,
)
OCCUPIED_TERRITORY_RE = re.compile(r"окупован|російськ|білорус|іран|перелік(?:у)?\s+територ", re.IGNORECASE)
FORMAT_CONTEXT_RE = re.compile(r"формат.{0,80}(?:microsoft\s+excel|doc|xls|xlsx|pdf|jpeg|jpg)", re.IGNORECASE)
OFFICE_SOFTWARE_CONTEXT_RE = re.compile(
    r"(?:microsoft\s+excel|excel\s+2007).{0,120}(?:іншим\s+програмним|підтримує\s+даний\s+формат)|"
    r"(?:файл|формат|таблиц|сумісн).{0,120}(?:microsoft\s+excel|excel\s+2007)",
    re.IGNORECASE | re.DOTALL,
)
COMPATIBILITY_LIST_RE = re.compile(
    r"(?:ATF|SAE|ACEA|API|OEM|допуск|сумісн|специфікац).{0,500}(?:/|,).{0,500}(?:/|,).{0,500}(?:/|,)",
    re.IGNORECASE | re.DOTALL,
)
CONTACT_INFO_RE = re.compile(
    r"відомості\s+про\s+учасника|банківські\s+реквізити|телефон|електронн(?:а|ої)\s+адрес",
    re.IGNORECASE,
)
ARMA_CONTEXT_RE = re.compile(
    r"Національн(?:ому|ого)\s+агентств.{0,120}(?:розшуку|актив)",
    re.IGNORECASE | re.DOTALL,
)


class TenderAnalyzer:
    def analyze(self, parsed_documents: list[ParsedDocument]) -> tuple[list[Issue], dict[str, int], int]:
        issues: list[Issue] = []
        seen: set[tuple[str, str]] = set()

        for parsed in parsed_documents:
            text = parsed.text
            for rule in RULES:
                for match in rule.pattern.finditer(text):
                    quote = evidence_window(text, match.start(), match.end())
                    key = (rule.category, quote.lower())
                    if key in seen:
                        continue
                    if should_skip_match(rule.category, quote):
                        continue
                    seen.add(key)
                    issues.append(
                        Issue(
                            category=rule.category,
                            title=rule.title,
                            severity=rule.severity,
                            evidence_quote=quote,
                            explanation=rule.explanation,
                            suggested_rewrite=rule.suggested_rewrite,
                            document_title=parsed.document.title,
                            document_id=parsed.document.id,
                        )
                    )
                    break

        all_text = "\n".join(parsed.text for parsed in parsed_documents)
        issues.extend(missing_context_issues(parsed_documents, all_text))
        issues.extend(parsing_issues(parsed_documents))
        subscores, overall = score_issues(issues)
        return dedupe_issues(issues), subscores, overall


def missing_context_issues(parsed_documents: list[ParsedDocument], all_text: str) -> list[Issue]:
    issues: list[Issue] = []
    if all_text and not PAYMENT_RE.search(all_text):
        issues.append(
            Issue(
                category="умови оплати/поставки",
                title="Не знайдено чітких умов оплати",
                severity="низька",
                evidence_quote="У витягнутому тексті не знайдено явного опису оплати або розрахунків.",
                explanation=(
                    "Це можлива проблема повноти: учаснику складно оцінити фінансові умови без "
                    "строку та порядку оплати."
                ),
                suggested_rewrite=(
                    "Додайте порядок розрахунків: тип оплати, строк після приймання, умови авансу "
                    "або відстрочки та документи для оплати."
                ),
            )
        )
    if all_text and not DELIVERY_RE.search(all_text):
        issues.append(
            Issue(
                category="умови оплати/поставки",
                title="Не знайдено чітких умов поставки або виконання",
                severity="низька",
                evidence_quote="У витягнутому тексті не знайдено явного опису поставки, доставки або строку виконання.",
                explanation=(
                    "Це можлива проблема повноти: без строку та місця виконання учасники можуть "
                    "по-різному оцінювати витрати."
                ),
                suggested_rewrite=(
                    "Додайте місце, строк, графік поставки або виконання, порядок приймання та "
                    "відповідальну контактну точку."
                ),
            )
        )
    contract_docs = [
        parsed for parsed in parsed_documents if CONTRACT_RE.search(parsed.document.title) or CONTRACT_RE.search(parsed.text[:2000])
    ]
    if not contract_docs:
        issues.append(
            Issue(
                category="проєкт договору",
                title="Не знайдено проєкт договору серед опрацьованих документів",
                severity="середня",
                evidence_quote="Серед назв та текстів опрацьованих документів MVP не знайшов явного проєкту договору.",
                explanation=(
                    "Відсутній або неідентифікований проєкт договору послаблює прозорість майбутніх "
                    "зобов'язань і потребує перевірки людиною."
                ),
                suggested_rewrite=(
                    "Додайте окремий проєкт договору з умовами предмета, ціни, поставки, оплати, "
                    "відповідальності, зміни та розірвання."
                ),
            )
        )
    elif not any(CONTRACT_TERMS_RE.search(parsed.text) for parsed in contract_docs):
        issues.append(
            Issue(
                category="проєкт договору",
                title="У проєкті договору не знайдено ключових умов відповідальності",
                severity="низька",
                evidence_quote="В опрацьованому проєкті договору не знайдено слів про відповідальність, штраф, пеню, розірвання або зміни договору.",
                explanation=(
                    "Це можлива проблема якості проєкту договору: ключові умови можуть бути неповними "
                    "або сформульованими в іншому документі."
                ),
                suggested_rewrite=(
                    "Перевірте та явно опишіть відповідальність сторін, штрафні санкції, порядок зміни "
                    "та розірвання договору."
                ),
            )
        )
    return issues


def parsing_issues(parsed_documents: list[ParsedDocument]) -> list[Issue]:
    issues: list[Issue] = []
    for parsed in parsed_documents:
        doc = parsed.document
        if SIGNATURE_RE.search(f"{doc.title} {doc.format}"):
            continue
        if doc.status in {"мало тексту", "не підтримується", "помилка парсингу", "обмежено"}:
            issues.append(
                Issue(
                    category="складність документів",
                    title="Документ складний для автоматичного аналізу",
                    severity="низька" if doc.status == "мало тексту" else "середня",
                    evidence_quote=doc.limitation or f"Статус документа: {doc.status}.",
                    explanation=(
                        "Сканований, застарілий або непідтримуваний формат знижує прозорість аналізу "
                        "і потребує перевірки людиною."
                    ),
                    suggested_rewrite=(
                        "Надавайте тендерну документацію у текстових PDF, DOCX або XLSX із доступним "
                        "для копіювання текстом."
                    ),
                    document_title=doc.title,
                    document_id=doc.id,
                )
            )
    return issues


def should_skip_match(category: str, quote: str) -> bool:
    if category == "бренд/модель без «або еквівалент»":
        if EQUIVALENT_RE.search(quote):
            return True
        if GENERIC_PRODUCER_RE.search(quote):
            return True
        if FORMAT_CONTEXT_RE.search(quote):
            return True
        if OFFICE_SOFTWARE_CONTEXT_RE.search(quote):
            return True
        if COMPATIBILITY_LIST_RE.search(quote):
            return True
    if category == "географічне обмеження":
        if OCCUPIED_TERRITORY_RE.search(quote):
            return True
        if CONTACT_INFO_RE.search(quote):
            return True
        if "на всій території України" in quote:
            return True
    if category == "документальні вимоги" and ARMA_CONTEXT_RE.search(quote):
        return True
    if category == "нечітка вимога" and "неналежн" in quote.lower():
        return True
    return False


def score_issues(issues: list[Issue]) -> tuple[dict[str, int], int]:
    subscores = {name: 100 for name in SUBSCORE_NAMES}
    category_to_subscores = {
        rule.category: rule.subscores for rule in RULES
    }
    category_to_subscores.update(
        {
            "проєкт договору": ("якість проєкту договору", "повнота"),
            "складність документів": ("повнота", "зрозумілість"),
            "умови оплати/поставки": ("повнота", "зрозумілість", "якість проєкту договору"),
            "бренд/модель без «або еквівалент»": ("конкурентність", "технічна нейтральність"),
        }
    )
    severity_penalty = {"висока": 14, "середня": 8, "низька": 4}
    overall = 100
    for issue in issues:
        penalty = severity_penalty.get(issue.severity, 4)
        overall -= penalty
        for subscore in category_to_subscores.get(issue.category, ("повнота",)):
            subscores[subscore] = max(0, subscores[subscore] - penalty)
    overall = max(0, min(100, overall))
    subscores = {name: max(0, min(100, value)) for name, value in subscores.items()}
    if issues:
        blended = round((overall * 0.6) + (sum(subscores.values()) / len(subscores) * 0.4))
        overall = max(0, min(100, blended))
    return subscores, overall


def evidence_window(text: str, start: int, end: int, radius: int = 240) -> str:
    left = max(0, start - radius)
    right = min(len(text), end + radius)
    snippet = text[left:right].replace("\n", " ")
    snippet = re.sub(r"\s+", " ", snippet).strip()
    if left:
        snippet = "..." + snippet
    if right < len(text):
        snippet += "..."
    return snippet[:700]


def dedupe_issues(issues: list[Issue]) -> list[Issue]:
    result: list[Issue] = []
    seen: set[tuple[str, str, str | None]] = set()
    for issue in issues:
        key = (issue.category, issue.evidence_quote.lower(), issue.document_id)
        if key in seen:
            continue
        seen.add(key)
        result.append(issue)
    return result
