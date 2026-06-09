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
            r"(?i:\b(?:hp|hewlett|canon|epson|xerox|samsung|lenovo|dell|apple|bosch|makita|cisco|intel|amd|microsoft|schneider)\b)|"
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
        category="еквівалентність",
        title="Еквівалент вимагається як ідентичний товар",
        severity="висока",
        pattern=re.compile(
            r"\b(еквівалент\w*|аналог(?!ічн)\w*)\b.{0,250}"
            r"(ідентичн|повністю\s+відповіда|співпада|збігає|без\s+відхилень|"
            r"100\s*%\s*відповідн|будь-як\w*\s+відмінност\w*.{0,80}відхиля)",
            re.IGNORECASE | re.UNICODE | re.DOTALL,
        ),
        explanation=(
            "Фраза «або еквівалент» формально дозволяє альтернативи, але вимога повної тотожності "
            "може фактично відтворювати конкретний товар."
        ),
        suggested_rewrite=(
            "Визначте мінімальні суттєві характеристики та допустимі відхилення, які не погіршують "
            "функціональність товару."
        ),
        subscores=("конкурентність", "технічна нейтральність"),
    ),
    Rule(
        category="еквівалентність",
        title="Пряма заборона або відхилення еквівалентів",
        severity="висока",
        pattern=re.compile(
            r"(еквівалент\w*(?:\s+\w+){0,3}\s+не\s+"
            r"(розгляда\w*|допуска\w*|прийма\w*|визначал\w*)|"
            r"у\s+разі.{0,80}еквівалент.{0,80}(не\s+відповіда|відхиля))",
            re.IGNORECASE | re.UNICODE | re.DOTALL,
        ),
        explanation=(
            "Документація прямо виключає або відхиляє альтернативні товари, що є сильним сигналом "
            "обмеження конкуренції."
        ),
        suggested_rewrite=(
            "Дозвольте еквівалентні товари за мінімальними технічними критеріями або наведіть "
            "конкретне обґрунтування неможливості еквіваленту."
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
            r"(?:досвід(?:\s+роботи)?.{0,80}не\s+менше\s+[3-9]\s+рок|"
            r"не\s+менше\s+[3-9]\s+рок.{0,60}досвід|"
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
    Rule(
        category="строки поставки / сервіс",
        title="Надкороткий строк поставки, заміни або ремонту",
        severity="середня",
        pattern=re.compile(
            r"(поставк\w*|поставити|поставля\w*|доставк\w*|доставити|замін\w*|"
            r"усун\w*|ремонт\w*|відвантаж\w*).{0,120}"
            r"(протягом|у\s+строк|не\s+пізніше).{0,40}"
            r"(24\s*год|(?<!\d)[1-5](?!\d))\s*(календарн\w*|робоч\w*|банківськ\w*)?\s*"
            r"(годин|год|дн|день|дні|днів)",
            re.IGNORECASE | re.UNICODE | re.DOTALL,
        ),
        explanation=(
            "Дуже короткий строк поставки, заміни або ремонту може давати перевагу учасникам із "
            "локальним складом чи сервісом."
        ),
        suggested_rewrite=(
            "Розділіть строк реакції, діагностики та фактичної поставки або заміни; встановіть "
            "реалістичний строк за категорією товару."
        ),
        subscores=("конкурентність", "зрозумілість"),
    ),
    Rule(
        category="умови оплати",
        title="Тривала післяоплата або бюджетна відстрочка",
        severity="середня",
        pattern=re.compile(
            r"((оплат\w*.{0,80}протягом\s+(60|90|120|150|180|270|365)\s*"
            r"(календарн\w*|робоч\w*|банківськ\w*)?\s*дн)|"
            r"((затримк\w*|відсутн\w*)\s+.{0,40}фінансуван.{0,180}"
            r"(не\s+несе\s+відповідальності|штрафн\w*\s+санкц\w*\s+не\s+застосов|"
            r"відстрочк\w*\s+платеж)))",
            re.IGNORECASE | re.UNICODE | re.DOTALL,
        ),
        explanation=(
            "Тривала післяоплата або невизначена бюджетна відстрочка перекладає фінансовий ризик "
            "на учасника та може звужувати конкуренцію."
        ),
        suggested_rewrite=(
            "Скоротіть строк оплати або встановіть максимальну межу відстрочки, порядок повідомлення "
            "та збалансовані наслідки прострочення."
        ),
        subscores=("конкурентність", "повнота", "якість проєкту договору"),
    ),
    Rule(
        category="договірні санкції",
        title="Надмірна пеня або штраф за коротке прострочення",
        severity="висока",
        pattern=re.compile(
            r"(пен[яю]|штраф|неустойк\w*).{0,100}"
            r"((?<![\d,.])(?:[1-9]|\d{2,})\s*%\s*.{0,80}(кожн\w*\s+день|за\s+день|в\s+день)|"
            r"(?<![\d,.])(?:20|25|30|40|50|100)\s*%.{0,120}"
            r"(понад\s+(1|3|5|7)\s+дн|відмов\w*\s+від\s+постач))",
            re.IGNORECASE | re.UNICODE | re.DOTALL,
        ),
        explanation=(
            "Непропорційні санкції можуть впливати на ціну пропозицій і готовність учасників "
            "подаватися."
        ),
        suggested_rewrite=(
            "Встановіть співмірну пеню, граничний розмір відповідальності та винятки для об'єктивно "
            "підтверджених затримок."
        ),
        subscores=("конкурентність", "якість проєкту договору"),
    ),
    Rule(
        category="договірний дисбаланс",
        title="Односторонній акт або мовчазна згода створює наслідки",
        severity="середня",
        pattern=re.compile(
            r"(односторонн\w*.{0,80}(акт|рекламац)|лист\s+замовника|мовчазн\w*\s+згод)"
            r".{0,180}(обов.?язков|повн\w*\s+юридичн\w*\s+сил|"
            r"підтвердженням\s+невідповідності|не\s+заперечує|неякісн)",
            re.IGNORECASE | re.UNICODE | re.DOTALL,
        ),
        explanation=(
            "Процедура приймання або претензій може ставати односторонньою, якщо акт, лист "
            "замовника чи мовчазна згода автоматично створюють наслідки для постачальника."
        ),
        suggested_rewrite=(
            "Передбачте двосторонній акт, повідомлення, строк заперечень і за потреби незалежну "
            "експертизу."
        ),
        subscores=("конкурентність", "якість проєкту договору"),
    ),
    Rule(
        category="договірний дисбаланс",
        title="Широкі односторонні права замовника змінити або розірвати договір",
        severity="середня",
        pattern=re.compile(
            r"(односторонн\w*.{0,80}(розірв|відмов|зменш|призупин)|"
            r"зменш\w*\s+в\s+односторонньому\s+порядку).{0,220}"
            r"(відпад\w*\s+потреб|відсутн\w*\s+потреб|відсутн\w*\s+фінансуван|"
            r"специфік\w*\s+діяльност|за\s+(1|3|5)\s*(календарн\w*|робоч\w*)?\s*дн|24\s*год)",
            re.IGNORECASE | re.UNICODE | re.DOTALL,
        ),
        explanation=(
            "Широкі односторонні права замовника можуть робити обсяг, строк або економіку договору "
            "непередбачуваними для постачальника."
        ),
        suggested_rewrite=(
            "Визначте підстави, межі, строк повідомлення, оплату фактично виконаного та компенсацію "
            "підтверджених витрат."
        ),
        subscores=("конкурентність", "якість проєкту договору"),
    ),
    Rule(
        category="приймання / логістика",
        title="Обов'язкова фізична присутність або заборона доставки перевізником",
        severity="середня",
        pattern=re.compile(
            r"(присутн\w*.{0,80}(постачальник|учасник|представник).{0,80}обов.?язков|"
            r"приймання.{0,80}(не\s+проводиться|не\s+розпочина)|"
            r"особисто\s+від.{0,80}представника|не.{0,40}від\s+3-ї\s+особи|"
            r"не.{0,40}(Нова\s+пошта|Укрпошта|перевізник|кур'єр))",
            re.IGNORECASE | re.UNICODE | re.DOTALL,
        ),
        explanation=(
            "Обов'язкова фізична присутність або заборона доставки перевізником може працювати як "
            "операційний бар'єр для учасників з інших регіонів."
        ),
        suggested_rewrite=(
            "Дозвольте приймання за документами, через перевізника, водія, експедитора або "
            "дистанційне підтвердження повноважень."
        ),
        subscores=("конкурентність", "зрозумілість"),
    ),
    Rule(
        category="логістика / поставка",
        title="Адреси поставки визначаються після аукціону або заявкою",
        severity="середня",
        pattern=re.compile(
            r"((місц\w*\s+поставки|адрес\w*|товароодержувач).{0,180}"
            r"(визначен\w*\s+у\s+заявц|вказан\w*\s+в\s+замовлен|лише\s+переможц|"
            r"буде\s+повідомлен)|"
            r"(місц\w*\s+поставки|адрес\w*)[^.]{0,80}мож\w*\s+бути\s+змінен)",
            re.IGNORECASE | re.UNICODE | re.DOTALL,
        ),
        explanation=(
            "Якщо адреси або місця поставки визначаються лише після аукціону чи заявками, учаснику "
            "складно точно оцінити логістику."
        ),
        suggested_rewrite=(
            "Надайте перелік можливих адрес або регіонів, порядок заявок, мінімальний строк "
            "повідомлення і правила компенсації додаткових витрат."
        ),
        subscores=("конкурентність", "повнота", "зрозумілість"),
    ),
    Rule(
        category="структура закупівлі / лоти",
        title="Багатопозиційна закупівля без лотів",
        severity="середня",
        pattern=re.compile(
            r"((без\s+поділу\s+на\s+лоти|лоти\s+не\s+передбачен|закупівл\w*\s+в\s+цілому)"
            r".{0,700}(\d{2,}\s*(позиці|найменуван)|повн\w*\s+перелік)|"
            r"(\d{2,}\s*(позиці|найменуван)|повн\w*\s+перелік).{0,700}"
            r"(без\s+поділу\s+на\s+лоти|лоти\s+не\s+передбачен|закупівл\w*\s+в\s+цілому))",
            re.IGNORECASE | re.UNICODE | re.DOTALL,
        ),
        explanation=(
            "Вимога подати пропозицію за багатопозиційним переліком без лотів може відсіювати "
            "спеціалізованих постачальників."
        ),
        suggested_rewrite=(
            "Розгляньте поділ на лоти за групами товарів або послуг чи надайте предметне "
            "обґрунтування неподілу."
        ),
        subscores=("конкурентність", "повнота"),
    ),
    Rule(
        category="фінансова спроможність",
        title="Дохід прив'язаний до високої частки очікуваної вартості",
        severity="середня",
        pattern=re.compile(
            r"(чист\w*\s+дохід|обсяг\s+доходу|виручк\w*|річн\w*\s+дохід).{0,160}"
            r"(не\s+менше|не\s+нижче).{0,40}(50|60|70|80|90|100|сто)\s*%"
            r".{0,120}очікуван\w*\s+варт",
            re.IGNORECASE | re.UNICODE | re.DOTALL,
        ),
        explanation=(
            "Високий поріг доходу, прив'язаний до очікуваної вартості, може відсіювати менших, "
            "але спроможних учасників."
        ),
        suggested_rewrite=(
            "Обґрунтуйте поріг або дозвольте альтернативні підтвердження здатності виконати договір."
        ),
        subscores=("конкурентність", "повнота"),
    ),
    Rule(
        category="кваліфікаційні вимоги",
        title="Аналогічний досвід звужено джерелом фінансування або типом об'єкта",
        severity="середня",
        pattern=re.compile(
            r"аналогічн\w*\s+договор\w*.{0,180}"
            r"(бюджетн\w*\s+кош|харчоблок|їдальн|конкретн\w*\s+тип\w*\s+приміщ|"
            r"виконан\w*\s+у\s+20\d{2}\s*,\s*20\d{2}|останн\w*\s+рік)",
            re.IGNORECASE | re.UNICODE | re.DOTALL,
        ),
        explanation=(
            "Формально аналогічний досвід може бути звужений до невиправдано малого кола учасників "
            "через джерело фінансування, тип об'єкта або дуже короткий період."
        ),
        suggested_rewrite=(
            "Визначайте аналогічність за суттю робіт або поставок незалежно від джерела фінансування "
            "та надмірно вузьких об'єктів."
        ),
        subscores=("конкурентність", "повнота"),
    ),
    Rule(
        category="вимоги до персоналу / МТБ",
        title="Фіксований склад персоналу або обладнання",
        severity="середня",
        pattern=re.compile(
            r"(обов.?язков\w*\s+наявн.{0,140}"
            r"(не\s+менше\s+\d+[-\s]?(х|ох)?\s*.{0,40}"
            r"(особ|одиниц|кран|стенд|автомоб|лаборатор|обладнан|персонал|працівн|"
            r"машин|механізм|технік)|\d+\s*(особ|одиниц)|кран|стенд|автомоб|лаборатор|обладнан)|"
            r"не\s+менше\s+\d+[-\s]?(х|ох)?\s*.{0,40}"
            r"(особ|одиниц|кран|стенд|автомоб|лаборатор|персонал|працівн|"
            r"машин|механізм|технік)|"
            r"перелік\s+обов.?язков\w*.{0,200}не\s+менше)",
            re.IGNORECASE | re.UNICODE | re.DOTALL,
        ),
        explanation=(
            "Детальна фіксація персоналу або обладнання може не відповідати різним способам "
            "виконання та відсіювати альтернативні організації робіт."
        ),
        suggested_rewrite=(
            "Вимагайте спроможність виконати роботи з можливістю еквівалентних ресурсів, суміщення "
            "функцій або залучення субпідрядників."
        ),
        subscores=("конкурентність", "повнота"),
    ),
]


EQUIVALENT_RE = re.compile(r"або\s+еквівалент|чи\s+еквівалент|еквівалентн|або\s+аналог|чи\s+аналог", re.IGNORECASE)
FUNCTIONAL_EQUIVALENT_RE = re.compile(
    r"не\s+гірш|допустим\w*\s+відхилен|мінімальн\w*\s+вимог|функціональн\w*\s+еквівалент",
    re.IGNORECASE,
)
DELIVERY_ANALOG_CONTEXT_RE = re.compile(
    r"(компані\w*[-\s]?аналоги|Нова\s+пошта|Укрпошта|перевізник|перевезення|доставки).{0,240}"
    r"(дата|датою|співпада|фактичн\w*\s+поставк)",
    re.IGNORECASE | re.DOTALL,
)
EQUIVALENT_DEFINITION_RE = re.compile(
    r"(тлумач\w*.{0,80}визначенн|під\s+терміном\s+[«\"]?еквівалент|"
    r"словник\s+української\s+мови|рівноцінн\w*.{0,80}рівнозначн\w*)",
    re.IGNORECASE | re.DOTALL,
)
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
AMD_AMENDMENT_RE = re.compile(r"\b(?:ISO|EN|ДСТУ|IEC|ANSI).{0,120}\bAmd\s+\d|\bAmd\s+\d.{0,120}\b(?:ISO|EN|ДСТУ|IEC|ANSI)", re.IGNORECASE)
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
BID_FORM_CONTEXT_RE = re.compile(
    r"форма\s+тендерн\w*\s+пропозиц|повне\s+найменування.{0,80}адрес.{0,80}місцезнаходжен",
    re.IGNORECASE | re.DOTALL,
)
SPECIFIC_LOCAL_REQUIREMENT_RE = re.compile(
    r"на\s+території\s+(?:міста|м\.|област|район)|(?:у|в)\s+місті|розташован\w*.{0,100}(?:м\.|міст|област|район)",
    re.IGNORECASE | re.DOTALL,
)
FUEL_CARD_TRADEMARK_RE = re.compile(
    r"торгов\w*\s+марк\w*.{0,80}(?:талон|скретч-карт|паливн\w*\s+карт|АЗС).{0,160}"
    r"торгов\w*\s+марк\w*.{0,80}(?:талон|скретч-карт|паливн\w*\s+карт|АЗС|співпада)",
    re.IGNORECASE | re.DOTALL,
)
TECH_CONTEXT_RE = re.compile(r"технічн|специфікац|характеристик|параметр|розмір|довжин|тиск|діаметр|конфіг", re.IGNORECASE)
FLEXIBLE_TECH_RE = re.compile(
    r"допустим\w*\s+відхилен|діапазон|не\s+гірш|функціональн|еквівалент",
    re.IGNORECASE,
)
BOQ_TECH_CONTEXT_RE = re.compile(
    r"найменування\s+(?:робіт|послуг|витрат)|робіт\s+і\s+витрат|локальн\w*\s+кошторис|"
    r"дефектн\w*\s+акт|відомість\s+обсяг|демонтаж|прокладання|розбирання|влаштування|"
    r"\bм[23]\b",
    re.IGNORECASE | re.DOTALL,
)
PRECISE_PARAMETER_RE = re.compile(
    r"(?<![\d.])\d+[,.]\d+\s*(?:мм|см|мл|F|Атм|грам|[\"″]|%|В|А)(?!\d)|"
    r"\b(?:довжина|довж|розмір|тиск|діаметр|товщина|густина|об.?єм|крива|конфіг\w*|"
    r"проф\w*|навантаження|сегмент)\s*[:=]?\s*[A-Za-zА-Яа-яІіЇїЄєҐґ\"'№\s/-]{0,24}"
    r"\d+(?:[,.]\d+)?\s*(?:мм|см|мл|F|Атм|грам|[\"″]|%)?|"
    r"Ø\s*\d+(?:[,.]\d+)?|"
    r"\b\d+\s*(?:мм|см|мл|F|Атм|грам)\b",
    re.IGNORECASE | re.UNICODE,
)
GRAMMAR_EXAMPLE_RE = re.compile(
    r"з\s+маленької\s+літери|уживання\s+розділових\s+знаків|відмінювання\s+слів|"
    r"наприклад|замість|орфографічн|формальн\w*\s+помил",
    re.IGNORECASE,
)
ARMA_CONTEXT_RE = re.compile(
    r"Національн(?:ому|ого)\s+агентств.{0,120}(?:розшуку|актив)",
    re.IGNORECASE | re.DOTALL,
)
NOTARY_TRANSLATION_RE = re.compile(
    r"нотаріальн\w*\s+завірен\w*.{0,80}переклад|переклад.{0,80}нотаріальн\w*\s+завірен|"
    r"нерезидент|іноземн\w*\s+мов|легалізован",
    re.IGNORECASE | re.DOTALL,
)
OPTIONAL_PRESENCE_RE = re.compile(
    r"за\s+бажан|за\s+можливост|може\s+бути\s+присут|не\s+є\s+обов.?язков",
    re.IGNORECASE,
)
STANDARD_CONTRACT_EXIT_RE = re.compile(
    r"за\s+згодою\s+сторін|рішенням\s+суду|істотн\w*\s+поруш.{0,80}строк.{0,40}усун",
    re.IGNORECASE | re.DOTALL,
)
NO_LOT_JUSTIFICATION_RE = re.compile(
    r"єдин\w*\s+(комплекс|систем)|комплект|технологічн\w*\s+пов.?язан|обґрунтуван\w*\s+неподіл",
    re.IGNORECASE,
)
DELIVERY_REQUEST_CLEAR_LIMIT_RE = re.compile(
    r"строк\s+поставки\s+за\s+заявк.{0,120}не\s+може\s+перевищувати\s+\d+",
    re.IGNORECASE | re.DOTALL,
)
SHORT_DELIVERY_NOTICE_RE = re.compile(
    r"(інформує|повідомл\w*).{0,140}не\s+пізніше.{0,100}до\s+закінчення\s+строку\s+постав",
    re.IGNORECASE | re.DOTALL,
)
SHORT_DELIVERY_NON_DELIVERY_RE = re.compile(
    r"(податков\w*\s+накладн|податков\w*\s+кредит|ПДВ).{0,220}не\s+пізніше\s+(?:[1-5])\s*(?:календарн\w*|робоч\w*)?\s*дн|"
    r"провести.{0,80}замін\w*.{0,140}повідомл\w*.{0,80}не\s+пізніше\s+(?:[1-5])|"
    r"(направити\s+представника|надати\s+відповідь|не\s+направлення).{0,160}не\s+пізніше.{0,80}(?:[1-5])\s*(?:календарн\w*|робоч\w*)?\s*дн|"
    r"дат[аою]\s+поставки.{0,140}узгоджен\w*.{0,100}не\s+пізніше.{0,120}до\s+бажан\w*\s+дати|"
    r"звільн\w*.{0,120}(місце|об.?єкт).{0,160}(смітт|будівельн\w*\s+машин|технічн\w*\s+обладнан|невикористан\w*\s+матеріал)|"
    r"неможлив\w*.{0,100}здійснити.{0,80}замін\w*.{0,120}повідомл\w*.{0,120}(?:не\s+перевищує|протягом|не\s+пізніше).{0,40}(?:[1-5])\s*(?:календарн\w*|робоч\w*)?\s*дн|"
    r"(?:забезпечити\s+)?вивезення\s+Товару\s+неналежної\s+якості.{0,160}(?:не\s+пізніше|протягом).{0,60}(?:[1-5])\s*(?:календарн\w*|робоч\w*)?\s*дн|"
    r"(?:не\s+пізніше|протягом)\s+(?:[1-5])\s*(?:календарн\w*|робоч\w*)?\s*дн.{0,180}(?:забезпечити\s+)?вивезення\s+Товару\s+неналежної\s+якості",
    re.IGNORECASE | re.DOTALL,
)
SHORT_DELIVERY_ACCEPTANCE_RE = re.compile(
    r"(?:оглянути|прийняти|підписати\s+Акт|надати\s+обґрунтовані\s+запереченн).{0,220}"
    r"протягом\s+(?:[1-5])\s*(?:календарн\w*|робоч\w*)?\s*дн",
    re.IGNORECASE | re.DOTALL,
)
BUYER_SIDE_PENALTY_RE = re.compile(
    r"(Виконавець|Постачальник|Продавець|Підрядник)\s+має\s+право\s+стягнути\s+"
    r"(?:із|з)\s+Замовника.{0,120}пен[яю].{0,80}(?:[1-9]|\d{2,})\s*%.{0,80}кожн\w*\s+день",
    re.IGNORECASE | re.DOTALL,
)
MTB_RESOURCE_CONTEXT_RE = re.compile(
    r"учасник|працівник|персонал|матеріально-технічн|наявн\w*\s+технік|\bСТО\b|"
    r"оренд|власн|субпідряд|фахів|довідк\w*.{0,80}наявн",
    re.IGNORECASE | re.DOTALL,
)
BREACH_ONLY_EXIT_RE = re.compile(
    r"односторонн\w*.{0,180}розірв.{0,240}(невиконан|неналежн|неякісн|порушен).{0,140}"
    r"(Постачальник|Виконавець|Підрядник|Продавець)|"
    r"(невиконан|неналежн|неякісн|порушен).{0,160}(Постачальник|Виконавець|Підрядник|Продавець)"
    r".{0,220}односторонн\w*.{0,120}розірв",
    re.IGNORECASE | re.DOTALL,
)
BUYER_NEED_EXIT_RE = re.compile(r"зменш|відсутн|відпад|фінанс|потреб|обсяг|ціна", re.IGNORECASE)


class TenderAnalyzer:
    def analyze(self, parsed_documents: list[ParsedDocument]) -> tuple[list[Issue], dict[str, int], int]:
        issues: list[Issue] = []
        seen: set[tuple[str, str]] = set()

        for parsed in parsed_documents:
            text = parsed.text
            for rule in RULES:
                for match in rule.pattern.finditer(text):
                    quote = evidence_window(text, match.start(), match.end())
                    key = (rule.category, rule.title, quote.lower())
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
        issues.extend(technical_precision_issues(parsed_documents))
        issues.extend(parsing_issues(parsed_documents))
        issues = dedupe_issues(issues)
        subscores, overall = score_issues(issues)
        return issues, subscores, overall


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


def technical_precision_issues(parsed_documents: list[ParsedDocument]) -> list[Issue]:
    issues: list[Issue] = []
    for parsed in parsed_documents:
        text = parsed.text
        if not text:
            continue
        for start in range(0, max(len(text), 1), 1000):
            window = text[start : start + 1600]
            if not TECH_CONTEXT_RE.search(window) or FLEXIBLE_TECH_RE.search(window):
                continue
            if BOQ_TECH_CONTEXT_RE.search(window):
                continue
            matches = list(PRECISE_PARAMETER_RE.finditer(window))
            decimal_count = sum(1 for match in matches if re.search(r"\d+[,.]\d+", match.group(0)))
            if len(matches) < 12 and decimal_count < 6:
                continue
            absolute_start = start + matches[0].start()
            absolute_end = start + matches[-1].end()
            issues.append(
                Issue(
                    category="технічна специфікація",
                    title="Надмірно точні технічні параметри без функціонального допуску",
                    severity="середня",
                    evidence_quote=evidence_window(text, absolute_start, absolute_end),
                    explanation=(
                        "Щільний набір точних числових параметрів може відтворювати профіль конкретної "
                        "моделі або виробу навіть без прямої назви бренду."
                    ),
                    suggested_rewrite=(
                        "Залиште функціонально необхідні мінімальні та максимальні показники, додайте "
                        "допустимі відхилення або критерії еквівалентності."
                    ),
                    document_title=parsed.document.title,
                    document_id=parsed.document.id,
                )
            )
            break
    return issues


def should_skip_match(category: str, quote: str) -> bool:
    if category == "еквівалентність" and FUNCTIONAL_EQUIVALENT_RE.search(quote):
        return True
    if category == "еквівалентність" and DELIVERY_ANALOG_CONTEXT_RE.search(quote):
        return True
    if category == "еквівалентність" and EQUIVALENT_DEFINITION_RE.search(quote):
        return True
    if category == "бренд/модель без «або еквівалент»":
        if EQUIVALENT_RE.search(quote):
            return True
        if GENERIC_PRODUCER_RE.search(quote):
            return True
        if FUEL_CARD_TRADEMARK_RE.search(quote):
            return True
        if FORMAT_CONTEXT_RE.search(quote):
            return True
        if AMD_AMENDMENT_RE.search(quote):
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
        if BID_FORM_CONTEXT_RE.search(quote):
            return True
        if re.search(r"склад", quote, re.IGNORECASE) and not SPECIFIC_LOCAL_REQUIREMENT_RE.search(quote):
            return True
        if GRAMMAR_EXAMPLE_RE.search(quote):
            return True
        if "на всій території України" in quote:
            return True
    if category == "документальні вимоги" and (ARMA_CONTEXT_RE.search(quote) or NOTARY_TRANSLATION_RE.search(quote)):
        return True
    if category == "нечітка вимога" and "неналежн" in quote.lower():
        return True
    if category == "умови оплати/поставки" and DELIVERY_REQUEST_CLEAR_LIMIT_RE.search(quote):
        return True
    if category == "строки поставки / сервіс" and SHORT_DELIVERY_NOTICE_RE.search(quote):
        return True
    if category == "строки поставки / сервіс" and SHORT_DELIVERY_NON_DELIVERY_RE.search(quote):
        return True
    if category == "строки поставки / сервіс" and SHORT_DELIVERY_ACCEPTANCE_RE.search(quote):
        return True
    if category == "договірні санкції" and BUYER_SIDE_PENALTY_RE.search(quote):
        return True
    if category == "вимоги до персоналу / МТБ" and not MTB_RESOURCE_CONTEXT_RE.search(quote):
        return True
    if category == "договірний дисбаланс" and STANDARD_CONTRACT_EXIT_RE.search(quote):
        return True
    if category == "договірний дисбаланс" and BREACH_ONLY_EXIT_RE.search(quote) and not BUYER_NEED_EXIT_RE.search(quote):
        return True
    if category == "приймання / логістика" and OPTIONAL_PRESENCE_RE.search(quote):
        return True
    if category == "структура закупівлі / лоти" and NO_LOT_JUSTIFICATION_RE.search(quote):
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
            "технічна специфікація": ("конкурентність", "технічна нейтральність", "зрозумілість"),
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
    seen: set[tuple[str, ...]] = set()
    for issue in issues:
        if issue.category == "складність документів":
            key = (issue.category, issue.title, issue.evidence_quote.lower(), issue.document_id or "")
        else:
            key = (issue.category, issue.title)
        if key in seen:
            continue
        seen.add(key)
        result.append(issue)
    return result
