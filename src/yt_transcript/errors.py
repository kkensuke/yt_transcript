class AppError(Exception):
    """An expected error that can be shown directly to the user."""

    code = "app_error"
    default_hint = "Check your input and network connection, then try again."

    def __init__(self, message: str, hint: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint or self.default_hint


class InvalidVideoError(AppError):
    code = "invalid_video"
    default_hint = "Enter a YouTube video URL or an 11-character video ID."


class VideoFetchError(AppError):
    code = "video_fetch_failed"
    default_hint = (
        "For unlisted or age-restricted videos, select cookies from a signed-in "
        "browser in Advanced settings."
    )


class NoTranscriptError(AppError):
    code = "no_transcript"
    default_hint = "This video has no available captions in the selected language."


class TranscriptDownloadError(AppError):
    code = "transcript_download_failed"
    default_hint = "The caption URL may have expired. Wait a moment, then try again."


class GeminiApiError(AppError):
    code = "gemini_api_failed"
    default_hint = "Check the Gemini API key, model ID, and quota."
