# MiMo API Notes

- Base URL: `https://api.xiaomimimo.com/v1`
- Model: `mimo-v2-tts`
- Endpoint: `POST /chat/completions`
- Auth header: `api-key: <key>`
- Recommended local env var: `XIAOMI_API_KEY`
- Output audio is returned as base64 at `choices[0].message.audio.data`
- Local skill hardening: retry transient HTTP failures, reject tiny decoded payloads, write output atomically before send, and prune old generated audio files in the same output directory
- MiMo TTS expects the text to synthesize inside an `assistant` role message
- Voice is passed inside `audio.voice`
- Optional style control is expressed by prefixing the text with `<style>...</style>`

Known voices from the official docs:

- `mimo_default`
- `default_zh`
- `default_en`

Example payload:

```json
{
  "model": "mimo-v2-tts",
  "messages": [
    {
      "role": "assistant",
      "content": "<style>开心</style>晚上好。"
    }
  ],
  "audio": {
    "format": "wav",
    "voice": "mimo_default"
  }
}
```
