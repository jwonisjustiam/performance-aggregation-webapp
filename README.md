# performance-aggregation-webapp

주문 Raw Data `.xlsx`를 업로드해 삼성/위클리/상세 실적을 집계하는 Streamlit 웹앱입니다.

## 주요 기능

- 삼성 실적: 쇼핑라이브 SM 모델 집계, 통합 실적표·회차별 합계·중복 주문 검증 생성
- 위클리 실적: 외장하드/웨어러블 회차별 수량·금액 집계
- 상세 실적: 위클리 규칙을 따르되 주문번호, 상품명, 옵션 관리 코드까지 행 단위로 정리
- `.xlsx` 다중 업로드
- 결과 파일 저장 후 재오픈 검증
- 앱 상단 사용 안내 제공

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

기존 Streamlit 앱 링크를 유지하려면 새 앱을 만들지 말고, 기존 앱과 연결된 GitHub 저장소의 파일을 수정합니다.

1. GitHub 저장소에 수정 파일을 업로드합니다.
2. `Commit directly to the main branch`를 선택합니다.
3. `Commit changes`를 누릅니다.
4. 기존 Streamlit 앱을 새로고침합니다.
5. 바로 반영되지 않으면 Streamlit의 `Manage app > Reboot app`을 실행합니다.

Main file path는 `app.py`입니다.

## GitHub에 올리면 안 되는 파일

- `.env`
- `.venv/`
- 실제 업무 엑셀 원본
- `outputs/`

## 테스트

```bash
python -m pytest
```
