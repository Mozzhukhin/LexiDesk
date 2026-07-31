from __future__ import annotations

import logging
from pathlib import Path

from .database import WordRepository
from .examples import MAX_EXAMPLE_LENGTH, example_is_informative
from .translation import ExampleResult, OfflineTranslator

logger = logging.getLogger(__name__)


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
        if refresh_example:
            generated_examples = list(
                translator.generate_examples(
                    word.source_text,
                    word.source_lang,
                    word.part_of_speech,
                    word.target_text,
                )
            )
            generated = generated_examples[0]
            example = generated.source
            translation = generated.translation
        else:
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
            generated_examples = list(
                translator.generate_examples(
                    word.source_text,
                    word.source_lang,
                    word.part_of_speech,
                    word.target_text,
                )
            )
            generated_examples.insert(0, ExampleResult(example, translation))
        if not example:
            return False
        repository.replace_examples(
            word.id,
            [(item.source, item.translation) for item in generated_examples],
        )
        return True
    except Exception:
        logger.exception("Could not enrich card %s", word_id)
        return False
    finally:
        repository.close()
