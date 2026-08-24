"""Transcribe audio (telegram voice note) thanh text - dung boi OpenClaw.

Cach dung: python scripts/stt_transcribe.py <media_path>
Model: bien env WHISPER_MODEL (mac dinh 'small', co the dung 'base' cho nhanh).
"""
import os
import sys
import time

from faster_whisper import WhisperModel


def main():
    if len(sys.argv) < 2:
        raise SystemExit("thieu media path")
    media = sys.argv[1]
    model_size = os.getenv("WHISPER_MODEL", "small")
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    segments, _info = model.transcribe(media, language="vi", beam_size=1, vad_filter=True)
    text = " ".join(s.text.strip() for s in segments).strip()
    print(text if text else "(khong nghe ro)")


if __name__ == "__main__":
    t0 = time.time()
    main()
    print(f"[transcribe {time.time() - t0:.1f}s]", file=sys.stderr)
