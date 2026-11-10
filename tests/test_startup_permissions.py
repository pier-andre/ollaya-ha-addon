"""Regression test: HA options are 0600 root-only, yet server runs unprivileged.

Requires root, runuser, and an 'ollaya' account. Skips on ordinary developer
machines; can also be run in a disposable Linux build container after adding
that account. No Home Assistant Supervisor is required.
"""
import json
import os
from pathlib import Path
import pwd
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class StartupPermissionsTest(unittest.TestCase):
    def test_private_configuration_bootstrap(self):
        if os.geteuid() != 0 or not shutil.which("runuser"):
            self.skipTest("requires root and runuser")
        try:
            pwd.getpwnam("ollaya")
        except KeyError:
            self.skipTest("requires ollaya system user and group")

        with tempfile.TemporaryDirectory(prefix="ollaya-startup-") as root_name:
            root = Path(root_name)
            root.chmod(0o755)  # let unprivileged test process traverse fixture
            options = root / "options.json"
            options.write_text(json.dumps({"default_model": "laya:en", "threads": 2}), encoding="utf-8")
            options.chmod(0o600)
            models = root / "data" / "ollaya"
            models.parent.mkdir(mode=0o755)
            runtime = root / "run" / "ollaya-ha"
            (root / "run").mkdir(mode=0o755)
            bindir = root / "bin"
            bindir.mkdir(mode=0o755)

            # Mock only the last gosu/exec step; run the *real* shell bootstrap.
            gosu = bindir / "gosu"
            gosu.write_text("""#!/bin/sh
set -eu
[ "$1" = "ollaya:ollaya" ] || exit 45
exec runuser -u ollaya -- python3 -c '
import json, os, pathlib, stat
stage = pathlib.Path(os.environ["OLLAYA_HA_OPTIONS"])
source = pathlib.Path(os.environ["OLLAYA_HA_SOURCE_OPTIONS"])
assert json.loads(stage.read_text())["default_model"] == "laya:en"
assert stat.S_IMODE(stage.stat().st_mode) == 0o640
assert stage.stat().st_uid == 0
assert stat.S_IMODE(stage.parent.stat().st_mode) == 0o750
assert stage.parent.stat().st_uid == 0
# App data is writable by the service account; persistent model files remain
# in /data/ollaya/models, not beside the Supervisor-owned options.json.
data = pathlib.Path(os.environ["OLLAYA_HA_DATA"])
models = data / "models"
assert data.stat().st_uid == os.geteuid()
assert models.stat().st_uid == os.geteuid()
assert stat.S_IMODE(data.stat().st_mode) == 0o700
assert stat.S_IMODE(models.stat().st_mode) == 0o700
proof = models / "write-test.txt"
if proof.exists():
    assert proof.read_text() == "persisted after restart"
else:
    proof.write_text("persisted after restart")
try:
    source.read_text()
except PermissionError:
    pass
else:
    raise AssertionError("unprivileged user could read original options")
print("configuration staged; service privileges dropped")
'
""", encoding="utf-8")
            gosu.chmod(0o755)
            env = {**os.environ,
                   "PATH": str(bindir) + ":" + os.environ["PATH"],
                   "OLLAYA_HA_SOURCE_OPTIONS": str(options),
                   "OLLAYA_HA_DATA": str(models),
                   "OLLAYA_HA_RUN_DIR": str(runtime)}
            result = subprocess.run(["/bin/sh", str(ROOT / "ollaya" / "start.sh")],
                                    env=env, text=True, capture_output=True, timeout=20)
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertIn("configuration staged; service privileges dropped", result.stdout)
            self.assertEqual(0o600, options.stat().st_mode & 0o777)
            # Re-run startup and verify model files are still present.
            rerun = subprocess.run(["/bin/sh", str(ROOT / "ollaya" / "start.sh")],
                                   env=env, text=True, capture_output=True, timeout=20)
            self.assertEqual(0, rerun.returncode, rerun.stdout + rerun.stderr)
            self.assertEqual("persisted after restart", (models / "models" / "write-test.txt").read_text())


if __name__ == "__main__":
    unittest.main()
