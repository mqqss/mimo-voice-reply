#!/usr/bin/env python3
import argparse
import base64
import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from urllib import error, request

AUDIO_EXTENSIONS = {".wav", ".mp3", ".ogg", ".pcm16"}


def parse_args():
    p = argparse.ArgumentParser(description="Synthesize speech with Xiaomi MiMo TTS")
    p.add_argument("--text", required=True, help="Assistant text to synthesize")
    p.add_argument("--out", required=True, help="Output audio path")
    p.add_argument("--voice", default=os.environ.get("MIMO_TTS_VOICE", "mimo_default"))
    p.add_argument("--style", default="", help="Optional MiMo <style> tag contents, e.g. '开心' or '唱歌'")
    p.add_argument("--base-url", default=os.environ.get("MIMO_TTS_BASE_URL", "https://api.xiaomimimo.com/v1"))
    p.add_argument("--api-key", default=os.environ.get("XIAOMI_API_KEY", ""))
    p.add_argument("--model", default=os.environ.get("MIMO_TTS_MODEL", "mimo-v2-tts"))
    p.add_argument("--format", default=os.environ.get("MIMO_TTS_FORMAT", "wav"), choices=["wav", "mp3", "pcm16"])
    p.add_argument(
        "--voice-note",
        dest="voice_note",
        action="store_true",
        help="Try converting output to ogg/opus for chat platforms that prefer voice-note style audio if ffmpeg is installed",
    )
    p.add_argument("--timeout", type=float, default=float(os.environ.get("MIMO_TTS_TIMEOUT", "45")), help="Request timeout in seconds")
    p.add_argument("--retries", type=int, default=int(os.environ.get("MIMO_TTS_RETRIES", "2")), help="Retry count for transient API failures")
    p.add_argument("--min-bytes", type=int, default=int(os.environ.get("MIMO_TTS_MIN_BYTES", "512")), help="Minimum decoded audio bytes to accept")
    p.add_argument("--cleanup-max-age-hours", type=float, default=float(os.environ.get("MIMO_TTS_CLEANUP_MAX_AGE_HOURS", "24")), help="Delete generated audio files older than this many hours in the output directory; set <0 to disable")
    p.add_argument("--cleanup-keep-latest", type=int, default=int(os.environ.get("MIMO_TTS_CLEANUP_KEEP_LATEST", "20")), help="Keep at least this many newest generated audio files in the output directory; set <0 to disable")
    return p.parse_args()


def build_text(text: str, style: str) -> str:
    text = text.strip()
    if not text:
        raise SystemExit("Input text is empty.")
    style = style.strip()
    if not style:
        return text
    return f"<style>{style}</style>{text}"


def post_json(url: str, headers: dict, payload: dict, timeout: float) -> dict:
    req = request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body)
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        if exc.code in {408, 409, 425, 429, 500, 502, 503, 504}:
            raise RuntimeError(f"MiMo API HTTP {exc.code}: {body}")
        raise SystemExit(f"MiMo API HTTP {exc.code}: {body}")
    except error.URLError as exc:
        raise RuntimeError(f"MiMo API request failed: {exc}")


def post_json_with_retries(url: str, headers: dict, payload: dict, timeout: float, retries: int) -> dict:
    attempts = retries + 1
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            return post_json(url, headers, payload, timeout)
        except RuntimeError as exc:
            last_error = exc
            if attempt == attempts:
                break
            time.sleep(min(2 ** (attempt - 1), 4))
    raise SystemExit(str(last_error) if last_error else "MiMo API request failed.")


def extract_audio_bytes(data: dict, min_bytes: int) -> bytes:
    if isinstance(data, dict) and data.get("error"):
        raise SystemExit(f"MiMo API returned an error payload: {json.dumps(data, ensure_ascii=False)[:4000]}")
    try:
        audio_b64 = data["choices"][0]["message"]["audio"]["data"]
    except Exception as exc:
        raise SystemExit(
            "MiMo API response missing audio payload: "
            f"{exc}\nResponse: {json.dumps(data, ensure_ascii=False)[:4000]}"
        )
    try:
        audio_bytes = base64.b64decode(audio_b64)
    except Exception as exc:
        raise SystemExit(f"Failed to decode audio payload: {exc}")
    if len(audio_bytes) < min_bytes:
        raise SystemExit(f"Decoded audio is unexpectedly small: {len(audio_bytes)} bytes")
    return audio_bytes


def atomic_write_bytes(dest: Path, content: bytes):
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=dest.parent, delete=False) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)
    tmp_path.replace(dest)


def maybe_convert_for_voice_note(src: Path, dest: Path):
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return False
    cmd = [
        ffmpeg,
        "-y",
        "-i",
        str(src),
        "-vn",
        "-c:a",
        "libopus",
        "-b:a",
        "32k",
        "-vbr",
        "on",
        "-ac",
        "1",
        str(dest),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise SystemExit(f"ffmpeg conversion failed: {proc.stderr}")
    if not dest.exists() or dest.stat().st_size == 0:
        raise SystemExit("ffmpeg conversion produced an empty file")
    return True


def cleanup_output_dir(output_path: Path, keep_latest: int, max_age_hours: float):
    if keep_latest < 0 and max_age_hours < 0:
        return
    parent = output_path.parent
    stem_prefix = output_path.stem
    cutoff = time.time() - max(max_age_hours, 0) * 3600 if max_age_hours >= 0 else None
    files = []
    for candidate in parent.iterdir():
        if not candidate.is_file():
            continue
        if candidate.suffix.lower() not in AUDIO_EXTENSIONS:
            continue
        if not candidate.stem.startswith(stem_prefix):
            continue
        try:
            stat = candidate.stat()
        except FileNotFoundError:
            continue
        files.append((stat.st_mtime, candidate))
    files.sort(key=lambda item: item[0], reverse=True)
    protected = {path for _, path in files[: max(keep_latest, 0)]} if keep_latest >= 0 else set()
    for mtime, candidate in files:
        if candidate in protected:
            continue
        if cutoff is not None and mtime >= cutoff:
            continue
        try:
            candidate.unlink()
        except FileNotFoundError:
            pass


def main():
    args = parse_args()
    if not args.api_key:
        raise SystemExit("Missing API key. Set XIAOMI_API_KEY or pass --api-key.")

    out_path = Path(args.out).expanduser().resolve()
    payload = {
        "model": args.model,
        "messages": [
            {
                "role": "assistant",
                "content": build_text(args.text, args.style),
            }
        ],
        "audio": {
            "format": args.format,
            "voice": args.voice,
        },
    }
    headers = {
        "Content-Type": "application/json",
        "api-key": args.api_key,
    }
    data = post_json_with_retries(
        args.base_url.rstrip("/") + "/chat/completions",
        headers,
        payload,
        timeout=args.timeout,
        retries=max(args.retries, 0),
    )
    audio_bytes = extract_audio_bytes(data, min_bytes=max(args.min_bytes, 1))

    if args.voice_note:
        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / f"source.{args.format}"
            atomic_write_bytes(src, audio_bytes)
            voice_note_path = out_path if out_path.suffix.lower() == ".ogg" else out_path.with_suffix(".ogg")
            converted = maybe_convert_for_voice_note(src, voice_note_path)
            if converted:
                cleanup_output_dir(voice_note_path, args.cleanup_keep_latest, args.cleanup_max_age_hours)
                print(str(voice_note_path))
                return

    final_path = out_path if out_path.suffix.lower() == f".{args.format}" else out_path.with_suffix(f".{args.format}")
    atomic_write_bytes(final_path, audio_bytes)
    cleanup_output_dir(final_path, args.cleanup_keep_latest, args.cleanup_max_age_hours)
    print(str(final_path))


if __name__ == "__main__":
    main()
