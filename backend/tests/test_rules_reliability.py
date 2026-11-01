import asyncio
import os
import shlex
import sys
import json
import tempfile
import time
import unittest
import zipfile
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError
from modules import time_settings, auth, instance_rules as rules, instance_store as store, instances, server_process as process, task_store


def session(role, code_id=None):
    return {"role": role, "code_id": code_id, "expires": time.monotonic() + 3600}


class RuleTests(unittest.TestCase):
    def setUp(self):
        zone = patch.object(time_settings, "SERVICE_TIMEZONE", "Asia/Seoul")
        zone.start()
        self.addCleanup(zone.stop)

    def config(self, **overrides):
        rule = {"kind": "restriction", "days": [0], "time": "22:00", "end_time": "06:00", **overrides}
        return rules.Rules(rules=[rule])

    def test_overnight_and_boundary(self):
        config = self.config()
        self.assertFalse(rules.restricted(config, datetime.fromisoformat("2026-11-02T21:59:00+09:00")))
        self.assertTrue(rules.restricted(config, datetime.fromisoformat("2026-11-02T22:00:00+09:00")))
        self.assertTrue(rules.restricted(config, datetime.fromisoformat("2026-11-03T05:59:00+09:00")))
        self.assertFalse(rules.restricted(config, datetime.fromisoformat("2026-11-03T06:00:00+09:00")))
        self.assertFalse(rules.restricted(config, datetime.fromisoformat("2026-11-03T23:00:00+09:00")))

    def test_daytime_disabled_and_week_wrap(self):
        config = self.config(days=[6])
        self.assertTrue(rules.restricted(config, datetime.fromisoformat("2026-11-02T05:00:00+09:00")))
        self.assertFalse(rules.restricted(self.config(enabled=False), datetime.fromisoformat("2026-11-02T23:00:00+09:00")))
        config = self.config(time="09:00", end_time="18:00")
        self.assertTrue(rules.restricted(config, datetime.fromisoformat("2026-11-02T00:00:00+00:00")))
        self.assertFalse(rules.restricted(config, datetime.fromisoformat("2026-11-02T18:00:00+09:00")))

    def test_system_timezone_and_dst(self):
        config = rules.Rules()
        self.assertNotIn("timezone", config.model_dump())
        with patch.object(time_settings, "SERVICE_TIMEZONE", "system"), patch.dict(os.environ, {"TZ": "America/New_York"}):
            winter = rules.local_time(config, datetime.fromisoformat("2026-01-05T14:00:00+00:00"))
            summer = rules.local_time(config, datetime.fromisoformat("2026-07-06T13:00:00+00:00"))
            self.assertEqual(winter.hour, 9)
            self.assertEqual(summer.hour, 9)
            self.assertNotEqual(winter.utcoffset(), summer.utcoffset())
        with patch.dict(os.environ, {"TZ": "UTC"}):
            explicit = rules.Rules()
            self.assertEqual(rules.local_time(explicit, datetime.fromisoformat("2026-11-02T00:00:00+00:00")).hour, 9)

    def test_system_localtime_file(self):
        import io
        from importlib.resources import files
        data = files("tzdata.zoneinfo").joinpath("Asia/Seoul").read_bytes()
        with patch.object(time_settings, "SERVICE_TIMEZONE", "system"), patch.dict(os.environ, {"TZ": ""}), patch.object(time_settings, "Path") as path:
            path.return_value.is_file.return_value = True
            path.return_value.open.return_value = io.BytesIO(data)
            result = rules.local_time(rules.Rules(), datetime.fromisoformat("2026-11-02T00:00:00+00:00"))
            self.assertEqual(result.hour, 9)

    def test_invalid_rules(self):
        for changes in [{"days": []}, {"days": [7]}, {"days": [1, 1]}, {"time": "24:00"}, {"end_time": "22:00"}, {"end_time": None}]:
            with self.assertRaises(ValidationError):
                self.config(**changes)
        with self.assertRaises(ValidationError):
            rules.Rules(timezone="unknown/zone")

    def test_scheduler_deduplicates_persistently_and_stop_wins(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "server"; path.mkdir()
            store.write_instance(path, {"id": "server", "status": "stopped"})
            config = rules.Rules(rules=[{"kind": kind, "days": [0], "time": "09:00"} for kind in ["start", "stop"]])
            store.atomic_json(path / "rules.json", config.model_dump())
            now = datetime.fromisoformat("2026-11-02T09:00:00+09:00")
            with patch.object(rules, "INSTANCE_DIR", root), patch.object(process, "start") as start, patch.object(process, "stop") as stop:
                rules.run_pending(now); rules.run_pending(now)
                start.assert_not_called(); stop.assert_called_once()
                rules.run_pending(datetime.fromisoformat("2026-11-09T09:00:00+09:00"))
                self.assertEqual(stop.call_count, 2)

    def test_rules_api_permissions_and_manual_start(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)
            store.write_instance(path, {"id": path.name, "status": "stopped"})
            app = FastAPI(); app.include_router(rules.router); app.include_router(instances.router)
            with patch.object(rules, "get_instance_path", return_value=path), patch.object(instances, "get_instance_path", return_value=path), patch.dict(auth.SESSIONS, {"a": session("admin"), "u": session("user")}), TestClient(app) as client:
                config = self.config(days=list(range(7)), time="00:00", end_time="23:59").model_dump()
                url = "/instances/server/rules"
                self.assertEqual(client.put(url, json=config, headers={"X-MArchitect-Token": "u"}).status_code, 403)
                self.assertEqual(client.put(url, json=config, headers={"X-MArchitect-Token": "a"}).status_code, 200)
                self.assertEqual(client.get(url).json(), config)
                self.assertEqual(client.put(url, json={**config, "timezone": "UTC"}, headers={"X-MArchitect-Token": "a"}).status_code, 422)
                store.atomic_json(path / "rules.json", {**config, "timezone": "America/New_York"})
                self.assertEqual(client.get(url).json(), config)
                self.assertEqual(rules.local_time(rules.load_rules(path), datetime.fromisoformat("2026-11-02T00:00:00+00:00")).hour, 9)
                with patch.object(rules, "is_start_restricted", return_value=True), patch.object(instances, "start_process", return_value={"status": "starting"}) as start:
                    self.assertEqual(client.post("/instances/server/start", headers={"X-MArchitect-Token": "u"}).status_code, 403)
                    self.assertEqual(client.post("/instances/server/start", headers={"X-MArchitect-Token": "a"}).status_code, 200)
                    start.assert_called_once()


class StorageTests(unittest.TestCase):
    def test_atomic_merge_of_stale_snapshots(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)
            store.write_instance(path, {"id": "x", "status": "running", "name": "old", "process_pid": 123})
            first, second = store.read_instance(path), store.read_instance(path)
            first["name"] = "new"; store.write_instance(path, first)
            second["status"] = "stopped"; second.pop("process_pid"); store.write_instance(path, second)
            result = store.read_instance(path)
            self.assertEqual(result["name"], "new"); self.assertEqual(result["status"], "stopped")
            self.assertNotIn("process_pid", result)
            self.assertEqual(list(path.glob(".marchitect-*")), [])

    def test_maintenance_blocks_running_and_duplicate_operations(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)
            with patch.object(process, "find_process_id", return_value=123):
                with self.assertRaises(HTTPException):
                    with store.maintenance(path): pass
            with patch.object(process, "find_process_id", return_value=None):
                with store.maintenance(path):
                    with self.assertRaises(HTTPException):
                        with store.maintenance(path): pass
                    with self.assertRaises(HTTPException): process.start(path)
                self.assertNotIn(str(path.resolve()), store.MAINTENANCE)

    def test_backup_on_disk_and_cleanup(self):
        async def scenario(path):
            response = await instances.download_world("server")
            archive_path = Path(response.path)
            self.assertTrue(archive_path.is_file())
            with zipfile.ZipFile(archive_path) as archive:
                self.assertEqual(archive.read("world/level.dat"), b"world")
            await response.background()
            self.assertFalse(archive_path.exists())
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary); (path / "world").mkdir(); (path / "world/level.dat").write_bytes(b"world")
            with patch.object(instances, "get_instance_path", return_value=path), patch.object(process, "find_process_id", return_value=None):
                asyncio.run(scenario(path))

    def test_stop_reports_unreachable_console_and_start_avoids_duplicate(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)
            store.write_instance(path, {"id": "server", "status": "running"})
            with patch.object(process, "synchronize_status", return_value={"id": "server", "status": "running"}), patch.object(process, "send_command", return_value=False):
                with self.assertRaises(HTTPException): process.stop(path)
            with patch.object(process, "find_process_id", return_value=123), patch.object(process, "synchronize_status", return_value={"status": "running"}), patch.object(process.subprocess, "Popen") as popen:
                self.assertEqual(process.start(path)["status"], "running"); popen.assert_not_called()


class AuthTests(unittest.TestCase):
    def test_legacy_upgrade_revocation_expiration_and_logout(self):
        import sqlite3
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "auth.sqlite3"
            with patch.object(auth, "AUTH_DATABASE", database), patch.object(auth, "INITIAL_ADMIN_CODE", "admin-secret"), patch.dict(auth.SESSIONS, {}, clear=True), patch.dict(auth.LOGIN_ATTEMPTS, {}, clear=True):
                asyncio.run(auth.initialize_auth_database())
                with closing(sqlite3.connect(database)) as db:
                    db.execute("UPDATE settings SET value = ? WHERE key = 'admin_code_hash'", (auth.code_hash("admin-secret"),)); db.commit()
                app = FastAPI(); app.include_router(auth.router)
                with TestClient(app) as client:
                    login = client.post("/auth/login", json={"code": "admin-secret"}); self.assertEqual(login.status_code, 200)
                    token = login.json()["token"]; admin = {"X-MArchitect-Token": token}
                    with closing(sqlite3.connect(database)) as db:
                        self.assertTrue(db.execute("SELECT value FROM settings WHERE key = 'admin_code_hash'").fetchone()[0].startswith("scrypt$"))
                    issued = client.post("/auth/user-codes", headers=admin).json()
                    user = client.post("/auth/login", json={"code": issued["code"]}).json()["token"]
                    self.assertEqual(auth.session_role(user), "user")
                    self.assertEqual(client.delete("/auth/user-codes/" + str(issued["id"]), headers=admin).status_code, 204)
                    self.assertIsNone(auth.session_role(user))
                    response = client.put("/auth/admin-code", headers=admin, json={"current_code": "admin-secret", "new_code": "changed-secret", "confirmation": "changed-secret"})
                    self.assertEqual(response.status_code, 200); self.assertIsNone(auth.session_role(token))
                    token = client.post("/auth/login", json={"code": "changed-secret"}).json()["token"]
                    auth.SESSIONS[token]["expires"] = 0; self.assertIsNone(auth.session_role(token))
                    token = client.post("/auth/login", json={"code": "changed-secret"}).json()["token"]
                    client.post("/auth/logout", headers={"X-MArchitect-Token": token}); self.assertIsNone(auth.session_role(token))

    def test_login_rate_limit(self):
        with patch.dict(auth.LOGIN_ATTEMPTS, {"testclient": __import__("collections").deque([time.monotonic()] * 10)}, clear=True):
            app = FastAPI(); app.include_router(auth.router)
            with TestClient(app) as client:
                self.assertEqual(client.post("/auth/login", json={"code": "invalid"}).status_code, 429)


class TaskTests(unittest.TestCase):
    def test_restart_marks_interrupted_and_cleans_only_staging(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary); instance = path / "kept"; instance.mkdir()
            staging = path / ".install-incomplete"; staging.mkdir()
            file = path / "tasks.json"
            store.atomic_json(file, {"tasks": [{"id": "test", "status": "running", "created_at": "now"}]})
            with patch.object(task_store, "TASK_FILE", file), patch.object(task_store, "INSTANCE_DIR", path), patch.dict(task_store.TASKS, {}, clear=True):
                task_store.restore_tasks()
                self.assertEqual(task_store.TASKS["test"]["status"], "failed")
                self.assertFalse(staging.exists()); self.assertTrue(instance.exists())
                self.assertEqual(json.loads(file.read_text(encoding="utf-8"))["tasks"][0]["status"], "failed")


@unittest.skipUnless(sys.platform == "linux", "Linux FIFO and /proc integration")
class LinuxProcessTests(unittest.TestCase):
    def test_console_and_graceful_stop_survive_api_restart(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); path = root / "server"; path.mkdir()
            java = root / "java"; java.symlink_to(sys.executable)
            script = path / "fake_server.py"
            script.write_text('import sys\nprint("Done (0.1s)!", flush=True)\nfor line in sys.stdin:\n print("received:" + line.strip(), flush=True)\n if line.strip() == "stop": break\n', encoding="utf-8")
            store.write_instance(path, {"id": "server", "status": "stopped", "launch_mode": "custom", "custom_command": shlex.join([str(java), "-u", str(script)])})
            with patch.object(store, "INSTANCE_DIR", root):
                handle = None
                try:
                    process.start(path)
                    handle = process.PROCESSES["server"]
                    deadline = time.monotonic() + 10
                    while time.monotonic() < deadline:
                        if process.synchronize_status(path)["status"] == "running": break
                        time.sleep(.05)
                    self.assertEqual(process.synchronize_status(path)["status"], "running")
                    pid = process.find_process_id("server")
                    process.PROCESSES.clear()  # Simulate losing all API process handles.
                    self.assertEqual(process.start(path)["status"], "running")
                    self.assertEqual(process.find_process_id("server"), pid)
                    self.assertTrue(process.send_command("server", "say recovered"))
                    process.stop(path)
                    handle.wait(timeout=10)
                    self.assertEqual(process.synchronize_status(path)["status"], "stopped")
                    self.assertIn("received:say recovered", process.console_snapshot("server")[1])
                    self.assertIn("received:stop", process.console_snapshot("server")[1])
                finally:
                    if handle and handle.poll() is None:
                        process.force_stop(path)
                        handle.wait(timeout=5)
                    process.PROCESSES.pop("server", None)
