import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]

class InstallTests(unittest.TestCase):
    def test_update_restore_and_tampered_backup(self):
        with tempfile.TemporaryDirectory() as temp:
            destination=Path(temp)/'skills/game-ui-production'
            def run(*args):
                return subprocess.run([sys.executable,str(ROOT/'tools/install.py'),'--destination',str(destination),*args],capture_output=True,text=True)
            self.assertEqual(run().returncode,0)
            skill=destination/'SKILL.md';old=skill.read_bytes()+b'\nPrevious isolated test version\n';skill.write_bytes(old)
            update=run('--update');self.assertEqual(update.returncode,0,update.stderr)
            backup=Path(json.loads(update.stdout)['backup']);self.assertEqual((backup/'SKILL.md').read_bytes(),old)
            restore=run('--update','--restore',str(backup));self.assertEqual(restore.returncode,0,restore.stderr)
            self.assertEqual(skill.read_bytes(),old)
            (backup/'SKILL.md').write_bytes(b'tampered')
            self.assertNotEqual(run('--update','--restore',str(backup)).returncode,0)
