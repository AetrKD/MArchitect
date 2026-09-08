# MArchitect ( ENG )

<img width="800" height="408" alt="MArchitect preview" src="https://github.com/user-attachments/assets/2b240789-9bd2-4d9e-a0e1-440dd9bad566" />

A web-based Minecraft server management application.

## Overview

Managing a Minecraft server from a Linux command line can be inconvenient, especially for people who are new to server administration. MArchitect provides a graphical interface for creating, configuring, starting, monitoring, and managing Minecraft server instances.

## Key features

- Access-code authentication with administrator and user roles
- Paper, Fabric, and NeoForge server creation and initial setup
- Server start, graceful stop, force stop, and real-time console monitoring
- File browsing, upload, download, and deletion for worlds, mods, plugins, logs, and configuration files
- Temurin Linux Java runtime download and management
- System and per-instance resource dashboards

## Getting started

1. Copy the example environment file.

   ```powershell
   Copy-Item .env.example .env
   ```

2. Set `MARCHITECT_INITIAL_ADMIN_CODE` in `.env` to a long, unique administrator access code.

3. Build and start the development containers.

   ```powershell
   docker compose up -d --build
   ```

4. Open `http://localhost:<MARCHITECT_WEB_PORT>` in a browser (default: `5173`).

The initial codes in `.env` are used only when the SQLite database is created for the first time. Afterwards, manage the administrator code and issue or delete user codes from the administrator screens.

If `data/marchitect.sqlite3` already exists, changing the initial codes in `.env` does not replace the existing codes.

The development backend API is published at `http://localhost:8800`. The frontend connects to it through the `/api` path.

`MARCHITECT_WEB_PORT` controls the host-side web port in both development and
production Compose files. After changing it, recreate the containers so Docker
applies the new port mapping.

### Custom domains

Sign in as an administrator using the server IP address, then open **Server
settings → Custom domains**. Enter one domain per line without a scheme,
port, or path. Only administrators can read or save this list. Domains and IP addresses persist in the SQLite `settings` table under
`allowed_hosts`. The backend exports `data/frontend-settings/domains.json`
for Vite and recreates it from the DB on startup. No `.env` domain setting is needed.

The development frontend mounts only this settings directory read-only and
reloads its host list automatically within a few seconds. Connections may
briefly reconnect. Removing a domain revokes development access through it;
IP and localhost access remain available for recovery. Recreate the frontend
once after this update to install the new mount: `docker compose up -d --build
--force-recreate frontend` (run this command on one line).

Production Nginx already accepts custom domains; this list is not a production
access-control mechanism. DNS must point to your server, and your HTTPS proxy
must forward traffic and WebSockets to the configured web port.
### Data directory ownership

At startup, the backend first tries to assign the `/data` and `/java`
mounts to `MARCHITECT_UID:MARCHITECT_GID` (default: `1000:1000`) and runs as
that user when the mounts are writable. Some bind-mount implementations
(rootless Docker, Docker Desktop, or root-squashed network filesystems) reject
`chown`; in that case the entrypoint verifies actual write access and falls
back to the current container user instead of exiting before SQLite can create
`data/marchitect.sqlite3`. Set both IDs in `.env` from `id -u` and `id -g`.
For an existing deployment with root-owned files inside those directories,
migrate them once:

```bash
sudo chown -R "$(id -u):$(id -g)" data backend/JAVA
```

### Minecraft server ports

Minecraft server processes are children of the backend container, so their
listening ports must be published by Docker. Both Compose files forward the
range in `MARCHITECT_MINECRAFT_PORT_RANGE` (default: `25565-25665`) from the
host to the backend container.

Marchitect does not choose, reserve, validate, or rewrite instance ports. Set
`server-port` yourself in each instance's `server.properties`; use a port in
that published range, then restart the instance. For example, use
`server-port=25565` for one server and `server-port=25566` for another. Players
connect to `HOST_IP:server-port`.

## Persistent data

Created instances, worlds, logs, and the SQLite database are stored in `data/`. Downloaded Java runtimes are stored in `backend/JAVA/`. These directories contain local server data and are excluded from Git.

Recreating containers or updating images does not remove this data as long as these directories remain in place. Back up `data/`, and optionally `backend/JAVA/`, before moving or updating a deployment.

## Production deployment

For production, use `docker-compose.production.yml` instead of the development `docker-compose.yml`. This configuration does not mount source folders or enable hot reload, and serves the frontend with Nginx.

```powershell
docker compose -f docker-compose.production.yml up -d --build
```

Open the web UI on the port set by `MARCHITECT_WEB_PORT` in `.env` (default: `5173`). Set each Minecraft instance's `server-port` manually to a port within `MARCHITECT_MINECRAFT_PORT_RANGE` (default: `25565-25665`).

## License

This project is licensed under the [MIT License](LICENSE).

---

# MArchitect ( 한국어 )

웹 기반 마인크래프트 서버 관리 애플리케이션입니다.

## 개요

리눅스 명령줄에서 마인크래프트 서버를 관리하는 일은, 서버 관리에 익숙하지 않은 사람에게 불편할 수 있습니다. MArchitect는 마인크래프트 서버 인스턴스의 생성, 설정, 시작, 모니터링, 관리를 위한 그래픽 인터페이스를 제공합니다.

## 주요 기능

- 접근 코드 기반의 관리자·사용자 역할 로그인
- Paper, Fabric, NeoForge 서버 생성 및 초기 구성
- 서버 시작, 정상 종료, 강제 종료 및 실시간 콘솔 확인
- 월드, 모드, 플러그인, 로그, 설정 파일 탐색·업로드·다운로드·삭제
- Temurin Linux Java 런타임 다운로드 및 관리
- 시스템 및 인스턴스별 리소스 대시보드

## 시작하기

1. 예시 환경 파일을 복사합니다.

   ```powershell
   Copy-Item .env.example .env
   ```

2. `.env` 파일의 `MARCHITECT_INITIAL_ADMIN_CODE`를 충분히 길고 고유한 관리자 접근 코드로 변경합니다.

3. 개발용 컨테이너를 빌드하고 실행합니다.

   ```powershell
   docker compose up -d --build
   ```

4. 브라우저에서 `http://localhost:5173`으로 접속합니다.

`.env`의 초기 접근 코드는 SQLite 데이터베이스가 처음 생성될 때만 적용됩니다. 이후에는 관리자 화면에서 관리자 코드 변경과 사용자 코드 발급·삭제를 관리할 수 있습니다.

`data/marchitect.sqlite3`가 이미 존재한다면 `.env`의 초기 코드를 변경해도 기존 코드는 바뀌지 않습니다.

개발 환경의 백엔드 API는 `http://localhost:8800`에 공개되며, 프론트엔드는 `/api` 경로를 통해 백엔드에 연결됩니다.

### 데이터 디렉터리 권한

백엔드는 시작할 때 `/data`와 `/java`를 먼저
`MARCHITECT_UID:MARCHITECT_GID`(기본값 `1000:1000`)로 사용할 수 있도록
조정한 뒤 해당 사용자로 실행합니다. rootless Docker, Docker Desktop,
root-squash가 적용된 네트워크 파일시스템처럼 bind mount가 `chown`을
허용하지 않는 환경에서는 실제 쓰기 가능 여부를 검사하고, SQLite가
`data/marchitect.sqlite3`를 만들기도 전에 종료되지 않도록 현재 컨테이너
사용자로 실행을 이어갑니다. Linux에서는 `.env`의 UID/GID를
`id -u`, `id -g` 결과와 맞추는 것을 권장합니다.

기존 배포에 root 소유 파일이 남아 있다면 한 번만 다음 명령으로
정리할 수 있습니다.

```bash
sudo chown -R "$(id -u):$(id -g)" data backend/JAVA
```

## 데이터 보존 위치

생성한 인스턴스, 월드, 로그, SQLite 데이터베이스는 `data/`에 저장됩니다. 다운로드한 Java 런타임은 `backend/JAVA/`에 저장됩니다. 이 경로에는 개인 서버 데이터가 포함되므로 Git에서 제외됩니다.

컨테이너를 다시 만들거나 이미지를 업데이트해도 이 폴더를 유지하면 데이터는 보존됩니다. 배포 환경을 옮기거나 업데이트하기 전에는 `data/`와 필요하다면 `backend/JAVA/`를 백업하세요.

## 운영 배포

운영 환경에서는 개발용 `docker-compose.yml` 대신 `docker-compose.production.yml`을 사용합니다. 이 구성은 소스 폴더를 마운트하거나 자동 새로고침을 사용하지 않으며, 프론트엔드는 Nginx가 제공합니다.

```powershell
docker compose -f docker-compose.production.yml up -d --build
```

웹 화면은 `.env`의 `MARCHITECT_WEB_PORT` 포트(기본값: `5173`)로 접속합니다. 마인크래프트 인스턴스는 `MARCHITECT_MINECRAFT_PORT_RANGE` 범위 안에서 서로 다른 포트를 사용해야 합니다. 기본 범위는 `25565-25665`입니다.

## 라이선스

이 프로젝트는 [MIT License](LICENSE)를 사용합니다.
