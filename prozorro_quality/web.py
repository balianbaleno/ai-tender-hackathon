from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .config import Settings, load_settings
from .models import TenderResult, priority_class, priority_label, priority_weight
from .processor import TenderProcessor
from .storage import ResultStorage


PACKAGE_DIR = Path(__file__).resolve().parent


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    storage = ResultStorage(settings.db_path)
    processor = TenderProcessor(settings, storage=storage)

    app = FastAPI(title="Якість тендерної документації Prozorro")
    templates = Jinja2Templates(directory=str(PACKAGE_DIR / "templates"))
    templates.env.filters["uah"] = format_uah
    templates.env.filters["date_ua"] = format_date
    templates.env.filters["priority_label"] = priority_label
    templates.env.filters["priority_class"] = priority_class
    templates.env.filters["tokens"] = format_tokens
    templates.env.filters["usd"] = format_usd
    templates.env.filters["category_label"] = category_label

    static_dir = PACKAGE_DIR / "static"
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request, category: str = "", max_score: str = "", sort: str = "processed_desc"):
        results = storage.list_results()
        categories = sorted({issue.category for result in results for issue in result.issues})
        filtered = results
        score_limit = parse_int(max_score)
        if category:
            filtered = [
                result
                for result in filtered
                if any(issue.category == category for issue in result.issues)
            ]
        if score_limit is not None:
            filtered = [result for result in filtered if result.overall_score <= score_limit]
        filtered = sort_results(filtered, sort)
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "results": filtered,
                "aggregate": storage.aggregate(),
                "categories": categories,
                "selected_category": category,
                "max_score": score_limit if score_limit is not None else "",
                "selected_sort": sort if sort in SORT_LABELS else "processed_desc",
                "sort_labels": SORT_LABELS,
                "score_sort": next_sort(sort, "score"),
                "score_sort_marker": sort_marker(sort, "score"),
                "priority_sort": next_sort(sort, "priority"),
                "priority_sort_marker": sort_marker(sort, "priority"),
                "settings": settings,
            },
        )

    @app.post("/process/batch")
    def process_batch(
        limit: int = Form(default=5),
        max_pages: int = Form(default=12),
        use_codex: bool = Form(default=False),
    ):
        processor.process_batch(
            batch_size=max(1, min(limit, 20)),
            max_pages=max(1, min(max_pages, 50)),
            use_codex=use_codex,
        )
        return RedirectResponse("/", status_code=303)

    @app.post("/process/tender")
    def process_tender(tender_id: str = Form(...), use_codex: bool = Form(default=False)):
        processor.process_tender(tender_id.strip(), use_codex=use_codex)
        return RedirectResponse("/", status_code=303)

    @app.get("/tenders/{tender_id}", response_class=HTMLResponse)
    def detail(request: Request, tender_id: str):
        result = storage.get(tender_id)
        if result is None:
            return HTMLResponse("Тендер не знайдено", status_code=404)
        grouped = defaultdict(list)
        for issue in result.issues:
            grouped[issue.category].append(issue)
        return templates.TemplateResponse(
            "detail.html",
            {
                "request": request,
                "result": result,
                "grouped_issues": dict(grouped),
            },
        )

    @app.get("/api/results")
    def api_results():
        return [result.to_dict() for result in storage.list_results()]

    @app.get("/api/results/{tender_id}")
    def api_result(tender_id: str):
        result = storage.get(tender_id)
        if result is None:
            return {"error": "not_found"}
        return result.to_dict()

    return app


def format_uah(amount: float | None, currency: str | None = "UAH") -> str:
    if amount is None:
        return "не вказано"
    return f"{amount:,.0f} {currency or ''}".replace(",", " ")


def format_date(value: str | None) -> str:
    if not value:
        return "не вказано"
    return value.replace("T", " ")[:19]


def format_tokens(value: int | None) -> str:
    if not value:
        return "0"
    return f"{int(value):,}".replace(",", " ")


def format_usd(value: float | None) -> str:
    if not value:
        return "$0.0000"
    if value < 0.0001:
        return f"${value:.6f}"
    return f"${value:.4f}"


def category_label(category: str | None) -> str:
    if not category:
        return ""
    category = category.strip()
    return f"{category[:1].upper()}{category[1:]}"


SORT_LABELS = {
    "processed_desc": "Новіші спочатку",
    "score_asc": "Нижчий бал спочатку",
    "score_desc": "Вищий бал спочатку",
    "priority_desc": "Вищий пріоритет спочатку",
    "priority_asc": "Нижчий пріоритет спочатку",
}


def parse_int(value: str | int | None) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def sort_results(results: list[TenderResult], sort: str) -> list[TenderResult]:
    if sort == "score_asc":
        return sorted(results, key=lambda result: (result.overall_score, -priority_weight(result.highest_severity)))
    if sort == "score_desc":
        return sorted(results, key=lambda result: (result.overall_score, priority_weight(result.highest_severity)), reverse=True)
    if sort == "priority_desc":
        return sorted(results, key=lambda result: (priority_weight(result.highest_severity), -result.overall_score), reverse=True)
    if sort == "priority_asc":
        return sorted(results, key=lambda result: (priority_weight(result.highest_severity), result.overall_score))
    return results


def next_sort(current_sort: str, column: str) -> str:
    if column == "score":
        return "score_desc" if current_sort == "score_asc" else "score_asc"
    if column == "priority":
        return "priority_asc" if current_sort == "priority_desc" else "priority_desc"
    return "processed_desc"


def sort_marker(current_sort: str, column: str) -> str:
    if column == "score":
        if current_sort == "score_asc":
            return "↑"
        if current_sort == "score_desc":
            return "↓"
    if column == "priority":
        if current_sort == "priority_asc":
            return "↑"
        if current_sort == "priority_desc":
            return "↓"
    return "↕"
