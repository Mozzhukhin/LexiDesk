from __future__ import annotations

import argparse
import json
from typing import Any

from .api import execute_request
from .backup import ensure_daily_backup
from .config import database_path, settings_path
from .database import WordRepository
from .diagnostics import configure_logging
from .service_client import request_service
from .settings import SettingsStore


def parser() -> argparse.ArgumentParser:
    command_parser = argparse.ArgumentParser(description="LexiDesk Plasma bridge")
    subparsers = command_parser.add_subparsers(dest="command", required=True)

    card = subparsers.add_parser("card", help="Select the next display card")
    card.add_argument("--exclude", type=int)
    card.add_argument("--adaptive", action="store_true")

    get_card = subparsers.add_parser("get", help="Return a specific card")
    get_card.add_argument("word_id", type=int)

    review = subparsers.add_parser("review", help="Review and select another card")
    review.add_argument("word_id", type=int)
    review.add_argument(
        "rating",
        choices=("again", "hard", "good", "easy", "know", "dont-know"),
    )
    review.add_argument("--duration-ms", type=int)
    review.add_argument("--quiz-type", default="")
    review.add_argument("--selected", default="")
    review.add_argument("--correct", default="")
    review.add_argument("--adaptive", action="store_true")

    check = subparsers.add_parser("check", help="Check a typed translation")
    check.add_argument("word_id", type=int)
    check.add_argument("answer")

    subparsers.add_parser("undo", help="Undo the most recent review")
    subparsers.add_parser("stats", help="Return vocabulary statistics")

    analytics = subparsers.add_parser("analytics", help="Return learning analytics")
    analytics.add_argument("--days", type=int, default=30)
    analytics.add_argument("--limit", type=int, default=10)
    return command_parser


def request_from_arguments(args: argparse.Namespace) -> dict[str, Any]:
    request: dict[str, Any] = {"command": args.command}
    if args.command == "card":
        if args.exclude is not None:
            request["exclude"] = args.exclude
        request["adaptive"] = args.adaptive
    elif args.command == "get":
        request["word_id"] = args.word_id
    elif args.command == "review":
        aliases = {"know": "good", "dont-know": "again"}
        request.update(
            {
                "word_id": args.word_id,
                "rating": aliases.get(args.rating, args.rating),
                "duration_ms": args.duration_ms,
                "quiz_type": args.quiz_type,
                "selected_answer": args.selected,
                "correct_answer": args.correct,
                "adaptive": args.adaptive,
            }
        )
    elif args.command == "check":
        request.update({"word_id": args.word_id, "answer": args.answer})
    elif args.command == "analytics":
        request.update({"days": args.days, "limit": args.limit})
    return request


def run(arguments: list[str] | None = None) -> dict[str, Any]:
    args = parser().parse_args(arguments)
    request = request_from_arguments(args)
    repository = WordRepository(database_path())
    try:
        ensure_daily_backup(repository)
        return execute_request(repository, request)
    finally:
        repository.close()


def main() -> int:
    configure_logging()
    try:
        args = parser().parse_args()
        request = request_from_arguments(args)
        if args.command in {"card", "review", "stats"}:
            settings_store = SettingsStore(settings_path())
            settings = settings_store.load()
            if not (
                settings.active_source_language and settings.active_target_language
            ):
                repository = WordRepository(database_path())
                try:
                    latest_pair = repository.latest_language_pair()
                finally:
                    repository.close()
                if latest_pair is not None:
                    (
                        settings.active_source_language,
                        settings.active_target_language,
                    ) = latest_pair
                    settings_store.save(settings)
            if settings.active_source_language and settings.active_target_language:
                request["source_lang"] = settings.active_source_language
                request["target_lang"] = settings.active_target_language
        payload = request_service(request)
        if payload is None:
            repository = WordRepository(database_path())
            try:
                ensure_daily_backup(repository)
                payload = execute_request(repository, request)
            finally:
                repository.close()
        if payload.get("error"):
            raise RuntimeError(str(payload["error"]))
    except Exception as error:
        print(
            json.dumps(
                {"error": str(error), "type": type(error).__name__},
                ensure_ascii=False,
            )
        )
        return 1
    print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
