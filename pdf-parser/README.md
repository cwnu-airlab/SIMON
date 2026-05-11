# pdf-parser

SIMON 백엔드를 위한 PDF 파싱 마이크로서비스. `opendataloader-pdf` (Java 코어 + docling-fast hybrid 백엔드)를 얇은 FastAPI HTTP 래퍼로 감쌌다.

## 엔드포인트

### `GET /health`
```json
{ "status": "ok", "hybrid": "ready" }
```
- `status`는 항상 `ok` (서비스 자체 상태).
- `hybrid`는 `5002` 백엔드 TCP open 여부 — `ready` 또는 `down`.

### `POST /parse`
multipart/form-data:
- `file` (required): PDF 파일 (≤ `MAX_FILE_MB`)
- `force_ocr` (optional, default `false`): hybrid 백엔드를 거쳐 강제 OCR 수행

응답:
```json
{
  "markdown": "...추출된 마크다운...",
  "pages": 12,
  "duration_ms": 1840
}
```

에러:
- `413` — 파일 크기 또는 페이지 수 초과
- `415` — content-type 이 `application/pdf` 아님
- `422` — pypdf 가 읽을 수 없는 손상 PDF
- `500` — opendataloader 변환 실패 / 마크다운 출력 없음

## 환경변수

| 이름 | 기본값 | 설명 |
|------|------|----|
| `MAX_FILE_MB` | `50` | 업로드 파일 크기 한도 |
| `MAX_PAGES` | `100` | PDF 페이지 수 한도 (pypdf로 사전 검사) |
| `OCR_LANG` | `ko,en` | hybrid 백엔드 OCR 언어 (entrypoint에서만 사용; 백엔드 시작 시 고정) |
| `HYBRID_BACKEND_URL` | `http://localhost:5002` | hybrid 백엔드 URL |

## 알려진 제약

1. **JVM cold start**: 첫 `/parse` 호출 시 1-3초 추가 지연. 두 번째부터 일반 latency.
2. **hybrid 백엔드 첫 부팅이 느림**: 처음 컨테이너 기동 시 EasyOCR / docling 모델을 huggingface 에서 다운로드 (수백 MB ~ 수 GB). `/cache` 볼륨 마운트로 영속화하면 두 번째 기동부터 빠름.
3. **OCR 언어가 hybrid 시작 시점에 고정**: `OCR_LANG` 변경 시 컨테이너 재시작 필요.
4. **JRE 11+ 필수**: 런타임 이미지는 `eclipse-temurin:17-jre-jammy`. opendataloader-pdf 가 `subprocess.run(['java', '-jar', ...])` 로 호출.
5. **메모리 모드**: 모든 처리가 `tempfile.TemporaryDirectory()` 안에서 끝나고 컨텍스트 종료 시 자동 정리. PDF 원본/출력 파일이 디스크에 잔존하지 않음.

## 로컬 개발

```bash
cd pdf-parser

# 의존성 설치 + venv 생성 (.venv/)
uv sync

# (옵션) hybrid 백엔드를 별도 터미널에서
uv run opendataloader-pdf-hybrid \
  --host 0.0.0.0 --port 5002 \
  --force-ocr --ocr-lang "ko,en" --device cpu

# FastAPI 래퍼 — 개발 모드
uv run uvicorn app:app --reload --port 8080

# 테스트
uv run pytest
```

## Docker 빌드

```bash
docker compose build pdf-parser
docker compose up pdf-parser
curl -F "file=@samples/text-1page.pdf" http://localhost:<exposed>/parse | jq .
```

이미지 레이어:
- builder: `ghcr.io/astral-sh/uv:python3.12-bookworm-slim` — uv sync 로 deps 설치
- runtime: `eclipse-temurin:17-jre-jammy` + apt `python3.12` — JRE+venv 합본

빌드 시 BuildKit 권장: `DOCKER_BUILDKIT=1 docker compose build pdf-parser`. uv cache 마운트가 효과 있음.
