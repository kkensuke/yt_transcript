from __future__ import annotations

import re
from dataclasses import dataclass

AUTO_SUMMARY_LANGUAGE = "auto"


@dataclass(frozen=True, slots=True)
class SummaryLanguageOption:
    code: str
    label: str
    prompt_name: str


COMMON_SUMMARY_LANGUAGES = (
    SummaryLanguageOption("en", "English", "English"),
    SummaryLanguageOption("ja", "Japanese", "Japanese"),
    SummaryLanguageOption("zh-Hans", "Chinese (Simplified)", "Simplified Chinese"),
    SummaryLanguageOption("zh-Hant", "Chinese (Traditional)", "Traditional Chinese"),
    SummaryLanguageOption("ko", "Korean", "Korean"),
    SummaryLanguageOption("es", "Spanish", "Spanish"),
    SummaryLanguageOption("fr", "French", "French"),
    SummaryLanguageOption("de", "German", "German"),
    SummaryLanguageOption("pt-BR", "Portuguese (Brazil)", "Brazilian Portuguese"),
    SummaryLanguageOption("hi", "Hindi", "Hindi"),
)

_BCP47_PATTERN = re.compile(r"^(?=.{2,35}$)[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$")
_COMMON_BY_CODE = {option.code.lower(): option for option in COMMON_SUMMARY_LANGUAGES}


def normalize_summary_language(value: object) -> str:
    """Return ``auto`` or a canonicalized, safe subset of BCP 47 language tags."""
    language = AUTO_SUMMARY_LANGUAGE if value is None else str(value).strip()
    if language.lower() == AUTO_SUMMARY_LANGUAGE:
        return AUTO_SUMMARY_LANGUAGE
    if not _BCP47_PATTERN.fullmatch(language):
        raise ValueError("Use 'auto' or a valid BCP 47 language tag such as en, ja, pt-BR, or it.")

    parts = language.split("-")
    canonical_parts = [parts[0].lower()]
    for part in parts[1:]:
        if len(part) == 4 and part.isalpha():
            canonical_parts.append(part.title())
        elif (len(part) == 2 and part.isalpha()) or (len(part) == 3 and part.isdigit()):
            canonical_parts.append(part.upper())
        else:
            canonical_parts.append(part.lower())
    canonical = "-".join(canonical_parts)
    known = _COMMON_BY_CODE.get(canonical.lower())
    return known.code if known else canonical


def summary_language_prompt_name(language: str) -> str:
    """Return a clear prompt description for a validated summary language."""
    normalized = normalize_summary_language(language)
    option = _COMMON_BY_CODE.get(normalized.lower())
    if option:
        return option.prompt_name
    return f'the language identified by BCP 47 tag "{normalized}"'


def summary_language_options() -> list[dict[str, str]]:
    """Return the shared language choices exposed by the browser API."""
    return [
        {"code": AUTO_SUMMARY_LANGUAGE, "label": "Same as transcript"},
        *[{"code": option.code, "label": option.label} for option in COMMON_SUMMARY_LANGUAGES],
    ]
