"""Source text transactions and accurate AST location -> Qt UTF-16 positions.

This module does not import Qt. Source text is the authority: graph state is a
reparse of the bytes that were safely committed, never a competing document.
"""
from __future__ import annotations
import ast
from dataclasses import dataclass, field
from pathlib import Path

from .python_edit import EditProposal, apply_proposal
from .draft_recovery import DraftRecoveryStore, RecoveryRecord, _digest
from .python_graph import PythonDocument, SourceError, MAX_SOURCE, decode_python_source


def _utf16_units(text: str) -> int:
    return len(text.encode('utf-16-le')) // 2


def span_to_utf16(text: str, span: dict) -> tuple[int, int]:
    """AST columns count UTF-8 bytes, Qt positions count UTF-16 units."""
    lines=text.splitlines(keepends=True)
    positions=[]
    for line_key, col_key in (('line','col'),('end_line','end_col')):
        line=span[line_key]
        col=span[col_key]
        if not 1 <= line <= len(lines) or col < 0:
            raise SourceError('Source location is out of range')
        try:
            prefix=lines[line-1].encode('utf-8')[:col].decode('utf-8')
        except UnicodeError as exc:
            raise SourceError('Source location divides a Unicode character') from exc
        if len(prefix.encode('utf-8')) != col:
            raise SourceError('Invalid source byte offset')
        positions.append(_utf16_units(''.join(lines[:line-1])+prefix))
    start,end=positions
    if end < start:raise SourceError('Invalid reversed source span')
    return start,end


def _editor_candidate_bytes(doc: PythonDocument, edited: str) -> bytes:
    """Translate a Qt LF text revision to original source bytes in one place.

    This is a pure conversion, not a save or an execution qualification. Disk
    mutation and external-change detection belong to the guarded writer.
    """
    if not isinstance(edited,str):raise SourceError('Expected Python source text')
    if '\r' in edited:raise SourceError('Editor text contains unexpected carriage returns')
    original=doc.source
    if '\r\n' in original:
        if original.replace('\r\n','').find('\n') >= 0 or original.replace('\r\n','').find('\r')>=0:
            raise SourceError('Mixed line endings require an external text editor')
        candidate_text=edited.replace('\n','\r\n')
    elif '\r' in original:
        raise SourceError('Legacy CR line endings require an external text editor')
    else:candidate_text=edited
    try:candidate=candidate_text.encode(doc.encoding)
    except (UnicodeError,LookupError) as exc:
        raise SourceError('Cannot encode edited source: '+str(exc)) from exc
    if len(candidate)>MAX_SOURCE:raise SourceError('Edited source exceeds 1.5 MB analysis limit')
    decoded,_=decode_python_source(candidate)
    if decoded.replace('\r\n','\n').replace('\r','\n')!=edited:
        raise SourceError('Python source encoding declaration changes the edited text; choose a compatible encoding')
    return candidate


def preview_source_change(doc: PythonDocument, edited: str) -> PythonDocument:
    """Produce a read-only graph-eligible snapshot from unsaved editor text.

    No temporary disk write, no second parser or source registry. Invalid
    Python reports SourceError; the caller must retain its original text and
    must not silently treat the previous graph as current.
    """
    return PythonDocument.from_bytes(doc.path,_editor_candidate_bytes(doc,edited))


def prepare_source_change(doc: PythonDocument, edited: str) -> EditProposal | None:
    """Validate text edits before guarded publication to the real source file.

    Keep this strict transaction contract for now; ordinary invalid-source
    saving moves with the revisioned document session in the next phase.
    """
    candidate=_editor_candidate_bytes(doc,edited)
    if candidate==doc.raw:return None
    try:
        text=candidate.decode(doc.encoding)
        tree=ast.parse(text,filename=str(doc.path),type_comments=True)
        compile(tree,str(doc.path),'exec',dont_inherit=True)
    except (SyntaxError,ValueError,TypeError) as exc:
        raise SourceError(f'Python syntax error: {exc}') from exc
    return EditProposal(doc.path,doc.raw,candidate,doc.encoding,'Edit Python source in Studio')


def save_source_change(doc: PythonDocument, edited: str, *, history=None):
    proposed=prepare_source_change(doc,edited)
    if proposed is None:return None
    return history.apply(proposed) if history is not None else apply_proposal(proposed)


@dataclass(frozen=True)
class _DraftDelta:
    """Minimal reversible text delta; no duplicate full-file snapshots."""
    offset: int
    removed: str
    inserted: str

    @classmethod
    def between(cls, original: str, edited: str) -> '_DraftDelta':
        start=0
        end=min(len(original),len(edited))
        while start<end and original[start]==edited[start]:
            start+=1
        old_end=len(original);new_end=len(edited)
        while old_end>start and new_end>start and original[old_end-1]==edited[new_end-1]:
            old_end-=1;new_end-=1
        return cls(start,original[start:old_end],edited[start:new_end])

    @property
    def weight(self) -> int:
        return len(self.removed)+len(self.inserted)


@dataclass
class SourceDocumentSession:
    """Single revisioned owner of one source file's text and analysis state.

    Qt widgets are views. Routes/canvases project `parsed` for this revision;
    a failed parse is explicitly represented by None, never by stale code.
    Disk publication uses the existing preimage-guarded source writer.
    """
    path: Path
    saved_raw: bytes
    encoding: str
    text: str
    revision: int = 0
    parsed: PythonDocument | None = None
    diagnostic: str | None = None
    _candidate: bytes | None = field(default=None, repr=False)
    _conversion_base: PythonDocument | None = field(default=None, repr=False)
    # Per-document unsaved text history. Qt has no independent undo authority.
    _draft_undo: list[_DraftDelta] = field(default_factory=list, repr=False)
    _draft_redo: list[_DraftDelta] = field(default_factory=list, repr=False)
    external_state: str = 'current'
    _recovery_token: str = field(default_factory=DraftRecoveryStore.new_token, repr=False)
    MAX_DRAFT_EDITS = 128
    MAX_DRAFT_CHARS = 8_000_000

    @classmethod
    def open(cls, path: str | Path) -> 'SourceDocumentSession':
        identity=PythonDocument._validated_path(path)
        raw=identity.read_bytes()
        text,encoding=decode_python_source(raw)
        # Qt text widgets normalize newlines to LF. Keep the document's
        # editor-facing text in the same form; raw bytes remain unchanged.
        text=text.replace('\r\n','\n').replace('\r','\n')
        doc=None;error=None
        try:
            doc=PythonDocument.from_bytes(identity,raw)
        except SourceError as exc:
            error=str(exc)
        return cls(identity,raw,encoding,text,parsed=doc,diagnostic=error,
                   _candidate=raw,_conversion_base=doc)

    @property
    def dirty(self) -> bool:
        return self._candidate != self.saved_raw

    @property
    def graph_ready(self) -> bool:
        return self.parsed is not None and self.diagnostic is None

    def _encode(self, text: str) -> bytes:
        if self._conversion_base is not None:
            # Identical newline/encoding behavior to existing qualified edits.
            return _editor_candidate_bytes(self._conversion_base,text)
        if '\r' in text:
            raise SourceError('Editor text contains unexpected carriage returns')
        old,_=decode_python_source(self.saved_raw)
        if '\r\n' in old:
            if '\n' in old.replace('\r\n','') or '\r' in old.replace('\r\n',''):
                raise SourceError('Mixed line endings require an external text editor')
            text=text.replace('\n','\r\n')
        elif '\r' in old:
            raise SourceError('Legacy CR line endings require an external text editor')
        try:
            result=text.encode(self.encoding)
        except (UnicodeError, LookupError) as exc:
            raise SourceError('Cannot encode edited source: '+str(exc)) from exc
        if len(result)>MAX_SOURCE:
            raise SourceError('Edited source exceeds 1.5 MB analysis limit')
        # Invalid drafts still need to remain editable, but the bytes must
        # decode back into exactly the revision being displayed in Qt.
        decoded,_=decode_python_source(result)
        if decoded.replace('\r\n','\n').replace('\r','\n')!=text.replace('\r\n','\n'):
            raise SourceError('Python source encoding declaration changes the edited text; choose a compatible encoding')
        return result

    def update(self, edited: str, *, parse: bool = True, record_history: bool = True) -> bool:
        """Set one live revision; record only minimal edits in bounded session history."""
        if not isinstance(edited,str):
            raise TypeError('Editor text must be str')
        if edited==self.text:
            return False
        if record_history:
            self._draft_undo.append(_DraftDelta.between(self.text,edited))
            self._draft_redo.clear()
            total=sum(delta.weight for delta in self._draft_undo)
            while (len(self._draft_undo)>self.MAX_DRAFT_EDITS or
                   total>self.MAX_DRAFT_CHARS):
                total-=self._draft_undo.pop(0).weight
        self.text=edited
        self.revision+=1
        self.parsed=None
        self.diagnostic='Source revision awaiting analysis'
        self._candidate=None
        if parse:
            self.qualify()
        return True

    def undo_draft(self, *, parse: bool = True) -> bool:
        """Reverse a text edit in this document, irrespective of the current Qt tab."""
        if not self._draft_undo:
            return False
        change=self._draft_undo[-1]
        start=change.offset
        end=start+len(change.inserted)
        if self.text[start:end]!=change.inserted:
            raise SourceError('Draft text history is inconsistent; refusing undo')
        previous=self.text[:start]+change.removed+self.text[end:]
        self.update(previous,parse=parse,record_history=False)
        self._draft_redo.append(self._draft_undo.pop())
        return True

    def redo_draft(self, *, parse: bool = True) -> bool:
        if not self._draft_redo:
            return False
        change=self._draft_redo[-1]
        start=change.offset
        end=start+len(change.removed)
        if self.text[start:end]!=change.removed:
            raise SourceError('Draft text history is inconsistent; refusing redo')
        result=self.text[:start]+change.inserted+self.text[end:]
        self.update(result,parse=parse,record_history=False)
        self._draft_undo.append(self._draft_redo.pop())
        return True

    def inspect_external(self) -> str:
        """Read-only disk conflict check. Never merge or discard the live draft."""
        try:
            identity=PythonDocument._validated_path(self.path)
            self.external_state=('current' if identity.read_bytes()==self.saved_raw
                                 else 'modified')
        except (OSError, SourceError):
            self.external_state='unavailable'
        return self.external_state

    def qualify(self) -> bool:
        """Analyze only the current revision, without mutating the file."""
        self.parsed=None
        self._candidate=None
        try:
            self._candidate=self._encode(self.text)
            self.parsed=PythonDocument.from_bytes(self.path,self._candidate)
            self.diagnostic=None
        except SourceError as exc:
            self.diagnostic=str(exc)
        return self.graph_ready

    def commit(self, *, history=None):
        """Publish the exact active revision, even when syntax is incomplete.

        The editor is allowed to persist invalid text. The *graph* stays
        unavailable until that text parses. No implicit code execution.
        """
        if self._candidate is None:
            raise SourceError(self.diagnostic or 'Source cannot be encoded')
        if not self.dirty:
            return None
        if self.inspect_external()!='current':
            raise SourceError('Source changed externally; draft preserved. Reload only after reviewing or saving your draft elsewhere')
        proposal=EditProposal(self.path,self.saved_raw,self._candidate,
                              self.encoding,'Save Python source document')
        backup=history.apply(proposal) if history is not None else apply_proposal(proposal)
        self.saved_raw=self._candidate
        self.encoding=decode_python_source(self.saved_raw)[1]
        self._conversion_base=self.parsed
        self.external_state='current'
        return backup

    def snapshot_recovery(self, store: DraftRecoveryStore) -> bool:
        """Durably record this live text revision; no source-file changes."""
        if not self.dirty:
            store.discard(self.path, self._recovery_token)
            return False
        store.write(self.path, self.saved_raw, self.text, self.revision,
                    token=self._recovery_token)
        return True

    def restore_recovery(self, record: RecoveryRecord) -> bool:
        """Only explicit user approval can restore an exact-base draft."""
        if (record.path != self.path or record.base_sha256 != _digest(self.saved_raw)):
            raise SourceError('Recovery base differs from source on disk; draft preserved in journal')
        if self.dirty:
            raise SourceError('Cannot restore recovery over an existing unsaved document')
        if record.text == self.text:
            self._recovery_token=record.token
            return False
        changed=self.update(record.text)
        self._recovery_token=record.token
        return changed

    def clear_recovery(self, store: DraftRecoveryStore) -> None:
        """Call only after explicit save or discard, never on a crash."""
        store.discard(self.path, self._recovery_token)

    def discard_and_reload(self, *, discard_unsaved: bool = False,
                           expected_raw: bytes | None = None):
        """Reload in place, preserving the document identity shared by all views.

        Only a caller that obtained explicit user consent may discard a dirty
        revision. Read/parse the replacement first; failure leaves this session
        and every connected view's text untouched.
        """
        if self.dirty and not discard_unsaved:
            raise SourceError('Unsaved document must be explicitly discarded')
        replacement=type(self).open(self.path)
        if expected_raw is not None and replacement.saved_raw != expected_raw:
            raise SourceError('Committed source changed externally before view synchronization; document preserved')
        self.saved_raw=replacement.saved_raw
        self.encoding=replacement.encoding
        self.text=replacement.text
        self.parsed=replacement.parsed
        self.diagnostic=replacement.diagnostic
        self._candidate=replacement._candidate
        self._conversion_base=replacement._conversion_base
        self._draft_undo.clear()
        self._draft_redo.clear()
        self.external_state='current'
        self.revision+=1

    def adopt_committed_revision(self, original: bytes, published: bytes) -> None:
        """Advance a clean document to an exact guarded write result.

        Caller is responsible for publishing through SourceEditHistory. If
        another process changes the file before this view synchronizes, refuse
        adoption and preserve the current document. No prompts or second writer.
        """
        if self.dirty:
            raise SourceError('Unsaved document cannot be replaced by a committed source edit')
        if self.saved_raw != original:
            raise SourceError('Committed source preimage differs from the open document')
        if not isinstance(published,bytes):
            raise SourceError('Committed source requires exact published bytes')
        self.discard_and_reload(expected_raw=published)
