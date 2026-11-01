import sqlite3
import tempfile
import time
import unittest
from contextlib import closing
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from modules import auth, instance_rules, time_settings


class ServiceTimeTests(unittest.TestCase):
    def test_permissions_validation_persistence_and_clock(self):
        with tempfile.TemporaryDirectory() as temporary:
            db = Path(temporary) / "auth.sqlite3"
            with closing(sqlite3.connect(db)) as connection:
                connection.execute("CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
                connection.commit()
            sessions = {role: {"role": role, "expires": time.monotonic() + 3600} for role in ["admin", "user"]}
            app = FastAPI(); app.include_router(time_settings.router)
            with patch.object(time_settings, "AUTH_DATABASE", db), patch.object(time_settings, "SERVICE_TIMEZONE", "system"), patch.dict(auth.SESSIONS, sessions), TestClient(app) as client:
                self.assertEqual(client.get("/settings/time").status_code, 401)
                self.assertEqual(client.get("/settings/time", headers={"X-MArchitect-Token": "user"}).json()["timezone"], "system")
                self.assertEqual(client.put("/settings/time", headers={"X-MArchitect-Token": "user"}, json={"timezone": "UTC"}).status_code, 403)
                admin = {"X-MArchitect-Token": "admin"}
                self.assertEqual(client.put("/settings/time", headers=admin, json={"timezone": "invalid/timezone"}).status_code, 422)
                saved = client.put("/settings/time", headers=admin, json={"timezone": "Asia/Seoul"})
                self.assertEqual(saved.status_code, 200)
                self.assertEqual(saved.json()["utc_offset_seconds"], 32400)
                self.assertEqual(datetime.fromisoformat(saved.json()["current_time"]).utcoffset().total_seconds(), 32400)
                time_settings.SERVICE_TIMEZONE = "system"
                time_settings.sync_time_settings()
                self.assertEqual(time_settings.SERVICE_TIMEZONE, "Asia/Seoul")
                now = datetime.fromisoformat("2026-11-02T00:00:00+00:00")
                self.assertEqual(instance_rules.local_time(instance_rules.Rules(), now).hour, 9)
                self.assertEqual(client.put("/settings/time", headers=admin, json={"timezone": "UTC"}).status_code, 200)
                self.assertEqual(instance_rules.local_time(instance_rules.Rules(), now).hour, 0)
                self.assertEqual(client.put("/settings/time", headers=admin, json={"timezone": "system"}).json()["timezone"], "system")
