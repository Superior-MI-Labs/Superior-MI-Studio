"""The canonical release runner fails closed when the headless doctor stalls."""
import os
import shutil
import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path


ROOT=Path(__file__).resolve().parents[1]


class DoctorWatchdogContract(unittest.TestCase):
    def setUp(self):
        self.home=tempfile.TemporaryDirectory()
        self.addCleanup(self.home.cleanup)
        self.base=Path(self.home.name)
        self.project=self.base/'fake-studio'
        self.project.mkdir()
        shutil.copyfile(ROOT/'RUN-ALL.sh',self.project/'RUN-ALL.sh')
        self.reports=self.base/'reports'

    def run_runner(self, doctor, timeout='0.15'):
        script=self.project/'doctor.sh'
        script.write_text('#!/usr/bin/env bash\n'+doctor+'\n',encoding='utf-8')
        env={**os.environ,'SMI_LOG_DIR':str(self.reports),
             'SMI_DOCTOR_TIMEOUT':timeout}
        return subprocess.run(['bash',str(self.project/'RUN-ALL.sh'),'--headless'],
             env=env,capture_output=True,text=True,timeout=8)

    def test_stalled_doctor_fails_with_new_uploadable_report(self):
        result=self.run_runner('sleep 3')
        self.assertNotEqual(result.returncode,0)
        self.assertIn('DOCTOR: TIMEOUT',result.stdout)
        self.assertIn('CHECKS_FAILED_OR_UNAVAILABLE_REVIEW_REQUIRED',result.stdout)
        reports=list(self.reports.glob('qualification-*.tar.gz'))
        self.assertEqual(len(reports),1)
        with tarfile.open(reports[0]) as archive:
            self.assertTrue(any(item.name.endswith('/doctor.log') for item in archive))

    def test_successful_doctor_still_gets_complete_headless_marker(self):
        result=self.run_runner('echo DOCTOR_FIXTURE_PASS',timeout='4')
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn('DOCTOR: PASS',result.stdout)
        self.assertIn('CHECKS_PASS',result.stdout)
        self.assertIn('QT: SKIPPED by --headless',result.stdout)
        self.assertEqual(len(list(self.reports.glob('qualification-*.tar.gz'))),1)

    def test_nonzero_doctor_is_not_reported_as_timeout_or_success(self):
        result=self.run_runner('echo BAD_FIXTURE; exit 17',timeout='4')
        self.assertNotEqual(result.returncode,0)
        self.assertIn('DOCTOR: FAIL (17)',result.stdout)
        self.assertNotIn('DOCTOR: TIMEOUT',result.stdout)
        self.assertIn('CHECKS_FAILED_OR_UNAVAILABLE_REVIEW_REQUIRED',result.stdout)


if __name__=='__main__':unittest.main()
