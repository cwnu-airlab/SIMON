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

## 11. What SIMON Exposes to OpenCode

SIMON currently supports the OpenAI-compatible endpoints OpenCode needs for this flow:

- `GET /v1/models`
- `POST /v1/chat/completions`

That is why OpenCode can use it as a custom OpenAI-compatible provider.
