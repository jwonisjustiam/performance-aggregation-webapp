# 기존 Streamlit 앱 수정 배포 가이드

## 1. GitHub에 올릴 파일

기존 앱과 연결된 GitHub 저장소에 아래 파일/폴더를 업로드합니다.

- `app.py`
- `requirements.txt`
- `.streamlit/config.toml`
- `processors/`
- `rules/`
- `services/`
- `README.md`
- `DEPLOYMENT.md`

올리면 안 되는 파일:

- `.env`
- `.venv/`
- `outputs/`
- 실제 업무 엑셀 파일

## 2. GitHub에서 반영하기

1. GitHub 저장소에서 `Add file > Upload files`를 누릅니다.
2. 수정된 파일과 폴더를 업로드합니다.
3. `Commit directly to the main branch`를 선택합니다.
4. `Commit changes`를 누릅니다.

## 3. 기존 Streamlit 링크 확인

1. 기존 Streamlit 앱 링크를 엽니다.
2. 1~3분 기다린 뒤 새로고침합니다.
3. 변경이 안 보이면 `Manage app > Reboot app`을 누릅니다.

## 4. 앱 사용 방법

1. 업무 유형을 선택합니다.
   - 삼성 취합
   - 위클리 취합
   - 상세 취합
2. 위클리/상세 취합이면 유형을 선택합니다.
   - 자동 판정
   - 외장하드
   - 웨어러블
3. 주문 Raw Data `.xlsx` 파일을 업로드합니다.
4. `분석 시작`을 누릅니다.
5. 결과를 확인합니다.
6. `결과 엑셀 다운로드` 버튼으로 파일을 받습니다.

## 5. 문제 해결

- 앱이 켜지지 않음: Streamlit 로그에서 오류를 확인합니다.
- 배포 실패: `requirements.txt` 설치 오류를 확인합니다.
- 업로드 실패: `.xlsx` 파일인지 확인합니다. 현재 `.xls`는 지원하지 않습니다.
- 화면이 안 바뀜: Streamlit 앱을 `Reboot`합니다.
