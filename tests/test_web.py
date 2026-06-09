from types import SimpleNamespace

from prozorro_quality.models import priority_label
from prozorro_quality.web import (
    category_label,
    format_tokens,
    format_usd,
    next_sort,
    parse_int,
    sort_marker,
    sort_results,
)


def result(code: str, score: int, priority: str):
    return SimpleNamespace(
        summary=SimpleNamespace(tender_code=code),
        overall_score=score,
        highest_severity=priority,
    )


def codes(results):
    return [item.summary.tender_code for item in results]


def test_priority_labels_use_masculine_forms_for_dashboard_priority():
    assert priority_label("висока") == "високий"
    assert priority_label("середня") == "середній"
    assert priority_label("низька") == "низький"
    assert priority_label("немає") == "без сигналів"


def test_sort_results_by_score_and_priority():
    results = [
        result("A", 95, "немає"),
        result("B", 80, "середня"),
        result("C", 90, "висока"),
        result("D", 70, "низька"),
    ]

    assert codes(sort_results(results, "score_asc")) == ["D", "B", "C", "A"]
    assert codes(sort_results(results, "score_desc")) == ["A", "C", "B", "D"]
    assert codes(sort_results(results, "priority_desc")) == ["C", "B", "D", "A"]
    assert codes(sort_results(results, "priority_asc")) == ["A", "D", "B", "C"]


def test_parse_int_tolerates_empty_filter_value():
    assert parse_int("") is None
    assert parse_int(None) is None
    assert parse_int("90") == 90


def test_table_header_sort_toggles_and_markers():
    assert next_sort("processed_desc", "score") == "score_asc"
    assert next_sort("score_asc", "score") == "score_desc"
    assert next_sort("priority_desc", "priority") == "priority_asc"
    assert sort_marker("processed_desc", "score") == "↕"
    assert sort_marker("score_asc", "score") == "↑"
    assert sort_marker("priority_desc", "priority") == "↓"


def test_cost_formatters():
    assert format_tokens(12345) == "12 345"
    assert format_usd(0) == "$0.0000"
    assert format_usd(0.012345) == "$0.0123"


def test_category_label_capitalizes_detail_issue_groups():
    assert category_label("складність документів") == "Складність документів"
    assert category_label("документальні вимоги") == "Документальні вимоги"
    assert category_label("географічне обмеження") == "Географічне обмеження"
    assert category_label("лист виробника") == "Лист виробника"
