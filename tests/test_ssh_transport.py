"""Check SSH key handling without making network connections."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "ci-deploy.sh"
SHA = "a" * 40
MOCK_GIT = r"""#!/usr/bin/env python3
import os, sys
args = sys.argv[1:]
if args[:2] == ["rev-parse", "HEAD"]:
    print(os.environ["SOURCE_SHA"])
elif args[:2] == ["ls-remote", "origin"]:
    print(os.environ["SOURCE_SHA"] + "\trefs/heads/master")
elif args and args[0] == "archive":
    sys.stdout.buffer.write(b"test source archive")
else:
    sys.exit("Unexpected git command")
"""
MOCK_SSH = r"""#!/usr/bin/env python3
import hashlib, json, os, pathlib, sys
args = sys.argv[1:]
key = pathlib.Path(args[args.index("-i") + 1])
with pathlib.Path(os.environ["SSH_TEST_LOG"]).open("a") as log:
    log.write(json.dumps({"key_hash": hashlib.sha256(key.read_bytes()).hexdigest(),
                         "key_mode": key.stat().st_mode & 0o777}) + "\n")
sys.stdin.buffer.read()
"""


class SSHTransportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        for name, code in (("git", MOCK_GIT), ("ssh", MOCK_SSH)):
            executable = self.bin / name
            executable.write_text(code)
            executable.chmod(0o755)
        self.key = self.root / "deployment-key"
        subprocess.run(
            ["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(self.key)],
            check=True, capture_output=True,
        )
        self.original = self.key.read_bytes()
        self.log = self.root / "ssh-calls.jsonl"
        self.env = dict(
            os.environ, PATH=f"{self.bin}:{os.environ['PATH']}",
            SOURCE_SHA=SHA, GITHUB_RUN_ID="123", GITHUB_RUN_ATTEMPT="1",
            RUNNER_TEMP=str(self.root), DEPLOY_HOST="ci.example.invalid",
            DEPLOY_USER="deploy", DEPLOY_PORT="22", DEPLOY_PATH="/srv/marchitect",
            DEPLOY_PROJECT="marchitect", DEPLOY_KNOWN_HOSTS="test-known-hosts",
            SSH_TEST_LOG=str(self.log),
        )
        self.env.pop("DEPLOY_SSH_KEY", None)
        self.env.pop("DEPLOY_SSH_KEY_PATH", None)

    def run_transport(self, **settings):
        return subprocess.run(
            ["bash", str(SCRIPT)], env=dict(self.env, **settings),
            text=True, capture_output=True, timeout=10,
        )

    def assert_correct_key_and_cleanup(self):
        calls = [json.loads(line) for line in self.log.read_text().splitlines()]
        self.assertEqual(len(calls), 2)
        expected = hashlib.sha256(self.original).hexdigest()
        self.assertTrue(all(call["key_hash"] == expected and call["key_mode"] == 0o600 for call in calls))
        self.assertEqual(self.key.read_bytes(), self.original)
        self.assertFalse(list(self.root.glob("marchitect-ssh.*")))

    def test_original_vm_key_works_without_a_valid_registered_secret(self):
        result = self.run_transport(
            DEPLOY_SSH_KEY_PATH=str(self.key), DEPLOY_SSH_KEY="invalid-copy",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assert_correct_key_and_cleanup()

    def test_registered_private_key_still_works(self):
        result = self.run_transport(DEPLOY_SSH_KEY=self.original.decode())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assert_correct_key_and_cleanup()

    def test_invalid_key_is_rejected_before_ssh(self):
        self.key.write_text("invalid-private-key-copy\n")
        result = self.run_transport(DEPLOY_SSH_KEY_PATH=str(self.key))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("key is invalid", result.stderr)
        self.assertFalse(self.log.exists())
        self.assertFalse(list(self.root.glob("marchitect-ssh.*")))

    def test_missing_vm_key_is_rejected_before_ssh(self):
        result = self.run_transport(DEPLOY_SSH_KEY_PATH=str(self.root / "missing-key"))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing or unreadable", result.stderr)
        self.assertFalse(self.log.exists())


if __name__ == "__main__":
    unittest.main()
