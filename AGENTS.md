# SIMON Development Guide

## Build

### Backend
```bash
# Install dependencies
uv sync

# Run development server
uv run python -m app.main

# Build for production
uv build
```

### Frontend
```bash
# Install dependencies
npm install

# Run development server
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

## Test

### Run Single Test
```bash
uv run pytest tests/test_chat.py::test_message_creation -v
```

### Run All Tests
```bash
uv run pytest tests/ -v
```

### Run with Coverage
```bash
uv run pytest tests/ --cov=app --cov-report=html
```

## Code Style

### Imports
- Use absolute imports: `from app.models import Message`
- Group imports: stdlib, third-party, local (separated by blank lines)
- Sort alphabetically within groups using `ruff`

### Formatting
- Line length: 100 characters
- Quotes: Double quotes for strings
- Indentation: 4 spaces
- No trailing whitespace

### Type Hints
- All function parameters and returns must have type hints
- Use `Optional[T]` for nullable values
- Use `list[T]` (Python 3.13+) instead of `List[T]`
- Use `dict[K, V]` instead of `Dict[K, V]`

### Naming Conventions
- Classes: PascalCase (e.g., `ChatMessage`, `UserSession`)
- Functions/variables: snake_case (e.g., `get_user_messages`, `max_tokens`)
- Constants: UPPER_SNAKE_CASE (e.g., `DEFAULT_MODEL`, `MAX_RETRIES`)
- Private members: prefix with `_` (e.g., `_internal_cache`)

### Error Handling
- Use specific exception types (not bare `except:`)
- Log errors with context: `logger.error(f"Failed to fetch model: {e}", exc_info=True)`
- Return meaningful error messages to clients
- Validate input before processing

### Linting & Formatting
```bash
# Check code style
uv run ruff check .

# Format code
uv run ruff format .

# Check formatting without changes
uv run ruff format . --check
```

## Design Tokens

### Colors
- **Primary Blue**: `#104486` — Main brand color, buttons, headers
- **Accent Blue**: `#9BC2F9` — Highlights, hover states, secondary actions
- **Dark Blue**: `#0D2E5F` — Dark mode primary, text on light backgrounds
- **Light Blue**: `#E8F0FF` — Light backgrounds, disabled states
- **Success Green**: `#34A853` — Success messages, checkmarks
- **Warning Orange**: `#FBBC04` — Warnings, alerts
- **Error Red**: `#EA4335` — Errors, destructive actions
- **Neutral Gray**: `#5F6368` — Secondary text, borders
- **White**: `#FFFFFF` — Backgrounds, text on dark

### Typography
- **Font Family**: System stack (sans-serif)
- **Body**: 14px, line-height 1.5
- **Heading**: 20px, font-weight 600
- **Small**: 12px, line-height 1.4

### Spacing
- **Base unit**: 8px
- **Padding**: 8px, 16px, 24px, 32px
- **Margin**: 8px, 16px, 24px, 32px
- **Gap**: 8px, 16px

## vLLM API Reference

### Base URL
```
http://localhost:7777
```

### Model
```
Qwen/Qwen3.5-9B
```

### Completions Endpoint

#### Request
```bash
curl -X POST http://localhost:7777/v1/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen3.5-9B",
    "prompt": "What is the capital of France?",
    "max_tokens": 100,
    "temperature": 0.7,
    "top_p": 0.9,
    "stream": false
  }'
```

#### Response
```json
{
  "id": "cmpl-abc123",
  "object": "text_completion",
  "created": 1234567890,
  "model": "Qwen/Qwen3.5-9B",
  "choices": [
    {
      "text": " Paris",
      "index": 0,
      "logprobs": null,
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 10,
    "completion_tokens": 2,
    "total_tokens": 12
  }
}
```

### Chat Completions Endpoint

#### Request
```bash
curl -X POST http://localhost:7777/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen3.5-9B",
    "messages": [
      {"role": "user", "content": "What is the capital of France?"}
    ],
    "max_tokens": 100,
    "temperature": 0.7,
    "stream": false
  }'
```

#### Response
```json
{
  "id": "chatcmpl-abc123",
  "object": "chat.completion",
  "created": 1234567890,
  "model": "Qwen/Qwen3.5-9B",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "The capital of France is Paris."
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 10,
    "completion_tokens": 5,
    "total_tokens": 15
  }
}
```

### Streaming

Add `"stream": true` to request. Response is newline-delimited JSON:

```
data: {"choices":[{"delta":{"content":"The"}}]}
data: {"choices":[{"delta":{"content":" capital"}}]}
data: [DONE]
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `model` | string | - | Model identifier (required) |
| `prompt` / `messages` | string / array | - | Input text or messages (required) |
| `max_tokens` | integer | 512 | Maximum tokens in response |
| `temperature` | float | 0.7 | Sampling temperature (0.0-2.0) |
| `top_p` | float | 0.9 | Nucleus sampling parameter |
| `top_k` | integer | 40 | Top-k sampling parameter |
| `stream` | boolean | false | Enable streaming responses |
| `stop` | string / array | null | Stop sequences |

### Error Handling

```json
{
  "error": {
    "message": "Model not found",
    "type": "InvalidRequestError",
    "param": "model",
    "code": "model_not_found"
  }
}
```

Common status codes:
- `200`: Success
- `400`: Bad request (invalid parameters)
- `401`: Unauthorized
- `404`: Model not found
- `429`: Rate limited
- `500`: Server error
