# mimo-voice-reply

Generate chat-ready voice replies with Xiaomi MiMo TTS.

This skill is built for OpenClaw agents that want to answer with spoken audio instead of plain text. It keeps the core logic platform-neutral:

- generate speech with MiMo TTS
- prefer voice-note friendly OGG/Opus output when appropriate
- send through OpenClaw's generic `asVoice=true` semantics
- let the active channel/plugin decide the last-mile provider behavior

## What it does

- turns reply text into speech with `scripts/synthesize_mimo_tts.py`
- supports optional speaking styles such as `开心`, `悄悄话`, or `唱歌`
- can emit normal audio files or voice-note oriented `.ogg` output
- is designed for chat channels where "voice message" and "audio attachment" may differ

## Files

- `SKILL.md` - agent-facing instructions and workflow
- `scripts/synthesize_mimo_tts.py` - deterministic TTS helper script
- `references/mimo-api.md` - MiMo API request/response shape reference

## Requirements

- Python 3
- Xiaomi MiMo API key in `XIAOMI_API_KEY`
- optional: `ffmpeg` for `--voice-note` conversion to OGG/Opus

## Environment Variables

- `XIAOMI_API_KEY`
- `MIMO_TTS_BASE_URL`
- `MIMO_TTS_MODEL`
- `MIMO_TTS_VOICE`
- `MIMO_TTS_FORMAT`
- `MIMO_TTS_TIMEOUT`
- `MIMO_TTS_RETRIES`
- `MIMO_TTS_MIN_BYTES`
- `MIMO_TTS_CLEANUP_MAX_AGE_HOURS`
- `MIMO_TTS_CLEANUP_KEEP_LATEST`

## Basic Usage

From the skill directory:

```bash
python3 scripts/synthesize_mimo_tts.py \
  --text "Hello, this is a spoken reply." \
  --out ./tmp/reply.wav
```

Voice-note oriented output:

```bash
python3 scripts/synthesize_mimo_tts.py \
  --text "This reply is sent as a voice message." \
  --style "开心" \
  --voice-note \
  --out ./tmp/reply.ogg
```

## OpenClaw Sending Model

Recommended send shape:

```json
{
  "action": "send",
  "filePath": "./tmp/reply.ogg",
  "asVoice": true
}
```

Notes:

- `asVoice=true` expresses the generic OpenClaw intent: send this as a voice message if the channel supports that concept.
- Some channels render native voice bubbles.
- Some channels fall back to regular audio attachments.
- The skill does not hardcode per-platform provider APIs unless a channel is proven to need a special case.

## Design Goal

This skill intentionally separates responsibilities:

- the skill decides when voice is appropriate and generates audio
- OpenClaw expresses the generic voice-message intent
- the channel adapter decides how that intent maps to the underlying platform

That makes the skill reusable across Telegram, WhatsApp, Feishu/Lark, iMessage-style adapters, and future channels without baking the entire platform matrix into the skill itself.

## Testing Status

Best validated on Telegram-style voice-message flows.

Other channels depend on adapter support for OpenClaw's voice-message semantics and may render as either:

- native voice messages
- audio cards
- plain file attachments

## Packaging

Package with the official helper:

```bash
python3 ~/.nvm/versions/node/v24.14.0/lib/node_modules/openclaw/skills/skill-creator/scripts/package_skill.py . ./dist
```
