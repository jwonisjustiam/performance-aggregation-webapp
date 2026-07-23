# GitHub + Streamlit Cloud 배포 가이드

## 1. GitHub에 올릴 파일

이 프로젝트 폴더 전체를 GitHub 저장소에 올립니다.

필수 파일:

- `app.py`
- `requirements.txt`
- `.streamlit/config.toml`
- `processors/`
- `rules/`
- `services/`
- `README.md`

올리면 안 되는 파일:

- `.env`
- `.venv/`
- `outputs/`
- 실제 업무 엑셀 파일
- API 키가 들어간 `secrets.toml`

## 2. Streamlit Cloud에서 앱 만들기

1. Streamlit Cloud에 로그인합니다.
2. `New app`을 누릅니다.
3. GitHub 저장소를 선택합니다.
4. Branch는 보통 `main`을 선택합니다.
5. Main file path는 `app.py`로 입력합니다.
6. `Deploy`를 누릅니다.

## 3. 네이버 API Secrets 설정

엑셀 직접 업로드만 쓰면 이 단계는 건너뛰어도 됩니다.

네이버 API 자동 수집을 쓰려면 Streamlit Cloud에서:

1. 배포된 앱의 `Settings`를 엽니다.
2. `Secrets` 메뉴를 엽니다.
3. 아래 값을 입력합니다.

```toml
NAVER_WEARABLE_CLIENT_ID = "발급값"
NAVER_WEARABLE_CLIENT_SECRET = "발급값"
NAVER_EXTERNAL_CLIENT_ID = "발급값"
NAVER_EXTERNAL_CLIENT_SECRET = "발급값"
```

4. 저장 후 앱을 재부팅합니다.

## 4. 앱 사용 방법

1. 업무 유형을 선택합니다.
   - 위클리 실적 취합
   - 삼성 실적 취합
2. 주문 Raw Data `.xlsx` 파일을 업로드합니다.
3. 필요한 경우 위클리 유형을 선택합니다.
   - 자동 판정
   - 외장하드
   - 웨어러블
4. `분석 시작`을 누릅니다.
5. 결과를 확인합니다.
6. `결과 엑셀 다운로드` 버튼으로 파일을 받습니다.

## 5. 문제 해결

- 배포 실패: Streamlit Cloud 로그에서 `requirements.txt` 설치 오류를 확인합니다.
- 앱이 켜지지 않음: Main file path가 `app.py`인지 확인합니다.
- API 수집 실패: Secrets 키 이름과 네이버 커머스 API 권한을 확인합니다.
- 업로드 실패: `.xlsx` 파일인지 확인합니다. 현재 `.xls`는 지원하지 않습니다.
