import asyncio
import logging
from pathlib import Path

from config import MODEL_DIR, WHISPER_MODEL_SIZE, WHISPER_COMPUTE_TYPE

logger = logging.getLogger(__name__)

_model = None


def _get_model():
    global _model
    if _model is None:
        from faster_whisper import WhisperModel
        logger.info("Caricamento modello Whisper '%s'...", WHISPER_MODEL_SIZE)
        _model = WhisperModel(
            WHISPER_MODEL_SIZE,
            device="cpu",
            compute_type=WHISPER_COMPUTE_TYPE,
            download_root=str(MODEL_DIR),
        )
        logger.info("Modello Whisper caricato.")
    return _model


def _transcribe_sync(audio_path: str) -> list:
    model = _get_model()
    try:
        segments, _info = model.transcribe(
            audio_path,
            beam_size=1,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 400},
            word_timestamps=True,
        )
        out = []
        for seg in segments:
            words = []
            if seg.words:
                for w in seg.words:
                    words.append({"start": round(w.start, 3), "end": round(w.end, 3), "word": w.word})
            out.append({
                "start": round(seg.start, 3),
                "end": round(seg.end, 3),
                "text": seg.text.strip(),
                "words": words,
            })
        return out
    except ValueError as e:
        # faster-whisper raises when VAD strips 100% of audio (silent/tone-only clips)
        logger.warning("Trascrizione senza parlato rilevabile: %s", e)
        return []
    except Exception as e:
        logger.exception("Errore Whisper: %s", e)
        return []


async def transcribe(audio_path: Path) -> list:
    """Transcribe audio file -> list of segments. Runs in a worker thread."""
    return await asyncio.to_thread(_transcribe_sync, str(audio_path))
