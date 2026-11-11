"""CI qualification runs once per feature-branch PR without losing either gate."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / '.github' / 'workflows' / 'headless.yml'
PIPELINE = ROOT / 'docs' / 'RELEASE-PIPELINE.md'


class WorkflowTriggerContractTests(unittest.TestCase):
    def test_main_push_and_pull_request_keep_both_qualification_lanes(self):
        content = WORKFLOW.read_text(encoding='utf-8')
        triggers = content.split('\njobs:', 1)[0]
        self.assertRegex(
            triggers,
            r'(?m)^on:\n(?:#.*\n)*  push:\n    branches: \[main\]\n  pull_request:\n  workflow_dispatch:')
        self.assertEqual(triggers.count('  push:'), 1)
        self.assertEqual(triggers.count('  pull_request:'), 1)
        self.assertIn('  headless:', content)
        self.assertIn('  native-qt:', content)
        self.assertEqual(content.count('run: bash scripts/agent-verify.sh --headless'), 1)
        self.assertEqual(content.count('run: bash scripts/agent-verify.sh --native'), 1)

    def test_native_qualification_and_diagnostics_not_downgraded(self):
        content = WORKFLOW.read_text(encoding='utf-8')
        self.assertIn("sudo apt-get install -y --no-install-recommends python3-pyqt6", content)
        self.assertIn("SMI_LOG_DIR:", content)
        self.assertIn("if: failure()", content)
        self.assertIn('studio-native-qt-diagnostics', content)
        self.assertIn('studio-native-qt-screenshots', content)
        self.assertIn('retention-days: 14', content)

    def test_release_pipeline_documents_manual_pre_pr_qualification(self):
        content = PIPELINE.read_text(encoding='utf-8')
        self.assertIn('pull requests (including drafts)', content)
        self.assertIn('direct pushes to `main`', content)
        self.assertIn('manually dispatch', content)
        self.assertIn('Linux Mint host evidence', content)


if __name__ == '__main__':
    unittest.main()
