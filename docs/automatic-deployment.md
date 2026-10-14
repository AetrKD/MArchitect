# 개인 Linux 서버 자동 배포

공개 소스 저장소의 CI와 내부망 배포 실행기를 분리합니다.

- **AetrKD/MArchitect**: master 및 PR에서 GitHub의 Ubuntu 실행기로 검사합니다.
- **비공개 AetrKD/MArchitect-deploy**: 내부망의 별도 Linux 실행기를 등록합니다.
- 배포 실행기는 5분마다 최신 master 커밋과 해당 커밋의 성공한 **push CI**를 확인합니다. GitHub 상황에 따라 예약 실행이 지연될 수 있습니다.
- CI 성공 후 SSH로 정확한 커밋의 빌드 입력을 전달하여 개인 서버에서 운영 이미지를 빌드합니다. 이미 정상 배포된 커밋은 다시 시작하지 않습니다.

공개 저장소에 자체 실행기를 등록하지 마세요. 이 워크플로의 조건은 다른 PR이 추가한 워크플로까지 제한하지 못합니다. 실행기와 SSH 비밀은 비공개 배포 저장소에만 둡니다. [GitHub 자체 실행기 보안 안내](https://docs.github.com/en/actions/reference/security/secure-use#hardening-for-self-hosted-runners)

## 서버 준비와 기존 설치 확인

대상 서버에는 Docker Engine, Docker Compose v2.24 이상, Bash, Python 3, tar, util-linux의 flock/realpath, OpenSSH 서버가 필요합니다. 실행기에는 Git, Bash, Python 3, OpenSSH 클라이언트가 필요하며, 서버와 달리 Docker는 필요하지 않습니다.

배포 계정은 배포 폴더를 읽고 쓸 수 있어야 하며, sudo 없이 Docker를 사용할 수 있어야 합니다. Docker 그룹은 호스트 전체에 대한 높은 권한이므로 계정·SSH 키를 배포 전용으로 사용하는 편이 좋습니다. 실행기 VM에는 다른 서비스의 비밀이나 운영 데이터를 두지 마세요.

기존 설치에서는 아래를 확인합니다.

```bash
cd /실제/MArchitect/설치/폴더
docker compose ls
docker ps --format '{{.Names}} {{.Label "com.docker.compose.project"}}'
```

DEPLOY_PROJECT는 **현재 Compose 프로젝트 이름**과 같아야 합니다. 폴더 이름이 MArchitect인 기본 설치라면 보통 marchitect이지만 위 출력으로 확인하세요. 다른 프로젝트 이름으로 새 컨테이너를 만들지 마세요.

자동 배포는 다음 위치를 사용합니다.

```text
설치 폴더/
├── .env                     # 기존 서버 설정, 자동 업로드/덮어쓰기하지 않음
├── data/                    # 월드, 인스턴스, SQLite, 설정
├── backend/JAVA/             # 기존 Java 런타임
├── releases/<commit>/       # 커밋별 소스와 배포 Compose
├── incoming/                # 일시적인 소스 아카이브
├── .current-release         # 마지막 성공 커밋
└── .failed-release          # 실제 적용 실패 시 재시도 차단
```

.env, data/, backend/JAVA/가 다른 위치에 있거나 사용자 정의 Compose를 사용 중이면 먼저 배포 구성을 그 경로에 맞게 조정하세요. 기존 컨테이너의 데이터 마운트가 이 위치와 다르면 스크립트가 배포를 거부합니다.

첫 적용 전 게임 서버를 웹에서 정상 종료하고 다운로드·Java 설치가 끝날 때까지 기다리세요. 기존 운영 Compose를 정지한 상태에서 .env, data/, backend/JAVA/를 별도 저장소에 백업한 뒤 기존 서비스를 다시 실행할 수 있습니다. 자동 복구는 **애플리케이션 이미지** 복구이며 DB나 월드의 과거 상태를 복원하지 않습니다.

기존 .env를 유지하세요. 신규 설치일 때만 .env.example을 복사하여 긴 고유 관리자 코드, 호스트 UID/GID, 포트 설정을 입력합니다. 신규 설치에서 예제 관리자 코드를 그대로 두면 자동 배포가 거부됩니다. 이미 초기화된 관리자 계정이 있는 DB는 읽기 전용으로 확인하며 기존 접근 코드를 변경하지 않습니다. .env는 서버에서 권한 600으로 유지합니다. 파일은 셸 코드로 실행하지 않습니다.

자동 배포 구성에서는 웹 포트를 기본적으로 127.0.0.1에만 공개합니다. 서버의 HTTPS 프록시나 SSH 터널을 사용하세요. 기존 LAN 접속을 유지하려면 서버 .env에 다음을 추가하고 해당 IP의 포트 접근을 방화벽으로 제한하세요.

```dotenv
MARCHITECT_WEB_BIND=서버의_LAN_IP
```

인터넷에 웹 콘솔을 공개할 때는 HTTPS 프록시를 구성하세요. 게임 포트 범위는 기존 .env 설정을 유지합니다. 백엔드 API 포트는 호스트에 공개하지 않습니다.

## 배포용 SSH 키와 호스트 키

실행기에서 배포 전용 Ed25519 키를 생성합니다. 자동 작업용이므로 이 키에는 암호를 설정하지 않고 비공개 GitHub 환경 비밀로 보관합니다.

```bash
ssh-keygen -t ed25519 -f ./marchitect-deploy-key -C marchitect-deployment
```

대상 계정의 ~/.ssh/authorized_keys에 **공개 키**를 등록하세요. 포트·에이전트·X11 전달과 PTY를 허용하지 않는 예시입니다. from은 실행기 VM의 고정 LAN IP로 바꿉니다.

```text
restrict,from="실행기_VM의_LAN_IP" ssh-ed25519 실제_공개키 marchitect-deployment
```

서버 콘솔에서 서버 호스트 키의 지문을 확인합니다.

```bash
sudo ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub
```

실행기에서 수집한 호스트 키의 지문을 위 값과 대조하고, 일치한 known_hosts 내용을 GitHub 비밀에 넣습니다.

```bash
ssh-keyscan -p 22 -t ed25519 서버주소 > verified_known_hosts
ssh-keygen -lf verified_known_hosts
```

ssh-keyscan 출력만으로 신뢰하지 마세요. 배포 중에는 호스트 키를 수집하지 않으며 StrictHostKeyChecking=yes로 저장한 키만 허용합니다. 포트가 22가 아니라면 known_hosts 항목은 [주소]:포트 형식이어야 합니다. 키 변경도 서버 콘솔로 확인한 뒤 비밀을 교체하세요.

원본 키가 실행기 VM에 이미 있다면 DEPLOY_SSH_KEY_PATH 변수에 해당 절대 경로를 지정할 수 있습니다. 예: /home/실행기계정/.ssh/marchitect-deploy. 이 모드에서는 개인 키를 GitHub에 복사하지 않고, 작업 중에만 일시 SSH 폴더로 복사하여 사용합니다. 원본 파일은 그대로 유지합니다.

## 비공개 배포 저장소와 내부망 실행기

1. AetrKD/MArchitect-deploy를 **비공개**로 유지하세요. deployment/private-repo/.github/workflows/deploy.yml을 그 저장소의 .github/workflows/deploy.yml로 복사합니다. 템플릿은 공개 소스 저장소에서 실행되지 않습니다.
2. 내부망에 별도 Linux VM을 마련합니다. 비공개 저장소의 **Settings → Actions → Runners → New self-hosted runner**에서 Linux와 VM 아키텍처에 맞는 공식 설치 명령을 사용하세요. 만료되는 등록 토큰은 문서나 소스에 저장하지 않습니다.
3. 등록 시 기본 self-hosted, linux 레이블에 사용자 레이블 **marchitect-deploy**를 추가합니다. 일반 사용자 계정으로 실행기를 설치하고 서비스로 등록합니다. 실행기 계정에는 VM의 root나 Docker 권한이 필요하지 않습니다.
4. 실행기는 비공개 저장소에만 등록합니다. VM에서 GitHub로 나가는 HTTPS와 배포 서버의 SSH 포트로 나가는 연결을 허용합니다. 공유기의 인바운드 포트 전달은 필요하지 않습니다.
5. 비공개 저장소의 Settings → Secrets and variables → Actions에 아래 저장소 비밀과 변수를 넣습니다. 저장소 접근 권한은 배포 운영자에게만 제공합니다. 유료 플랜의 환경 기능은 필수로 사용하지 않습니다.

[GitHub 공식 실행기 설치 안내](https://docs.github.com/en/actions/how-tos/manage-runners/self-hosted-runners/add-runners)

### 비공개 저장소 Secrets

| 이름 | 값 |
|---|---|
| DEPLOY_SSH_KEY | 배포 전용 개인 키 전체. VM 원본 키 경로를 쓰면 생략 가능 |
| DEPLOY_KNOWN_HOSTS | 지문 대조를 마친 known_hosts 내용 |

### 비공개 저장소 Variables

| 이름 | 값 |
|---|---|
| DEPLOY_HOST | 개인 서버의 LAN IP 또는 DNS |
| DEPLOY_USER | 서버 배포 계정 |
| DEPLOY_PORT | SSH 포트. 기본 22 |
| DEPLOY_PATH | .env와 data/가 있는 절대 설치 경로. 공백 없이 지정 |
| DEPLOY_PROJECT | 기존 Compose 프로젝트 이름 |
| DEPLOY_SSH_KEY_PATH | 선택 사항. 실행기 VM 원본 키의 절대 경로. 지정하면 DEPLOY_SSH_KEY 대신 사용 |

### 비공개 저장소 Repository Variable

| 이름 | 값 |
|---|---|
| DEPLOY_ENABLED | 준비가 끝난 뒤 true. 환경 변수가 아닌 **저장소 변수**로 설정 |

DEPLOY_ENABLED가 없으면 배포 작업을 건너뜁니다. 설정을 마치고 공개 저장소의 CI 변경을 master에 병합한 뒤, 비공개 저장소의 **Actions → Deploy MArchitect → Run workflow**로 첫 실행을 확인하세요. 이후 최신 master의 성공한 push CI가 발견되면 예약 작업이 배포합니다. 추가 승인 절차를 원하면 GitHub 플랜이 환경 기능을 지원하는지 확인한 뒤 배포 환경을 별도로 추가할 수 있습니다.

공개 저장소의 master에 브랜치 보호를 설정하고 Test production containers 검사를 병합 조건으로 사용하는 편이 좋습니다.

## 배포 절차와 실패 처리

1. 배포할 SHA가 여전히 master의 최신 커밋인지 확인합니다.
2. SSH 키는 실행기의 일시 폴더에 권한 600으로 저장하고 작업 종료 시 삭제합니다. GitHub 토큰과 서버 .env를 SSH로 전달하지 않습니다.
3. 서버에서 파일 잠금으로 다른 배포와의 겹침을 막습니다.
4. 정확한 커밋의 소스로 커밋별 태그 marchitect-backend:<SHA>, marchitect-frontend:<SHA>를 빌드합니다. 이미 만들어진 태그는 재빌드하지 않습니다. 빌드 실패는 기존 서비스에 영향을 주지 않습니다.
5. 게임 Java 프로세스가 실행 중이면 기존 서비스를 건드리지 않고 중단합니다. 웹 콘솔을 잠깐 정지한 뒤 다시 게임 프로세스를 확인하며, 그 사이 시작된 게임이 있으면 웹 콘솔만 복구합니다.
6. 게임이 없는 상태에서 컨테이너를 교체합니다. API와 웹 화면, Nginx의 API 프록시 건강 검사를 모두 통과해야 성공으로 기록합니다.
7. 적용 실패 시 이전 커밋의 이미지·Compose로 복구하고 실패 커밋을 .failed-release에 기록합니다. 같은 커밋의 다음 예약 실행은 교체를 재시도하지 않습니다. 최초 설치에 이전 버전이 없으면 새 서비스만 정지하고 데이터를 남깁니다.
8. 첫 자동 배포에서는 기존 컨테이너에 기록된 실제 Compose 파일들을 순서대로 복사하고 실제 이미지의 별도 태그를 복구용으로 보관합니다. 개발용 설치도 원래 Compose 구성으로 복구합니다. 데이터·볼륨 삭제, 시스템 전체 이미지 정리는 수행하지 않습니다.

게임 서버는 컨테이너 안에서 실행되므로 배포 후 자동으로 게임을 다시 시작하지 않습니다. 게임이 실행 중이라 배포가 보류되면 게임을 정상 종료한 후 다음 예약 작업이나 수동 실행을 기다리세요. 배포 전 긴 다운로드·설치 작업을 끝내세요. 중단 없는 웹 배포나 DB 마이그레이션 복구는 포함되지 않습니다.

실패 로그와 서버 상태를 확인한 뒤 **같은 커밋**을 재시도하려면 설치 폴더의 .failed-release 파일만 제거하고 수동 실행하세요. 이전 정상 버전을 유지하려면 비공개 저장소의 DEPLOY_ENABLED를 false로 설정합니다.

```bash
cd /실제/MArchitect/설치/폴더
release=$(cat .current-release)
export MARCHITECT_RELEASE="$release"
export MARCHITECT_DATA_DIR="$PWD/data"
export MARCHITECT_JAVA_DIR="$PWD/backend/JAVA"
docker compose -p 실제_프로젝트_이름 --project-directory "$PWD/releases/$release" \
  --env-file "$PWD/.env" -f "$PWD/releases/$release/docker-compose.deploy.yml" ps -a
```

.env 설정을 수동 변경할 때는 게임을 정상 종료하고 위 명령의 ps -a 대신 up -d --no-build --force-recreate --wait를 사용하세요. 이전 release 폴더와 이미지는 자동 삭제하지 않으므로 저장 공간을 확인하며 필요한 복구 버전을 보관하세요.

이미지 복구로 호환되지 않는 DB 변경까지 되돌릴 수는 없습니다. 향후 DB 스키마를 변경하는 릴리스는 별도 백업·복구 절차가 필요합니다.

## GHCR 대신 서버 빌드를 선택한 이유

서버의 CPU 아키텍처를 전제로 하지 않고 기존 두 운영 Dockerfile을 사용할 수 있습니다. 서버에 Git 인증이나 GHCR 읽기 토큰을 추가하지 않아도 됩니다. 대신 서버의 빌드 시간·CPU·외부 이미지 및 패키지 다운로드가 필요하며, 현재 Dockerfile의 의존성과 기본 이미지가 고정되지 않아 CI 이미지와 서버 이미지가 완전히 동일하지는 않습니다.

서버 아키텍처를 확인한 뒤 GHCR 방식으로 전환하면 CI에서 만든 이미지를 digest로 고정하여 가져올 수 있습니다. 그 경우에도 내부망 실행기에서 SSH로 Compose 갱신 명령을 보내는 연결은 계속 필요합니다.
