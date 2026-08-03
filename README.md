# performance-aggregation-webapp

네이버·11번가·지마켓·옥션·카카오 주문 Raw Data `.xlsx`/`.xls`를 업로드해 삼성/위클리/워치9 사전판매 실적을 집계하는 Streamlit 웹앱입니다.

## 주요 기능

- 삼성 실적: 쇼핑라이브 SM 모델 집계, 통합 실적표·회차별 합계·중복 주문 검증 생성
- 위클리 실적: 외장하드/웨어러블 회차별 수량·금액 집계
- 워치9 사전판매 판매 실적: 화면에서 수정 가능한 SKU 목록 기준으로 웨어러블/모바일 ACC를 분리하고 각각 별도 파일로 다운로드
- 삼성/위클리/워치9 업무 유형별 분류 규칙을 웹 화면에서 직접 수정 가능
- 삼성/위클리 Raw Data 업로드 후 파일명의 다운로드 날짜·시간을 무시하고, 웹에서 선택한 작업 대상 날짜 범위만 사용
- 위클리 유형은 웹에서 `외장하드` 또는 `웨어러블`을 선택할 수 있어 파일명에 유형을 넣지 않아도 됨
- 현재 접속 중 임시 저장한 시간 템플릿은 삼성/위클리 취합에서 공통으로 불러오기 가능
- 쇼핑몰별 열 이름을 공통 열로 자동 변환하고 원본/수정본 시트의 중복 주문행 제거
- `결제일시`, `예약결제완료일시`, `주문일시`, `결제일` 날짜 열과 `YYYY.MM.DD` 형식 인식
- 옵션 코드 열이 없거나 비어 있으면 상품명에서 `SM-L350N` 같은 SKU 자동 추출
- `.xlsx`/`.xls` 다중 업로드 및 비밀번호 `0000`/`1234` 자동 시도
- 쇼핑라이브 구분 열이 없는 파일은 업로드 행 전체를 후보로 사용하고 화면에 경고 표시
- 결과 파일 저장 후 재오픈 검증
- 접기/펼치기 가능한 사용 안내 제공

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
