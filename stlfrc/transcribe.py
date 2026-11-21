"""Speech-to-text with faster-whisper (runs locally, no API costs)."""

from __future__ import annotations


class Transcriber:
    def __init__(self, model: str = "small.en", device: str = "auto", prompt: str = ""):
        from faster_whisper import WhisperModel  # imported lazily: heavy dependency

        compute = "int8" if device in ("auto", "cpu") else "float16"
        self.model = WhisperModel(model, device=device, compute_type=compute)
        self.prompt = prompt or None

    def transcribe(self, audio_path: str) -> str:
        segments, _ = self.model.transcribe(
            audio_path,
            language="en",
            beam_size=5,
            vad_filter=True,
            # Priming with local vocabulary noticeably improves accuracy on
            # unit names and street names.
            initial_prompt=self.prompt,
        )
        return " ".join(s.text.strip() for s in segments).strip()
