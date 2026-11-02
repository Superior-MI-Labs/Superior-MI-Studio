"""CI reduces the host-only Qt feedback loop without hiding the desktop gate."""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]

class ContinuousQualificationContract(unittest.TestCase):
    def test_single_existing_workflow_runs_isolated_qt_stage(self):
        source=(ROOT/'.github/workflows/headless.yml').read_text()
        self.assertIn('  headless:',source)
        self.assertIn('  native-qt:',source)
        self.assertIn('sudo apt-get install -y --no-install-recommends python3-pyqt6',source)
        self.assertIn('bash scripts/agent-verify.sh --native',source)
        self.assertIn('if: failure()',source)
        self.assertIn('studio-native-qt-diagnostics',source)
        self.assertNotIn('QT: SKIPPED',source)

    def test_doctor_banner_uses_installer_version(self):
        source=(ROOT/'doctor.sh').read_text()
        self.assertIn('from install_linux import VERSION',source)
        self.assertNotIn('v2.88 doctor',source)

if __name__=='__main__':unittest.main()
