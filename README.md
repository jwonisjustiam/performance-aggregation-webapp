# performance-aggregation-webapp

네이버 주문 Raw Data `.xlsx`를 업로드하거나 네이버 커머스 API에서 가져와 위클리/삼성 방송 실적을 집계하는 Streamlit 웹앱입니다.

## 주요 기능

- 위클리 실적: 외장하드/웨어러블 회차별 수량·금액 집계
- 삼성 실적: 쇼핑라이브 SM 모델 집계, 통합 실적표·회차별 합계·중복 주문 검증 생성
- `.xlsx` 다중 업로드
- 네이버 커머스 API 계정별 수집
- 결과 파일 저장 후 재오픈 검증

## 로컬 실행

Windows:

```powershell
cd "C:\Users\visit\Documents\web app\performance-aggregation-webapp"
.\scripts\setup_windows.ps1
.\scripts\run_windows.ps1
```

macOS/Linux:

```bash
chmod +x scripts/*.sh
./scripts/setup_macos.sh
./scripts/run_macos.sh
```

실행 후 브라우저에 표시되는 주소로 접속합니다. 보통 아래 주소입니다.

```text
http://localhost:8501
```

## Streamlit Cloud 배포

1. 이 폴더를 GitHub 저장소에 올립니다.
2. Streamlit Community Cloud에서 `Create app`을 누릅니다.
3. GitHub 저장소를 선택합니다.
4. Main file path는 `app.py`로 지정합니다.
5. 배포합니다.

네이버 API 자동 수집을 쓸 경우 Streamlit Cloud의 `App settings > Secrets`에 아래 값을 넣습니다.

```toml
NAVER_WEARABLE_CLIENT_ID = "발급값"
NAVER_WEARABLE_CLIENT_SECRET = "발급값"
NAVER_EXTERNAL_CLIENT_ID = "발급값"
NAVER_EXTERNAL_CLIENT_SECRET = "발급값"
```

엑셀 직접 업로드만 사용할 경우 Secrets 설정은 없어도 됩니다.

## GitHub에 올리면 안 되는 파일

- `.env`
- `.venv/`
- 실제 업무 엑셀 원본
- Streamlit Secrets 실제 값

## 테스트

```bash
python -m pytest
```
