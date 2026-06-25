# 배포 가이드

일반 사용자는 배포된 URL만 사용합니다. 업무 원본에 개인정보나 회사 기밀이 포함될 수 있으므로 배포 위치의 저장·로그·접근 통제를 먼저 검토해야 합니다.

## 1. Streamlit Community Cloud

샘플 테스트 또는 개인용에 적합합니다.

1. `performance-aggregation-webapp` 폴더 내용을 GitHub 저장소 루트에 올립니다.
2. `https://share.streamlit.io`에서 **Create app**을 선택합니다.
3. GitHub 저장소, 배포 브랜치, 진입 파일 `app.py`를 지정합니다.
4. Advanced settings에서 Python `3.11` 또는 `3.12`를 선택합니다.
5. Deploy를 누른 뒤 생성된 `https://...streamlit.app` 주소를 사용자에게 공유합니다.

Community Cloud는 GitHub 저장소 기반입니다. 원본 업무 데이터는 저장소에 올리지 말고 웹 화면에서만 업로드합니다.

## 2. Render

회사 업무용 외부 배포의 초기 선택지입니다.

- Render Dashboard에서 **New > Web Service**를 선택하고 GitHub 저장소를 연결합니다.
- Runtime: `Python 3`
- Build command: `pip install -r requirements.txt`
- Start command: `streamlit run app.py --server.address 0.0.0.0 --server.port $PORT`
- Health Check Path: `/_stcore/health`
- 배포 후 생성되는 `https://...onrender.com` 주소를 사용자에게 공유합니다.
- HTTPS, 인증, 접근 IP, 로그 보존 기간을 회사 정책에 맞게 설정합니다.

## 3. Docker 서버

보안 중요 자료에는 사내 서버 또는 회사 클라우드의 전용 환경을 권장합니다.

```bash
docker compose up --build
```

기본 포트는 `8501`입니다. 운영에서는 reverse proxy, HTTPS, SSO/VPN, 업로드 크기 제한, 컨테이너 로그 제한, 취약점 스캔을 적용합니다.

## 4. 회사 내부/클라우드 서버 고려사항

- 외부 인터넷 전송 금지 여부와 데이터 처리 지역
- 사용자 인증, 권한 분리, 접속 감사
- 임시 디스크 암호화와 자동 삭제
- 백업 대상에서 업로드/임시 파일 제외
- Streamlit 업로드 크기와 동시 사용자 메모리 산정
- OS 및 Python 보안 업데이트
- 오류 로그에 원본 셀 값이 남지 않는지 점검
- 배포 전 샘플 및 익명화 실제 구조 파일로 회귀 테스트

## 추천

- 샘플 테스트/개인용: Streamlit Community Cloud
- 회사 업무용 외부 배포: Render
- 보안 중요 자료: Docker 기반 사내 서버 또는 회사 클라우드
