# MArchitect

Docker 기반 Minecraft 서버 인스턴스 관리 도구입니다. Paper, Fabric, NeoForge 및 사용자 업로드 JAR을 지원하며, 서버 콘솔·파일·월드·Java 런타임을 한 화면에서 관리합니다.

## 주요 기능

- 접근 코드 기반 관리자/사용자 로그인
- Paper, Fabric, NeoForge 서버 생성과 초기 구성
- 서버 시작·정지·강제 종료 및 실시간 콘솔 확인
- 월드, 모드, 플러그인, 설정 파일 탐색·업로드·다운로드·삭제
- Temurin Linux Java 런타임 다운로드와 관리
- 시스템 및 인스턴스 리소스 대시보드
- 한국어/영어와 다크/라이트 테마

## 시작하기

필수 프로그램: Docker Desktop과 Docker Compose

1. 예시 환경 파일을 복사합니다.

   ```powershell
   Copy-Item .env.example .env
   ```

2. `.env`의 `MARCHITECT_INITIAL_ADMIN_CODE`를 충분히 긴 고유 코드로 변경합니다.

3. 컨테이너를 빌드하고 실행합니다.

   ```powershell
   docker compose up -d --build
   ```

4. 브라우저에서 `http://localhost:5173`으로 접속합니다.

백엔드 API는 호스트의 `http://localhost:8800`에 공개됩니다. 프론트엔드는 `/api` 경로를 통해 백엔드에 연결됩니다.

## 데이터 보관 위치

실행 중 만들어지는 인스턴스, 월드, 로그, SQLite 데이터베이스는 `data/`에 저장됩니다. Java 런타임은 `backend/JAVA/`에 저장됩니다. 두 경로는 개인 서버 데이터이므로 Git에 포함하지 않습니다.

컨테이너를 다시 만들거나 이미지를 갱신해도 두 경로를 삭제하지 않는 한 데이터는 유지됩니다. 백업할 때는 `data/`와 필요하다면 `backend/JAVA/`를 별도로 보관하세요.

## 초기 접근 코드

새 데이터베이스를 처음 만들 때만 `.env`의 값이 적용됩니다. 이후에는 관리자 화면에서 관리자 코드 변경과 사용자 코드 발급/삭제를 관리합니다.

이미 `data/marchitect.sqlite3`가 존재한다면 `.env`의 초기 코드를 바꿔도 기존 코드는 바뀌지 않습니다.

## 개발 확인

```powershell
npm.cmd run lint --prefix frontend
npm.cmd run build --prefix frontend
```

## 라이선스

이 프로젝트는 [MIT License](LICENSE)를 사용합니다.
