"""Cross-file contracts: avoid another stale smoke count or duplicate work queue."""
from pathlib import Path
import tempfile
import csv
import re
import unittest

ROOT=Path(__file__).resolve().parents[1]


class ReleaseContracts(unittest.TestCase):
    def test_versioned_installer_gui_and_readme_agree(self):
        source=(ROOT/'install_linux.py').read_text()
        match=re.search(r"^VERSION\s*=\s*'(v\d+\.\d+)'",source,re.M)
        self.assertIsNotNone(match)
        version=match.group(1)
        readme=(ROOT/'README.md').read_text()
        gui=(ROOT/'studio_native/gui.py').read_text()
        pipeline=(ROOT/'docs/RELEASE-PIPELINE.md').read_text()
        self.assertIn('Superior MI Studio',readme)
        self.assertIn(version,readme)
        self.assertIn('docs/RELEASE-PIPELINE.md',readme)
        self.assertIn('install_linux.py',pipeline)
        self.assertIn('scripts/build_release.py',pipeline)
        self.assertIn('Visual Programming Lab '+version.removeprefix('v'),gui)

    def test_release_script_uses_exact_installer_version_and_native_gate(self):
        installer=(ROOT/'install_linux.py').read_text()
        script=(ROOT/'INSTALL-AND-REPORT.sh').read_text()
        version=re.search(r"^VERSION\s*=\s*'(v\d+\.\d+)'",installer,re.M).group(1)
        self.assertRegex(script,rf'(?m)^VERSION={re.escape(version)}$')
        self.assertIn('python3 "$INSTALLER" "$ZIP" --no-launch',script)
        self.assertIn('if (( STATUS != 0 ))',script)
        self.assertIn('-newer "$REPORT_MARKER"',script)
        self.assertIn('No qualification archive produced',script)
        self.assertIn('bash "$APP/launch-linux.sh"',script)

    def test_single_work_queue_and_valid_acceptance_matrix(self):
        queue=(ROOT/'docs/agents/NEXT-TASKS.md').read_text()
        ledger=(ROOT/'docs/architecture/IMPLEMENTATION-AND-TRACEABILITY.md').read_text()
        self.assertIn('canonical implementation queue',queue)
        self.assertIn('docs/agents/NEXT-TASKS.md',ledger)
        self.assertNotIn('## 3. Recommended first 14 agent work tickets',ledger)
        with (ROOT/'docs/architecture/ACCEPTANCE-MATRIX.csv').open(newline='') as stream:
            reader=csv.DictReader(stream)
            self.assertEqual(reader.fieldnames,['test_id','phase','category','scenario',
              'acceptance','test_method','status','evidence'])
            rows=list(reader)
        self.assertTrue(rows)
        self.assertFalse(any(None in row or None in row.values() for row in rows))
        ids=[row['test_id'] for row in rows]
        self.assertEqual(len(set(ids)),len(ids))

    def test_release_builder_reuses_installer_contract_and_refuses_overwrite(self):
        from scripts.build_release import BASENAME, source_files
        from install_linux import BASENAME as INSTALL_BASENAME
        self.assertEqual(BASENAME, INSTALL_BASENAME)
        included={p.relative_to(ROOT).as_posix() for p in source_files(ROOT)}
        self.assertIn('studio_native/draft_recovery.py',included)
        self.assertIn('tests/test_v259_source_recovery.py',included)
        self.assertNotIn('REPOSITORY-SHA256SUMS.txt',included)
        self.assertFalse(any('.agent-artifacts' in name or '__pycache__' in name for name in included))

    def test_release_builder_preserves_existing_archive(self):
        from scripts.build_release import build
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder)/'already-created.zip'
            target.write_bytes(b'other agent output')
            with self.assertRaises(FileExistsError):
                build(target)
            self.assertEqual(target.read_bytes(),b'other agent output')

    def test_recovery_native_smoke_isolated_and_supervised(self):
        smoke=(ROOT/'studio_native/qt_smoke.py').read_text()
        shell=(ROOT/'test-qt-offscreen.sh').read_text()
        self.assertIn('QT_STAGE crash-recovery-prompt-and-conflict',smoke)
        self.assertIn('exercise_source_recovery(app)',smoke)
        self.assertGreaterEqual(smoke.count('exercise_modal(app,QMessageBox'),2)
        self.assertIn('SMI_RECOVERY_DIR',shell)
        self.assertIn('mktemp -d',shell)
        self.assertIn('trap',shell)


if __name__=='__main__':
    unittest.main()
