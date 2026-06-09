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


def test_repeated_non_parsing_signal_counts_once_per_tender():
    text = """
    Учасник надає авторизаційний лист від виробника.
    Строк поставки 10 днів. Оплата протягом 15 банківських днів.
    Проєкт договору містить відповідальність сторін та порядок розірвання.
    """
    issues, _, overall = TenderAnalyzer().analyze([doc(text), doc(text)])

    assert sum(1 for issue in issues if issue.category == "лист виробника") == 1
    assert overall == 90


def test_equivalent_phrase_reduces_brand_false_positive():
    text = """
    Поставка принтера Canon або еквівалент із ресурсом картриджа не менше 3000 сторінок.
    Фарба Farbmann або аналог, шпаклівка Knauf або аналог.
    Строк поставки 10 днів. Оплата протягом 15 банківських днів.
    Проєкт договору містить відповідальність сторін та порядок розірвання.
    """
    issues, _, _ = TenderAnalyzer().analyze([doc(text)])

    assert "бренд/модель без «або еквівалент»" not in {issue.category for issue in issues}


def test_detects_restrictive_equivalent_wording():
    text = """
    Дозволяється товар Canon або еквівалент, але всі характеристики товару повинні співпадати
    по всім технічним характеристикам без відхилень. Еквіваленти товару не допускаються.
    Строк поставки 10 днів. Оплата протягом 15 банківських днів.
    Проєкт договору містить відповідальність сторін та порядок розірвання.
    """
    issues, _, _ = TenderAnalyzer().analyze([doc(text)])
    titles = {issue.title for issue in issues}

    assert "Еквівалент вимагається як ідентичний товар" in titles
    assert "Пряма заборона або відхилення еквівалентів" in titles


def test_detects_short_delivery_long_payment_and_excessive_penalty():
    text = """
    Поставка товару здійснюється протягом 3 календарних днів з моменту заявки.
    Оплата за поставлений товар здійснюється протягом 90 календарних днів.
    Проєкт договору передбачає штраф 30% понад 3 дні прострочення та пеню 3%
    за кожний день прострочення. Договір містить порядок розірвання.
    """
    issues, subscores, overall = TenderAnalyzer().analyze([doc(text)])
    categories = {issue.category for issue in issues}

    assert "строки поставки / сервіс" in categories
    assert "умови оплати" in categories
    assert "договірні санкції" in categories
    assert subscores["конкурентність"] < 100
    assert overall < 100


def test_standard_penalty_and_response_time_are_not_new_restrictive_findings():
    text = """
    Реакція сервісної служби на звернення протягом 2 годин.
    Пеня становить 0,1% за кожний день прострочення.
    Про дату оформлення ярлика на придатний поставлений товар письмово повідомити
    Постачальника не пізніше 1 робочого дня.
    Про виникнення істотних обставин сторона інформує іншу сторону не пізніше ніж
    за 5 днів до закінчення строку поставки.
    Строк поставки 10 днів. Оплата протягом 15 банківських днів.
    Проєкт договору містить відповідальність сторін та порядок розірвання.
    """
    issues, _, _ = TenderAnalyzer().analyze([doc(text)])
    categories = {issue.category for issue in issues}

    assert "строки поставки / сервіс" not in categories
    assert "договірні санкції" not in categories


def test_cycle_one_false_positive_contexts_are_ignored():
    text = """
    Наявність форс-мажорних обставин для нерезидента засвідчується документом з додаванням
    нотаріально завіреного перекладу українською мовою.
    Формальними помилками є написання адреси з маленької літери, наприклад м. кропивницький,
    та фраза: наявність складських приміщень замість наявність складських приміщень.
    Рукавички мають обов'язкову наявність рифлення на долонній частині. Довжина: не менше 300 мм.
    Строк поставки 10 днів. Оплата протягом 15 банківських днів.
    Проєкт договору містить відповідальність сторін та порядок розірвання.
    """
    issues, _, _ = TenderAnalyzer().analyze([doc(text)])
    categories = {issue.category for issue in issues}

    assert "документальні вимоги" not in categories
    assert "географічне обмеження" not in categories
    assert "вимоги до персоналу / МТБ" not in categories


def test_cycle_two_false_positive_contexts_are_ignored():
    text = """
    Мінімальні технічні вимоги: ДСТУ EN ISO 20471:2016 (EN ISO 20471:2013/A1:2016,
    IDT ISO 20471:2013/Amd 1:2016, IDT). Термін придатності на момент постачання
    не менше 5 років. Під аналогічним за предметом закупівлі договором слід розуміти
    договір, предмет якого збігається з предметом закупівлі.
    Постачальник зобов'язаний поставити Товар у строк відповідно до Заявки Покупця.
    Строк поставки за Заявкою Покупця не може перевищувати 20 робочих днів.
    Оплата протягом 15 банківських днів.
    Проєкт договору містить відповідальність сторін та порядок розірвання.
    """
    issues, _, _ = TenderAnalyzer().analyze([doc(text)])
    categories = {issue.category for issue in issues}

    assert "бренд/модель без «або еквівалент»" not in categories
    assert "еквівалентність" not in categories
    assert "кваліфікаційні вимоги" not in categories
    assert "умови оплати/поставки" not in categories


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


def test_detects_contract_imbalance_and_logistics_barrier():
    text = """
    Односторонній рекламаційний акт матиме повну юридичну силу для обох Сторін.
    Замовник має право зменшити в односторонньому порядку обсяг закупівлі за 1 календарний день,
    якщо відпадає потреба у даному товарі. Присутність представника Постачальника при прийманні
    є обов'язковою, у разі його відсутності приймання не проводиться.
    Строк поставки 10 днів. Оплата протягом 15 днів.
    Проєкт договору містить відповідальність сторін та порядок розірвання.
    """
    issues, _, _ = TenderAnalyzer().analyze([doc(text)])
    categories = {issue.category for issue in issues}

    assert "договірний дисбаланс" in categories
    assert "приймання / логістика" in categories


def test_detects_no_lots_revenue_threshold_and_fixed_resources():
    text = """
    Закупівля здійснюється без поділу на лоти, учасник подає пропозицію за повним
    переліком із 45 найменувань. Річний дохід учасника має бути не менше 80%
    очікуваної вартості закупівлі. Обов'язкова наявність не менше 2 одиниць
    спеціалізованого автомобільного обладнання.
    Строк поставки 10 днів. Оплата протягом 15 днів.
    Проєкт договору містить відповідальність сторін та порядок розірвання.
    """
    issues, _, _ = TenderAnalyzer().analyze([doc(text)])
    categories = {issue.category for issue in issues}

    assert "структура закупівлі / лоти" in categories
    assert "фінансова спроможність" in categories
    assert "вимоги до персоналу / МТБ" in categories


def test_detects_dense_exact_technical_parameters():
    text = """
    Технічна специфікація: направляючий катетер для трансрадіального доступу,
    Ø зовн. 6 F, Ø внутр. 0,071", конфігурація Judkins Left JL3.5, L 100 см,
    тиск 6/12 Атм, профіль верхівки 0,016, діаметр дистального шафту 2,4F,
    довжина катетера 145 см, Ø входу у стенд 0,016", Ø проходу стенду 0,024",
    навантаження на кінчик 0,6 грам, довжина сегменту 3,0 см.
    Строк поставки 10 днів. Оплата протягом 15 днів.
    Проєкт договору містить відповідальність сторін та порядок розірвання.
    """
    issues, _, _ = TenderAnalyzer().analyze([doc(text)])

    assert "технічна специфікація" in {issue.category for issue in issues}


def test_clause_numbers_do_not_count_as_dense_technical_parameters():
    text = """
    1.1. Постачальник передає товар згідно зі Специфікацією.
    1.2. Замовник приймає товар згідно ДК 021:2015 42160000-8.
    2.1. Ціна договору складає 100000 грн з ПДВ.
    3.1. Технічні вимоги зазначені в додатку до договору.
    Строк поставки 10 днів. Оплата протягом 15 днів.
    Проєкт договору містить відповідальність сторін та порядок розірвання.
    """
    issues, _, _ = TenderAnalyzer().analyze([doc(text)])

    assert "технічна специфікація" not in {issue.category for issue in issues}


def test_missing_contract_affects_contract_subscore():
    text = "Оплата протягом 10 днів. Поставка за адресою замовника протягом 5 днів."
    issues, subscores, overall = TenderAnalyzer().analyze([doc(text)])

    assert any(issue.category == "проєкт договору" for issue in issues)
    assert subscores["якість проєкту договору"] < 100
    assert overall < 100
