# OpenCode 튜토리얼

이 문서는 처음 사용하는 사용자가 다음 작업을 할 수 있도록 안내합니다.

- OpenCode 설치
- SIMON API 키 생성
- OpenCode에 SIMON 모델 등록
- OpenCode가 SIMON 엔드포인트와 정상적으로 통신하는지 확인

이 튜토리얼은 아래의 공개 SIMON 배포를 사용한다고 가정합니다.

- 웹 UI: `https://air.changwon.ac.kr/simon/`
- OpenAI 호환 API 기본 URL: `https://air.changwon.ac.kr/simon/v1`
- 모델 ID: `Qwen/Qwen3.5-9B`

## 1. 준비물

다음이 필요합니다.

- Linux, macOS, 또는 WSL 환경의 터미널
- SIMON 계정
- SIMON API 키

아직 API 키가 없다면:

1. `https://air.changwon.ac.kr/simon/` 에 접속합니다.
2. 로그인합니다.
3. 사이드바에서 `API Keys` 패널을 엽니다.
4. 새 키를 만들고 바로 복사합니다.

SIMON은 전체 API 키를 생성 시점에 한 번만 보여줍니다.

## 2. OpenCode 설치

Linux/macOS에서 권장 설치 방법:

```bash
curl -fsSL https://opencode.ai/install | bash
```

다른 설치 방법:

```bash
npm install -g opencode-ai
```

```bash
brew install anomalyco/tap/opencode
```

설치 후 정상 동작을 확인합니다.

```bash
opencode --help
```

## 3. 설정 파일 위치 확인

OpenCode는 보통 아래 위치에서 설정을 읽습니다.

- 전역 설정: `~/.config/opencode/opencode.json`
- 프로젝트 설정: `./opencode.json`

개인 환경 전체에서 쓰려면 전역 설정 파일을 사용하는 것이 일반적입니다.

## 4. OpenCode에 SIMON Provider 추가

`~/.config/opencode/opencode.json` 파일을 새로 만들거나 수정합니다.

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

이 설정이 동작하는 이유:

- `@ai-sdk/openai-compatible` 가 OpenCode에 OpenAI 호환 provider임을 알려줍니다.
- `baseURL` 은 SIMON의 `/v1` 엔드포인트를 가리킵니다.
- `apiKey` 는 비밀값을 설정 파일에 하드코딩하지 않고 환경 변수에서 읽습니다.
- `model` 은 OpenCode의 기본 모델을 SIMON으로 지정합니다.

## 5. API 키 저장

권장 방법:

```bash
export SIMON_API_KEY="your-simon-api-key"
```

영구적으로 쓰려면 셸 프로필에 추가하세요.

- `~/.bashrc`
- `~/.zshrc`

셸 설정 파일에 직접 넣고 싶지 않다면, 별도 파일에 키를 저장하고 OpenCode의 파일 치환 기능을 사용할 수도 있습니다.

```json
"apiKey": "{file:~/.secrets/simon-key}"
```

## 6. 먼저 SIMON 엔드포인트 자체를 확인하기

OpenCode를 테스트하기 전에, SIMON API가 직접 호출되는지 먼저 확인합니다.

```bash
curl -H "Authorization: Bearer $SIMON_API_KEY" \
  https://air.changwon.ac.kr/simon/v1/models
```

정상이라면 모델 목록이 담긴 JSON 응답이 반환됩니다.

그 다음 completion도 한 번 확인합니다.

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

## 7. OpenCode에서 테스트하기

간단한 one-shot 테스트:

```bash
opencode run --model simon/Qwen/Qwen3.5-9B "Reply with OK only."
```

또는 인터랙티브 UI를 실행할 수 있습니다.

```bash
opencode
```

OpenCode 내부에서 provider와 model이 정상적으로 보이면 설정이 완료된 것입니다.

## 8. 문제 해결

### `404 Not Found`

대개 reverse proxy가 `/v1/`를 올바르게 전달하지 못할 때 발생합니다.

다음을 확인하세요.

- 실제 공개 URL이 `https://air.changwon.ac.kr/simon/v1` 인지
- 내부 proxy가 `/v1/` 요청을 FastAPI backend로 전달하는지

### `401 Authentication required`

보통 아래 중 하나입니다.

- API 키가 잘못됨
- API 키가 revoke 됨
- OpenCode를 실행한 셸에서 `SIMON_API_KEY` 가 비어 있음

다음으로 확인할 수 있습니다.

```bash
echo "$SIMON_API_KEY"
```

### OpenCode가 실행되지만 SIMON을 사용하지 않음

설정 파일 위치와 모델 이름을 다시 확인하세요.

- 설정 파일 위치: `~/.config/opencode/opencode.json`
- provider/model: `simon/Qwen/Qwen3.5-9B`

### 프로젝트별 설정을 쓰고 싶다면?

전역 설정 대신, 프로젝트 루트의 `./opencode.json`에 같은 JSON을 넣어도 됩니다.

## 9. 빠른 복붙 설정

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

그 다음:

```bash
export SIMON_API_KEY="your-simon-api-key"
opencode run --model simon/Qwen/Qwen3.5-9B "Reply with OK only."
```

## 10. Python OpenAI SDK로 API 호출하기

공식 `openai` 패키지를 사용해서 Python에서 직접 SIMON API를 호출할 수도 있습니다.

### SDK 설치

```bash
pip install openai
```

### Python 예제

아래는 thinking 모드를 끈 스트리밍 예제입니다:

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

## 11. OpenCode가 실제로 쓰는 SIMON API

SIMON은 현재 OpenCode가 이 흐름에 필요한 OpenAI 호환 엔드포인트를 제공합니다.

- `GET /v1/models`
- `POST /v1/chat/completions`

그래서 OpenCode에서 custom OpenAI-compatible provider로 사용할 수 있습니다.
