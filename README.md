# MArchitect
<img width="800" height="408" alt="created-gif" src="https://github.com/user-attachments/assets/2b240789-9bd2-4d9e-a0e1-440dd9bad566" />

도커 기반 마인크래프트 서버 제어 웹 애플리케이션

## 상세
저는 마인크래프트도 좋아하고, 컴퓨터 하드웨어도 좋아하고, 개발도 좋아합니다. 그래서 마인크래프트 서버를 주로 제가 여는데, 리눅스 등의 환경에서 마인크래프트 서버를 실행하는건 보통 번거로운 일이 아닙니다.

그래서 귀찮은 과정들과 높은 진입장벽 등의 문제를 해결하기 위해 웹 GUI 환경에서 쉽게 서버를 제어할 수 있는 프로젝트를 만들게 되었습니다.

## 주요 기능
- 접근 코드 기반 관리자/사용자 로그인
- Paper, Fabric, NeoForge 서버 생성과 초기 구성
- 서버 시작·정지·강제 종료 및 실시간 콘솔 확인
- 월드, 모드, 플러그인, 설정 파일 탐색·업로드·다운로드·삭제
- Temurin Linux Java 런타임 다운로드와 관리
- 시스템 및 인스턴스 리소스 대시보드

## 시작하기
1. 예시 환경 파일을 복사합니다.

   ```powershell
   Copy-Item .env.example .env
   ```

2. `.env`의 `MARCHITECT_INITIAL_ADMIN_CODE`를 충분히 긴 고유 코드로 변경합니다.( 관리자용 접근 코드 )

3. 컨테이너를 빌드하고 실행합니다.

   ```powershell
   docker compose up -d --build
   ```

4. 브라우저에서 `http://localhost:5173`으로 접속합니다.

새 데이터베이스를 처음 만들 때만 `.env`의 값이 적용됩니다. 이후에는 관리자 화면에서 관리자 코드 변경과 사용자 코드 발급/삭제를 관리합니다.

이미 `data/marchitect.sqlite3`가 존재한다면 `.env`의 초기 코드를 바꿔도 기존 코드는 바뀌지 않습니다.

백엔드 API는 호스트의 `http://localhost:8800`에 공개됩니다. 프론트엔드는 `/api` 경로를 통해 백엔드에 연결됩니다.

## 데이터 보관 위치
실행 중 만들어지는 인스턴스, 월드, 로그, SQLite 데이터베이스는 `data/`에 저장됩니다. Java 런타임은 `backend/JAVA/`에 저장됩니다. 두 경로는 개인 서버 데이터이므로 Git에 포함하지 않습니다.

컨테이너를 다시 만들거나 이미지를 갱신해도 두 경로를 삭제하지 않는 한 데이터는 유지됩니다. 백업할 때는 `data/`와 필요하다면 `backend/JAVA/`를 별도로 보관하세요.

## 운영 배포

운영 환경에서는 개발용 `docker-compose.yml` 대신 아래 명령을 사용합니다. 이 구성은 소스 폴더를 마운트하거나 자동 새로고침을 사용하지 않으며, 프론트엔드는 Nginx가 제공합니다.

```powershell
docker compose -f docker-compose.production.yml up -d --build
```

웹 화면은 `.env`의 `MARCHITECT_WEB_PORT`(기본 `5173`)로 접속합니다. Minecraft 서버는 `MARCHITECT_MINECRAFT_PORT_RANGE` 안에서 인스턴스별로 서로 다른 포트를 사용해야 합니다. 기본 범위는 `25565-25665`입니다.

## 라이선스
이 프로젝트는 [MIT License](LICENSE)를 사용합니다.
