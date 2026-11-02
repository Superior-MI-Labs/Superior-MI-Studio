"""One existing qualification owner: durable verdict + bounded process tree."""
import os
import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from install_linux import run_qualification


ROOT=Path(__file__).resolve().parents[1]


class ReleaseSupervision(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.app=Path(self.temp.name)/'studio'
        self.app.mkdir()
        self.runner=self.app/'RUN-ALL.sh'

    def fake(self,body):
        self.runner.write_text('#!/usr/bin/env bash\n'+body+'\n',encoding='utf-8')

    def test_run_existing_runner_success_and_headless_flag(self):
        self.fake('test "${1:-}" = "--headless"')
        with patch.dict(os.environ,{'SMI_INSTALL_QUALIFICATION_TIMEOUT':'2'}):
            self.assertEqual(run_qualification(self.app,headless=True),0)
            self.assertNotEqual(run_qualification(self.app,headless=False),0)

    def test_child_failure_cannot_become_success(self):
        self.fake('exit 31')
        with patch.dict(os.environ,{'SMI_INSTALL_QUALIFICATION_TIMEOUT':'2'}):
            self.assertEqual(run_qualification(self.app,headless=True),31)

    def test_hanging_runner_and_descendants_are_bounded(self):
        # The subprocess waits on a descendant rather than terminating at the
        # immediate shell; the private group must be terminated together.
        self.fake('sleep 20 & wait')
        with patch.dict(os.environ,{'SMI_INSTALL_QUALIFICATION_TIMEOUT':'0.2'}):
            self.assertEqual(run_qualification(self.app,headless=True),124)

    def test_invalid_timeout_refuses_before_runner(self):
        self.fake('touch should-not-exist')
        for value in ('garbage','-1','0','3601','nan','inf'):
            with self.subTest(value=value):
                with patch.dict(os.environ,{'SMI_INSTALL_QUALIFICATION_TIMEOUT':value}):
                    with self.assertRaises(ValueError):
                        run_qualification(self.app,headless=True)
        self.assertFalse((self.app/'should-not-exist').exists())

    def test_failed_doctor_verdict_is_archived_as_failure(self):
        (self.app/'doctor.sh').write_text('#!/usr/bin/env bash\nexit 19\n')
        self.runner.write_bytes((ROOT/'RUN-ALL.sh').read_bytes())
        reportdir=Path(self.temp.name)/'reports'
        env={**os.environ,'SMI_LOG_DIR':str(reportdir),'SMI_DOCTOR_TIMEOUT':'4'}
        result=subprocess.run(['bash',str(self.runner),'--headless'],
            cwd=self.app,env=env,capture_output=True,text=True,timeout=10)
        self.assertNotEqual(result.returncode,0)
        with tarfile.open(next(reportdir.glob('qualification-*.tar.gz'))) as tar:
            member=next(m for m in tar.getmembers()
                if m.name.endswith('qualification-verdict.txt'))
            verdict=tar.extractfile(member).read().decode()
        self.assertIn('doctor_status=19\n',verdict)
        self.assertIn('verdict=CHECKS_FAILED_OR_UNAVAILABLE_REVIEW_REQUIRED\n',verdict)

    def test_verdict_is_in_the_archived_report_but_not_a_new_authority(self):
        (self.app/'doctor.sh').write_text('#!/usr/bin/env bash\necho OK\n')
        self.runner.write_bytes((ROOT/'RUN-ALL.sh').read_bytes())
        reportdir=Path(self.temp.name)/'reports'
        env={**os.environ,'SMI_LOG_DIR':str(reportdir),'SMI_DOCTOR_TIMEOUT':'4'}
        result=subprocess.run(['bash',str(self.runner),'--headless'],
            cwd=self.app,env=env,capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn('CHECKS_PASS',result.stdout)
        archives=list(reportdir.glob('qualification-*.tar.gz'))
        self.assertEqual(len(archives),1)
        with tarfile.open(archives[0]) as tar:
            records=[m for m in tar.getmembers()
                if m.name.endswith('qualification-verdict.txt')]
            self.assertEqual(len(records),1)
            evidence=tar.extractfile(records[0]).read().decode()
        self.assertIn('doctor_status=0\n',evidence)
        self.assertIn('qt_status=0\n',evidence)
        self.assertIn('verdict=CHECKS_PASS\n',evidence)


if __name__=='__main__': unittest.main()
