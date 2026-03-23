---
name: mimo-voice-reply
description: Generate and send Xiaomi MiMo TTS voice replies for chat messages. Use when the user asks for a voice reply, asks to hear something read aloud, or when a spoken response is better than text such as stories, long explanations, warm check-ins, summaries, bedtime-style narration, or emotionally sensitive replies. Prefer OpenClaw's platform-neutral voice-message semantics first, then let the active channel/plugin handle the last-mile rendering.
---

# Mimo Voice Reply

Use this skill to turn a reply into audio with Xiaomi MiMo TTS and send it as a voice message.

Keep instructions platform-neutral. Prefer OpenClaw's generic voice-message semantics and only add channel-specific handling when testing proves it is necessary.

## Quick Start

1. Silently understand the user's real intent first; for inbound voice, this means doing ASR internally before deciding how to answer.
2. Decide whether voice is appropriate for the final reply.
3. Draft the exact spoken reply text.
4. Run `scripts/synthesize_mimo_tts.py` to create audio.
5. Write the audio into a message-tool-safe local path under the workspace, not `/tmp`.
6. Prefer a voice-note friendly `.ogg`/Opus output when the reply is meant to behave like a chat voice message.
7. Send the generated file with the `message` tool, using OpenClaw's generic voice-message semantics first.
8. Only rely on channel-specific quirks when the generic path is known to be insufficient.
9. If the voice message is the user-visible reply, respond with `NO_REPLY` and do not send any separate explanatory text.

## When To Prefer Voice

Prefer voice when one or more of these are true:

- The user explicitly asks for voice, audio, narration, or read-aloud output.
- The reply is easier to listen to than read.
- The tone matters: comfort, encouragement, storytelling, playful delivery, or spoken briefing.
- The content benefits from pacing, style tags, or vocal performance.

Prefer plain text when the reply is short, highly structured, code-heavy, or needs easy copy/paste.

## Workflow

### 1. Draft the spoken text

Write the exact words to speak. Keep it natural and slightly more conversational than a text-only reply.

### 2. Choose voice settings

Defaults are usually fine:

- model: `mimo-v2-tts`
- voice: `mimo_default`
- format: `wav`

Practical recommendation:

- If you plan to send a normal audio attachment, keep the default `wav`.
- If you plan to send a playable chat voice message, prefer `--voice-note` and let the script produce `.ogg` output for the channel plugin.

Optional style examples:

- `开心`
- `悲伤`
- `悄悄话`
- `东北话`
- `唱歌`

The script adds `<style>...</style>` automatically when `--style` is provided.

### 3. Synthesize audio

Basic example:

```bash
python3 scripts/synthesize_mimo_tts.py \
  --text "晚上好。今天要我先帮你处理什么？" \
  --out ./tmp/mimo-voice.wav
```

Voice-note oriented example for chat replies that should render as a playable voice message when the active channel supports it:

```bash
python3 scripts/synthesize_mimo_tts.py \
  --text "这条消息我用语音来回复。" \
  --style "开心" \
  --voice-note \
  --out ./tmp/mimo-voice.ogg
```

Environment variables supported by the script:

- `XIAOMI_API_KEY`
- `MIMO_TTS_BASE_URL`
- `MIMO_TTS_MODEL`
- `MIMO_TTS_VOICE`
- `MIMO_TTS_FORMAT`

Read `references/mimo-api.md` if you need the request shape.

### 4. Send the audio

Send the generated file with the `message` tool.

Preferred generic send shape:

- `action: send`
- `filePath: <generated audio path>`
- `channel: <current channel>` when needed
- `asVoice: true` when you want OpenClaw to express a platform-level "send this as a voice message" intent
- `target` only if sending proactively outside the current chat

Generate directly into a workspace-local path such as `./tmp/mimo-voice.ogg` so the `message` tool can hand the file to the active channel/plugin without a follow-up copy step.

If the `--voice-note` conversion path produced `.ogg`, prefer that file. It is the most portable output for OpenClaw's voice-message flows. Official docs also expose the related `[[audio_as_voice]]` reply tag for channels that interpret reply text directives, but for tool-driven sends this skill should prefer `message(..., asVoice=true)` as the primary generic signal.

When voice is the final user-visible reply, do not narrate tool calls, do not explain the send step, and do not emit any normal text reply before or after sending. The only post-send assistant output should be `NO_REPLY`.

Default execution rule for future calls:

- Prefer `--voice-note` whenever the target is a chat reply rather than a generic audio file send.
- Prefer the generic `asVoice=true` signal before reaching for channel-specific behavior.
- Only special-case a channel when the generic path is documented to be ignored or behaves incorrectly.

The script also performs lightweight cleanup in the output directory after a successful write. By default it keeps the newest 20 matching audio files and removes older ones once they are over 24 hours old.

## Platform Strategy

- First express the generic intent: produce voice-note friendly audio and send it with `message(..., asVoice=true)`.
- If the active channel supports OpenClaw's voice-message semantics, let the adapter decide the exact provider-side shape.
- If a channel ignores the generic signal or documents a different default, adapt only that final hop instead of baking platform branches into the whole skill.
- Use `[[audio_as_voice]]` only in reply-text driven flows where a text directive is the natural mechanism; for tool-driven sends, prefer `asVoice`.

## Guardrails

- Do not send both a full text answer and a voice answer unless the user asked for both.
- Keep spoken replies concise unless the user wants narration.
- For technical answers, voice can be paired with a short text summary if needed.
- If synthesis fails, fall back to text and briefly say that voice was unavailable.
- Keep using the current local-file workflow for sending; the script now writes atomically and validates the returned audio before handing it off.
