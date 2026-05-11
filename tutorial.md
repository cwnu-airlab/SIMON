# OpenCode Tutorial

This guide shows a first-time user how to:

- install OpenCode
- create an SIMON API key
- register the SIMON model in OpenCode
- verify that OpenCode can talk to the SIMON endpoint

This tutorial assumes you want to use the public SIMON deployment:

- Web UI: `https://air.changwon.ac.kr/simon/`
- OpenAI-compatible base URL: `https://air.changwon.ac.kr/simon/v1`
- Model ID: `Qwen/Qwen3.5-9B`

## 1. Prerequisites

You need:

- a terminal on Linux, macOS, or WSL
- an SIMON account
- an SIMON API key

If you do not have an API key yet:

1. Open `https://air.changwon.ac.kr/simon/`
2. Sign in
3. Open the `API Keys` panel from the sidebar
4. Create a key and copy it immediately

SIMON only shows the full API key once.

## 2. Install OpenCode

Recommended install method on Linux and macOS:

```bash
curl -fsSL https://opencode.ai/install | bash
```

Other install methods:

```bash
npm install -g opencode-ai
```

```bash
brew install anomalyco/tap/opencode
```

After installation, confirm it works:

```bash
opencode --help
```

## 3. Know the Config Location

OpenCode reads config from these common locations:

- global config: `~/.config/opencode/opencode.json`
- project config: `./opencode.json`

For a personal machine-wide setup, use the global config.

## 4. Add the SIMON Provider

Create or edit `~/.config/opencode/opencode.json`:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "simon": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "SIMON",
      "options": {
        "baseURL": "https://air.changwon.ac.kr/simon/v1",
        "apiKey": "{env:SIMON_API_KEY}"
      },
      "models": {
        "Qwen/Qwen3.5-9B": {
          "name": "Qwen 3.5 9B"
        }
      }
    }
  },
  "model": "simon/Qwen/Qwen3.5-9B"
}
```

Why this config works:

- `@ai-sdk/openai-compatible` tells OpenCode to use an OpenAI-style provider
- `baseURL` points at SIMON's `/v1` endpoint
- `apiKey` is read from an environment variable instead of hardcoding secrets
- `model` sets SIMON as the default model for OpenCode

## 5. Store Your API Key

Recommended:

```bash
export SIMON_API_KEY="your-simon-api-key"
```

To make it persistent, add that export to your shell profile such as:

- `~/.bashrc`
- `~/.zshrc`

If you do not want to keep the key in your shell config, you can store it in a separate file and use OpenCode's file substitution instead:

```json
"apiKey": "{file:~/.secrets/simon-key}"
```

## 6. Verify the SIMON Endpoint First

Before testing OpenCode, confirm the SIMON API is reachable:

```bash
curl -H "Authorization: Bearer $SIMON_API_KEY" \
  https://air.changwon.ac.kr/simon/v1/models
```

You should get a JSON response listing models.

Then test one completion:

```bash
curl -X POST "https://air.changwon.ac.kr/simon/v1/chat/completions" \
  -H "Authorization: Bearer $SIMON_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen3.5-9B",
    "messages": [
      {"role": "user", "content": "Reply with OK only."}
    ],
    "stream": false
  }'
```

## 7. Test OpenCode

Run a simple one-shot command:

```bash
opencode run --model simon/Qwen/Qwen3.5-9B "Reply with OK only."
```

Or start the interactive UI:

```bash
opencode
```

Inside OpenCode, the configured provider and model should now be available.

## 8. Troubleshooting

### `404 Not Found`

This usually means the reverse proxy is not forwarding `/v1/` correctly.

Check that:

- the public URL really points to `https://air.changwon.ac.kr/simon/v1`
- the inner proxy forwards `/v1/` to the FastAPI backend

### `401 Authentication required`

This usually means:

- the API key is invalid
- the API key was revoked
- `SIMON_API_KEY` is missing from the shell where OpenCode runs

Check with:

```bash
echo "$SIMON_API_KEY"
```

### OpenCode starts but does not use SIMON

Check your config file path and model id:

- config path: `~/.config/opencode/opencode.json`
- provider/model: `simon/Qwen/Qwen3.5-9B`

### Want a project-specific config instead?

Instead of using the global config, you can put the same JSON in `./opencode.json` inside a project directory.

## 9. Quick Copy/Paste Setup

```bash
mkdir -p ~/.config/opencode
cat > ~/.config/opencode/opencode.json <<'EOF'
{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "simon": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "SIMON",
      "options": {
        "baseURL": "https://air.changwon.ac.kr/simon/v1",
        "apiKey": "{env:SIMON_API_KEY}"
      },
      "models": {
        "Qwen/Qwen3.5-9B": {
          "name": "Qwen 3.5 9B"
        }
      }
    }
  },
  "model": "simon/Qwen/Qwen3.5-9B"
}
EOF
```

Then:

```bash
export SIMON_API_KEY="your-simon-api-key"
opencode run --model simon/Qwen/Qwen3.5-9B "Reply with OK only."
```

## 10. Using the Python OpenAI SDK

You can also call the SIMON API directly from Python using the official `openai` package.

### Install the SDK

```bash
pip install openai
```

### Python Example

Use this streaming example with thinking mode disabled:

```python
from openai import OpenAI

client = OpenAI(
    base_url="https://air.changwon.ac.kr/simon/v1",
    api_key="your-simon-api-key",
)

stream = client.chat.completions.create(
    model="Qwen/Qwen3.5-9B",
    messages=[
        {"role": "user", "content": "hi, let me know about yourself."},
    ],
    stream=True,
    extra_body={
        "chat_template_kwargs": {"enable_thinking": False},
        "top_k": 20,
    },
)
for chunk in stream:
    content = chunk.choices[0].delta.content
    if content:
        print(content, end="", flush=True)
```

## 11. Uploading PDFs and Images via the App API

The OpenAI-compatible `/v1` endpoints do not support file attachments — those live on the app-native `/api` routes. The same API key works on both. PDF and image upload share one endpoint (`POST /api/conversations/{id}/attachments`); the backend dispatches on `Content-Type`.

| Type | MIME | Max size | Scope | Pages |
|---|---|---|---|---|
| PDF | `application/pdf` | 50 MB | conversation-scoped (auto-injected every turn as a system block) | ≤ 100 |
| Image | `image/png`, `image/jpeg`, `image/webp` | 10 MB | message-scoped (bind per turn via `attachment_ids`) | — |

### Setup

```bash
export SIMON_API_KEY="your-simon-api-key"
export BASE="https://air.changwon.ac.kr/simon"

# Create a new conversation (or reuse an existing id)
export CONV=$(curl -s -X POST "$BASE/api/conversations" \
  -H "Authorization: Bearer $SIMON_API_KEY" | jq -r .id)
echo "CONV=$CONV"
```

### Upload a PDF (conversation-scoped)

```bash
curl -X POST "$BASE/api/conversations/$CONV/attachments" \
  -H "Authorization: Bearer $SIMON_API_KEY" \
  -F "file=@report.pdf;type=application/pdf"
```

Response:

```json
{
  "id": 42,
  "filename": "report.pdf",
  "pages": 17,
  "attachment_type": "pdf",
  "message_id": null,
  "created_at": "2026-05-11T05:00:12+00:00"
}
```

Server-side OCR can take 20–40 seconds for scan PDFs (the first call also loads OCR models). Use a generous client timeout.

Once uploaded, every subsequent chat turn on the same conversation automatically receives the extracted markdown as a system message — no `attachment_ids` needed for PDFs.

### Send a chat message

The app chat endpoint (`/api/chat/completions`) takes `conversation_id`, `message`, and optionally `attachment_ids`. It streams the response as SSE:

```bash
curl -N -X POST "$BASE/api/chat/completions" \
  -H "Authorization: Bearer $SIMON_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"conversation_id\":\"$CONV\",\"message\":\"Summarize this document.\"}"
```

### Upload an image (message-scoped)

```bash
ATT=$(curl -s -X POST "$BASE/api/conversations/$CONV/attachments" \
  -H "Authorization: Bearer $SIMON_API_KEY" \
  -F "file=@photo.jpg;type=image/jpeg" | jq -r .id)
echo "ATT=$ATT"
```

The backend resizes the image to fit 1568×1568, re-encodes it as JPEG (stripping EXIF), and deduplicates by SHA-256. To use the image in a chat turn, pass its id in `attachment_ids`:

```bash
curl -N -X POST "$BASE/api/chat/completions" \
  -H "Authorization: Bearer $SIMON_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"conversation_id\":\"$CONV\",
    \"message\":\"What is in this image?\",
    \"attachment_ids\":[$ATT]
  }"
```

Once bound to a user message, the image is preserved across all future history replays — you do not need to re-send the id on subsequent turns.

Multiple images at once:

```bash
... -d "{\"message\":\"Compare these.\",\"attachment_ids\":[43,44,45], ...}"
```

### Python combined example

```python
import httpx

BASE = "https://air.changwon.ac.kr/simon"
KEY  = "your-simon-api-key"
HEADERS = {"Authorization": f"Bearer {KEY}"}

with httpx.Client(headers=HEADERS, timeout=120) as c:
    conv = c.post(f"{BASE}/api/conversations").json()["id"]

    # PDF (conversation-scoped)
    with open("report.pdf", "rb") as f:
        c.post(
            f"{BASE}/api/conversations/{conv}/attachments",
            files={"file": ("report.pdf", f, "application/pdf")},
        ).raise_for_status()

    # Image (message-scoped)
    with open("photo.jpg", "rb") as f:
        img = c.post(
            f"{BASE}/api/conversations/{conv}/attachments",
            files={"file": ("photo.jpg", f, "image/jpeg")},
        ).json()

    with c.stream(
        "POST", f"{BASE}/api/chat/completions",
        json={
            "conversation_id": conv,
            "message": "Summarize the PDF and describe the image.",
            "attachment_ids": [img["id"]],
        },
    ) as r:
        for line in r.iter_lines():
            if line:
                print(line)
```

### Listing, fetching, deleting

```bash
# All attachments in a conversation
curl -H "Authorization: Bearer $SIMON_API_KEY" \
  "$BASE/api/conversations/$CONV/attachments"

# Raw image bytes (image attachments only; PDFs are stored as extracted markdown)
curl -H "Authorization: Bearer $SIMON_API_KEY" \
  "$BASE/api/conversations/$CONV/attachments/$ATT/raw" \
  -o photo.jpg

# Delete (the image file is reaped from disk if no other row references it)
curl -X DELETE -H "Authorization: Bearer $SIMON_API_KEY" \
  "$BASE/api/conversations/$CONV/attachments/$ATT"
```

### Inlining an image on `/v1` instead

If you would rather skip the upload step and inline the image directly as a data URI on the OpenAI-compatible path, `/v1/chat/completions` forwards multimodal payloads as-is to vLLM:

```bash
curl -X POST "$BASE/v1/chat/completions" \
  -H "Authorization: Bearer $SIMON_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen3.5-9B",
    "messages": [{
      "role": "user",
      "content": [
        {"type": "text", "text": "Describe this image."},
        {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,'"$(base64 -w0 photo.jpg)"'"}}
      ]
    }]
  }'
```

`/v1` is stateless — no conversation history, no `attachment_ids`. PDFs are not supported on `/v1`; they only flow through the app `/api` routes that own the parser sidecar.

## 12. What SIMON Exposes to OpenCode

SIMON currently supports the OpenAI-compatible endpoints OpenCode needs for this flow:

- `GET /v1/models`
- `POST /v1/chat/completions`

That is why OpenCode can use it as a custom OpenAI-compatible provider.
