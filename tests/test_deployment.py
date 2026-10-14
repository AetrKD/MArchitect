"""Exercise deployment failure paths without contacting Docker or a real server."""
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "deploy.sh"
CURRENT = "a" * 40
PREVIOUS = "b" * 40

MOCK_DOCKER = r"""#!/usr/bin/env python3
import json, os, pathlib, sys
args = sys.argv[1:]
root = pathlib.Path(os.environ["MOCK_ROOT"])
release = os.environ.get("MARCHITECT_RELEASE", "")
with (root / "docker-calls.jsonl").open("a") as log:
    log.write(json.dumps({"args": args, "release": release}) + "\n")
if args[:2] == ["compose", "version"]:
    print("Docker Compose version v2.39.0")
elif args[:2] == ["image", "inspect"]:
    sys.exit(0 if (root / "built").exists() else 1)
elif args[:2] == ["image", "tag"]:
    pass
elif args and args[0] == "ps":
    if os.environ.get("EXISTING") == "1":
        print("frontend-id" if any("service=frontend" in a for a in args) else "backend-id")
elif args and args[0] == "inspect":
    if ".State.Status" in args[-1]:
        print("running healthy\nrunning healthy")
    elif "project.config_files" in args[-1]:
        print(os.environ.get("LEGACY_COMPOSE_FILES", str(root / "docker-compose.production.yml")))
    elif args[-1] == "{{.Image}}":
        print("sha256:old-image")
    else:
        data = str(root / ("wrong" if os.environ.get("WRONG_MOUNT") else "data"))
        print(json.dumps([
            {"Destination": "/data", "Type": "bind", "Source": data},
            {"Destination": "/java", "Type": "bind", "Source": str(root / "backend/JAVA")},
        ]))
elif args and args[0] in {"stop", "start"}:
    pass
elif args and args[0] == "top":
    print("COMMAND")
    tops = len([json.loads(line) for line in (root / "docker-calls.jsonl").read_text().splitlines() if json.loads(line)["args"][0] == "top"])
    print("java" if os.environ.get("LIVE_GAME") or (os.environ.get("RACING_GAME") and tops > 1) else "uvicorn")
elif args and args[0] == "compose":
    if "config" in args:
        if "--format" in args:
            print(json.dumps({"services": {"backend": {"environment": {
                "MARCHITECT_INITIAL_ADMIN_CODE": os.environ.get("ADMIN_CODE", "private-test-code")
            }}}}))
    elif "ps" in args:
        print("backend-id\nfrontend-id")
    elif "build" in args:
        if os.environ.get("FAIL_BUILD"):
            sys.exit(23)
        (root / "built").touch()
    elif "up" in args:
        if release == os.environ.get("FAIL_RELEASE") and not any("legacy-images.yml" in a for a in args):
            sys.exit(24)
    elif "stop" in args:
        pass
    else:
        sys.exit("Unexpected compose command: " + repr(args))
else:
    sys.exit("Unexpected docker command: " + repr(args))
"""


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        docker = self.bin / "docker"
        docker.write_text(MOCK_DOCKER)
        docker.chmod(0o755)
        (self.root / ".env").write_text("MARCHITECT_INITIAL_ADMIN_CODE=private-test-code\n")
        (self.root / "data").mkdir()
        (self.root / "data/world-sentinel").write_text("preserve-world")
        (self.root / "backend/JAVA").mkdir(parents=True)
        (self.root / "backend/JAVA/java-sentinel").write_text("preserve-java")
        (self.root / "incoming").mkdir()
        self.upload = f"{CURRENT}-123-1.tar"
        inputs = self.root / "source"
        for name in ("backend", "frontend"):
            (inputs / name).mkdir(parents=True, mode=0o755)
            (inputs / name / "Dockerfile.production").write_text("FROM scratch\n")
        (inputs / "docker-compose.deploy.yml").write_text("services: {}\n")
        with tarfile.open(self.root / "incoming" / self.upload, "w") as archive:
            for entry in inputs.iterdir():
                archive.add(entry, arcname=entry.name)
        self.env = dict(os.environ, PATH=f"{self.bin}:{os.environ['PATH']}", MOCK_ROOT=str(self.root))

    def previous(self):
        folder = self.root / "releases" / PREVIOUS
        folder.mkdir(parents=True)
        (folder / "docker-compose.deploy.yml").write_text("services: {}\n")
        (self.root / ".current-release").write_text(PREVIOUS + "\n")
        self.env["EXISTING"] = "1"

    def run_deploy(self, **settings):
        return subprocess.run(
            ["bash", str(SCRIPT), str(self.root), CURRENT, "marchitect", self.upload],
            env=dict(self.env, **settings), text=True, capture_output=True, timeout=10,
        )

    def calls(self):
        log = self.root / "docker-calls.jsonl"
        return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []

    def assert_data_preserved(self):
        self.assertEqual((self.root / "data/world-sentinel").read_text(), "preserve-world")
        self.assertEqual((self.root / "backend/JAVA/java-sentinel").read_text(), "preserve-java")
        self.assertIn("private-test-code", (self.root / ".env").read_text())

    def test_success_keeps_storage_and_records_commit(self):
        result = self.run_deploy()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((self.root / ".current-release").read_text().strip(), CURRENT)
        source = self.root / "releases" / CURRENT / "backend/Dockerfile.production"
        self.assertEqual(source.stat().st_mode & 0o444, 0o444)
        self.assert_data_preserved()
        self.assertNotIn("private-test-code", result.stdout + result.stderr)

    def test_already_healthy_release_does_not_restart_live_games(self):
        folder = self.root / "releases" / CURRENT
        folder.mkdir(parents=True)
        (folder / "docker-compose.deploy.yml").write_text("services: {}\n")
        (self.root / ".current-release").write_text(CURRENT + "\n")
        result = self.run_deploy(LIVE_GAME="1", EXISTING="1")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(any("up" in call["args"] or "build" in call["args"] for call in self.calls()))
        self.assert_data_preserved()

    def test_game_running_refuses_before_replacing_containers(self):
        self.previous()
        result = self.run_deploy(LIVE_GAME="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Minecraft is running", result.stderr)
        self.assertFalse(any("up" in call["args"] for call in self.calls()))
        self.assertEqual((self.root / ".current-release").read_text().strip(), PREVIOUS)
        self.assert_data_preserved()

    def test_game_started_during_preparation_restores_only_frontend(self):
        self.previous()
        result = self.run_deploy(RACING_GAME="1")
        self.assertNotEqual(result.returncode, 0)
        calls = self.calls()
        self.assertTrue(any(call["args"][0] == "stop" for call in calls))
        self.assertTrue(any(call["args"][0] == "start" for call in calls))
        self.assertFalse(any("up" in call["args"] for call in calls))
        self.assertFalse((self.root / ".failed-release").exists())
        self.assert_data_preserved()

    def test_wrong_existing_mount_refuses_without_building(self):
        self.previous()
        result = self.run_deploy(WRONG_MOUNT="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(any("build" in call["args"] or "up" in call["args"] for call in self.calls()))
        self.assert_data_preserved()

    def test_build_failure_does_not_touch_running_version(self):
        self.previous()
        result = self.run_deploy(FAIL_BUILD="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(any("up" in call["args"] for call in self.calls()))
        self.assertEqual((self.root / ".current-release").read_text().strip(), PREVIOUS)

    def test_unhealthy_release_restores_previous_images(self):
        self.previous()
        result = self.run_deploy(FAIL_RELEASE=CURRENT)
        self.assertNotEqual(result.returncode, 0)
        ups = [call for call in self.calls() if "up" in call["args"]]
        self.assertEqual([call["release"] for call in ups], [CURRENT, PREVIOUS])
        self.assertEqual((self.root / ".failed-release").read_text().strip(), CURRENT)
        self.assertTrue(all("--no-build" in call["args"] for call in ups))
        self.assertEqual((self.root / ".current-release").read_text().strip(), PREVIOUS)
        self.assert_data_preserved()

    def test_failed_first_install_stops_new_services(self):
        result = self.run_deploy(FAIL_RELEASE=CURRENT)
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(any("stop" in call["args"] for call in self.calls()))
        self.assertFalse((self.root / ".current-release").exists())
        self.assert_data_preserved()

    def test_first_migration_snapshots_and_restores_legacy_images(self):
        self.env["EXISTING"] = "1"
        (self.root / "docker-compose.production.yml").write_text("services: {}\n")
        result = self.run_deploy(FAIL_RELEASE=CURRENT)
        self.assertNotEqual(result.returncode, 0)
        tags = [call for call in self.calls() if call["args"][:2] == ["image", "tag"]]
        self.assertEqual(len(tags), 2)
        ups = [call for call in self.calls() if "up" in call["args"]]
        self.assertEqual(len(ups), 2)
        self.assertTrue(any("legacy-images.yml" in arg for arg in ups[-1]["args"]))
        self.assert_data_preserved()

    def test_development_stack_rollback_preserves_original_configuration(self):
        self.env["EXISTING"] = "1"
        development = self.root / "docker-compose.yml"
        original = "services:\n  frontend:\n    ports: ['5173:5173']\n"
        development.write_text(original)
        result = self.run_deploy(FAIL_RELEASE=CURRENT, LEGACY_COMPOSE_FILES=str(development))
        self.assertNotEqual(result.returncode, 0)
        snapshot = self.root / "releases" / CURRENT / "legacy-compose-0.yml"
        self.assertEqual(snapshot.read_text(), original)
        rollback = [c for c in self.calls() if "up" in c["args"]][-1]
        self.assertIn(str(snapshot), rollback["args"])
        self.assert_data_preserved()

    def test_rollback_preserves_multiple_compose_files_in_order(self):
        self.env["EXISTING"] = "1"
        base, override = self.root / "compose.yml", self.root / "override.yml"
        base.write_text("services: {}\n")
        override.write_text("services: {frontend: {ports: ['5173:5173']}}\n")
        result = self.run_deploy(FAIL_RELEASE=CURRENT, LEGACY_COMPOSE_FILES=f"{base},{override}")
        self.assertNotEqual(result.returncode, 0)
        folder = self.root / "releases" / CURRENT
        snapshot0, snapshot1 = folder / "legacy-compose-0.yml", folder / "legacy-compose-1.yml"
        self.assertEqual(snapshot0.read_text(), base.read_text())
        self.assertEqual(snapshot1.read_text(), override.read_text())
        rollback = [c for c in self.calls() if "up" in c["args"]][-1]["args"]
        self.assertLess(rollback.index(str(snapshot0)), rollback.index(str(snapshot1)))

    def test_example_admin_code_is_rejected_without_logging_it(self):
        result = self.run_deploy(ADMIN_CODE="replace-with-a-long-unique-admin-code")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(any("build" in call["args"] for call in self.calls()))
        self.assertNotIn("replace-with-a-long-unique-admin-code", result.stdout + result.stderr)

    def test_missing_env_refuses_without_replacing_containers(self):
        (self.root / ".env").unlink()
        result = self.run_deploy()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(any("up" in call["args"] for call in self.calls()))


if __name__ == "__main__":
    unittest.main()
