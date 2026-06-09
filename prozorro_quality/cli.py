from __future__ import annotations

import argparse
import json
from pathlib import Path

import uvicorn

from .config import load_settings
from .models import priority_label
from .processor import TenderProcessor
from .storage import ResultStorage
from .web import create_app


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="prozorro-quality",
        description="MVP аналізу якості тендерної документації Prozorro.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    process_one = subparsers.add_parser("process", help="Обробити один тендер за Prozorro UUID.")
    process_one.add_argument("tender_id", help="UUID тендера з Prozorro API.")
    process_one.add_argument("--use-codex", action="store_true", help="Увімкнути коротке Codex-збагачення пояснень.")
    process_one.add_argument("--refresh", action="store_true", help="Оновити кеш метаданих.")

    batch = subparsers.add_parser("batch", help="Обробити партію нових придатних тендерів.")
    batch.add_argument("--limit", type=int, default=None, help="Кількість тендерів, типово 5.")
    batch.add_argument("--max-pages", type=int, default=None, help="Максимум сторінок API для пошуку.")
    batch.add_argument("--use-codex", action="store_true", help="Увімкнути коротке Codex-збагачення пояснень.")
    batch.add_argument("--refresh", action="store_true", help="Оновити кеш метаданих для вибраних тендерів.")

    list_cmd = subparsers.add_parser("list", help="Показати збережені результати.")
    list_cmd.add_argument("--json", action="store_true", help="Вивести повний JSON.")

    serve = subparsers.add_parser("serve", help="Запустити український dashboard.")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)

    args = parser.parse_args(argv)
    settings = load_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)

    if args.command == "serve":
        app = create_app(settings)
        uvicorn.run(app, host=args.host, port=args.port)
        return 0

    processor = TenderProcessor(settings)
    if args.command == "process":
        result = processor.process_tender(args.tender_id, use_codex=args.use_codex, refresh=args.refresh)
        print_result_line(result)
        print(f"Збережено: {settings.db_path}")
        return 0

    if args.command == "batch":
        limit = args.limit or settings.default_batch_size
        max_pages = args.max_pages or settings.default_max_pages
        results = processor.process_batch(
            batch_size=limit,
            max_pages=max_pages,
            use_codex=args.use_codex,
            refresh=args.refresh,
        )
        if not results:
            print("Не знайдено нових придатних тендерів за поточними фільтрами.")
            print(f"Спробуйте збільшити --max-pages або змінити межі вартості через PROZORRO_MIN_VALUE/PROZORRO_MAX_VALUE.")
            return 1
        for result in results:
            print_result_line(result)
        print(f"Збережено {len(results)} результат(ів): {settings.db_path}")
        return 0

    if args.command == "list":
        storage = ResultStorage(settings.db_path)
        results = storage.list_results()
        if args.json:
            print(json.dumps([result.to_dict() for result in results], ensure_ascii=False, indent=2))
        else:
            for result in results:
                print_result_line(result)
            print(f"Усього: {len(results)}")
        return 0

    return 1


def print_result_line(result) -> None:
    summary = result.summary
    value = format_value(summary.value_amount, summary.currency)
    print(
        f"{summary.tender_code} | {result.overall_score}/100 | "
        f"{len(result.issues)} сигнал(ів) | {priority_label(result.highest_severity)} | "
        f"{result.llm_usage.total_tokens} токенів | ${result.llm_usage.total_cost_usd:.4f} | "
        f"{value} | {summary.title[:90]}"
    )


def format_value(amount: float | None, currency: str | None) -> str:
    if amount is None:
        return "вартість не вказана"
    return f"{amount:,.0f} {currency or ''}".replace(",", " ")


if __name__ == "__main__":
    raise SystemExit(main())
