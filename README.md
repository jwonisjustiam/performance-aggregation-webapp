# performance-aggregation-webapp

브라우저에서 `.xlsx` 주문 Raw Data를 1개 이상 업로드해 위클리 또는 삼성 방송 실적을 집계하고, 검증된 결과 엑셀을 다운로드하는 Streamlit 웹앱입니다. 일반 사용자는 배포된 웹주소만 사용하며 Python이나 Excel 설치가 필요하지 않습니다.

## 지원 범위

- Python `>=3.11,<3.13`
- `.xlsx` 전용 (`.xls`는 변환 후 업로드)
- Windows와 macOS에서 동일 소스 사용
- Excel 프로그램, COM, VBA, 운영체제 절대경로 미사용
- 암호화 파일은 `1234`, `0000` 순서로만 시도
- 여러 Raw Data 파일을 열 기준으로 통합한 뒤 파일 간 완전 동일 행도 중복 제거
- 위클리 외장하드 파일과 웨어러블 파일은 한 번에 혼합하지 않고 업무 유형별로 나누어 처리

## Windows 개발자 실행

```powershell
cd performance-aggregation-webapp
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
python -m streamlit run app.py
```

또는:

```powershell
.\scripts\setup_windows.ps1
.\scripts\run_windows.ps1
```

## macOS 개발자 실행

```bash
cd performance-aggregation-webapp
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
python -m streamlit run app.py
```

또는:

```bash
chmod +x scripts/*.sh
./scripts/setup_macos.sh
./scripts/run_macos.sh
```

접속 주소는 `http://localhost:8501`입니다.

## 테스트와 샘플

```bash
python scripts/generate_samples.py
python -m pytest
```

샘플 파일은 `samples/weekly`, `samples/samsung`에 생성됩니다.

## Docker

```bash
docker compose up --build
```

접속 주소: `http://localhost:8501`

## 처리 규칙

- 위클리: 파일명 `외장하드`/`웨어러블` 판정, 고유 주문번호 수량, 상품행별 금액 합산, ±8분 회차, 자정 귀속, 전체 회차 유지
- 삼성: 쇼핑라이브 + SM 코드만 포함, 주문번호당 대표 모델 1개, 모델별 실적과 회차별 주문/금액, 검증 시트 생성
- 결과는 저장 후 다시 열어 필수 시트, 빈 시트, Excel 오류값을 검사한 뒤에만 다운로드됩니다.

## 명시적 설정 및 TODO

- 실제 파일에서 열 이름은 별칭으로 탐지하지만, 알려지지 않은 사내 전용 열 이름은 `services/excel_reader.py`의 `ALIASES`에 추가해야 합니다.
- 삼성 작업 대상일은 유효 결제 데이터에서 가장 많이 나타나는 방송일로 결정합니다. 여러 방송일을 한 파일에서 선택 처리해야 한다면 UI 날짜 선택 옵션을 추가해야 합니다.
- 선택 방송 실적표의 기존 표시값 보존은 데이터 계약이 제공되지 않아 현재 기본값을 사용합니다. 해당 파일의 실제 열 구조가 확정되면 명시적 매핑을 추가해야 합니다.
- 암호화 샘플 파일 자체는 저장소에 포함하지 않으며, 암호 처리 순서와 실패 경로를 단위 테스트합니다.
- `.xls`를 서버에서 자동 변환하지 않습니다.

## 보안

업로드와 복호화 파일은 임시 폴더에서 처리하고 종료 시 삭제합니다. 원본 전체를 로그에 기록하거나 traceback을 화면에 노출하지 않습니다.
