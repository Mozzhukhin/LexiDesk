from __future__ import annotations

import logging
from pathlib import Path

from .database import WordRepository
from .examples import MAX_EXAMPLE_LENGTH, example_is_informative
from .models import Word
from .translation import ExampleResult, OfflineTranslator

logger = logging.getLogger(__name__)


def useful_examples(repository: WordRepository, word: Word) -> list[tuple[str, str]]:
    return [
        (example, translation)
        for example, translation in repository.examples_for_word(word.id)
        if example_is_informative(
            example,
            word.source_text,
            allow_inflection=word.source_lang == "ru",
        )
        and example_is_informative(
            translation,
            word.target_text,
            allow_inflection=True,
        )
    ]


def needs_example_enrichment(repository: WordRepository, word: Word) -> bool:
    return len(useful_examples(repository, word)) < 3


def enrich_example(database: Path, word_id: int) -> bool:
    """Complete a card example using an isolated database connection."""
    repository = WordRepository(database)
    try:
        word = repository.get_word(word_id)
        example = word.example
        translation = word.example_translation
        translator = OfflineTranslator()
        refresh_example = (
            not example
            or len(example) > MAX_EXAMPLE_LENGTH
            or not example_is_informative(
                example,
                word.source_text,
                allow_inflection=word.source_lang == "ru",
            )
            or (
                word.source_lang == "en"
                and example.casefold().startswith(
                    f"{word.source_text.casefold()} means "
                )
            )
        )
        retained: list[ExampleResult] = []
        if not refresh_example:
            if not example_is_informative(
                translation,
                word.target_text,
                allow_inflection=True,
            ):
                completed = translator.complete_example(
                    example,
                    word.source_text,
                    word.source_lang,
                    word.target_text,
                    word.part_of_speech,
                )
                example = completed.source
                translation = completed.translation
            if example_is_informative(
                example,
                word.source_text,
                allow_inflection=word.source_lang == "ru",
            ) and example_is_informative(
                translation,
                word.target_text,
                allow_inflection=True,
            ):
                retained.append(ExampleResult(example, translation))
        generated_examples = list(
            translator.generate_examples(
                word.source_text,
                word.source_lang,
                word.part_of_speech,
                word.target_text,
            )
        )
        retained.extend(generated_examples)
        if not retained:
            return False
        repository.replace_examples(
            word.id,
            [(item.source, item.translation) for item in retained],
        )
        return True
    except Exception:
        logger.exception("Could not enrich card %s", word_id)
        return False
    finally:
        repository.close()
