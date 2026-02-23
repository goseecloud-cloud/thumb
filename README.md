# 썸네일 생성기 서비스 (FastAPI)

이미지 URL 또는 업로드 파일로 썸네일을 생성하는 서비스입니다.
모든 결과는 항상 로컬 파일(`output/`)로 저장되고 로컬 URL로 반환됩니다.

## 🚀 Docker로 실행

### 빌드 및 실행
```bash
docker-compose up --build
```

### 접근 주소
- **API 루트(기존 호환)**: http://localhost:8001
- **고객용 웹 서비스**: http://localhost:8001/service
- **API 정보**: http://localhost:8001/api
- **Swagger 문서**: http://localhost:8001/docs
- **헬스체크**: http://localhost:8001/health

## 📡 API 엔드포인트

### 1) URL로 썸네일 생성
**POST** `/generate`

```json
{
  "url": "https://example.com/image.jpg",
  "title": "첫 명품시계 천만원대 뭐실까?",
  "output_type": "external"
}
```

**응답:**
```json
{
  "success": true,
  "message": "썸네일이 성공적으로 생성되었습니다.",
  "thumbnail_url": "http://localhost:8001/output/output_thumbnail_xxx.png",
  "local_path": "/app/output/xxx.png",
  "filename": "output_thumbnail_xxx.png"
}
```

`output_type` (호환용)
- 현재는 값과 무관하게 항상 `output/` 로컬 파일 저장 + 로컬 URL 반환으로 동작

### 2) 파일 업로드로 썸네일 생성
**POST** `/generate-file`

- Content-Type: `multipart/form-data`
- 필드:
  - `file`: 이미지 파일
  - `title`: 썸네일 텍스트
  - `output_type`: 호환용(생략 가능, 동작은 항상 local)

### 3) 외부 업로드 전용 엔드포인트 (호환)
**POST** `/generate-external`

- 과거 호환을 위해 유지되며, 현재는 `/generate`와 동일하게 로컬 파일 저장으로 처리

### 4) 서버 상태
**GET** `/health`

## 💻 사용 예시

### curl 요청
```bash
curl -X POST "http://localhost:8001/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://picsum.photos/800/600",
    "title": "첫 명품시계 천만원대 뭐실까? 오메가 문위치 사야하는 이유",
    "output_type": "external"
  }'
```

### 파일 업로드 요청
```bash
curl -X POST "http://localhost:8001/generate-file" \
  -F "file=@./sample.jpg" \
  -F "title=업로드 이미지 썸네일 테스트" \
  -F "output_type=local"
```

### JavaScript 요청
```javascript
const response = await fetch('http://localhost:8001/generate', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    url: 'https://picsum.photos/800/600',
    title: '첫 명품시계 천만원대 뭐실까?',
    output_type: 'local'
  })
});

const result = await response.json();
console.log('썸네일 URL:', result.thumbnail_url);
```

## 🎨 기능

- ✅ **180pt 대형 폰트** (페이퍼로지 볼드)
- ✅ **자동 줄바꿈** 및 다중 라인 지원
- ✅ **43% 어두운 필터**
- ✅ **8px 하얀 테두리**
- ✅ **1080x1080 정방형** 크기
- ✅ **외부 서버 업로드** 지원
- ✅ **업로드 파일 입력** 지원
- ✅ **웹 UI 서비스 화면** 지원
- ✅ **RESTful API**
- ✅ **Docker 컨테이너**
- ✅ **항상 로컬 파일 저장/반환**

## 📁 파일 구조

```
├── fastapi_server.py    # FastAPI 서버 + 웹 UI
├── main.py              # 썸네일 생성 로직
├── Dockerfile           # Docker 이미지
├── docker-compose.yml   # Docker Compose
├── requirements.txt     # Python 의존성
├── fonts/               # 폰트 파일 (Paperlogy-7Bold.ttf)
├── output/              # 생성된 이미지
└── README.md           # 이 파일
```

## ⚙️ 환경 변수

- `PYTHONPATH`: /app
- `PYTHONUNBUFFERED`: 1

## 🔧 트러블슈팅

1. **폰트 문제**: `fonts/Paperlogy-7Bold.ttf` 파일이 있는지 확인
2. **포트 충돌**: `docker-compose.yml`에서 포트 변경
3. **권한 문제**: `output/` 폴더 권한 확인
4. **결과 확인**: 생성 결과는 `output/` 폴더와 `/output/...` URL에서 확인할 수 있습니다.