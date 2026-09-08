# MArchitect

[한국어](#한국어) · [English](#english)

<img width="800" height="408" alt="MArchitect web console / MArchitect 웹 콘솔" src="https://github.com/user-attachments/assets/2b240789-9bd2-4d9e-a0e1-440dd9bad566" />

## 한국어

MArchitect는 브라우저에서 마인크래프트 게임 서버를 만들고 관리하는 프로그램입니다. 서버 시작과 종료, 설정 변경, 월드 백업, 로그 확인을 한곳에서 할 수 있습니다.

### 주요 기능

- Paper, Fabric, NeoForge 서버 생성 또는 서버 JAR 파일 업로드
- 게임 서버 시작·종료, 명령어 전송, 실시간 로그 확인
- 월드·모드·플러그인·설정 파일 업로드, 다운로드, 삭제
- 게임 서버에 필요한 Java 설치 및 관리
- CPU, 메모리, 디스크, 네트워크 사용량 확인
- 관리자 접근 코드 변경, 사용자 접근 코드 발급·삭제

### 설치하고 접속하기

Docker와 Docker Compose가 설치되어 있어야 합니다. Windows에서는 Docker Desktop을 실행해 두세요. 아래 명령은 다운로드한 MArchitect 폴더에서 실행합니다.

1. `.env.example`을 복사해 `.env` 파일을 만드세요.

   Ubuntu/Linux:

   ```bash
   cp .env.example .env
   ```

   Windows PowerShell:

   ```powershell
   Copy-Item .env.example .env
   ```

2. `.env`의 `MARCHITECT_INITIAL_ADMIN_CODE`를 본인만 아는 긴 접근 코드로 바꾸세요. Linux에서는 `id -u`, `id -g`로 확인한 값을 각각 `MARCHITECT_UID`, `MARCHITECT_GID`에 입력하세요.
3. MArchitect를 실행하세요. 처음에는 필요한 파일을 내려받으므로 시간이 걸릴 수 있습니다.

   ```bash
   docker compose -f docker-compose.production.yml up -d --build
   ```

4. 같은 컴퓨터에서는 `http://localhost:5173`, 다른 컴퓨터에서는 `http://서버-IP:5173`에 접속하세요. 웹 포트를 바꿨다면 `5173` 대신 설정한 번호를 사용하세요. `.env`에 입력한 관리자 접근 코드로 로그인하면 됩니다.

### 처음 로그인한 뒤

**Java 관리**에서 게임 버전에 맞는 Java를 설치하고 **게임 서버 목록 → 게임 서버 만들기**에서 서버를 추가하세요. 서버의 실행 설정에서 사용할 Java와 메모리를 확인한 뒤 시작하세요. 실행에 실패하면 서버 콘솔에서 오류를 확인할 수 있습니다.

**서버 설정**에서는 관리자 접근 코드와 접속 주소를 관리합니다. **사용자 관리**에서는 다른 사람에게 전달할 접근 코드를 발급하거나 삭제할 수 있습니다. 사용자 코드 전체는 발급 직후에만 표시되므로 안전한 곳에 보관하세요. 사용자는 게임 서버 상태를 확인하고 시작·종료할 수 있으며, 관리 기능은 관리자에게만 표시됩니다.

### 설치 설정 안내

| `.env` 항목 | 용도 | 기본값 / 입력 방법 |
|---|---|---|
| `MARCHITECT_INITIAL_ADMIN_CODE` | 최초 관리자 접근 코드 | 반드시 직접 입력 |
| `MARCHITECT_INITIAL_USER_CODE` | 사용자 접근 코드 자동 생성 | 선택 사항. 웹에서 발급하려면 비워 두세요 |
| `MARCHITECT_WEB_PORT` | 웹 콘솔 접속 포트 | `5173` |
| `MARCHITECT_MINECRAFT_PORT_RANGE` | 게임 접속에 사용할 포트 범위 | `25565-25665` |
| `MARCHITECT_UID`, `MARCHITECT_GID` | Linux 데이터 폴더를 사용할 사용자·그룹 | 각각 `1000`. `id -u`, `id -g`로 확인 |

관리자 코드는 이후 **서버 설정**에서 바꾸세요. `.env`를 수정해도 저장된 관리자 코드는 바뀌지 않습니다. 다만 실행 설정에서 이 항목을 요구하므로 `.env`에서 삭제하지 마세요. 초기 사용자 코드를 설정하면 사용자 코드가 하나도 없을 때 해당 코드가 생성됩니다.

웹 포트, 게임 포트 범위, UID/GID를 변경한 뒤에는 위 실행 명령을 다시 실행하세요. 게임 서버가 실행 중이라면 먼저 웹 콘솔에서 정상 종료하세요.

### 게임 접속 포트

각 게임 서버의 설정 화면에서 `server.properties`의 `server-port`를 지정하세요. 동시에 실행할 서버는 서로 다른 포트를 사용해야 합니다. 예를 들어 첫 서버는 `25565`, 두 번째 서버는 `25566`을 사용하고, 플레이어는 `서버-IP:포트`로 접속합니다.

포트는 `.env`에 지정한 공개 범위 안에서 선택하세요. 범위를 벗어난 포트를 사용하려면 공개 범위도 바꾸고 MArchitect 실행 명령을 다시 실행해야 합니다. 게임 포트를 바꾼 서버는 재시작하세요. 외부 접속에는 공유기의 포트 전달과 서버 방화벽 설정도 필요할 수 있습니다.

### 도메인으로 접속하기

도메인의 DNS가 서버를 가리키도록 설정하고 웹 콘솔의 포트로 연결하세요. HTTPS를 사용하려면 인증서와 HTTPS 연결을 처리할 프록시를 별도로 설정해야 합니다. 실시간 콘솔을 사용하려면 프록시에서 WebSocket 연결도 허용하세요.

**서버 설정 → 접속 주소 설정**에서 도메인과 IP 주소를 저장할 수 있습니다. 한 줄에 하나씩 입력하고 `https://`, 포트, 경로는 제외하세요. 저장된 주소는 재시작 후에도 유지됩니다. 이 메뉴는 DNS나 인증서를 설정하지 않으며, 접속자를 제한하는 기능도 아닙니다. 운영용 실행에서는 별도 등록 없이 도메인으로 접속할 수 있습니다.

### 업데이트와 백업

게임 서버를 정상 종료하고 진행 중인 다운로드·설치가 끝날 때까지 기다리세요. 일관된 백업을 위해 MArchitect도 정지한 뒤 `.env`와 `data/` 폴더를 복사해 보관하세요. 필요하면 다운로드한 Java가 있는 `backend/JAVA/`도 함께 보관하세요.

```bash
docker compose -f docker-compose.production.yml stop
```

백업을 마쳤다면 최신 코드를 받고 다시 실행하세요.

```bash
git pull
docker compose -f docker-compose.production.yml up -d --build
```

게임 서버·월드·로그·접근 코드·접속 주소는 `data/`에 보관됩니다. 이 폴더와 `.env`를 유지하면 업데이트 후에도 설정과 데이터가 남습니다. `git pull`이 로컬 변경 때문에 중단되면 수정한 파일부터 백업하세요.

### 실행이나 접속에 문제가 있다면

다음 명령으로 실행 상태와 최근 오류를 확인하세요. 도움을 요청할 때는 오류 문구를 함께 전달하되 접근 코드와 개인 정보는 공유하지 마세요. 데이터 파일이 만들어지지 않더라도 기존 `data/` 폴더를 삭제하지 말고 로그와 폴더 쓰기 권한을 먼저 확인하세요.

```bash
docker compose -f docker-compose.production.yml ps -a
docker compose -f docker-compose.production.yml logs --tail=100 backend frontend
```

### 소스를 직접 수정하는 경우

개발용 구성은 `docker compose up -d --build`로 실행할 수 있습니다. 이 구성에서 도메인이 차단되면 IP 주소로 로그인해 **접속 주소 설정**에 등록하세요. 변경은 몇 초 안에 자동 반영되며 웹 연결이 잠시 끊길 수 있습니다. 도메인 목록을 비워도 IP 주소로는 계속 접속할 수 있습니다. 기존 개발용 설치에 이 기능을 적용할 때도 위 실행 명령을 다시 실행하세요.

## English

MArchitect lets you create and manage Minecraft game servers from your browser. Start and stop servers, change settings, back up worlds, and read logs in one place.

### Features

- Create Paper, Fabric, or NeoForge servers, or upload your own server JAR
- Start and stop game servers, send commands, and view live logs
- Upload, download, and delete worlds, mods, plugins, and configuration files
- Install and manage Java versions for your game servers
- Monitor CPU, memory, disk, and network usage
- Change the administrator access code and issue or delete user access codes

### Install and sign in

Install Docker and Docker Compose first. On Windows, keep Docker Desktop running. Run these commands from your downloaded MArchitect folder.

1. Copy `.env.example` to `.env`.

   Ubuntu/Linux:

   ```bash
   cp .env.example .env
   ```

   Windows PowerShell:

   ```powershell
   Copy-Item .env.example .env
   ```

2. Set `MARCHITECT_INITIAL_ADMIN_CODE` in `.env` to a long, private access code. On Linux, set `MARCHITECT_UID` and `MARCHITECT_GID` to the values returned by `id -u` and `id -g`.
3. Start MArchitect. The first run may take a while to download the required files.

   ```bash
   docker compose -f docker-compose.production.yml up -d --build
   ```

4. Open `http://localhost:5173` on the same computer, or `http://SERVER-IP:5173` from another computer. If you changed the web port, replace `5173` with that number. Sign in with the administrator code you entered in `.env`.

### After signing in

Install a compatible Java version in **Java management**, then select **Game servers → Create game server**. Check the server's Java and memory settings before starting it. If it fails to start, check its console for errors.

Use **Server settings** to manage your administrator code and connection addresses. Use **User management** to issue or delete access codes for other people. The full user code is shown only when it is issued; keep it somewhere safe. Users can view game server status and start or stop servers. Management tools are available only to administrators.

### Installation settings

| `.env` setting | Purpose | Default / instructions |
|---|---|---|
| `MARCHITECT_INITIAL_ADMIN_CODE` | First administrator code | Required; choose your own |
| `MARCHITECT_INITIAL_USER_CODE` | Automatically create a user code | Optional; leave empty to issue codes in the web console |
| `MARCHITECT_WEB_PORT` | Web console port | `5173` |
| `MARCHITECT_MINECRAFT_PORT_RANGE` | Available game connection ports | `25565-25665` |
| `MARCHITECT_UID`, `MARCHITECT_GID` | Linux user and group for data folders | `1000` each; check with `id -u` and `id -g` |

After setup, change your administrator code in **Server settings**. Editing `.env` does not replace the saved code. Keep the initial administrator setting in `.env`, as it is still required to start MArchitect. If an initial user code is set, it is created whenever there are no user codes.

After changing ports or UID/GID, run the start command above again. Stop any running game servers from the web console first.

### Game connection ports

In each game's settings, set `server-port` in `server.properties`. Servers running at the same time need different ports. For example, use `25565` for the first and `25566` for the second. Players connect to `SERVER-IP:PORT`.

Choose a port within the range set in `.env`. To use a port outside that range, update the range and run the MArchitect start command again. Restart the game server after changing its port. External connections may also require router port forwarding and server firewall settings.

### Connect with a domain

Point your domain's DNS to the server and route traffic to the web console port. HTTPS requires a certificate and a separately configured HTTPS proxy. Allow WebSocket connections through the proxy to use the live console.

Save domains and IP addresses in **Server settings → Connection addresses**. Enter one per line, without `https://`, a port, or a path. Saved addresses remain after a restart. This menu does not configure DNS or certificates, or restrict who can connect. The production setup accepts domains without registration.

### Updates and backups

Stop game servers normally and wait for downloads and installations to finish. For a consistent backup, stop MArchitect too, then copy `.env` and `data/` to a safe location. You can also back up `backend/JAVA/` to keep downloaded Java versions.

```bash
docker compose -f docker-compose.production.yml stop
```

After backing up, download the latest code and start MArchitect again.

```bash
git pull
docker compose -f docker-compose.production.yml up -d --build
```

Game servers, worlds, logs, access codes, and connection addresses are kept in `data/`. Keep this folder and `.env` to preserve your data and settings through updates. If local changes prevent `git pull`, back up your edited files first.

### Troubleshooting

Check the running services and recent errors with the commands below. Include the error message when asking for help, but do not share access codes or personal information. If data files are missing, check the logs and folder write permissions before making changes. Do not delete existing data to retry.

```bash
docker compose -f docker-compose.production.yml ps -a
docker compose -f docker-compose.production.yml logs --tail=100 backend frontend
```

### Editing the source

Use `docker compose up -d --build` for the development setup. If a domain is blocked in this setup, sign in using the server IP and register it in **Connection addresses**. Changes apply automatically within a few seconds and may briefly interrupt the web connection. IP access remains available even with an empty list. Run the development start command again to enable this feature on an existing installation.

## License · 라이선스

[MIT License](LICENSE)
