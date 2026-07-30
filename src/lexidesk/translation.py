from __future__ import annotations

import os
import re
from dataclasses import dataclass

from .config import bundled_language_data_dir
from .dictionary import (
    OfflineDictionary,
    SpellingSuggestion,
    _damerau_levenshtein,
    normalize_headword,
)
from .examples import SemanticExampleIndex, example_is_suitable

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
        self._translate_module = None
        self.dictionary = dictionary or OfflineDictionary()
        self.autocorrect = autocorrect
        self.examples = examples or SemanticExampleIndex()

    def _module(self):
        if self._translate_module is None:
            bundled = bundled_language_data_dir()
            if bundled is not None:
                packages = bundled / "argos-translate" / "packages"
                if packages.is_dir():
                    os.environ.setdefault("ARGOS_PACKAGES_DIR", str(packages))
            try:
                import argostranslate.translate
            except ImportError as error:
                raise TranslationError(
                    "Offline translator is not installed. Run scripts/setup.sh."
                ) from error
            self._translate_module = argostranslate.translate
        return self._translate_module

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
                if example_is_suitable(
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
        )

    def complete_example(
        self,
        sentence: str,
        source_text: str,
        source_language: str,
        target_text: str,
    ) -> ExampleResult:
        """Translate an example and keep both sides tied to the card meaning."""
        translation = self.translate(sentence).translation
        if target_text:
            translation = _align_quoted_term(translation, target_text)
            if not example_is_suitable(
                translation,
                target_text,
                allow_inflection=True,
            ):
                if source_language == "en":
                    sentence = f"The word “{source_text}” is used in this example."
                    translation = f"В этом примере используется слово «{target_text}»."
                else:
                    sentence = f"В этом примере используется слово «{source_text}»."
                    translation = f"The word “{target_text}” is used in this example."
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
        module = self._module()
        installed = module.get_installed_languages()
        source_language = next(
            (language for language in installed if language.code == source), None
        )
        target_language = next(
            (language for language in installed if language.code == target), None
        )
        if source_language is None or target_language is None:
            raise TranslationError(
                f"The {source.upper()} → {target.upper()} model is missing. "
                "Run scripts/install_models.py while connected to the internet."
            )
        engine = source_language.get_translation(target_language)
        hypotheses = engine.hypotheses(cleaned, num_hypotheses=4)
        candidates: list[str] = []
        seen: set[str] = set()
        for hypothesis in hypotheses:
            value = _clean_model_candidate(
                hypothesis.value,
                single_word=len(cleaned.split()) == 1,
            )
            key = value.casefold()
            if value and key not in seen:
                candidates.append(value)
                seen.add(key)
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
    return cleaned.replace(".", "").strip() if single_word else cleaned


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
            return f"В тексте встретилось существительное «{term}»."
        if category.startswith("verb") or category.startswith("глаг"):
            return f"В этом предложении используется глагол «{term}»."
        if category.startswith("adj") or category.startswith("прилаг"):
            return f"В тексте встретилось прилагательное «{term}»."
        if category.startswith("adv") or category.startswith("нареч"):
            return f"В этом предложении используется наречие «{term}»."
        if category.startswith("phrase") or category.startswith("фраз"):
            return f"В разговоре прозвучала фраза «{term}»."
        return f"В разговоре встретилось выражение «{term}»."

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
