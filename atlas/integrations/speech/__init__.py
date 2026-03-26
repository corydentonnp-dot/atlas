"""Local speech / wakeword capture interface.

TODO: Implement after scaffolding is approved. (Phase 3+)
Would use local speech recognition (Whisper, Vosk, etc.)

Capabilities:
- start_listening() -> None
- stop_listening() -> None
- on_wakeword(callback) -> None
- transcribe(audio_bytes) -> str
- get_intent(text) -> CapturedIntent
"""
