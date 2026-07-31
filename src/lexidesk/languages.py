from __future__ import annotations

import re
from dataclasses import dataclass

LANGUAGE_CODE_RE = re.compile(r"^[a-z]{2,3}(?:-[a-z0-9]{2,8})*$")


@dataclass(frozen=True, slots=True)
class Language:
    code: str
    name: str
    native_name: str

    @property
    def label(self) -> str:
        return f"{self.name} ({self.code.upper()})"


_LANGUAGES = (
    Language("ar", "Arabic", "العربية"),
    Language("bg", "Bulgarian", "Български"),
    Language("ca", "Catalan", "Català"),
    Language("cs", "Czech", "Čeština"),
    Language("da", "Danish", "Dansk"),
    Language("de", "German", "Deutsch"),
    Language("el", "Greek", "Ελληνικά"),
    Language("en", "English", "English"),
    Language("es", "Spanish", "Español"),
    Language("et", "Estonian", "Eesti"),
    Language("fa", "Persian", "فارسی"),
    Language("fi", "Finnish", "Suomi"),
    Language("fr", "French", "Français"),
    Language("he", "Hebrew", "עברית"),
    Language("hi", "Hindi", "हिन्दी"),
    Language("hu", "Hungarian", "Magyar"),
    Language("id", "Indonesian", "Bahasa Indonesia"),
    Language("it", "Italian", "Italiano"),
    Language("ja", "Japanese", "日本語"),
    Language("ko", "Korean", "한국어"),
    Language("lt", "Lithuanian", "Lietuvių"),
    Language("lv", "Latvian", "Latviešu"),
    Language("nl", "Dutch", "Nederlands"),
    Language("no", "Norwegian", "Norsk"),
    Language("pl", "Polish", "Polski"),
    Language("pt", "Portuguese", "Português"),
    Language("ro", "Romanian", "Română"),
    Language("ru", "Russian", "Русский"),
    Language("sk", "Slovak", "Slovenčina"),
    Language("sl", "Slovenian", "Slovenščina"),
    Language("sv", "Swedish", "Svenska"),
    Language("th", "Thai", "ไทย"),
    Language("tr", "Turkish", "Türkçe"),
    Language("uk", "Ukrainian", "Українська"),
    Language("vi", "Vietnamese", "Tiếng Việt"),
    Language("zh", "Chinese", "中文"),
)
LANGUAGES = {language.code: language for language in _LANGUAGES}


def normalize_language_code(code: str) -> str:
    normalized = code.strip().replace("_", "-").casefold()
    if not LANGUAGE_CODE_RE.fullmatch(normalized):
        raise ValueError(f"Invalid language code: {code!r}")
    return normalized


def language_name(code: str) -> str:
    normalized = code.casefold()
    language = LANGUAGES.get(normalized)
    return language.name if language else normalized.upper()


def language_label(code: str) -> str:
    normalized = code.casefold()
    language = LANGUAGES.get(normalized)
    return language.label if language else normalized.upper()
