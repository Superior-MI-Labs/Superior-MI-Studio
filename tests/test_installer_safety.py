"""Destructive installer behavior is bounded to exact app names and log formats."""
import os
from pathlib import Path
import stat
import tempfile
import unittest
import zipfile
from install_linux import (BASENAME,installed_versions,validate_archive,
    matches_gui_process,prune_versions,prune_logs,latest_report,installed_matches_archive)


class InstallerSafetyTests(unittest.TestCase):
    def test_only_direct_versioned_directories_are_candidates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            old=root/'Superior-MI-Python-Visual-Programming-Lab-v2.12';old.mkdir()
            current=root/BASENAME;current.mkdir()
            other=root/'Superior-MI-Python-Visual-Programming-Lab-v2.12-my-edits';other.mkdir()
            (root/'random-project').mkdir()
            (root/'Superior-MI-Python-Visual-Programming-Lab-v1.1').symlink_to(other, target_is_directory=True)
            self.assertEqual(installed_versions(root),[old,current])

    def test_numeric_version_ordering_survives_multiple_digits(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            names=('v2.9','v2.12','v2.99','v2.100','v3.1','v3.1.2')
            for version in names:
                (root/f'Superior-MI-Python-Visual-Programming-Lab-{version}').mkdir()
            self.assertEqual([p.name.removeprefix('Superior-MI-Python-Visual-Programming-Lab-')
                              for p in installed_versions(root)], list(names))

    def test_prune_versions_preserves_nonmatching_and_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            old=root/'Superior-MI-Python-Visual-Programming-Lab-v2.12';old.mkdir()
            current=root/BASENAME;current.mkdir()
            keep=root/'Superior-MI-Python-Visual-Programming-Lab-v2.12-CHANGES';keep.mkdir()
            link=root/'Superior-MI-Python-Visual-Programming-Lab-v2.11';link.symlink_to(keep, target_is_directory=True)
            prune_versions(root,current)
            self.assertFalse(old.exists())
            self.assertTrue(current.exists() and keep.exists() and link.is_symlink())

    def test_log_cleanup_keeps_current_report_and_unrelated_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            downloads=Path(tmp)
            root=downloads/'SMI-NodeLab-Logs';root.mkdir()
            current=root/'qualification-20261029-031122-123';current.mkdir()
            (root/(current.name+'.tar.gz')).write_text('new')
            old=root/'qualification-20261028-031122-12';old.mkdir()
            (root/(old.name+'.tar.gz')).write_text('old')
            (root/'launch-20261028-031122-22.log').write_text('old')
            unrelated=root/'my-debug-notes.txt';unrelated.write_text('keep')
            (downloads/'SMI-v2.12-doctor.log').write_text('old')
            (downloads/'other-project.log').write_text('keep')
            prune_logs(downloads,keep=current)
            self.assertTrue(current.exists())
            self.assertTrue((root/(current.name+'.tar.gz')).exists())
            self.assertFalse(old.exists())
            self.assertFalse((root/(old.name+'.tar.gz')).exists())
            self.assertTrue(unrelated.exists())
            self.assertTrue((downloads/'other-project.log').exists())
            self.assertEqual(latest_report(downloads),current)

    def test_process_match_requires_exact_module_and_managed_cwd(self):
        with tempfile.TemporaryDirectory() as tmp:
            projects=Path(tmp)
            cwd=projects/'Superior-MI-Python-Visual-Programming-Lab-v2.13'
            self.assertTrue(matches_gui_process(['/usr/bin/python3','-m','studio_native'],cwd,projects))
            self.assertFalse(matches_gui_process(['/usr/bin/python3','-m','studio_native.qt_smoke'],cwd,projects))
            self.assertFalse(matches_gui_process(['bash','RUN-ALL.sh'],cwd,projects))
            self.assertFalse(matches_gui_process(['python3','-m','studio_native'],projects/'Unrelated',projects))
            self.assertFalse(matches_gui_process(['python3','-m','studio_native'],cwd,projects/'elsewhere'))

    def test_existing_install_requalified_only_when_archive_bytes_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            target=root/BASENAME;target.mkdir()
            (target/'RUN-ALL.sh').write_text('good')
            (target/'__pycache__').mkdir()
            (target/'__pycache__'/'extra.pyc').write_text('generated')
            archive=root/'build.zip'
            with zipfile.ZipFile(archive,'w') as z:
                z.writestr(f'{BASENAME}/RUN-ALL.sh','good')
            with zipfile.ZipFile(archive) as z:
                self.assertTrue(installed_matches_archive(z,target))
                (target/'RUN-ALL.sh').write_text('user modified')
                self.assertFalse(installed_matches_archive(z,target))

    def test_zip_rejects_traversal_and_symlinks(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'bad.zip'
            with zipfile.ZipFile(path,'w') as z:
                z.writestr(f'{BASENAME}/../escape','x')
            with zipfile.ZipFile(path) as z, self.assertRaisesRegex(ValueError,'Unsafe ZIP entry'):
                validate_archive(z)
            with zipfile.ZipFile(path,'w') as z:
                info=zipfile.ZipInfo(f'{BASENAME}/link')
                info.create_system=3
                info.external_attr=(stat.S_IFLNK | 0o777)<<16
                z.writestr(info,'/etc/passwd')
            with zipfile.ZipFile(path) as z,self.assertRaisesRegex(ValueError,'symlink refused'):
                validate_archive(z)

if __name__=='__main__':unittest.main()
