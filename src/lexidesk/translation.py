from __future__ import annotations

import os
import re
from dataclasses import dataclass

from .dictionary import (
    OfflineDictionary,
    SpellingSuggestion,
    _damerau_levenshtein,
    normalize_headword,
)
from .examples import SemanticExampleIndex, example_is_informative
from .model_translation import OfflineModelRegistry

CYRILLIC_RE = re.compile(r"[\u0400-\u04ff]")
LATIN_RE = re.compile(r"[A-Za-z]")


class TranslationError(RuntimeError):
    pass


def detect_language(text: str) -> str:
    cyrillic = len(CYRILLIC_RE.findall(text))
    latin = len(LATIN_RE.findall(text))
    if cyrillic == latin == 0:
        raise TranslationError("Enter a word or a short phrase.")
    if cyrillic and latin:
        raise TranslationError("Use only one language in the source field.")
    return "ru" if cyrillic > latin else "en"


@dataclass(frozen=True, slots=True)
class TranslationResult:
    source_language: str
    target_language: str
    translation: str
    alternatives: tuple[str, ...] = ()
    part_of_speech: str = ""
    dictionary_match: bool = False
    corrected_source: str = ""
    spelling_suggestions: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ExampleResult:
    source: str
    translation: str


class OfflineTranslator:
    def __init__(
        self,
        dictionary: OfflineDictionary | None = None,
        *,
        autocorrect: bool = True,
        examples: SemanticExampleIndex | None = None,
    ) -> None:
        self._model_registry: OfflineModelRegistry | None = None
        self._model_cache: dict[tuple[str, str, str], tuple[str, ...]] = {}
        self.dictionary = dictionary or OfflineDictionary()
        self.autocorrect = autocorrect
        self.examples = examples or SemanticExampleIndex()

    def _models(self) -> OfflineModelRegistry:
        if self._model_registry is None:
            # Keep third-party runtimes offline even if they are installed by
            # another application in the same user environment.
            os.environ.setdefault("HF_HUB_OFFLINE", "1")
            os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
            self._model_registry = OfflineModelRegistry()
        return self._model_registry

    def translate(self, text: str) -> TranslationResult:
        cleaned = " ".join(text.strip().split())
        source = detect_language(cleaned)
        target = "ru" if source == "en" else "en"
        dictionary_entry = self.dictionary.lookup(cleaned, source)
        if dictionary_entry and dictionary_entry.translations:
            reciprocal = self.dictionary.reciprocal_translations(cleaned, source)
            ranked = _rank_dictionary_translations(
                dictionary_entry.translations,
                reciprocal,
                cleaned,
                source,
                self.dictionary,
            )
            return TranslationResult(
                source,
                target,
                ranked[0],
                ranked[1:8],
                dictionary_entry.part_of_speech,
                True,
            )
        candidates = self._model_candidates(cleaned, source, target)
        suggestions: tuple[SpellingSuggestion, ...] = ()
        if self.autocorrect and not self._is_known_inflection(cleaned, source):
            suggestions = self.dictionary.suggestions(cleaned, source)
        correction = _best_correction(suggestions, candidates, len(cleaned))
        if correction is not None:
            entry = correction.entry
            return TranslationResult(
                source,
                target,
                entry.translations[0],
                entry.translations[1:8],
                entry.part_of_speech,
                True,
                _match_source_case(entry.headword, cleaned),
            )
        translation = candidates[0] if candidates else ""
        primary_tokens = set(translation.casefold().split())
        alternatives = tuple(
            candidate
            for candidate in candidates[1:]
            if not (
                primary_tokens
                and primary_tokens.issubset(set(candidate.casefold().split()))
            )
        )
        if not translation.strip():
            raise TranslationError("The offline model returned an empty translation.")
        nearby: tuple[str, ...] = ()
        if suggestions:
            best_distance = suggestions[0].distance
            nearby = tuple(
                suggestion.entry.headword
                for suggestion in suggestions
                if suggestion.distance == best_distance
            )[:5]
        return TranslationResult(
            source,
            target,
            translation.strip(),
            alternatives,
            spelling_suggestions=nearby,
        )

    def generate_example(
        self,
        source_text: str,
        source_language: str = "",
        part_of_speech: str = "",
        target_text: str = "",
    ) -> ExampleResult:
        language = source_language or detect_language(source_text)
        if language == "ru":
            english_term = (
                target_text.strip() or self.translate(source_text).translation
            )
            english_example = self.examples.lookup(english_term, part_of_speech)
            if english_example:
                russian_example = self.translate(english_example).translation
                if example_is_informative(
                    russian_example,
                    source_text,
                    allow_inflection=True,
                ):
                    return ExampleResult(russian_example, english_example)
        sentence = self.example_sentence(source_text, language, part_of_speech)
        return self.complete_example(
            sentence,
            source_text,
            language,
            target_text,
            part_of_speech,
        )

    def generate_examples(
        self,
        source_text: str,
        source_language: str = "",
        part_of_speech: str = "",
        target_text: str = "",
        *,
        limit: int = 3,
    ) -> tuple[ExampleResult, ...]:
        """Create several short examples in the background for varied quizzes."""
        language = source_language or detect_language(source_text)
        primary = self.generate_example(
            source_text,
            language,
            part_of_speech,
            target_text,
        )
        results = [primary]
        seen = {primary.source.casefold()}
        if language == "en":
            candidates = self.examples.lookup_many(
                source_text,
                part_of_speech,
                limit=max(limit * 2, 8),
            )
            candidates.extend(
                _varied_fallback_sentences(source_text, language, part_of_speech)
            )
            for sentence in candidates:
                completed = self.complete_example(
                    sentence,
                    source_text,
                    language,
                    target_text,
                    part_of_speech,
                )
                key = completed.source.casefold()
                if key not in seen:
                    results.append(completed)
                    seen.add(key)
                if len(results) >= limit:
                    break
        else:
            english_term = (
                target_text.strip() or self.translate(source_text).translation
            )
            candidates = self.examples.lookup_many(
                english_term,
                part_of_speech,
                limit=max(limit * 2, 8),
            )
            candidates.extend(
                _varied_fallback_sentences(english_term, "en", part_of_speech)
            )
            for sentence in candidates:
                completed = self.complete_example(
                    sentence,
                    english_term,
                    "en",
                    source_text,
                    part_of_speech,
                )
                reversed_result = ExampleResult(completed.translation, completed.source)
                key = reversed_result.source.casefold()
                if key not in seen:
                    results.append(reversed_result)
                    seen.add(key)
                if len(results) >= limit:
                    break
        return tuple(results[:limit])

    def complete_example(
        self,
        sentence: str,
        source_text: str,
        source_language: str,
        target_text: str,
        part_of_speech: str = "",
    ) -> ExampleResult:
        """Translate an example and keep both sides tied to the card meaning."""
        translation = self.translate(sentence).translation
        if target_text:
            quoted_source = re.search(
                rf"[«“\"]\s*{re.escape(source_text)}\s*[»”\"]",
                sentence,
                flags=re.IGNORECASE,
            )
            if quoted_source is not None:
                translation = _align_quoted_term(translation, target_text)
            if not example_is_informative(
                translation,
                target_text,
                allow_inflection=True,
            ):
                fallback = _contextual_fallback(
                    sentence,
                    source_text,
                    source_language,
                    target_text,
                    part_of_speech,
                )
                sentence = fallback.source
                translation = fallback.translation
        return ExampleResult(sentence, translation)

    def example_sentence(
        self,
        source_text: str,
        source_language: str = "",
        part_of_speech: str = "",
    ) -> str:
        language = source_language or detect_language(source_text)
        return build_example_sentence(
            source_text,
            language,
            part_of_speech,
            self.examples,
        )

    def _model_candidates(self, cleaned: str, source: str, target: str) -> list[str]:
        cache_key = (cleaned, source, target)
        cached = self._model_cache.get(cache_key)
        if cached is not None:
            return list(cached)
        try:
            hypotheses = self._models().candidates(cleaned, source, target)
        except (LookupError, RuntimeError) as error:
            raise TranslationError(
                f"The {source.upper()} → {target.upper()} model is missing. "
                "Run scripts/install_models.py while connected to the internet."
            ) from error
        candidates: list[str] = []
        seen: set[str] = set()
        for hypothesis in hypotheses:
            value = _clean_model_candidate(
                hypothesis,
                single_word=len(cleaned.split()) == 1,
            )
            key = value.casefold()
            if value and key not in seen:
                candidates.append(value)
                seen.add(key)
        if len(self._model_cache) >= 256:
            self._model_cache.pop(next(iter(self._model_cache)))
        self._model_cache[cache_key] = tuple(candidates)
        return candidates

    def _is_known_inflection(self, text: str, source_language: str) -> bool:
        if source_language != "en" or not text.isalpha():
            return False
        return any(
            self.dictionary.lookup(stem, "en") is not None
            for stem in _english_stems(text.casefold())
        )


def _clean_model_candidate(value: str, *, single_word: bool) -> str:
    cleaned = " ".join(value.strip().split())
    if single_word and cleaned.endswith(".") and cleaned.count(".") == 1:
        cleaned = cleaned[:-1]
    return cleaned.strip()


def _match_source_case(correction: str, original: str) -> str:
    if original.isupper():
        return correction.upper()
    if original[:1].isupper() and original[1:] == original[1:].casefold():
        return correction[:1].upper() + correction[1:]
    return correction


def _rank_dictionary_translations(
    direct: tuple[str, ...],
    reciprocal: tuple[str, ...],
    source_text: str,
    source_language: str,
    dictionary: OfflineDictionary,
) -> tuple[str, ...]:
    """Rank meanings using agreement between both dictionary directions."""
    direct_ranks = {
        normalize_headword(value): rank for rank, value in enumerate(direct)
    }
    reciprocal_ranks = {
        normalize_headword(value): rank for rank, value in enumerate(reciprocal)
    }
    candidates = list(dict.fromkeys((*direct, *reciprocal)))
    target_language = "ru" if source_language == "en" else "en"
    scores: dict[str, int] = {}
    for value in candidates:
        key = normalize_headword(value)
        direct_rank = direct_ranks.get(key)
        score = max(0, 70 - direct_rank * 2) if direct_rank is not None else 0
        reciprocal_rank = reciprocal_ranks.get(key)
        if reciprocal_rank is not None:
            score += 60
        if dictionary.lookup(value, target_language) is not None:
            score += 20
        if source_text[:1].islower() and value[:1].isupper():
            score -= 100
        if len(value) <= 2 or value.endswith("."):
            score -= 18
        scores[key] = score

    suspicious: set[str] = set()
    for value in candidates:
        key = normalize_headword(value)
        if key in reciprocal_ranks or dictionary.lookup(value, target_language):
            continue
        for confirmed in reciprocal:
            confirmed_key = normalize_headword(confirmed)
            if len(key) >= 5 and _damerau_levenshtein(key, confirmed_key) == 1:
                suspicious.add(key)
                break

    ranked = sorted(
        candidates,
        key=lambda value: (
            normalize_headword(value) in suspicious,
            -scores[normalize_headword(value)],
            candidates.index(value),
        ),
    )
    primary = ranked[0]
    primary_key = normalize_headword(primary)
    direct_primary_key = normalize_headword(direct[0])
    alternatives = [
        value
        for value in direct
        if normalize_headword(value) not in suspicious
        and normalize_headword(value) != primary_key
        and (
            not reciprocal_ranks
            or normalize_headword(value) in reciprocal_ranks
            or normalize_headword(value) == direct_primary_key
        )
        and not (source_text[:1].islower() and value[:1].isupper())
    ]
    return tuple((primary, *alternatives))


def _align_quoted_term(sentence: str, target_text: str) -> str:
    """Replace a model-translated quoted headword with the selected meaning."""
    pattern = re.compile(r"([«“\"])[^»”\"]+([»”\"])")
    return pattern.sub(
        lambda match: f"{match.group(1)}{target_text}{match.group(2)}",
        sentence,
        count=1,
    )


def _best_correction(
    suggestions: tuple[SpellingSuggestion, ...],
    model_translations: list[str],
    source_length: int,
) -> SpellingSuggestion | None:
    if not suggestions:
        return None

    model_keys = {
        normalize_headword(translation)
        for translation in model_translations
        if translation.strip()
    }
    semantic_matches = [
        suggestion
        for suggestion in suggestions
        if model_keys.intersection(
            normalize_headword(translation)
            for translation in suggestion.entry.translations
        )
    ]
    if semantic_matches:
        return semantic_matches[0]

    best_distance = suggestions[0].distance
    equally_close = [
        suggestion for suggestion in suggestions if suggestion.distance == best_distance
    ]
    if source_length >= 5 and best_distance == 1 and len(equally_close) == 1:
        return equally_close[0]
    return None


def _english_stems(word: str) -> tuple[str, ...]:
    stems: list[str] = []
    if len(word) > 3 and word.endswith("s"):
        stems.append(word[:-1])
    if len(word) > 4 and word.endswith("es"):
        stems.append(word[:-2])
    if len(word) > 4 and word.endswith("ies"):
        stems.append(word[:-3] + "y")
    if len(word) > 4 and word.endswith("ed"):
        base = word[:-2]
        stems.extend((base, base + "e"))
        if word.endswith("ied"):
            stems.append(word[:-3] + "y")
    if len(word) > 5 and word.endswith("ing"):
        base = word[:-3]
        stems.extend((base, base + "e"))
        if len(base) > 2 and base[-1] == base[-2]:
            stems.append(base[:-1])
    return tuple(dict.fromkeys(stem for stem in stems if len(stem) >= 3))


def build_example_sentence(
    source_text: str,
    source_language: str,
    part_of_speech: str = "",
    examples: SemanticExampleIndex | None = None,
) -> str:
    term = " ".join(source_text.strip().split())
    if not term:
        raise TranslationError("Cannot create an example for an empty word.")
    if source_language not in {"en", "ru"}:
        raise TranslationError("Examples are supported for English and Russian.")

    category = part_of_speech.strip().casefold()
    if source_language == "en":
        semantic = (examples or SemanticExampleIndex()).lookup(term, category)
        if semantic:
            return semantic
    if source_language == "ru":
        if category.startswith("noun") or category.startswith("сущ"):
            return f"Понятие «{term}» оказалось важным для обсуждения."
        if category.startswith("verb") or category.startswith("глаг"):
            return f"В итоге они решили: «{term}»."
        if category.startswith("adj") or category.startswith("прилаг"):
            return f"Результат можно описать как «{term}»."
        if category.startswith("adv") or category.startswith("нареч"):
            return f"Её ответ прозвучал именно «{term}»."
        if category.startswith("phrase") or category.startswith("фраз"):
            return f"Фраза «{term}» точно передала её мысль."
        return f"Выражение «{term}» помогло уточнить смысл разговора."

    insertion = term
    if len(term.split()) == 1 and not term.isupper():
        insertion = term.casefold()
    if category.startswith("noun"):
        return f"The {insertion} changed the situation completely."
    if category.startswith("verb"):
        return f"They decided to {insertion} when the time was right."
    if category.startswith("adj"):
        return f"The result seemed {insertion} in this situation."
    if category.startswith("adv"):
        return f"They handled the situation {insertion}."
    if category.startswith("phrase"):
        return f"I heard the phrase “{term}” during the conversation."
    return f"The term “{term}” appeared in the conversation."


def _varied_fallback_sentences(
    source_text: str,
    source_language: str,
    part_of_speech: str,
) -> list[str]:
    term = " ".join(source_text.strip().split())
    category = part_of_speech.casefold()
    if source_language == "ru":
        if category.startswith(("noun", "сущ")):
            return [
                f"Мы обсудили «{term}» перед принятием решения.",
                f"Понятие «{term}» стало главным в разговоре.",
                f"Она объяснила «{term}» на понятном примере.",
            ]
        return [
            f"В разговоре естественно прозвучало «{term}».",
            f"Ситуация помогла понять выражение «{term}».",
            f"Он использовал «{term}», объясняя свою мысль.",
        ]
    insertion = term if term.isupper() else term.casefold()
    if category.startswith("noun"):
        return [
            f"We discussed the {insertion} before making a decision.",
            f"The {insertion} became central to their conversation.",
            f"She explained the {insertion} with a practical example.",
        ]
    if category.startswith("verb"):
        return [
            f"They agreed to {insertion} when the time was right.",
            f"We may need to {insertion} before the deadline.",
            f"She showed us how to {insertion} safely.",
        ]
    if category.startswith("adj"):
        return [
            f"The final result was clearly {insertion}.",
            f"His explanation seemed {insertion} to everyone.",
            f"The situation became increasingly {insertion} over time.",
        ]
    if category.startswith("adv"):
        return [
            f"She responded {insertion} during the meeting.",
            f"The team worked {insertion} to solve the problem.",
            f"He explained the decision very {insertion}.",
        ]
    return [
        f"We encountered {insertion} during the discussion.",
        f"The conversation offered a clear example of {insertion}.",
        f"They used {insertion} while explaining the situation.",
    ]


def _contextual_fallback(
    source_sentence: str,
    source_text: str,
    source_language: str,
    target_text: str,
    part_of_speech: str,
) -> ExampleResult:
    """Keep a useful source sentence and build a compact meaning-aware pair."""
    category = part_of_speech.strip().casefold()
    if source_language == "en":
        source = source_sentence or build_example_sentence(
            source_text,
            "en",
            category,
        )
        if category.startswith("noun"):
            target = f"Понятие «{target_text}» повлияло на итоговое решение."
        elif category.startswith("verb"):
            target = f"Они решили «{target_text}», когда пришло время действовать."
        elif category.startswith("adj"):
            target = f"Результат оказался «{target_text}» в этой ситуации."
        elif category.startswith("adv"):
            target = f"Она ответила «{target_text}» и объяснила своё решение."
        else:
            target = f"Выражение «{target_text}» точно передало смысл разговора."
        return ExampleResult(source, _shorten_fallback(target, target_text, "ru"))

    source = source_sentence or build_example_sentence(
        source_text,
        "ru",
        category,
    )
    if category.startswith("noun"):
        target = f"The idea of “{target_text}” shaped the final decision."
    elif category.startswith("verb"):
        prefix = "" if target_text.casefold().startswith("to ") else "to "
        target = f"They decided {prefix}{target_text} when the time was right."
    elif category.startswith("adj"):
        target = f"The result seemed {target_text} in that situation."
    elif category.startswith("adv"):
        target = f"She answered {target_text} and explained her decision."
    else:
        target = f"The phrase “{target_text}” expressed the idea clearly."
    return ExampleResult(source, _shorten_fallback(target, target_text, "en"))


def _shorten_fallback(sentence: str, term: str, language: str) -> str:
    if len(sentence) <= 70:
        return sentence
    if language == "ru":
        return f"Важный смысл здесь — «{term}»."
    return f"The intended meaning here is “{term}”."
