import sqlite3
from contextlib import closing
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from modules import domain_settings
from modules.auth import SESSIONS


class DomainSettingsTests(unittest.TestCase):
    def test_admin_persistence_validation_and_permissions(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "frontend-settings" / "domains.json"
            db_path = Path(directory) / "auth.sqlite3"
            with closing(sqlite3.connect(db_path)) as db:
                db.execute("CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
                db.commit()
            app = FastAPI()
            app.include_router(domain_settings.router)
            with patch.object(domain_settings, "AUTH_DATABASE", db_path), patch.object(domain_settings, "SETTINGS_FILE", path), patch.dict(
                SESSIONS, {"admin-test": "admin", "user-test": "user"}
            ), TestClient(app) as client:
                admin = {"X-MArchitect-Token": "admin-test"}
                self.assertEqual(client.get("/settings/domains").status_code, 401)
                self.assertEqual(client.put("/settings/domains", headers={"X-MArchitect-Token": "user-test"}, json={"domains": []}).status_code, 403)
                self.assertEqual(client.get("/settings/domains", headers=admin).json(), {"domains": []})
                result = client.put("/settings/domains", headers=admin, json={"domains": [" Panel.Example.com ", "panel.example.com"]})
                self.assertEqual(result.status_code, 200)
                self.assertEqual(result.json(), {"domains": ["panel.example.com"]})
                self.assertEqual(client.get("/settings/domains", headers=admin).json(), result.json())
                self.assertIn("panel.example.com", path.read_text())
                for invalid in ["https://example.com", "*.example.com", "example.com:5173", "example.com/path", ".com", "true"]:
                    self.assertEqual(client.put("/settings/domains", headers=admin, json={"domains": [invalid]}).status_code, 422)
                self.assertEqual(client.get("/settings/domains", headers=admin).json(), result.json())
                self.assertEqual(client.put("/settings/domains", headers=admin, json={"domains": []}).json(), {"domains": []})

    def test_frontend_copy_is_recreated_from_database(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "domains.json"
            path.write_text("invalid")
            db_path = Path(directory) / "auth.sqlite3"
            with closing(sqlite3.connect(db_path)) as db:
                db.execute("CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
                db.commit()
            app = FastAPI()
            app.include_router(domain_settings.router)
            with patch.object(domain_settings, "AUTH_DATABASE", db_path), patch.object(domain_settings, "SETTINGS_FILE", path), patch.dict(SESSIONS, {"admin-test": "admin"}), TestClient(app) as client:
                self.assertEqual(client.put("/settings/domains", headers={"X-MArchitect-Token": "admin-test"}, json={"domains": ["192.168.1.10", "2001:db8::1", "panel.example.com"]}).status_code, 200)
                path.unlink()
                domain_settings.sync_domain_settings()
                self.assertIn("192.168.1.10", path.read_text())
                self.assertIn("2001:db8::1", path.read_text())
