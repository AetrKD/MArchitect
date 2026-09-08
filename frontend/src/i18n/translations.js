// 화면에 남아 있는 문구를 한곳에서 관리하는 한국어→영어 번역 사전입니다.
export const ENGLISH = {
  "접속 주소 설정": "Connection addresses",
  "도메인 / IP 주소": "Domain / IP address",
  "접속 주소 저장": "Save addresses",
  "도메인을 저장했습니다. 잠시 후 적용됩니다.": "Addresses saved. Changes will apply shortly.",
  "도메인 설정을 불러오지 못했습니다. 페이지를 새로고침해 주세요.": "Could not load addresses. Please refresh the page.",
  "도메인 형식을 확인해 주세요. https://, 포트, 경로는 제외하세요.": "Check the address format. Omit https://, ports, and paths.",
  "처음에는 서버 IP 주소로 접속해 도메인을 등록하세요. DNS와 HTTPS 연결은 별도로 설정해야 합니다.": "Connect using the server IP to register a domain. Configure DNS and HTTPS separately.",
  "도메인 또는 IP 주소를 한 줄에 하나씩 입력하세요. SQLite DB에 저장됩니다. 비우면 등록한 도메인이 삭제됩니다. IP 주소로는 계속 접속할 수 있습니다.": "Enter one domain or IP address per line. Addresses are stored in SQLite. Clear the list to remove registered addresses. IP access remains available.",
  "개발용 서버에는 자동 적용되며 잠시 연결이 끊길 수 있습니다. 운영용 서버는 이미 모든 도메인의 접속을 허용합니다.": "Development settings apply automatically and may briefly interrupt the connection. Production already accepts all domains.",
  "홈": "Home", "인스턴스 목록": "Instances", "서버 설정": "Server settings", "사용자 관리": "User management", "Java 관리": "Java runtimes", "언어": "Language", "라이트 모드": "Light mode", "관리자": "Administrator", "사용자": "User",
  "로그아웃": "Log out", "입장하기": "Sign in", "확인 중...": "Checking...", "접근 코드": "Access code", "접근 코드 입력": "Enter access code", "유효하지 않은 접근 코드입니다.": "Invalid access code.",
  "서버 관리 로그인": "Server management login", "부여받은 접근 코드 하나를 입력해 계속하세요.": "Enter the access code you received to continue.",
  "서버 대시보드": "Server dashboard", "인스턴스": "Instances", "서버 시작": "Start server", "서버 정지": "Stop server", "시작": "Start", "정지": "Stop", "정지됨": "Stopped", "실행 중": "Running", "서버 시작 중...": "Starting server...", "서버 종료 중...": "Stopping server...",
  "인스턴스 생성": "Create instance", "새 인스턴스 생성": "Create instance", "+ 인스턴스 생성": "+ Create instance", "새 마인크래프트 서버를 추가합니다.": "Add a new Minecraft server.", "서버 이름": "Server name", "서버 유형": "Server type", "마인크래프트 버전": "Minecraft version", "버전 선택": "Select version", "목록 불러오는 중...": "Loading versions...", "생성 중...": "Creating...", "취소": "Cancel", "기타 (JAR 업로드)": "Other (JAR upload)", "서버 JAR 파일": "Server JAR file",
  "개요": "Overview", "설정": "Settings", "인스턴스 설정": "Instance settings", "접근 관리": "Access management", "로그": "Logs", "월드": "World", "모드": "Mods", "플러그인": "Plugins", "강제 종료": "Force stop", "서버 콘솔": "Server console", "서버 로그를 기다리는 중입니다.": "Waiting for server logs.", "서버 명령어 입력": "Enter server command", "전송": "Send",
  "실행 설정": "Launch settings", "기본": "Basic", "커스텀": "Custom", "전체 시작 명령어": "Full launch command", "Java 버전": "Java version", "Java 종류": "Java distribution", "메모리": "Memory", "추가 JVM 인수": "Additional JVM arguments", "실행 파일 경로": "Launch file path", "최종 시작 명령어": "Final launch command", "저장": "Save", "저장 중...": "Saving...",
  "서버 아이콘": "Server icon", "서버 삭제": "Delete server", "삭제": "Delete", "삭제 중...": "Deleting...", "전체 삭제": "Delete all", "파일 업로드": "Upload files", "업로드 중...": "Uploading...", "다운로드": "Download", "보기": "View", "닫기": "Close", "상위 폴더": "Parent folder", "world 폴더 업로드": "Upload world folder", "world 폴더 ZIP 다운로드": "Download world ZIP",
  "화이트리스트": "Whitelist", "블랙리스트": "Blacklist", "플레이어 이름 검색": "Search player name", "추가": "Add", "서버를 한 번 실행하면 이 파일이 생성됩니다.": "This file is created after the server starts once.", "서버를 한 번 실행하면 이 폴더가 생성됩니다.": "This folder is created after the server starts once.", "이 폴더는 비어 있습니다.": "This folder is empty.",
  "디스크 사용량": "Disk usage", "네트워크 트래픽": "Network traffic", "인스턴스 리소스": "Instance resources", "서버가 실행 중이 아닙니다.": "The server is not running.", "컨테이너 전체 CPU 대비 · 실시간 메모리": "CPU share of container · live memory", "시스템 사용량을 불러오는 중입니다.": "Loading system metrics...",
  "Java 런타임 관리": "Java runtime management", "설치된 런타임": "Installed runtimes", "감지된 Java 런타임이 없습니다.": "No Java runtimes were detected.", "Temurin Linux x64 다운로드": "Temurin Linux x64 download", "설치": "Install", "설치 중...": "Installing...", "이미 설치됨": "Already installed", "Java 런타임 정보를 불러오는 중입니다.": "Loading Java runtime information.", "설치된 Java와 다운로드 가능한 버전을 확인하고 있습니다.": "Checking installed Java runtimes and available download versions.", "(설치됨)": "(installed)", "예: -Dfile.encoding=UTF-8": "e.g. -Dfile.encoding=UTF-8",
  "관리자 코드 변경": "Change administrator code", "현재 코드": "Current code", "바뀔 코드": "New code", "바뀔 코드 확인": "Confirm new code", "변경 저장": "Save changes", "관리자 코드를 변경했습니다.": "Administrator code changed.",
  "사용자 코드": "User codes", "새 사용자 코드 발급": "Issue new user code", "발급 중...": "Issuing...", "새로 발급한 사용자 코드": "Newly issued user code", "이 코드는 지금만 전체를 확인할 수 있습니다. 사용자에게 전달한 뒤 보관해 주세요.": "The full code is shown only now. Give it to the user and store it safely.", "발급된 사용자 코드가 없습니다.": "No user codes have been issued.", "사용자 코드 목록을 불러오는 중입니다.": "Loading user codes...",
  "백그라운드 작업": "Background tasks", "대기 중": "Queued", "진행 중": "In progress", "완료": "Completed", "실패": "Failed", "작업을 시작했습니다.": "Task started.", "완료되었습니다.": "Completed.",
  "파일 정보 없음": "No file information", "최근 사용량 그래프": "Recent usage graph", "2초 간격 · 컨테이너 기준": "Every 2 seconds · container scope", "인스턴스 저장소": "Instance storage", "파랑: 다운로드 · 회색: 업로드": "Blue: download · gray: upload",
  "바닐라 (Paper)": "Vanilla (Paper)", "서버 유형을 먼저 선택하세요. 직접 JAR을 올리는 경우에는 버전 선택이 필요하지 않습니다.": "Choose a server type first. A directly uploaded JAR does not need a version.", "마인크래프트 버전 목록을 불러오지 못했습니다.": "Could not load Minecraft versions.", "선택한 마인크래프트 버전에 맞는 로더가 없습니다.": "No loader is available for the selected Minecraft version.", "서버 JAR 파일을 선택해 주세요.": "Select a server JAR file.", "인스턴스를 생성하지 못했습니다.": "Could not create the instance.", "Fabric Loader 버전": "Fabric Loader version", "NeoForge 로더 버전": "NeoForge loader version",
  "사용자 코드 목록을 불러오지 못했습니다.": "Could not load user codes.", "새 사용자 코드를 발급했습니다.": "Issued a new user code.", "사용자 코드를 발급하지 못했습니다.": "Could not issue a user code.", "사용자 코드를 삭제했습니다.": "Deleted the user code.", "사용자 코드를 삭제하지 못했습니다.": "Could not delete the user code.", "사용자 역할로 로그인할 수 있는 접근 코드를 발급하고 삭제합니다.": "Issue and delete access codes that can sign in as users.", "코드를 삭제할까요?": "Delete this code?",
  "관리자 접근 코드를 변경합니다.": "Change the administrator access code.", "관리자 코드를 변경하지 못했습니다.": "Could not change the administrator code.", "서버 아이콘 미리보기": "Server icon preview", "64 × 64 픽셀 PNG 파일을": "A 64 × 64 PNG file is saved as", "로 저장합니다.": ".", "인스턴스와 월드, 모드, 플러그인 등 내부의 모든 파일을 삭제합니다.": "Deletes the instance and all files inside it, including worlds, mods, and plugins.",
  "인스턴스 상세 정보를 불러오지 못했습니다.": "Could not load instance details.", "서버 상태를 변경하지 못했습니다.": "Could not change server status.", "서버를 강제 종료할까요? 저장되지 않은 데이터가 손상될 수 있습니다.": "Force stop the server? Unsaved data may be damaged.", "서버를 강제 종료했습니다.": "Server force stopped.", "서버 아이콘을 저장했습니다.": "Server icon saved.", "서버 아이콘을 저장하지 못했습니다.": "Could not save server icon.", "인스턴스를 삭제하지 못했습니다.": "Could not delete the instance.", "실행 설정을 저장했습니다.": "Launch settings saved.", "서버 이름을 저장했습니다.": "Server name saved.",
  "파일 또는 폴더를 삭제할까요?": "Delete this file or folder?", "폴더와 내부 파일을 모두 삭제할까요?": "Delete this folder and all files inside it?", "파일을 업로드하지 못했습니다.": "Could not upload files.", "텍스트 파일을 읽지 못했습니다.": "Could not read the text file.", "폴더 내용을 불러오지 못했습니다.": "Could not load folder contents.", "삭제하지 못했습니다.": "Could not delete it.", "폴더를 비우지 못했습니다.": "Could not empty the folder.",
};

export function translate(language, text) {
  // 문장 전체가 일치할 때만 번역해 단어 일부가 섞여 깨지는 것을 방지합니다.
  if (!text) return text;
  const pairs = language === "en" ? Object.entries(ENGLISH) : Object.entries(ENGLISH).map(([korean, english]) => [english, korean]);
  const trimmed = text.trim();
  const match = pairs.find(([source]) => source === trimmed);
  return match ? text.replace(trimmed, match[1]) : text;
}

/** Key-based UI copy for new and migrated components. */
export const MESSAGES = {
  ko: {
    common: { cancel: "취소", confirm: "확인", delete: "삭제", start: "시작", stop: "정지", forceStop: "강제 종료", clearAll: "전체 삭제", logOut: "로그아웃" },
    sidebar: { home: "홈", instances: "인스턴스 목록", serverSettings: "서버 설정", users: "사용자 관리", java: "Java 관리", language: "언어", lightMode: "라이트 모드", admin: "관리자", user: "사용자", menuToggle: "메뉴 열기 또는 닫기" },
    status: { running: "실행 중", stopped: "정지됨", starting: "시작 중", stopping: "정지 중" },
    dashboard: { title: "서버 대시보드", description: "시스템 사용량을 실시간으로 확인하세요.", loading: "시스템 사용량을 불러오는 중입니다.", interval: "2초 간격 · 컨테이너 기준", disk: "디스크 사용량", storage: "인스턴스 저장소", traffic: "네트워크 트래픽", trafficHelp: "파랑: 다운로드 · 회색: 업로드", resources: "인스턴스 리소스", memory: "메모리", backgroundTasks: "백그라운드 작업", acknowledgeAll: "전체 확인", taskHint: "작업을 누르면 목록에서 사라집니다.", queued: "대기 중", completed: "완료", failed: "실패", inProgress: "진행 중" },
    instances: { title: "인스턴스 목록", description: "마인크래프트 서버 인스턴스를 관리하세요.", createTitle: "+ 인스턴스 생성", createDescription: "새 마인크래프트 서버를 추가합니다.", createBadge: "새 서버", create: "생성", noJar: "JAR 파일 정보 없음" },
    runtime: { title: "Java 런타임 관리", description: "Temurin Linux x64 JDK를 프로젝트 JAVA 폴더에 설치합니다." },
  },
  en: {
    common: { cancel: "Cancel", confirm: "Confirm", delete: "Delete", start: "Start", stop: "Stop", forceStop: "Force stop", clearAll: "Clear all", logOut: "Log out" },
    sidebar: { home: "Home", instances: "Instances", serverSettings: "Server settings", users: "Users", java: "Java runtimes", language: "Language", lightMode: "Light mode", admin: "Admin", user: "User", menuToggle: "Open or close menu" },
    status: { running: "Running", stopped: "Stopped", starting: "Starting", stopping: "Stopping" },
    dashboard: { title: "Server dashboard", description: "Monitor system usage in real time.", loading: "Loading system metrics...", interval: "Every 2 seconds · container scope", disk: "Disk usage", storage: "Instance storage", traffic: "Network traffic", trafficHelp: "Blue: download · gray: upload", resources: "Instance resources", memory: "Memory", backgroundTasks: "Background tasks", acknowledgeAll: "Acknowledge all", taskHint: "Select a task to dismiss it.", queued: "Queued", completed: "Completed", failed: "Failed", inProgress: "In progress" },
    instances: { title: "Instances", description: "Manage Minecraft server instances.", createTitle: "+ Create instance", createDescription: "Add a new Minecraft server.", createBadge: "New", create: "Create", noJar: "No JAR file information" },
    runtime: { title: "Java runtime management", description: "Install Temurin Linux x64 JDKs in the project JAVA folder." },
  },
};

/** Return the key-based UI copy bundle for the selected language. */
export function getMessages(language) {
  return MESSAGES[language] ?? MESSAGES.ko;
}
