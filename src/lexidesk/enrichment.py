from __future__ import annotations

import logging
from pathlib import Path

from .database import WordRepository
from .examples import MAX_EXAMPLE_LENGTH, example_is_suitable
from .translation import OfflineTranslator

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
            or not example_is_suitable(
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
            generated = translator.generate_example(
                word.source_text,
                word.source_lang,
                word.part_of_speech,
                word.target_text,
            )
            example = generated.source
            translation = generated.translation
        elif not example_is_suitable(
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
        if not example:
            return False
        repository.update_example(word.id, example, translation)
        return True
    except Exception:
        logger.exception("Could not enrich card %s", word_id)
        return False
    finally:
        repository.close()
