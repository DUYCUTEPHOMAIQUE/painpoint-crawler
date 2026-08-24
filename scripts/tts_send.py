"""Tao giong noi tu van ban (TTS tieng Viet) va/gui qua Telegram.

Cach dung:
    python scripts/tts_send.py "Noi gi do"            # in ra file mp3
    python scripts/tts_send.py "Noi gi do" --send     # gui voice note qua Telegram
"""
import asyncio
import os
import sys

import edge_tts
import requests

VOICE = os.getenv("TTS_VOICE", "vi-VN-HoaiMyNeural")
OUT = "/tmp/opencode/tts_out.mp3"


async def gen(text, out):
    tts = edge_tts.Communicate(text, VOICE)
    await tts.save(out)


def main():
    text = sys.argv[1] if len(sys.argv) > 1 else "Xin chao"
    send = "--send" in sys.argv
    asyncio.run(gen(text, OUT))
    size = os.path.getsize(OUT)
    print(f"da tao {OUT} ({size} bytes)")
    if send:
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        chat = os.getenv("TELEGRAM_CHAT_ID") or "8871776087"
        with open(OUT, "rb") as f:
            r = requests.post(
                f"https://api.telegram.org/bot{token}/sendVoice",
                data={"chat_id": chat},
                files={"voice": ("reply.ogg", f, "audio/ogg")},
                timeout=60,
            )
        print("gui telegram:", "OK" if r.ok else r.text[:150])


if __name__ == "__main__":
    main()
