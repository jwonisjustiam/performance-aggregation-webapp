# 다른 PC에서 이어서 작업하기

## 현재 상태

- 배포 방향을 GitHub + Streamlit Cloud로 변경했습니다.
- 앱 진입점은 `app.py`입니다.
- 위클리 및 삼성 실적 계산 규칙과 엑셀 생성 로직은 유지했습니다.
- 업무 유형은 삼성 취합, 위클리 취합, 워치9 사전판매 판매 실적 취합 3가지입니다.
- 워치9 사전판매 판매 실적 취합은 라이브 시간/회차 규칙 없이 SKU 목록 기준으로 웨어러블과 모바일 ACC를 분리합니다.
- 워치9 사전판매 판매 실적 취합의 SKU 목록은 웹 화면에서 바로 수정할 수 있습니다.
- 삼성 취합의 모델/SKU 시작값과 위클리 취합의 포함 SKU 목록도 웹 화면에서 바로 수정할 수 있습니다.
- 삼성/위클리 취합은 Raw Data 업로드 후 날짜별 시작 시간, 소요 시간을 웹 화면에서 바로 수정할 수 있습니다. 현재 접속 중 임시 저장한 시간 템플릿은 두 업무 유형에서 공통으로 불러옵니다.
- 워치9 사전판매 판매 실적 취합 결과는 웨어러블 파일과 모바일 ACC 파일을 각각 다운로드합니다.
- 2026-07-23 기준 DOCX 규칙을 반영했습니다.
- Docker/시놀로지 전용 파일은 제거했습니다.
- 현재 PC에는 `pytest`가 없어 전체 테스트는 실행하지 못했고, 핵심 스모크 테스트와 문법검사를 통과했습니다.

## 주요 파일

- `app.py`: Streamlit 화면과 업로드/분석/다운로드 흐름
- `requirements.txt`: Streamlit Cloud 설치 의존성
- `.streamlit/config.toml`: Streamlit 기본 설정
- `processors/`: 위클리/삼성 집계 로직
- `rules/`: 회차/모델/예외 규칙
- `services/`: 엑셀 읽기, 저장, 검증
- `DEPLOYMENT.md`: GitHub + Streamlit Cloud 배포 순서

## 다른 PC에서 프로젝트 열기

권장 방식은 GitHub 저장소로 관리하는 것입니다.

1. 이 폴더를 GitHub 저장소에 올립니다.
2. 다른 PC에서 GitHub 저장소를 내려받습니다.
3. 실제 주문 엑셀 파일은 GitHub에 올리지 않습니다.

## 로컬 실행

Windows:

```powershell
cd "동기화된경로\performance-aggregation-webapp"
.\scripts\setup_windows.ps1
.\scripts\run_windows.ps1
```

macOS:

```bash
cd "/동기화된경로/performance-aggregation-webapp"
chmod +x scripts/*.sh
./scripts/setup_macos.sh
./scripts/run_macos.sh
```

접속 주소는 보통 `http://localhost:8501`입니다.

## Streamlit Cloud 배포

`DEPLOYMENT.md` 순서대로 GitHub 저장소를 Streamlit Cloud에 연결합니다.

Main file path는 반드시 `app.py`입니다.

## 보안 주의사항

- `.env`와 실제 주문 엑셀은 공개 Git 저장소나 공유 ZIP에 포함하지 않습니다.
- `~/.codex/auth.json`은 로그인 토큰이므로 PC 간 일반 파일 동기화 대상으로 두지 않습니다.
