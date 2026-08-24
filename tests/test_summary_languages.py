import pytest

from yt_transcript.summary_languages import (
    normalize_summary_language,
    summary_language_options,
    summary_language_prompt_name,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("AUTO", "auto"),
        (None, "auto"),
        ("ZH-hans", "zh-Hans"),
        ("pt-br", "pt-BR"),
        ("sr-latn-rs", "sr-Latn-RS"),
        ("it", "it"),
    ],
)
def test_normalize_summary_language(value: object, expected: str) -> None:
    assert normalize_summary_language(value) == expected


@pytest.mark.parametrize("value", ["", "custom", "e", "english", "en_US", "en--US"])
def test_normalize_summary_language_rejects_invalid_values(value: str) -> None:
    with pytest.raises(ValueError, match="BCP 47"):
        normalize_summary_language(value)


def test_options_and_prompt_names_share_the_common_language_definition() -> None:
    options = summary_language_options()

    assert options[0] == {"code": "auto", "label": "Same as transcript"}
    assert {item["code"] for item in options} >= {"ja", "zh-Hans", "pt-BR", "hi"}
    assert summary_language_prompt_name("pt-br") == "Brazilian Portuguese"
    assert summary_language_prompt_name("it") == 'the language identified by BCP 47 tag "it"'
