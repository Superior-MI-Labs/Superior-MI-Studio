"""Cross-process source publication: no data loss among cooperating Studio writers."""
from __future__ import annotations
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest

from studio_native.python_edit import EditProposal, SourceEditHistory, _source_write_lock, apply_proposal
from studio_native.python_graph import SourceError
from studio_native.source_editor import SourceDocumentSession

ROOT=Path(__file__).resolve().parents[1]

WORKER='''
import sys
from pathlib import Path
from studio_native.python_edit import EditProposal, apply_proposal
path=Path(sys.argv[1]);old=bytes.fromhex(sys.argv[2]);new=bytes.fromhex(sys.argv[3])
print('READY',flush=True)
try:
    apply_proposal(EditProposal(path,old,new,'utf-8','child'))
except Exception as exc:
    print('REFUSED',str(exc),flush=True)
    sys.exit(12)
print('COMMITTED',flush=True)
'''


class ProcessWriterTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        self.path=self.root/'program.py'
        self.original=b'def f(a):\n    return a\n'
        self.path.write_bytes(self.original)

    def edit(self,change,original=None):
        return EditProposal(self.path, self.original if original is None else original,
                            change,'utf-8','qualified source change')

    def child(self,change):
        return subprocess.Popen([sys.executable,'-u','-c',WORKER,str(self.path),
                                 self.original.hex(),change.hex()],
                                cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)

    def test_process_waits_on_stable_lock_then_refuses_stale_bytes(self):
        changed=b'def f(a):\n    return a * 2\n'
        child=None
        with _source_write_lock(self.path):
            child=self.child(changed)
            self.assertEqual(child.stdout.readline().strip(),'READY')
            # The child must not be able to publish while another process
            # holds the sidecar lock. Unlike time-based races, this setup
            # makes the ordering deterministic.
            self.assertIsNone(child.poll())
            self.path.write_bytes(b'def f(a):\n    return a + 3\n')
        out,err=child.communicate(timeout=7)
        self.assertEqual(child.returncode,12,out+err)
        self.assertIn('changed externally',out)
        self.assertEqual(self.path.read_bytes(),b'def f(a):\n    return a + 3\n')
        self.assertFalse(list(self.root.glob('*.smi-backup*')))

    def test_competing_process_writers_have_one_winner(self):
        a=b'def f(a):\n    return a + 2\n'
        b=b'def f(a):\n    return a * 3\n'
        with _source_write_lock(self.path):
            first=self.child(a)
            second=self.child(b)
            self.assertEqual(first.stdout.readline().strip(),'READY')
            self.assertEqual(second.stdout.readline().strip(),'READY')
            self.assertIsNone(first.poll())
            self.assertIsNone(second.poll())
        results=[p.communicate(timeout=7) for p in (first,second)]
        statuses=[p.returncode for p in (first,second)]
        self.assertEqual(sorted(statuses),[0,12],results)
        self.assertIn(self.path.read_bytes(),(a,b))
        self.assertEqual(len(list(self.root.glob('*.smi-backup*'))),1)
        self.assertEqual((self.root/'program.py.smi-backup').read_bytes(),self.original)

    def test_existing_lock_is_private_stable_and_not_deleted(self):
        candidate=b'def f(a):\n    return a + 1\n'
        apply_proposal(self.edit(candidate))
        lock=self.root/'.program.py.smi-lock'
        inode=lock.stat().st_ino
        self.assertEqual(stat.S_IMODE(lock.stat().st_mode),0o600)
        apply_proposal(self.edit(self.original,original=candidate))
        self.assertEqual(lock.stat().st_ino,inode)
        self.assertEqual(self.path.read_bytes(),self.original)

    def test_symlinked_or_public_lock_refused(self):
        lock=self.root/'.program.py.smi-lock'
        target=self.root/'another-file'
        target.write_bytes(b'locked')
        lock.symlink_to(target)
        with self.assertRaisesRegex(SourceError,'lock'):
            apply_proposal(self.edit(b'pass\n'))
        lock.unlink()
        lock.write_bytes(b'')
        lock.chmod(0o666)
        with self.assertRaisesRegex(SourceError,'ownership or permissions'):
            apply_proposal(self.edit(b'pass\n'))
        self.assertEqual(self.path.read_bytes(),self.original)

    def test_history_undo_refuses_other_process_change_without_consuming_history(self):
        history=SourceEditHistory()
        first=b'def f(a):\n    return a + 1\n'
        history.apply(self.edit(first))
        external=b'def f(a):\n    return a + 2\n'
        child=subprocess.run([sys.executable,'-u','-c',WORKER,str(self.path),
                              first.hex(),external.hex()],cwd=ROOT,
                              capture_output=True,text=True,timeout=7)
        self.assertEqual(child.returncode,0,child.stdout+child.stderr)
        with self.assertRaisesRegex(SourceError,'externally'):
            history.undo(self.path)
        self.assertTrue(history.can_undo(self.path))
        self.assertEqual(self.path.read_bytes(),external)

    def test_source_session_save_inherits_cross_process_guard(self):
        session=SourceDocumentSession.open(self.path)
        session.update('def f(a):\n    return a + 8\n')
        competing=b'def f(a):\n    return a + 9\n'
        child=subprocess.run([sys.executable,'-u','-c',WORKER,str(self.path),
                              self.original.hex(),competing.hex()],cwd=ROOT,
                              capture_output=True,text=True,timeout=7)
        self.assertEqual(child.returncode,0,child.stdout+child.stderr)
        with self.assertRaisesRegex(SourceError,'externally'):
            session.commit()
        self.assertTrue(session.dirty)
        self.assertIn('return a + 8',session.text)
        self.assertEqual(self.path.read_bytes(),competing)


if __name__=='__main__': unittest.main()
