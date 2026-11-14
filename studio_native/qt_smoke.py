"""Native Qt host-only smoke test: no remote network, no external files changed."""
import ast
import os
import sys
from pathlib import Path
from .python_graph import PythonDocument
from .navigation import Route
from .graph_routes import resolve_graph
from PyQt6.QtWidgets import QApplication, QWidget, QFileDialog, QToolBar, QToolButton, QComboBox, QLineEdit, QCheckBox, QDialog, QMessageBox, QLabel, QPushButton
from PyQt6.QtCore import QTimer, QElapsedTimer, Qt, QPointF
from PyQt6.QtTest import QTest
import tempfile
from .gui import NativeLab, css, NodeItem, GraphSurfaceItem, GraphContentItem
from .source_editor import SourceDocumentSession
from . import model

def _alter_compiled_literal(preview, node_id: str, replacement: int) -> str:
    """Make a *real* QA edit to the current mapped node, not a guessed fixture.

    Source-edit smoke previously used string replacement of a value from an
    earlier stage. A no-op replacement passed silently and an assertion much
    later blamed the compiler. Keep the fixture anchored to compiler evidence.
    This helper does not run in production or introduce a second source owner.
    """
    assert preview.source and not preview.issues, preview.issues
    source=preview.source
    location=dict(preview.node_lines).get(node_id)
    assert type(location) is int and location>0, f'No source map for {node_id}'
    tree=ast.parse(source)
    statements=[n for n in ast.walk(tree)
                if isinstance(n,ast.Assign) and n.lineno==location and
                isinstance(n.value,ast.Constant) and type(n.value.value) is int]
    assert len(statements)==1,(node_id,location,len(statements))
    literal=statements[0].value
    assert literal.value != replacement, (
        f'Smoke fixture attempted a no-op for {node_id}: {literal.value}')
    assert literal.lineno==literal.end_lineno
    lines=source.splitlines(keepends=True)
    line=lines[literal.lineno-1]
    lines[literal.lineno-1]=(line[:literal.col_offset]+str(replacement)+
                              line[literal.end_col_offset:])
    changed=''.join(lines)
    assert changed != source and ast.parse(changed)
    return changed


def _replace_once_for_smoke(source: str, old: str, new: str) -> str:
    """Explicitly disallow no-op or ambiguous string edits in QA fixtures."""
    assert old!=new and source.count(old)==1,(old,source.count(old))
    changed=source.replace(old,new,1)
    assert changed!=source
    return changed


def capture_node(canvas, node, destination, app):
    """Evidence screenshot containing the entire node/interface, not a cropped viewport.

    Fit only for capture. Restore the prior root camera afterward so test
    interactions and the user's presentation state do not inherit QA zoom.
    """
    previous_transform=canvas.transform()
    previous_center=canvas.mapToScene(canvas.viewport().rect().center())
    try:
        rect=node.sceneBoundingRect().adjusted(-35,-35,90,55)
        canvas.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)
        app.processEvents()
        visible=canvas.mapFromScene(node.sceneBoundingRect()).boundingRect()
        viewport=canvas.viewport().rect()
        assert viewport.contains(visible.adjusted(-1,-1,1,1)), (
            'QA screenshot clipped the target node', node.data['id'], visible, viewport)
        if not canvas.grab().save(destination,'PNG'):
            raise AssertionError(f'Unable to write graph screenshot: {destination}')
    finally:
        canvas.setTransform(previous_transform)
        canvas.centerOn(previous_center)
        app.processEvents()


def exercise_modal(app, kind, object_name, invoke, operate, *, deadline_ms=6000):
    """Own the entire lifecycle of a smoke-only modal interaction.

    Never assume a single-shot callback will run after the widget is shown.
    Check visibility on the Qt event loop, and report exceptions synchronously
    *after* the nested exec() returns. Production dialogs are not modified.
    A blocked event loop is still stopped by RUN-ALL's outer process timeout.
    """
    if deadline_ms < 100:
        raise ValueError('Modal qualification deadline is too short')
    state={'seen':False,'error':None}
    elapsed=QElapsedTimer();elapsed.start()
    poll=QTimer(app);poll.setInterval(25)
    def inspect():
        # A top-level window can remain visible after an unrelated stage.
        # Interact only with the *active modal*, not the first global widget
        # that happens to match a type or object name.
        dialog=app.activeModalWidget()
        if (isinstance(dialog,kind) and dialog.isVisible() and
                (object_name is None or dialog.objectName()==object_name)):
            state['seen']=True
            poll.stop()
            try:
                operate(dialog)
            except BaseException as exc:
                state['error']=exc
            finally:
                if dialog.isVisible():dialog.reject()
        elif elapsed.elapsed() >= deadline_ms:
            poll.stop()
            state['error']=AssertionError('Expected visible modal dialog not found: '+str(object_name))
            # If a different dialog appeared, close it instead of leaving the
            # application inside a different nested Qt event loop.
            modal=app.activeModalWidget()
            if isinstance(modal,QDialog):modal.reject()
    poll.timeout.connect(inspect)
    poll.start()
    try:
        result=invoke()
    finally:
        poll.stop();poll.deleteLater()
    if state['error'] is not None:
        raise AssertionError(f'Modal smoke failed: {object_name}') from state['error']
    if not state['seen']:
        raise AssertionError(f'Modal smoke never displayed {object_name}')
    return result


def exercise_revisioned_source_session(app):
    """Isolate document-history GUI tests from the long-lived graph workspace.

    This stage opens extra source tabs and mutates a temporary document.
    Those views must not leak into later navigation tests. A separate
    NativeLab exercises the real production interactions without manually
    resetting private tab, route, document, or editor registries.
    """
    w=NativeLab()
    w.show();app.processEvents()
    print('QT_STAGE revisioned-source-session',flush=True)
    with tempfile.TemporaryDirectory() as source_tmp:
        editable=Path(source_tmp)/'editable.py'
        editable.write_text('def sample(a):\n    return a + 2\n',encoding='utf-8')
        assert w._open_python_source_path(editable,discard_confirmed=True), "Opening editable failed"
        w._source_expanded=set(w.python_doc.scopes)-{'module'}
        w._load_source_editor()
        w._refresh_whole_file()
        assert w.source_editor.toPlainText()==w.python_doc.source
        w.source_editor.setPlainText('def sample(a):\n    return a + 3\n')
        assert w._source_editor_dirty
        assert w.save_python_editor(), 'Text editor failed to commit valid Python'
        assert not w._source_editor_dirty
        assert 'a + 3' in w.python_doc.source
        assert editable.read_text().endswith('return a + 3\n')
        assert list(editable.parent.glob('editable.py.smi-backup*'))
        print('QT_STAGE document-draft-history-and-external-changes',flush=True)
        # Qt's text widget is a view. Ctrl+Z must traverse the document session,
        # not a QTextDocument undo stack that resets across source-tab changes.
        session=w._active_source_document()
        assert session is not None
        assert w.source_editor.__class__.__name__=='PythonSourceTextEdit'
        w.source_editor.setPlainText('def sample(a):\n    return a + 44\n')
        assert session.text==w.source_editor.toPlainText()
        assert session._draft_undo and session._draft_undo[-1].inserted.endswith('44')
        print('QT_STAGE source-document-keyboard-routing',flush=True)
        w.source_editor.setFocus();app.processEvents()
        QTest.keyClick(w.source_editor,Qt.Key.Key_Z,Qt.KeyboardModifier.ControlModifier)
        app.processEvents()
        assert w.source_editor.toPlainText().endswith('return a + 3\n'), 'Source draft undo key dispatch failed'
        assert session.text==w.source_editor.toPlainText()
        QTest.keyClick(w.source_editor,Qt.Key.Key_Z,
                       Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)
        app.processEvents()
        assert w.source_editor.toPlainText().endswith('return a + 44\n'), 'Source draft redo key dispatch failed'
        assert w.undo_source_draft()
        assert w.source_editor.toPlainText().endswith('return a + 3\n')
        assert w.python_doc is session.parsed
        # An external writer must not replace an unsaved draft or the current
        # graph. Revert test disk fixture before continuing the original checks.
        w.source_editor.setPlainText('def sample(a):\n    return a + 7\n')
        editable.write_text('def sample(a):\n    return a + 99\n')
        assert w.check_python_external_change()=='modified'
        assert 'DISK MODIFIED' in w.source_file_label.text()
        assert w.source_editor.toPlainText().endswith('return a + 7\n')
        editable.write_text('def sample(a):\n    return a + 3\n')
        assert w.check_python_external_change()=='current'
        assert w.undo_source_draft()
        assert w.source_editor.toPlainText().endswith('return a + 3\n')
        # A second graph tab for the same file is a separate view, not a
        # second document/undo owner. Undo survives switching between views.
        original_page=w.source_page
        assert w.open_source_in_new_tab(editable)
        assert w._active_source_document() is session
        w.source_editor.setPlainText('def sample(a):\n    return a + 12\n')
        w._source_analysis_timer.stop();w._refresh_live_source()
        w.tabs.setCurrentWidget(original_page);app.processEvents()
        assert w._active_source_document() is session
        assert w.source_editor.toPlainText().endswith('return a + 12\n')
        assert w.undo_source_draft()
        assert w.source_editor.toPlainText().endswith('return a + 3\n')
        fn=next(n for n in w.source_canvas.items_by_id.values()
                if n.data.get('source_kind')=='function')
        assert fn.data.get('terminal_return_label','').startswith('return ')
        ret=next(n for n in w.source_graph['nodes'] if n.get('source_kind')=='return')
        assert ret.get('terminal_boundary_owner') and ret.get('presentation_hidden')
        assert fn.inner_ports, 'Return must have a visible inner boundary dot'
        # Live valid revisions update the graph without a disk write.
        w.source_editor.setPlainText('def sample(a):\n    return a * 9\n')
        assert editable.read_text().endswith('return a + 3\n')
        w._source_analysis_timer.stop();w._refresh_live_source()
        assert w.python_doc is w._active_source_document().parsed
        scope=next(k for k,v in w.python_doc.scopes.items() if v.title=='sample')
        assert 'a * 9' in w.python_doc.source
        assert w.source_editor.toPlainText().endswith('return a * 9\n')
        # Invalid unsaved source has no graph and remains editable.
        w.source_editor.setPlainText('def sample(a):\n    return (\n')
        w._source_analysis_timer.stop();w._refresh_live_source()
        assert w.python_doc is None and w.source_graph is None
        assert 'graph unavailable' in w.source_file_label.text()
        assert w.source_editor.toPlainText().endswith('return (\n')
        # An invalid Python document can be saved safely, without pretending
        # that the previous graph still represents its source.
        assert w.save_python_editor()
        assert editable.read_text().endswith('return (\n')
        assert not w._source_editor_dirty
        # Restore a valid revision and re-qualify graph projection.
        w.source_editor.setPlainText('def sample(a):\n    return a + 3\n')
        w._source_analysis_timer.stop();w._refresh_live_source()
        assert w.python_doc is not None and w.source_graph is not None
        assert w.save_python_editor(), 'Restoring the temporary test source failed'
    # A second view is intentional inside this fixture, but must not become
    # part of the original workspace's source-tab registry.
    assert len(w._source_tabs)==2, 'Shared-source fixture did not create its second graph view'
    assert len(w._source_documents)==1, 'Fixture created duplicate source document sessions'
    assert all(w._view_sessions.get(sid).route.path==str(session.path)
               for sid in w._source_tabs), 'Fixture tabs do not share a source path'
    assert all(not source.dirty for source in w._source_documents.values()), (
        'Fixture left an unsaved source document before shutdown')
    assert w.close(), 'Isolated source-session fixture did not close cleanly'
    app.processEvents()


def exercise_source_recovery(app):
    """Isolated host test of explicit recovery and stale-file refusal.

    Neither the main smoke window nor the user's real recovery directory is
    modified. A real modal interaction is supervised, not dismissed by timing.
    """
    print('QT_STAGE crash-recovery-prompt-and-conflict',flush=True)
    with tempfile.TemporaryDirectory() as temp_dir:
        path=Path(temp_dir)/'recover.py'
        path.write_text('def f(x):\n    return x + 1\n',encoding='utf-8')
        w=NativeLab();w.show();app.processEvents()
        draft=SourceDocumentSession.open(path)
        draft.update('def f(x):\n    return x + 8\n')
        draft.snapshot_recovery(w._draft_recovery)
        before=path.read_bytes()
        def approve(dialog):
            assert dialog.windowTitle()=='Recover unsaved Python draft'
            # Click the actual Qt button. QDialog.done(integer) does not prove
            # QMessageBox's clicked-button state or question() return value.
            button=dialog.button(QMessageBox.StandardButton.Yes)
            assert button is not None and button.isEnabled(), 'Recovery Yes button unavailable'
            button.click()
        opened=exercise_modal(app,QMessageBox,None,
            lambda:w._open_python_source_path(path),approve)
        assert opened is True, 'Source open failed after recovery prompt'
        active=w._active_source_document()
        assert active is not None, 'Recovery open did not publish a source session'
        assert active.path==path, 'Recovery open published the wrong source identity'
        assert active.text.endswith('return x + 8\n'), (
            'Recovery approval did not publish the recovered draft: '
            f'dirty={active.dirty}, revision={active.revision}, '
            f'journal_text_matches={w._draft_recovery.latest(path).text==active.text if w._draft_recovery.latest(path) else False}')
        assert w.source_editor.toPlainText()==active.text, 'Qt editor does not show the recovered revision'
        assert active.dirty and path.read_bytes()==before
        assert w._draft_recovery.latest(path) is not None
        assert w.save_python_editor()
        assert path.read_text().endswith('return x + 8\n')
        assert w._draft_recovery.latest(path) is None
        assert w.close();app.processEvents()

        # Different disk preimage: show warning and retain the draft untouched.
        conflict=SourceDocumentSession.open(path)
        conflict.update('def f(x):\n    return x + 9\n')
        conflict.snapshot_recovery(w._draft_recovery)
        path.write_text('def f(x):\n    return x + 100\n',encoding='utf-8')
        w2=NativeLab();w2.show();app.processEvents()
        def acknowledge(dialog):
            assert dialog.windowTitle()=='Source recovery conflict'
            button=dialog.button(QMessageBox.StandardButton.Ok)
            assert button is not None and button.isEnabled(), 'Recovery warning OK button unavailable'
            button.click()
        assert exercise_modal(app,QMessageBox,None,
            lambda:w2._open_python_source_path(path),acknowledge)
        assert w2._active_source_document().text.endswith('return x + 100\n')
        assert w2._draft_recovery.latest(path) is not None
        assert w2.close();app.processEvents()


def exercise_program_workspace(app):
    """Independent host-only acceptance for the actual graph-owned Qt editor."""
    print('QT_STAGE program-graph-editor',flush=True)
    from .program_graph import ProgramGraph
    from .gui import ProgramWorkspace
    w=NativeLab();w.show();app.processEvents()
    with tempfile.TemporaryDirectory() as directory:
        path=Path(directory)/'visual.smi-graph'
        program=w.new_visual_program()
        assert isinstance(program,ProgramWorkspace)
        assert w.current_canvas() is program.canvas
        assert program.new_function(name='compute')
        assert program.choose_node(operation='python.literal',scene_pos=QPointF(110,100))
        assert program.choose_node(operation='python.add',scene_pos=QPointF(330,100))
        assert program.choose_node(operation='python.return',scene_pos=QPointF(550,100))
        app.processEvents()
        nodes=program.document.state['nodes']
        assert len(program.canvas.items_by_id)==3
        literal,add,ret=nodes
        source=literal['ports']['outputs'][0]
        target=add['ports']['inputs'][0]
        src=program.canvas.items_by_id[literal['id']].ports[0]
        dst=next(p for p in program.canvas.items_by_id[add['id']].ports if p.data['id']==target['id'])
        src_pos=program.canvas.mapFromScene(src.mapToScene(QPointF(0,0)))
        dst_pos=program.canvas.mapFromScene(dst.mapToScene(QPointF(0,0)))
        QTest.mousePress(program.canvas.viewport(),Qt.MouseButton.LeftButton,pos=src_pos)
        app.processEvents()
        assert program.canvas.pending is not None,'ProgramGraph pin drag did not start'
        QTest.mouseRelease(program.canvas.viewport(),Qt.MouseButton.LeftButton,pos=dst_pos)
        app.processEvents()
        assert len(program.document.state['edges'])==1,'ProgramGraph pin drag did not commit'
        assert program.document.state['edges'][0]['target_port']==target['id']
        assert program.document.dirty
        program.undo();app.processEvents()
        assert not program.document.state['edges']
        program.redo();app.processEvents()
        assert len(program.document.state['edges'])==1
        program.move_node(ret['id'],655,220)
        app.processEvents()
        assert program.document.state['layout'][ret['id']]=={'x':655,'y':220}
        program.undo();app.processEvents()
        assert program.document.state['layout'][ret['id']]=={'x':550,'y':100}
        # Actual selection deletion goes through the graph owner, never
        # through model.py's legacy Draft API.
        program.canvas.items_by_id[ret['id']].setSelected(True)
        program.delete_selected();app.processEvents()
        assert len(program.document.state['nodes'])==2
        program.undo();app.processEvents()
        assert len(program.document.state['nodes'])==3
        assert program.save(path=path)
        assert not program.document.dirty
        assert w._close_graph_tab(w.tabs.indexOf(program)) is None
        assert program not in w._program_tabs
        assert w.tabs.indexOf(program)<0
        reopened=w.open_visual_program(path=path)
        assert isinstance(reopened,ProgramWorkspace)
        assert reopened.document.state==ProgramGraph.open(path).state
        assert len(reopened.canvas.items_by_id)==3
        assert len(reopened.canvas.edge_items)==1
        assert reopened.document.dirty is False
        print('QT_STAGE program-interface-literal-rewire-save-as',flush=True)
        assert reopened.add_parameter(name='input_value')
        parameter=reopened.document.state['functions'][0]['parameters'][0]['id']
        assert reopened.edit_parameter('rename_parameter',parameter=parameter,name='number')
        assert reopened.rename_function(name='compute_value')
        assert reopened.document.state['functions'][0]['name']=='compute_value'
        assert reopened.document.state['functions'][0]['parameters'][0]['name']=='number'
        assert reopened.edit_literal(literal['id'],value_json='42')
        assert reopened.document.state['nodes'][0]['properties']['value']==42
        assert reopened.canvas.items_by_id[literal['id']].data['title'].endswith('42')
        assert reopened.choose_node(operation='python.literal',scene_pos=QPointF(100,250))
        fresh=reopened.document.state['nodes'][-1]
        existing_wire=reopened.document.state['edges'][0]['id']
        original_source=reopened.document.state['edges'][0]['source']
        assert reopened.connect(fresh['id'],fresh['ports']['outputs'][0]['id'],
                                add['id'],add['ports']['inputs'][0]['id'])
        app.processEvents()
        assert len(reopened.document.state['edges'])==1
        assert reopened.document.state['edges'][0]['id']==existing_wire
        assert reopened.document.state['edges'][0]['source']==fresh['id']
        reopened.undo();app.processEvents()
        assert reopened.document.state['edges'][0]['source']==original_source
        reopened.redo();app.processEvents()
        assert reopened.document.state['edges'][0]['source']==fresh['id']
        original_bytes=path.read_bytes()
        copied=Path(directory)/'visual-copy.smi-graph'
        original_id=reopened.document.state['id']
        assert reopened.save_as(path=copied)
        assert path.read_bytes()==original_bytes
        assert reopened.document.path==copied
        assert reopened.document.state['id']!=original_id
        assert ProgramGraph.open(copied).state==reopened.document.state
        assert not reopened.document.dirty
        print('QT_STAGE program-python-preview',flush=True)
        visual=w.new_visual_program()
        assert isinstance(visual,ProgramWorkspace)
        assert visual.new_function(name='increment')
        increment=visual.current_function
        assert visual.add_parameter(name='x',kind='py:int')
        parameter_id=visual.document.state['functions'][0]['parameters'][0]['id']
        assert visual.edit('set_return_type',function=increment,type='py:int')
        assert visual.choose_node(operation='python.parameter',parameter_id=parameter_id)
        assert visual.choose_node(operation='python.literal')
        assert visual.choose_node(operation='python.add')
        assert visual.choose_node(operation='python.return')
        p,one,addition,finish=visual.document.state['nodes']
        assert visual.edit_literal(one['id'],value_json='1')
        def wire(a,ap,b,bp):
            src=next(port['id'] for port in a['ports']['outputs'] if port['name']==ap)
            dst=next(port['id'] for port in b['ports']['inputs'] if port['name']==bp)
            assert visual.connect(a['id'],src,b['id'],dst)
            app.processEvents()
        wire(p,'value',addition,'left')
        wire(one,'value',addition,'right')
        wire(addition,'result',finish,'value')
        preview=visual.preview_python(show=False)
        assert preview.source and not preview.issues,preview.issues
        assert 'def increment(x):' in preview.source
        assert len(preview.node_lines)==4
        from PyQt6.QtWidgets import QPlainTextEdit
        def close_preview(dialog):
            display=dialog.findChild(QPlainTextEdit,'GeneratedPythonPreview')
            assert display is not None and display.isReadOnly()
            assert display.toPlainText()==preview.source
            dialog.accept()
        assert exercise_modal(app,QDialog,'ProgramPythonPreview',
                              lambda:visual.preview_python(),close_preview)
        assert visual.new_function(name='compose')
        compose=visual.current_function
        assert visual.add_parameter(name='y',kind='py:int')
        parameter_y=visual.document.state['functions'][1]['parameters'][0]['id']
        assert visual.edit('set_return_type',function=compose,type='py:int')
        assert visual.choose_node(operation='python.parameter',parameter_id=parameter_y)
        assert visual.choose_node(operation='python.call',callee_id=increment)
        assert visual.choose_node(operation='python.multiply')
        assert visual.choose_node(operation='python.return')
        arg,call,product,done=visual.document.state['nodes'][-4:]
        wire(arg,'value',call,'x')
        wire(call,'result',product,'left')
        wire(call,'result',product,'right')
        wire(product,'result',done,'value')
        compiled=visual.preview_python(show=False)
        assert compiled.source and not compiled.issues,compiled.issues
        assert 'increment(' in compiled.source and 'def compose(y):' in compiled.source
        graph_path=Path(directory)/'qualified-graph.smi-graph'
        assert visual.save(path=graph_path)
        assert not visual.document.dirty
        assert ProgramGraph.open(graph_path).state==visual.document.state
        assert visual.preview_python(show=False).source==compiled.source
        print('QT_STAGE program-python-publication',flush=True)
        from PyQt6.QtWidgets import QPushButton
        assert visual.findChild(QPushButton,'ProgramPublishPython') is not None
        published_path=Path(directory)/'published-from-visual.py'
        assert visual.publish_python(path=published_path)
        assert published_path.read_text(encoding='utf-8')==compiled.source
        assert graph_path.read_bytes()==visual.document._base
        assert visual.document.dirty is False
        # After a graph edit, old publication is never silently refreshed.
        assert visual.edit('move_node',node=p['id'],x=580,y=440)
        assert visual.document.dirty
        assert published_path.read_text(encoding='utf-8')==compiled.source
        assert visual.save(path=graph_path)
        assert not visual.document.dirty
        print('QT_STAGE program-pure-boolean-and-eager-selection',flush=True)
        condition_workspace=w.new_visual_program()
        assert isinstance(condition_workspace,ProgramWorkspace)
        assert condition_workspace.new_function(name='choose_value')
        operations=('python.equal_int','python.not','python.select_int','python.select_bool')
        for operation in operations:
            assert condition_workspace.choose_node(operation=operation), operation
        selection_nodes=condition_workspace.document.state['nodes']
        assert [node['operation'] for node in selection_nodes]==list(operations)
        for node in selection_nodes:
            assert node['operation_version']==1
            assert node['ports']['inputs'],node['operation']
            expected_type='py:int' if node['operation']=='python.select_int' else 'py:bool'
            assert node['ports']['outputs'][0]['type']==expected_type, node['operation']
        assert condition_workspace.preview_python(show=False).source is None  # incomplete is savable
        condition_file=Path(directory)/'incomplete-conditional.smi-graph'
        assert condition_workspace.save(path=condition_file)
        assert not condition_workspace.document.dirty
        assert ProgramGraph.open(condition_file).state==condition_workspace.document.state
        print('QT_STAGE program-structured-execution-branch',flush=True)
        flow_workspace=w.new_visual_program()
        assert isinstance(flow_workspace,ProgramWorkspace)
        assert flow_workspace.new_function(name='route_value')
        assert flow_workspace.edit('set_return_type',function=flow_workspace.current_function,type='py:int')
        for operation in ('python.entry','python.branch','python.return_flow','python.return_flow'):
            assert flow_workspace.choose_node(operation=operation),operation
        entry,branch,yes,no=flow_workspace.document.state['nodes']
        def flow_pin(node,side,name):
            return next(p['id'] for p in node['ports'][side] if p['name']==name)
        assert flow_workspace.connect(entry['id'],flow_pin(entry,'outputs','then'),
                                      branch['id'],flow_pin(branch,'inputs','exec'))
        assert flow_workspace.connect(branch['id'],flow_pin(branch,'outputs','true'),
                                      yes['id'],flow_pin(yes,'inputs','exec'))
        assert flow_workspace.connect(branch['id'],flow_pin(branch,'outputs','false'),
                                      no['id'],flow_pin(no,'inputs','exec'))
        assert all(edge['relation']=='control' for edge in flow_workspace.document.state['edges'])
        assert flow_workspace.preview_python(show=False).source is None  # missing data is still a draft
        flow_file=Path(directory)/'incomplete-flow.smi-graph'
        assert flow_workspace.save(path=flow_file)
        assert ProgramGraph.open(flow_file).state==flow_workspace.document.state
        print('QT_STAGE program-nested-structured-branches',flush=True)
        # Exercise the same graph-owned GUI preview and guarded publication
        # with nested control trees, in an isolated copy of the release fixture.
        from .python_lowering import preview_python as qualified_preview
        nested_example=Path(__file__).resolve().parent.parent/'examples'/'qualified-nested-branches.smi-graph'
        nested_file=Path(directory)/'nested-branches.smi-graph'
        nested_file.write_bytes(nested_example.read_bytes())
        nested_workspace=w.open_visual_program(path=nested_file)
        assert isinstance(nested_workspace,ProgramWorkspace)
        nested_result=nested_workspace.preview_python(show=False)
        assert nested_result.source and not nested_result.issues,nested_result.issues
        assert len([node for node in ast.walk(ast.parse(nested_result.source))
                    if isinstance(node,ast.If)])==2
        nested_lines=dict(nested_result.node_lines)
        assert 'if ' in nested_result.source.splitlines()[nested_lines['inner']-1]
        assert nested_result==qualified_preview(nested_workspace.document.state)
        nested_output=Path(directory)/'nested-output.py'
        assert nested_workspace.publish_python(path=nested_output)
        assert nested_output.read_text(encoding='utf-8')==nested_result.source
        nested_workspace.move_node('inner',420,250)
        assert nested_workspace.document.state['layout']['inner']=={'x':420,'y':250}
        assert nested_workspace.preview_python(show=False)==nested_result
        nested_workspace.undo();app.processEvents()
        assert nested_workspace.preview_python(show=False)==nested_result
        assert nested_workspace.save(path=nested_file)
        assert ProgramGraph.open(nested_file).state==nested_workspace.document.state
        print('QT_STAGE program-qualified-sequential-require',flush=True)
        require_example=Path(__file__).resolve().parent.parent/'examples'/'qualified-guarded-branches.smi-graph'
        require_file=Path(directory)/'guarded-branches.smi-graph'
        require_file.write_bytes(require_example.read_bytes())
        require_workspace=w.open_visual_program(path=require_file)
        assert isinstance(require_workspace,ProgramWorkspace)
        require_result=require_workspace.preview_python(show=False)
        assert require_result.source and not require_result.issues,require_result.issues
        assert 'raise ValueError' in require_result.source
        assert 'assert ' not in require_result.source
        require_ast=ast.parse(require_result.source)
        assert len([n for n in ast.walk(require_ast) if isinstance(n,ast.Raise)])==1
        require_lines=dict(require_result.node_lines)
        assert require_lines['guard']<require_lines['outer']
        assert require_result==qualified_preview(require_workspace.document.state)
        require_output=Path(directory)/'guarded-output.py'
        assert require_workspace.publish_python(path=require_output)
        assert require_output.read_text(encoding='utf-8')==require_result.source
        require_workspace.move_node('guard',150,340)
        assert require_workspace.preview_python(show=False)==require_result
        assert require_workspace.save(path=require_file)
        assert ProgramGraph.open(require_file).state==require_workspace.document.state
        # The template is available via the same canonical Node Library.
        fresh_guard=w.new_visual_program()
        assert fresh_guard.new_function(name='guard_preview')
        assert fresh_guard.choose_node(operation='python.require')
        assert fresh_guard.preview_python(show=False).source is None  # incomplete
        # Incomplete graphs are valid documents. Save the fixture explicitly;
        # never leave a dirty visual program for a blocking close confirmation.
        incomplete_file=Path(directory)/'incomplete-require.smi-graph'
        assert fresh_guard.save(path=incomplete_file)
        assert ProgramGraph.open(incomplete_file).state==fresh_guard.document.state
        assert fresh_guard.document.dirty is False
        print('QT_STAGE program-ordered-bindings',flush=True)
        binding_example=Path(__file__).resolve().parent.parent/'examples'/'qualified-ordered-bindings.smi-graph'
        binding_file=Path(directory)/'ordered-bindings.smi-graph'
        binding_file.write_bytes(binding_example.read_bytes())
        binding_workspace=w.open_visual_program(path=binding_file)
        assert isinstance(binding_workspace,ProgramWorkspace)
        binding_result=binding_workspace.preview_python(show=False)
        assert binding_result.source and not binding_result.issues,binding_result.issues
        assert binding_result==qualified_preview(binding_workspace.document.state)
        assert set(dict(binding_result.node_lines))=={
            node['id'] for node in binding_workspace.document.state['nodes']}
        binding_output=Path(directory)/'ordered-bindings.py'
        assert binding_workspace.publish_python(path=binding_output)
        assert binding_output.read_text(encoding='utf-8')==binding_result.source
        assert not binding_workspace.document.dirty
        print('QT_STAGE program-mutable-local-state',flush=True)
        local_example=Path(__file__).resolve().parent.parent/'examples'/'qualified-mutable-locals.smi-graph'
        local_file=Path(directory)/'mutable-locals.smi-graph'
        local_file.write_bytes(local_example.read_bytes())
        local_workspace=w.open_visual_program(path=local_file)
        assert isinstance(local_workspace,ProgramWorkspace)
        local_result=local_workspace.preview_python(show=False)
        assert local_result.source and not local_result.issues,local_result.issues
        assert set(dict(local_result.node_lines))=={
            node['id'] for node in local_workspace.document.state['nodes']}
        assert local_workspace.choose_node(operation='python.read_int',local_id='local')
        assert local_workspace.preview_python(show=False).source is None  # incomplete
        local_workspace.undo()
        assert local_workspace.preview_python(show=False).source==local_result.source
        assert local_workspace.save(path=local_file)
        assert not local_workspace.document.dirty
        local_output=Path(directory)/'mutable-locals.py'
        assert local_workspace.publish_python(path=local_output)
        assert local_output.read_text(encoding='utf-8')==local_result.source
        print('QT_STAGE program-bounded-repeat',flush=True)
        repeat_example=Path(__file__).resolve().parent.parent/'examples'/'qualified-bounded-repeat.smi-graph'
        repeat_file=Path(directory)/'bounded-repeat.smi-graph'
        repeat_file.write_bytes(repeat_example.read_bytes())
        repeat_workspace=w.open_visual_program(path=repeat_file)
        assert isinstance(repeat_workspace,ProgramWorkspace)
        repeat_preview=repeat_workspace.preview_python(show=False)
        assert repeat_preview.source and not repeat_preview.issues,repeat_preview.issues
        assert len(repeat_preview.node_lines)==len(repeat_workspace.document.state['nodes'])
        assert any(isinstance(x,ast.For) for x in ast.walk(ast.parse(repeat_preview.source)))
        assert repeat_workspace.choose_node(operation='python.repeat_end')
        assert repeat_workspace.preview_python(show=False).source is None  # incomplete
        repeat_workspace.undo()
        assert repeat_workspace.preview_python(show=False)==repeat_preview
        assert repeat_workspace.save(path=repeat_file)
        repeat_output=Path(directory)/'bounded-repeat.py'
        assert repeat_workspace.publish_python(path=repeat_output)
        assert repeat_output.read_text(encoding='utf-8')==repeat_preview.source
        assert ProgramGraph.open(repeat_file).state==repeat_workspace.document.state
        print('QT_STAGE program-ordered-effectful-call',flush=True)
        effect_call_example=Path(__file__).resolve().parent.parent/'examples'/'qualified-execution-call.smi-graph'
        effect_call_file=Path(directory)/'execution-call.smi-graph'
        effect_call_file.write_bytes(effect_call_example.read_bytes())
        effect_workspace=w.open_visual_program(path=effect_call_file)
        assert isinstance(effect_workspace,ProgramWorkspace)
        effect_preview=effect_workspace.preview_python(show=False)
        assert effect_preview.source and not effect_preview.issues,effect_preview.issues
        assert set(dict(effect_preview.node_lines))=={
            node['id'] for node in effect_workspace.document.state['nodes']}
        assert 'guarded(' in effect_preview.source
        effect_workspace.current_function='caller'
        assert effect_workspace.choose_node(operation='python.call_exec',callee_id='callee')
        assert effect_workspace.preview_python(show=False).source is None  # incomplete operation
        effect_workspace.undo()
        assert effect_workspace.preview_python(show=False)==effect_preview
        assert effect_workspace.save(path=effect_call_file)
        effect_output=Path(directory)/'execution-call.py'
        assert effect_workspace.publish_python(path=effect_output)
        assert effect_output.read_text(encoding='utf-8')==effect_preview.source
        print('QT_STAGE program-generated-source-import-editor',flush=True)
        from .python_lowering import preview_python
        original=Path(__file__).resolve().parent.parent/'examples'/'qualified-integer-program.smi-graph'
        source_graph_file=Path(directory)/'generated-roundtrip.smi-graph'
        source_graph_file.write_bytes(original.read_bytes())
        roundtrip=w.open_visual_program(path=source_graph_file)
        before=roundtrip.document.state
        base_source=preview_python(before).source
        assert base_source and '_smi_value_0 = 1' in base_source
        assert roundtrip.findChild(QPushButton,'ProgramEditPython') is not None
        def import_supported(dialog):
            editor=dialog.findChild(QPlainTextEdit,'ProgramPythonEditText')
            assert editor is not None and not editor.isReadOnly()
            assert editor.toPlainText()==base_source
            edited=_replace_once_for_smoke(base_source,
                '_smi_value_0 = 1','_smi_value_0 = 17')
            edited=_replace_once_for_smoke(edited,
                '_smi_value_1 + _smi_value_0','_smi_value_1 * _smi_value_0')
            editor.setPlainText(edited)
            assert dialog.import_candidate() is True
            assert not dialog.isVisible()
        assert exercise_modal(app,QDialog,'ProgramPythonEditDialog',
                              lambda:roundtrip.edit_generated_python(),import_supported)
        assert next(node for node in roundtrip.document.state['nodes'] if node['id']=='one')['properties']['value']==17
        assert next(node for node in roundtrip.document.state['nodes'] if node['id']=='add')['operation']=='python.multiply'
        assert roundtrip.document.state['edges']==before['edges']
        assert roundtrip.document.state['layout']==before['layout']
        assert roundtrip.document.dirty
        assert '_smi_value_0 = 17' in roundtrip.preview_python(show=False).source
        roundtrip.undo();app.processEvents()
        assert roundtrip.preview_python(show=False).source==base_source
        roundtrip.redo();app.processEvents()
        assert '_smi_value_0 = 17' in roundtrip.preview_python(show=False).source
        assert roundtrip.save(path=source_graph_file)
        assert ProgramGraph.open(source_graph_file).state==roundtrip.document.state
        revised_source=roundtrip.preview_python(show=False).source
        exported=Path(directory)/'unimported-python-draft.py'
        def export_unsupported(dialog):
            editor=dialog.findChild(QPlainTextEdit,'ProgramPythonEditText')
            unexpected=_replace_once_for_smoke(revised_source,'_smi_value_0 = 17','_smi_value_0 = missing_name')
            editor.setPlainText(unexpected)
            assert dialog.import_candidate() is False
            assert editor.toPlainText()==unexpected,'Rejected source was lost'
            assert 'refused' in dialog.feedback.text().lower()
            assert dialog.export_draft(path=exported) is True
            assert exported.read_text(encoding='utf-8')==unexpected
            editor.setPlainText(dialog.base_source)
            dialog.reject()
        assert exercise_modal(app,QDialog,'ProgramPythonEditDialog',
                              lambda:roundtrip.edit_generated_python(),export_unsupported) is False
        assert roundtrip.preview_python(show=False).source==revised_source
        assert not roundtrip.document.dirty
        def reject_stale(dialog):
            editor=dialog.findChild(QPlainTextEdit,'ProgramPythonEditText')
            candidate=_replace_once_for_smoke(dialog.base_source,'_smi_value_0 = 17','_smi_value_0 = 19')
            editor.setPlainText(candidate)
            assert roundtrip.edit('move_node',node='one',x=210,y=90)
            assert dialog.import_candidate() is False
            assert editor.toPlainText()==candidate
            assert 'revision' in dialog.feedback.text().lower()
            editor.setPlainText(dialog.base_source)
            dialog.reject()
        assert exercise_modal(app,QDialog,'ProgramPythonEditDialog',
                              lambda:roundtrip.edit_generated_python(),reject_stale) is False
        roundtrip.undo();app.processEvents()
        assert roundtrip.save(path=source_graph_file)
        print('QT_STAGE program-linked-source-document-reconciliation',flush=True)
        linked_path=Path(directory)/'linked-real-source.py'
        linked_source=roundtrip.preview_python(show=False).source
        linked_path.write_text(linked_source,encoding='utf-8')
        assert w._open_python_source_path(linked_path,frame=False)
        linked_session=w._source_documents[str(linked_path.resolve())]
        assert w.source_editor.toPlainText()==linked_source
        w.tabs.setCurrentWidget(roundtrip);app.processEvents()
        assert roundtrip.findChild(QPushButton,'ProgramLinkopen.py') is not None
        assert roundtrip.findChild(QPushButton,'ProgramImportopen.py') is not None
        assert roundtrip.link_python_source(session=linked_session)
        candidate=_replace_once_for_smoke(linked_source,'_smi_value_0 = 17','_smi_value_0 = 23')
        w.activate_source_tab();app.processEvents()
        w.source_editor.setPlainText(candidate);app.processEvents()
        assert linked_session.text==candidate and linked_session.dirty
        w.tabs.setCurrentWidget(roundtrip);app.processEvents()
        print('QT_STAGE program-linked-source-review-preflight',flush=True)
        graph_before_review=roundtrip.document.state
        def inspect_review(dialog):
            body=dialog.text()
            assert 'one' in body and 'set_property' in body,body
            assert '17' in body and '23' in body,body
            assert 'compiler verifies' in body.lower(),body
            dialog.accept()
        assert exercise_modal(app,QMessageBox,None,
               lambda:roundtrip.review_linked_python_source(),inspect_review)
        assert roundtrip.document.state==graph_before_review
        assert linked_session.dirty and linked_session.text==candidate
        assert roundtrip.import_linked_python_source(), w.statusBar().currentMessage()
        assert roundtrip.preview_python(show=False).source==candidate
        assert linked_path.read_text(encoding='utf-8')==linked_source
        roundtrip.undo();app.processEvents()
        assert roundtrip.preview_python(show=False).source==linked_source
        roundtrip.redo();app.processEvents()
        assert roundtrip.preview_python(show=False).source==candidate
        assert roundtrip.save(path=source_graph_file)
        assert linked_session.qualify()
        linked_session.commit()
        # Source saves are independent. A source-owned edit after a save can
        # still be imported against the last exact common graph baseline.
        more=_replace_once_for_smoke(candidate,'_smi_value_0 = 23','_smi_value_0 = 24')
        linked_session.update(more)
        assert roundtrip.import_linked_python_source(), w.statusBar().currentMessage()
        assert roundtrip.preview_python(show=False).source==more
        assert roundtrip.save(path=source_graph_file)
        assert linked_session.qualify()
        linked_session.commit()
        assert roundtrip.link_python_source(session=linked_session)
        assert not roundtrip.import_linked_python_source()
        # Independently authored source is not a generated whole-file link.
        # Other definitions stay under source ownership and the selected
        # function is proven through the SAME graph lowering/import compiler.
        print('QT_STAGE program-independent-function-review-and-import',flush=True)
        foreign=Path(directory)/'independent-author.py'
        independent_preview=roundtrip.preview_python(show=False)
        # Source map identity and current value determine a guaranteed real edit.
        # Do not assume a previous stage left the graph literal at a fixed value.
        independent=_alter_compiled_literal(independent_preview,'one',31)
        function_text=independent.split('def increment(x):',1)[1].split('\ndef ',1)[0]
        foreign_text='import math\n\ndef other():\n    return math.pi\n\ndef increment(x):'+function_text
        foreign.write_text(foreign_text,encoding='utf-8')
        foreign_owner=w._new_source_document(foreign)
        w._source_documents[str(foreign_owner.path)]=foreign_owner
        before_foreign=roundtrip.document.state
        receipt=roundtrip.review_independent_python_function(
            session=foreign_owner,function='increment',show=False)
        assert receipt and receipt.function=='increment' and receipt.unmodeled_top_level==2
        assert len(receipt.changes)==1
        assert roundtrip.document.state==before_foreign
        assert roundtrip.import_independent_python_function(confirm=False)
        assert foreign.read_text(encoding='utf-8')==foreign_text
        assert roundtrip.document.revision==before_foreign['revision']+1
        roundtrip.undo();app.processEvents()
        assert roundtrip.document.state['nodes']==before_foreign['nodes']
        roundtrip.redo();app.processEvents()
        assert roundtrip.save(path=source_graph_file)
        # The independent-source smoke is not a new baseline for the subsequent
        # *linked* source tests. Restore the exact original graph semantically,
        # including its source map, rather than letting a prior fixture's edit
        # leak into unrelated stages of the same long-lived Qt workspace.
        roundtrip.undo();app.processEvents()
        assert roundtrip.document.state['nodes']==before_foreign['nodes']
        assert roundtrip.preview_python(show=False).source==independent_preview.source
        assert roundtrip.save(path=source_graph_file)
        # Source-owned comments are nonsemantic and must never be re-emitted
        # by the graph authority or dropped from the source owner's document.
        annotated='# retained source-only note\n'+more
        linked_session.update(annotated)
        assert not roundtrip.import_linked_python_source()
        assert roundtrip.preview_python(show=False).source==more
        annotated_next=_replace_once_for_smoke(annotated,'_smi_value_0 = 24','_smi_value_0 = 25')
        linked_session.update(annotated_next)
        assert roundtrip.import_linked_python_source(), w.statusBar().currentMessage()
        assert roundtrip.preview_python(show=False).source==_replace_once_for_smoke(more,'_smi_value_0 = 24','_smi_value_0 = 25')
        assert linked_session.text==annotated_next
        assert roundtrip.save(path=source_graph_file)
        assert linked_session.qualify()
        linked_session.commit()
        assert linked_path.read_text(encoding='utf-8')==annotated_next
        # Two authored functions are reviewed and imported as ONE graph edit.
        # This exercises the actual Function menu handler without UI duplicates.
        print('QT_STAGE program-independent-multi-function-atomic-review',flush=True)
        batch_source=roundtrip.preview_python(show=False).source
        assert 'def increment(' in batch_source and 'def compose(' in batch_source
        independent_batch=Path(directory)/'independent-batch-author.py'
        candidate=_alter_compiled_literal(roundtrip.preview_python(show=False),'one',43)
        candidate=_replace_once_for_smoke(candidate,
            '_smi_value_1 * _smi_value_1','_smi_value_1 + _smi_value_1')
        author_text='import math\n\ndef opaque_helper():\n    return math.pi\n\n'+candidate
        independent_batch.write_text(author_text,encoding='utf-8')
        author_session=w._new_source_document(independent_batch)
        current_graph=roundtrip.document.state
        receipt=roundtrip.review_independent_python_function(
            session=author_session,function='*',show=False)
        assert receipt and set(receipt.functions)=={'increment','compose'}
        assert len(receipt.changes)==2 and len(receipt.regions)==2
        assert roundtrip.document.state==current_graph
        assert roundtrip.import_independent_python_function(confirm=False)
        assert roundtrip.document.revision==current_graph['revision']+1
        assert independent_batch.read_text(encoding='utf-8')==author_text
        roundtrip.undo();app.processEvents()
        assert roundtrip.document.state['nodes']==current_graph['nodes']
        assert roundtrip.save(path=source_graph_file)
        pending=[panel.document.state['id'] for panel in w._program_tabs.values()
                 if panel.document.dirty]
        assert not pending, f'Qt smoke leaked unsaved visual program fixtures: {pending}'
        print('QT_STAGE program-require-clean-shutdown',flush=True)
        if os.environ.get('SMI_QT_PROGRAM_SCREENSHOT'):
            reopened.canvas.frame_visible_nodes();app.processEvents()
            assert reopened.canvas.grab().save(os.environ['SMI_QT_PROGRAM_SCREENSHOT'],'PNG')
        assert w.close();app.processEvents()



def exercise_save_command_ownership(app):
    """Ctrl+S and Save As must never save an inactive prototype graph."""
    print('QT_STAGE selected-document-save-ownership',flush=True)
    w=NativeLab();w.show();app.processEvents()
    with tempfile.TemporaryDirectory() as directory:
        source=Path(directory)/'editable.py'
        source.write_text('value = 1\n',encoding='utf-8')
        assert w._open_python_source_path(source)
        w.tabs.setCurrentWidget(w.source_page);w.source_canvas.setFocus()
        w.source_editor.setPlainText('value = 2\n');app.processEvents()
        assert w._active_source_document().dirty
        assert w.save_current_document()
        assert source.read_text(encoding='utf-8')=='value = 2\n'
        assert w.save_as() is False

        assert w.open_source_in_new_tab(source)
        assert w.tabs.currentWidget() is not w._source_tabs['source'].page
        w.source_canvas.setFocus();app.processEvents()
        w.source_editor.setPlainText('value = 3\n');app.processEvents()
        assert w.save_current_document(), 'Secondary source view lost its owner'
        assert source.read_text(encoding='utf-8')=='value = 3\n'
        assert w.save_as() is False

        w.tabs.setCurrentWidget(w.resource_page)
        w.resource_canvas.setFocus();app.processEvents()
        assert w.save_current_document() is False
        assert w.save_as() is False
        assert source.read_text(encoding='utf-8')=='value = 3\n'
        assert w.current_path is None

        # Preserve the explicitly selected prototype page until migration.
        w.open_legacy_graph(w.canvas,'Node workspace')
        w.canvas.setFocus();app.processEvents()
        w.current_path=Path(directory)/'legacy.json'
        w.save_current_document()
        assert w.current_path.is_file()
    assert w.close();app.processEvents()


def exercise_linked_import_outcome(app):
    """A refused postcommit receipt must still show the committed graph."""
    print('QT_STAGE linked-postcommit-ui-outcome',flush=True)
    from unittest.mock import patch
    from . import python_lowering as compiler
    from .program_graph import ProgramGraphError

    w=NativeLab();w.show();app.processEvents()
    with tempfile.TemporaryDirectory() as directory:
        example=Path(__file__).resolve().parents[1]/'examples/qualified-integer-program.smi-graph'
        program=w.open_visual_program(path=example)
        assert program is not None
        original=program.preview_python(show=False).source
        assert original is not None
        source=Path(directory)/'linked.py'
        source.write_text(original,encoding='utf-8')
        session=SourceDocumentSession.open(source)
        assert program.link_python_source(session=session)
        accepted_revision=program._source_link.graph_revision
        session.update(_replace_once_for_smoke(original,'_smi_value_0 = 1','_smi_value_0 = 17'))
        original_preview=compiler.preview_python

        def refuse_after_graph_commit(state):
            if program.document.revision!=accepted_revision:
                raise ProgramGraphError('injected postcommit receipt failure')
            return original_preview(state)

        with patch.object(compiler,'preview_python',side_effect=refuse_after_graph_commit):
            assert program.import_linked_python_source() is False
        assert program.document.revision==accepted_revision+1
        assert program._source_link.graph_revision==accepted_revision
        assert f'revision {program.document.revision}' in program.status.text()
        status=w.statusBar().currentMessage()
        assert 'Graph changed during Python source import' in status,status
        assert 'link not accepted' in status,status
        assert source.read_text(encoding='utf-8')==original
        assert session.dirty and '17' in session.text
        assert program.save_as(path=Path(directory)/'retained-graph.smi-graph')
    assert w.close();app.processEvents()



def exercise_legacy_command_ownership(app):
    """Native IDE and explicit legacy prototype must never cross command owners."""
    print('QT_STAGE native-program-and-legacy-command-ownership',flush=True)
    from .gui import ProgramWorkspace
    w=NativeLab();w.show();app.processEvents()
    file_menu=next(a.menu() for a in w.menuBar().actions() if a.text()=='File')
    view_menu=next(a.menu() for a in w.menuBar().actions() if a.text()=='View')
    graph_menu=next(a.menu() for a in w.menuBar().actions() if a.text()=='Graph')
    legacy_menu=next(a.menu() for a in view_menu.actions() if a.text()=='Legacy / Dev')
    file_actions={a.text():a for a in file_menu.actions()}
    legacy_actions={a.text():a for a in legacy_menu.actions()}
    assert 'New graph' not in file_actions and 'Open JSON graph…' not in file_actions
    assert 'Add String Constant' not in {a.text() for a in graph_menu.actions()}
    assert 'Add Custom Node' not in {a.text() for a in graph_menu.actions()}
    new_program=file_actions['New visual program (.smi-graph)']
    open_program=file_actions['Open visual program (.smi-graph)…']
    assert new_program.shortcut().toString()=='Ctrl+N'
    assert open_program.shortcut().toString()=='Ctrl+O'
    assert {'New prototype graph','Open prototype JSON…',
            'Add String Constant','Add Custom Node'}.issubset(legacy_actions)
    original_prototype=w.state
    with tempfile.TemporaryDirectory() as directory:
        new_program.trigger();app.processEvents()
        program=w.tabs.currentWidget()
        assert isinstance(program,ProgramWorkspace)
        assert w.state is original_prototype
        assert w.current_canvas() is program.canvas
        saved=Path(directory)/'native.smi-graph'
        assert program.save(path=saved)
        w._close_graph_tab(w.tabs.indexOf(program));app.processEvents()
        assert w.tabs.indexOf(program)<0
        chosen=[]
        original_picker=w._choose_file
        w._choose_file=lambda **kw:(chosen.append(kw) or str(saved))
        try:open_program.trigger()
        finally:w._choose_file=original_picker
        opened=w.tabs.currentWidget()
        assert isinstance(opened,ProgramWorkspace)
        assert opened.document.path==saved
        assert w.state is original_prototype
        w._close_graph_tab(w.tabs.indexOf(opened));app.processEvents()

        legacy_actions['New prototype graph'].trigger();app.processEvents()
        assert w.tabs.currentWidget() is w._legacy_pages[w.canvas]
        assert w.current_path is None
        prototype=Path(directory)/'prototype.json'
        w.current_path=prototype
        w.save_current_document()
        assert prototype.is_file() and model.read_state(prototype)['format']==model.FORMAT
        legacy_actions['Add String Constant'].trigger();app.processEvents()
        assert w.tabs.currentWidget() is w._legacy_pages[w.canvas]
        assert w.dirty and any(n['kind']=='string' for n in w.state['nodes'])
        w.save_current_document()
        assert not w.dirty
    assert w.close();app.processEvents()


def main():
    # Qt may report an exception raised by a Python slot through sys.excepthook
    # and continue its event loop. A completed screenshot is not proof of a
    # clean run: retain all slot errors and fail the qualification at the end.
    uncaught_callbacks=[]
    previous_excepthook=sys.excepthook
    def record_uncaught(exc_type,exc_value,exc_tb):
        uncaught_callbacks.append((exc_type,exc_value))
        previous_excepthook(exc_type,exc_value,exc_tb)
        # A failed QTimer automation must not strand a modal .exec() loop.
        # Reject the visible dialog; the subsequent test assertion will fail.
        modal=QApplication.activeModalWidget()
        if isinstance(modal,QDialog):
            modal.reject()
    sys.excepthook=record_uncaught
    # Isolate this host-only test from the user's real presentation preferences.
    _test_config=tempfile.TemporaryDirectory(prefix='smi-v25-qt-smoke-')
    os.environ['SMI_PRESENTATION_STATE_FILE']=str(Path(_test_config.name)/'view-state.json')
    print('QT_STAGE application-init',flush=True)
    app=QApplication.instance() or QApplication([])
    app.setStyle('Fusion');app.setStyleSheet(css())
    # Run crash recovery in a clean Qt process, not after dozens of unrelated
    # modal dialogs. The shell gate invokes both independently.
    if os.environ.get('SMI_QT_RECOVERY_ONLY')=='1':
        print('QT_STAGE recovery-process-init',flush=True)
        exercise_source_recovery(app)
        app.processEvents()
        _test_config.cleanup()
        sys.excepthook=previous_excepthook
        assert not uncaught_callbacks, ('Uncaught recovery Qt callback exceptions',
                                        [(kind.__name__,str(value)) for kind,value in uncaught_callbacks])
        print('NATIVE_QT_RECOVERY_PASS',flush=True)
        return
    if os.environ.get('SMI_QT_PROGRAM_ONLY')=='1':
        exercise_program_workspace(app)
        exercise_save_command_ownership(app)
        exercise_linked_import_outcome(app)
        exercise_legacy_command_ownership(app)
        app.processEvents()
        _test_config.cleanup()
        sys.excepthook=previous_excepthook
        assert not uncaught_callbacks, ('Uncaught program Qt callback exceptions',
                                        [(kind.__name__,str(value)) for kind,value in uncaught_callbacks])
        print('NATIVE_QT_PROGRAM_PASS',flush=True)
        return
    # Document history has its own process and NativeLab. It may create tabs,
    # nested dialogs and temporary source documents without affecting the
    # wider graph-integration fixture or inheriting its QApplication state.
    if os.environ.get('SMI_QT_DOCUMENT_ONLY')=='1':
        print('QT_STAGE document-process-init',flush=True)
        exercise_revisioned_source_session(app)
        app.processEvents()
        _test_config.cleanup()
        sys.excepthook=previous_excepthook
        assert not uncaught_callbacks, ('Uncaught document Qt callback exceptions',
                                        [(kind.__name__,str(value)) for kind,value in uncaught_callbacks])
        print('NATIVE_QT_DOCUMENT_PASS',flush=True)
        return
    w=NativeLab();w.show();app.processEvents()
    # v2.0 regression: no source is loaded at startup. The source canvas
    # must NOT describe the draft nodes, then KeyError on empty source nodes.
    assert w.tabs.count()==2, 'Normal workspace must not show legacy prototype tabs'
    assert w.tabs.widget(0) is w.resource_page
    assert w.tabs.widget(1) is w.source_page
    assert w.source_toolbar.parentWidget() is w.source_page
    assert w.resource_toolbar.parentWidget() is w.resource_page
    assert w.current_canvas() is w.resource_canvas
    assert w.library_modes.currentIndex()==0, 'Resource tab must not advertise Python edits'
    assert w._view_sessions.get('resource').route.kind=='resource'
    assert w._view_sessions.get('source') is None
    assert not any(toolbar.isVisible() for toolbar in w.findChildren(QToolBar)
                   if toolbar.parentWidget() is w), 'No global toolbar strip should remain'
    legacy=next(a.menu() for a in w.menuBar().actions() if a.text()=='View').actions()
    assert any(action.menu() and action.text()=='Legacy / Dev' for action in legacy)
    # Legacy graphs are inspectable but do not occupy permanent workspace tabs.
    dev=w._legacy_actions[w.canvas]
    dev.setChecked(True);app.processEvents()
    assert w.tabs.indexOf(w._legacy_pages[w.canvas])>=0
    dev.setChecked(False);app.processEvents()
    assert w.tabs.indexOf(w._legacy_pages[w.canvas])==-1 and w.tabs.count()==2
    assert w.source_canvas.graph_contract is None
    assert w.source_canvas.items_by_id=={}
    assert w.resource_canvas.graph_contract is not None
    # v2.45: Blueprint graph controls use right-drag pan, left-drag marquee,
    # and right-click context. These must survive native Qt input dispatch,
    # not just headless geometry-policy tests.
    from PyQt6.QtCore import QPoint
    canvas=w.resource_canvas
    viewport=canvas.viewport()
    blanks=(QPoint(x,y)
            for y in range(45,max(46,viewport.height()-40),42)
            for x in range(45,max(46,viewport.width()-40),42))
    blank=next((point for point in blanks if canvas._blank_graph_at(point) is not None),None)
    assert blank is not None, 'No blank region available for Qt gesture acceptance'
    card=next((card for card in canvas.items_by_id.values()
               if card.parentItem() is canvas.root_surface.content and card.isVisible()),None)
    assert card is not None
    card.setSelected(True)
    QTest.mouseClick(viewport,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,blank)
    assert not card.isSelected(), 'Left-click blank should clear the selection'
    assert canvas.marquee is None
    # Keep a generous horizontal scrollbar runway before testing root pan.
    horizontal=canvas.horizontalScrollBar()
    horizontal.setValue(min(horizontal.maximum()-100,max(horizontal.minimum()+100,
                                                          horizontal.value())))
    start=blank
    end=QPoint(min(viewport.width()-20,start.x()+50),start.y())
    if end.x()-start.x()<QApplication.startDragDistance()+5:
        start=QPoint(max(30,viewport.width()-100),start.y())
        end=QPoint(start.x()-45,start.y())
    before=horizontal.value()
    calls=[]
    original_show=canvas._show_graph_context
    canvas._show_graph_context=lambda *args:calls.append(args)
    try:
        QTest.mousePress(viewport,Qt.MouseButton.RightButton,Qt.KeyboardModifier.NoModifier,start)
        QTest.mouseMove(viewport,end)
        QTest.mouseRelease(viewport,Qt.MouseButton.RightButton,Qt.KeyboardModifier.NoModifier,end)
        assert canvas.right_pan is None
        assert horizontal.value()!=before, 'Right drag must pan the existing camera'
        assert not calls, 'Right pan incorrectly triggered a context menu'
        QTest.mouseClick(viewport,Qt.MouseButton.RightButton,Qt.KeyboardModifier.NoModifier,blank)
        assert len(calls)==1, 'Right click must open exactly one context menu'
    finally:
        canvas._show_graph_context=original_show
    # Unloaded source and legacy tabs must tolerate Qt tab-change signals.
    # Neither has authority to offer Python creation actions or invent a graph.
    for page in (w.source_page, w._legacy_pages.get(w.canvas), w.resource_page):
        if page is None:continue
        if w.tabs.indexOf(page)<0:
            w.tabs.addTab(page,'Temporary QA tab')
        w.tabs.setCurrentWidget(page)
        app.processEvents()
        assert w.library_modes.currentIndex()==(1 if page is w.source_page else 0), (
            'Node Library must reflect the selected graph authority')
        w._refresh_operation_library()
        assert not any(button.isEnabled() for button in w.source_builder_buttons.values())
    assert w.source_canvas.graph_contract is None
    assert w.canvas.graph_contract is not None
    # Restore normal tabs for the existing smoke sequence.
    legacy_page=w._legacy_pages.get(w.canvas)
    if legacy_page is not None and w.tabs.indexOf(legacy_page)>=0:
        w.tabs.removeTab(w.tabs.indexOf(legacy_page))
    w.tabs.setCurrentWidget(w.resource_page)
    app.processEvents()
    # v2.15: one menu on the LEFT of each breadcrumb toolbar. No duplicate
    # Frame / Path buttons to the right, and no command migration to Qt shell.
    for kind in ('source','resource'):
        bar=getattr(w,kind+'_toolbar')
        first=bar.actions()[0].defaultWidget()
        assert isinstance(first,QToolButton)
        assert first.objectName()==kind.title()+'GraphMenu'
        commands={entry.text() for entry in first.menu().actions()}
        assert 'Frame visible nodes' in commands
        assert ('Whole-file overview' if kind=='source' else 'Browse directory…') in commands
        assert not any(entry.text() in ('Frame','Path','Crumbs') for entry in bar.actions())
    # Every dock in the same Qt-side region shares a visibility policy, not
    # a separate copy attached to each editor/inspector widget.
    right=w._dock_regions['right']
    left=w._dock_regions['left']
    assert set(right.docks)=={w.source_editor_dock,w.inspector_dock}
    assert left.docks==[w.library_dock]
    original_source=w.source_editor.toPlainText()
    assert w.source_editor_dock.isVisible() and w.source_editor_dock.widget().isVisible()
    right.set_mode('collapsed');app.processEvents()
    assert right.mode=='collapsed' and w.source_editor_dock.isVisible()
    assert not w.source_editor_dock.widget().isVisible(), 'Dock grip must survive collapse'
    assert w.source_editor_dock.titleBarWidget().isVisible()
    if os.environ.get('SMI_QT_DOCK_SCREENSHOT'):
        assert w.grab().save(os.environ['SMI_QT_DOCK_SCREENSHOT'],'PNG')
    right.set_mode('pinned');app.processEvents()
    assert w.source_editor_dock.widget().isVisible()
    right.set_mode('auto-hide');app.processEvents()
    assert not w.source_editor_dock.widget().isVisible()
    right.on_grip_enter();app.processEvents()
    assert w.source_editor_dock.widget().isVisible()
    right._collapse();app.processEvents()
    assert not w.source_editor_dock.widget().isVisible()
    right.set_mode('pinned');app.processEvents()
    assert w.source_editor.toPlainText()==original_source
    assert w._dock_modes['right']=='pinned'

    # The File menu must summon a visible, non-native Qt dialog even on Linux
    # hosts where the native desktop portal silently fails to appear.
    seen=[]
    def dismiss_picker(dialog):
        seen.append((dialog.isVisible(),dialog.testOption(QFileDialog.Option.DontUseNativeDialog)))
        dialog.reject()
    print('QT_STAGE file-picker',flush=True)
    assert exercise_modal(app,QFileDialog,None,
        lambda:w._choose_file(title='Qt file dialog smoke', filters='Python Source (*.py)'),
        dismiss_picker) == ''
    assert any(visible and nonnative for visible,nonnative in seen), (
        'No visible non-native QFileDialog was created', seen)
    assert len(w.canvas.items_by_id)==3
    assert len(w.canvas.edge_items)==1
    assert len(w.settings_canvas.items_by_id)==2
    a=next(i for i in w.canvas.items_by_id.values() if i.data['kind']=='audio')
    assert a.panel.isVisible() and len(a.ports)==7
    assert len(a.panel.sections)==3
    before=a.height
    a.panel.sections[0].toggle_collapse()
    app.processEvents()
    assert a.height < before, (a.height,before)
    w.change_setting('port_label_mode','always')
    app.processEvents()
    assert all(p.active() for p in a.ports)
    # Contextual chips hug the rendered text instead of using a fixed
    # 128px rectangle. Paint and shape/hit-testing use the same geometry.
    from PyQt6.QtGui import QFontMetricsF
    for port in a.ports:
        label, rect=port._label_geometry()
        width=QFontMetricsF(port.CHIP_FONT).horizontalAdvance(label)
        assert rect.width() >= width+2*port.CHIP_PADDING-1
        assert rect.width() <= width+2*port.CHIP_PADDING+1
        assert port.shape().contains(rect.center()), (label,rect)
        assert rect.width() < 128, ('Short pin label contains unused padding',label,rect)
    # The label-geometry test uses ALWAYS mode only as a temporary fixture.
    # Never leave it enabled for source screenshots or they become an unreadable
    # forest of pills unrelated to the real contextual-label default.
    w.change_setting('port_label_mode','contextual')
    assert w.state['settings']['port_label_mode']=='contextual'
    a.hovered=False; a.canvas.space_held=False; a.canvas.pending=None
    assert not any(p.active() for p in a.ports), 'Smoke left labels permanently enabled'
    w.create_node('string')
    app.processEvents()
    assert len(w.state['nodes'])==4
    assert len(w.canvas.items_by_id)==4
    assert model.validate(w.state)==[]
    # create_node rebuilds the scene, destroying the *old* Qt C++ NodeItem.
    # Never call methods on a stale Python wrapper (original v0.5 smoke bug).
    a=next(i for i in w.canvas.items_by_id.values() if i.data['kind']=='audio')
    assert a.scene() is w.canvas.graph_scene
    # v2.11: exercise the REAL Qt inspector edit lifecycle, not just the
    # headless model. A mutated draft must rebuild with a fresh descriptor and
    # retain one authoritative port identity across paint and interaction.
    draft_id=a.data['id']
    first_pin=a.data['draft_ports']['inputs'][0]
    original_label=first_pin['label']
    pin_id=first_pin['id']
    w.update_port(a,first_pin,label='v211-edited-input')
    app.processEvents()
    a=w.canvas.items_by_id[draft_id]
    updated=next(pin for pin in a.ports if pin.data['id']==pin_id)
    assert updated.data['label']=='v211-edited-input'
    assert next(pin for pin in a.descriptor.ports if pin.id==pin_id).label=='v211-edited-input'
    assert a.scene() is w.canvas.graph_scene
    candidate_pin=model.port('v211-new-input','f32')
    assert w.commit_draft_change(
        lambda draft: model.find_node(draft,draft_id)['draft_ports']['inputs'].append(candidate_pin),
        inspector_node=draft_id)
    app.processEvents()
    a=w.canvas.items_by_id[draft_id]
    assert any(pin.data['id']==candidate_pin['id'] for pin in a.ports)
    if os.environ.get('SMI_QT_DRAFT_SCREENSHOT'):
        capture_node(w.canvas,a,os.environ['SMI_QT_DRAFT_SCREENSHOT'],app)
    before_invalid=model.find_node(w.state,draft_id)['draft_ports']['inputs'][0]['type']
    assert not w.commit_draft_change(
        lambda draft: model.find_node(draft,draft_id)['draft_ports']['inputs'][0].update(type='invalid-v211'))
    assert model.find_node(w.state,draft_id)['draft_ports']['inputs'][0]['type']==before_invalid
    a=w.canvas.items_by_id[draft_id]
    w.delete_port(a,next(pin for pin in a.data['draft_ports']['inputs']
                         if pin['id']==candidate_pin['id']))
    app.processEvents()
    a=w.canvas.items_by_id[draft_id]
    edited=next(pin for pin in a.data['draft_ports']['inputs'] if pin['id']==pin_id)
    w.update_port(a,edited,label=original_label)
    app.processEvents()
    a=w.canvas.items_by_id[draft_id]
    assert a.descriptor is not None
    assert len(a.ports)==7
    assert all(port.data['id'] in {p.id for p in a.descriptor.ports} for port in a.ports)
    assert model.validate(w.state)==[]
    # Regression for container addition invalidating outer shell geometry.
    previous=a.height
    a.data['containers'].append(model.section('ADDED IN SMOKE', [model.row('text','New text')]))
    a.rebuild()
    app.processEvents()
    app.processEvents()
    assert a.height > previous, (a.height,previous)
    # Source graph is derived from the real Python file, not manually-authored
    # demo pins. Navigation into a nested scope reuses NodeItem/GraphCanvas.
    demo=Path(__file__).resolve().parents[1]/'examples'/'python-scope-demo.py'
    # Exercise File menu dispatch, without blocking in a modal picker.
    open_action=next(action for action in w.menuBar().actions()[0].menu().actions()
                     if action.text().startswith('Open Python file as graph'))
    save_action=next(action for action in w.menuBar().actions()[0].menu().actions()
                     if action.text().startswith('Save as'))
    view_menu=next(action.menu() for action in w.menuBar().actions()
                   if action.text()=='View')
    legacy_menu=next(action.menu() for action in view_menu.actions()
                     if action.text()=='Legacy / Dev')
    open_json_action=next(action for action in legacy_menu.actions()
                          if action.text().startswith('Open prototype JSON'))
    picked=[]
    original_picker=w._choose_file
    w._choose_file=lambda **kw:(picked.append(kw) or str(demo))
    try: open_action.trigger()
    finally: w._choose_file=original_picker
    assert picked and w.python_doc and w.python_doc.path==demo, picked
    assert w.tabs.currentWidget() is w.source_page
    assert w._view_sessions.get('source').route.path==str(demo)
    assert w._view_sessions.get('resource').route.kind=='resource'
    assert w._view_sessions.get('source').route.kind=='source'
    assert w._view_sessions.get('resource') is not w._view_sessions.get('source')
    assert any(action.text().endswith('python-scope-demo.py')
               for action in w.source_toolbar.actions()), 'Source file missing from breadcrumb trail'
    # Frame the actual root nodes, not the giant 8500x6000 scene rectangle.
    w.fit_source_graph();app.processEvents()
    assert .3<=w.source_canvas.transform().m11()<=1.3, 'Frame zoom fell outside usable limits'
    assert w.current_canvas() is w.source_canvas
    screenshot=os.environ.get('SMI_QT_WORKSPACE_SCREENSHOT')
    if screenshot:
        assert w.grab().save(screenshot,'PNG'), 'Workspace visual capture failed'
    # Source-owned Save As must never write the unrelated legacy draft.
    # The original JSON fixture now selects its actual Legacy / Dev owner.
    assert w.save_as() is False
    with tempfile.TemporaryDirectory() as tmp:
        destination=Path(tmp)/'menu-smoke.json'
        w.open_legacy_graph(w.canvas,'Node workspace')
        w.canvas.setFocus();app.processEvents()
        w._choose_file=lambda **kw:(picked.append(kw) or str(destination))
        try:save_action.trigger()
        finally:w._choose_file=original_picker
        assert destination.is_file(), 'File > Save as did not save'
        assert w.current_path==destination, 'Save as did not set the saved location'
        assert model.read_state(destination)['format']==model.FORMAT
        w._choose_file=lambda **kw:(picked.append(kw) or str(destination))
        try:open_json_action.trigger()
        finally:w._choose_file=original_picker
        assert w.current_path==destination
    w.activate_source_tab();w.source_canvas.setFocus();app.processEvents()
    # v1.6: the default right side is an editable .py text document, not the
    # old inspector. Node selection must highlight the exact source span.
    assert w.source_editor_dock.isVisible()
    assert not w.inspector_dock.isVisible()
    assert w.source_editor.toPlainText()==w.python_doc.source
    file_node=next(item for item in w.source_canvas.items_by_id.values()
                   if item.data.get('source_kind')=='function')
    w.show_inspector(file_node);app.processEvents()
    assert w.source_editor.extraSelections(), 'Selecting a node did not highlight Python'
    assert 'def ' in w.source_editor.textCursor().selectedText()
    # Re-clicking a selected node must be able to restore its source position.
    from PyQt6.QtGui import QTextCursor
    w.source_editor.moveCursor(QTextCursor.MoveOperation.End)
    w.highlight_python_node(file_node.data);app.processEvents()
    assert 'def ' in w.source_editor.textCursor().selectedText()
    # The revisioned-source test already ran in an independent Qt process.
    # The full integration stage must retain its own single source view.
    assert set(w._source_tabs)=={'source'}, 'Document-history fixture leaked source tabs'
    assert w.tabs.currentWidget() is w.source_page, 'Document-history fixture switched the main workspace'
    assert w.python_doc is not None and w.python_doc.path==demo, (
        'Document-history fixture replaced the main workspace source')
    # Return to the original demo; smoke must never modify bundled examples.
    assert w._open_python_source_path(demo,discard_confirmed=True), "Opening demo failed"
    w._source_expanded=set(w.python_doc.scopes)-{'module'}
    w._load_source_editor()
    w._refresh_whole_file()
    # Qt-native chooser is forced in the production helper; no platform portal.
    from pathlib import Path as _Path
    assert 'DontUseNativeDialog' in (_Path(__file__).parent/'gui.py').read_text()
    assert w._open_python_source_path(demo,discard_confirmed=True), "Opening demo failed"
    w._source_expanded=set(w.python_doc.scopes)-{'module'}
    w._refresh_whole_file()
    assert w.source_view_mode=='whole'
    assert w.source_graph.get('presentation')=='composite'
    assert not w.source_graph.get('scope_regions'), 'Duplicate scope rectangles must be gone'
    from PyQt6.QtWidgets import QGraphicsItem
    for node in w.source_canvas.items_by_id.values():
        assert node.compact, 'Python nodes should use minimal chrome'
        if node.data.get('containing_scope') not in (None,'module'):
            graph=w.source_canvas.surfaces.get(node.data['containing_scope'])
            assert graph is not None, ('Missing graph owner',node.data['id'])
            assert node.parentItem() is graph.content, 'Wrong graph-region owner'
            assert graph.parentItem().region is not None
            assert graph.parentItem().surface is graph
            assert graph.flags() & graph.GraphicsItemFlag.ItemClipsChildrenToShape
    assert isinstance(w.source_canvas.root_surface, GraphSurfaceItem)
    assert w.source_canvas.root_surface.is_root
    assert len(w.source_canvas.surfaces)>1
    # Surface cameras are independent of Python graph ownership and positions.
    owner=next(card for card in w.source_canvas.items_by_id.values()
               if card.surface is not None)
    surface=owner.surface
    scope_key=surface.graph_id
    original_node_positions={key: (card.data['x'],card.data['y'])
                             for key,card in w.source_canvas.items_by_id.items()}
    assert surface.boundingRect().height()<=425
    assert surface.boundingRect().width()<=810
    # A new graph fits its content rather than opening with clipped nodes.
    assert surface.camera.content_width*surface.camera.zoom<=surface.camera.viewport_width+.01
    assert surface.camera.content_height*surface.camera.zoom<=surface.camera.viewport_height+.01
    assert owner.region['surface_top']==31, 'Composite header must be one line'
    assert len(owner.inner_ports)==len(owner.ports)
    assert all(port.parentItem() is surface for port in owner.inner_ports)
    assert all(p.pos().y()>=owner.region['surface_top'] for p in owner.ports)
    assert owner._resize_corner(QPointF(4,4))=='nw'
    assert owner._resize_corner(QPointF(owner.width-4,4))=='ne'
    assert owner._resize_corner(QPointF(4,owner.height-4))=='sw'
    assert owner._resize_corner(QPointF(owner.width-4,owner.height-4))=='se'
    initial_zoom=surface.camera.zoom
    surface.zoom_by(1.2,surface.mapToScene(QPointF(60,40)))
    assert surface.camera.zoom>initial_zoom
    assert original_node_positions=={key: (card.data['x'],card.data['y'])
                                    for key,card in w.source_canvas.items_by_id.items()}
    view_pt=w.source_canvas.mapFromScene(surface.mapToScene(QPointF(10,10)))
    # The route is decided by the same controller irrespective of nesting.
    assert w.source_canvas.navigation_surface(view_pt,Qt.KeyboardModifier.ControlModifier) is w.source_canvas.root_surface
    assert w.source_canvas.navigation_surface(view_pt,Qt.KeyboardModifier.ShiftModifier) is surface.parent_surface()
    # An unselected nested graph cannot hijack the parent camera merely
    # because the mouse happens to cross its visible child viewport.
    w.source_canvas.graph_scene.clearSelection()
    assert w.source_canvas.navigation_surface(view_pt,Qt.KeyboardModifier.NoModifier) is w.source_canvas.root_surface
    owner.setSelected(True)
    assert w.source_canvas.navigation_surface(view_pt,Qt.KeyboardModifier.NoModifier) is surface
    owner.setSelected(False)
    # Resizing is view state, survives rebuild and leaves source untouched.
    owner._resize_graph_to(740,370)
    assert surface.boundingRect().width()==740
    assert surface.boundingRect().height()==370
    assert owner.width==752
    assert all(abs(p.pos().x()-owner.width)<.01 for p in owner.ports if p.direction=='outputs')
    assert w._graph_sizes[w.source_canvas.graph_camera_key(scope_key)]==(740,370)
    previous_zoom=surface.camera.zoom
    previous_size=(surface.boundingRect().width(),surface.boundingRect().height())
    w._refresh_whole_file();app.processEvents()
    assert w.source_canvas.surfaces[scope_key].camera.zoom==previous_zoom
    refreshed=w.source_canvas.surfaces[scope_key]
    assert (refreshed.boundingRect().width(),refreshed.boundingRect().height())==previous_size
    assert all(isinstance(card.parentItem(),GraphContentItem)
               for card in w.source_canvas.items_by_id.values())
    # Regression: PyQt6 QPainter.drawLine rejects mixed int/float overloads.
    from PyQt6.QtGui import QImage, QPainter, QColor
    image=QImage(850,500,QImage.Format.Format_ARGB32)
    image.fill(QColor('#071827'))
    painter=QPainter(image)
    for card in w.source_canvas.items_by_id.values():
        if card.compact:
            card.paint_compact(painter,QColor('#39a8d3'))
    painter.end()
    child=next(card for card in w.source_canvas.items_by_id.values()
               if not card.parentItem().surface.is_root)
    original_owner=child.parentItem()
    child.setPos(QPointF(-50,-60))
    assert child.parentItem() is original_owner, 'Dragging must not reparent a node'
    assert child.pos().x()>=0 and child.pos().y()>=0, 'Child escaped graph origin'
    # v2.31: Branch and Loop are compact operations in the SAME function
    # surface. Nested function implementation remains a true graph. A stale
    # collapsed-region preference must not hide an executable statement.
    v15=Path(__file__).resolve().parents[1]/'examples'/'python-v15-boundary-regions.py'
    assert v15.exists()
    assert w._open_python_source_path(v15,discard_confirmed=True), "Opening v15 failed"
    w._source_expanded=set(w.python_doc.scopes)-{'module'}
    w._refresh_whole_file();app.processEvents()
    controls=[card for card in w.source_canvas.items_by_id.values()
              if card.data.get('source_kind') in ('branch','loop')]
    assert controls and all(card.surface is None and card.region is None for card in controls)
    assert all(card.interface is not None for card in controls)
    assert all(card.parentItem().surface.graph_id in w.python_doc.scopes for card in controls)
    assert not any(' BODY' in card.data['title'] for card in controls)
    before_ids=set(w.source_canvas.items_by_id)
    before_edges={edge['id'] for edge in w.source_graph['edges']}
    before_source=w.python_doc.path.read_bytes()
    w._region_collapsed.add('obsolete/control-region')
    w._refresh_whole_file();app.processEvents()
    assert set(w.source_canvas.items_by_id)==before_ids
    assert {edge['id'] for edge in w.source_graph['edges']}==before_edges
    assert all(not c.data.get('presentation_hidden') for c in w.source_canvas.items_by_id.values()
               if c.data.get('source_kind') in ('branch','loop'))
    focused_scope=next(k for k,scope in w.python_doc.scopes.items()
                       if scope.title=='nested')
    w.navigate_source(focused_scope);app.processEvents()
    focus_controls=[card for card in w.source_canvas.items_by_id.values()
                    if card.data.get('source_kind') in ('branch','loop')]
    assert len(focus_controls)==3
    assert all(card.surface is None and card.parentItem().surface.is_root for card in focus_controls)
    target=next(card for card in focus_controls if card.data['source_kind']=='branch')
    if os.environ.get('SMI_QT_FOCUSED_REGION_SCREENSHOT'):
        capture_node(w.source_canvas,target,
                     os.environ['SMI_QT_FOCUSED_REGION_SCREENSHOT'],app)
    assert w.python_doc.path.read_bytes()==before_source
    # Resume the existing tests against the original Python demo.
    assert w._open_python_source_path(demo,discard_confirmed=True), "Opening demo failed"
    w._source_expanded=set(w.python_doc.scopes)-{'module'}
    w._refresh_whole_file();app.processEvents()
    # Source code never changes when a node is dragged within its graph.
    assert w.python_doc.path.read_bytes()==w.python_doc.raw
    assert len(w.source_canvas.items_by_id)>len(w.python_doc.scope_graph('module')['nodes'])
    assert len(w.source_canvas.edge_items)>len(w.python_doc.scope_graph('module')['edges'])
    assert any(card.compact for card in w.source_canvas.items_by_id.values())
    w.set_all_scopes(False)
    assert len(w.source_canvas.items_by_id)==len(w.python_doc.scope_graph('module')['nodes'])
    w.set_all_scopes(True)
    assert w.source_view_mode=='whole', 'Expanded function smoke requires whole-file view'
    assert any(n.data['title']=='OUTER' for n in w.source_canvas.items_by_id.values())
    # v2.9: a focused MODULE graph contains only module-level constructs.
    # The previous smoke navigated to module before looking for INNER, then
    # crashed with StopIteration. Check the nested definition in the actual
    # expanded whole-file graph, where its embedded surface exists.
    nested_candidates=[n for n in w.source_canvas.items_by_id.values()
                       if n.data.get('source_kind')=='nested' and n.data.get('title')=='INNER']
    assert len(nested_candidates)==1, (
        'Expected INNER in expanded whole-file graph', w.source_view_mode,
        [(n.data.get('source_kind'),n.data.get('title'))
         for n in w.source_canvas.items_by_id.values()])
    inner_def=nested_candidates[0]
    assert inner_def.descriptor.semantic_role=='definition'
    assert inner_def.surface is not None
    outer_exec=[p for p in inner_def.ports if p.data.get('type')=='execution']
    inner_exec=[p for p in inner_def.inner_ports if p.data.get('type')=='execution']
    assert outer_exec and all(p.isVisible() for p in outer_exec)
    assert len(inner_exec)==len(outer_exec) and all(not p.isVisible() for p in inner_exec)
    assert 'does not enter' in outer_exec[0].toolTip()
    # Keep a real Qt screenshot of the precise nested-boundary interaction
    # under test. Center the node instead of capturing an unrelated viewport.
    nested_image=os.environ.get('SMI_QT_NESTED_SCREENSHOT')
    if nested_image:
        capture_node(w.source_canvas, inner_def, nested_image, app)
        print(f'Nested-boundary screenshot saved: {nested_image}',flush=True)
    # The module focus intentionally omits INNER; parent focus includes it.
    # Context navigation must create a legible root-scale focus without a
    # duplicate code document or a second writable source authority.
    focus_card=next((card for card in w.source_canvas.items_by_id.values()
                     if card.data.get('source_scope') and card.isVisible()),None)
    if focus_card:
        focus_card.setSelected(True)
        target_scope=focus_card.data['source_scope']
        w.focus_selected_scope();app.processEvents()
        assert w.source_view_mode=='focus' and w.source_scope==target_scope
        assert .3<=w.source_canvas.transform().m11()<=1.3
    w._refresh_whole_file();app.processEvents()
    w.navigate_source('module')
    assert any(n.data['title']=='OUTER' for n in w.source_canvas.items_by_id.values())
    assert not any(n.data.get('source_kind')=='nested' and n.data.get('title')=='INNER'
                   for n in w.source_canvas.items_by_id.values()), (
                   'Module focus unexpectedly contains a nested definition')
    outer_key=next(k for k in w.python_doc.scopes if k.endswith('function:outer:5:0'))
    w.navigate_source(outer_key)
    assert any(n.data['source_kind']=='nested' for n in w.source_canvas.items_by_id.values())
    nested_key=next(k for k in w.python_doc.scopes if k.endswith('function:inner:8:4'))
    w.navigate_source(nested_key)
    # Real QAction breadcrumbs navigate to lexical ancestors, while history
    # retains the previous focused graph and its source file identity.
    assert w._view_sessions.get('source').route.scope==nested_key
    outer_action=next(a for a in w.source_toolbar.actions()
                      if a.text().endswith('outer'))
    outer_action.trigger();app.processEvents()
    assert w.source_scope==outer_key and w.source_view_mode=='focus'
    assert w._navigate_history('source',-1)
    assert w.source_scope==nested_key
    assert w._navigate_history('source',1)
    assert w.source_scope==outer_key
    assert w._navigate_history('source',-1)
    assert w.source_scope==nested_key
    assert any(a.text().endswith('inner') for a in w.source_toolbar.actions())
    if os.environ.get('SMI_QT_NAV_SCREENSHOT'):
        assert w.grab().save(os.environ['SMI_QT_NAV_SCREENSHOT'],'PNG')
    assert any(n.data['title']=='CAPTURE base' for n in w.source_canvas.items_by_id.values())
    assert any(e.get('relation')=='data' for e in w.source_graph['edges'])
    w.show_source_inspector(next(i for i in w.source_canvas.items_by_id.values() if i.data['source_kind']=='operation'))
    app.processEvents()
    # Source rewiring is a diff proposal, not a second, silently edited graph.
    fn=next(k for k,scope in w.python_doc.scopes.items()
            if k!='module' and scope.title=='square_plus_ten')
    # Source edit verifier retains the full AST-analysis node IDs. The
    # readable projection omits literal cards when they are inline values.
    w.source_detail='analysis'
    w.navigate_source(fn)
    source_nodes=w.source_graph['nodes']
    literal=next(n for n in source_nodes if n['source_kind']=='literal')
    operator=next(n for n in source_nodes if n['source_kind']=='operation' and 'a * a' in n['subtitle'])
    rhs=next(p for p in operator['draft_ports']['inputs'] if p['id'].endswith(':rhs'))
    reviewed=[]
    original_review=w.review_source_proposal
    w.review_source_proposal=lambda proposal:reviewed.append(proposal)
    try:
        w.rewire_python_input(literal['id'],literal['draft_ports']['outputs'][0]['id'],operator['id'],rhs['id'])
    finally:
        w.review_source_proposal=original_review
    assert len(reviewed)==1 and 'a * 10' in reviewed[0].candidate.decode()
    assert w.python_doc.path.read_bytes()==w.python_doc.raw
    w.source_detail='readable'
    # Unconnected scalar fallbacks remain valid draft values; a wire hides the
    # displayed editor without destroying the stored fallback.
    custom=model.make_node('custom')
    assert custom['draft_ports']['inputs'][0]['default']==0.5
    assert model.validate({'format':model.FORMAT,'version':model.VERSION,
        'nodes':[custom],'edges':[],'settings':model.new_state()['settings']})==[]
    app.processEvents()
    cf=Path(__file__).resolve().parents[1]/'examples'/'python-control-flow-demo.py'
    assert w._open_python_source_path(cf,discard_confirmed=True), "Opening cf failed"
    w._source_expanded=set(w.python_doc.scopes)-{'module'}
    # Regression: focused routing to whole-file preserves one canonical
    # document while normalizing the scope before rebuilding breadcrumbs.
    scope_key=next(k for k,v in w.python_doc.scopes.items() if v.kind=='function')
    assert w.navigate_source(scope_key)
    assert w.source_view_mode=='focus'
    w._refresh_whole_file();app.processEvents()
    assert w.source_scope=='module' and w.source_view_mode=='whole', (
        'Whole-file navigation retained stale focus',w.source_scope,w.source_view_mode)
    assert w._navigation_route('source').scope=='module'
    assert w.source_toolbar.actions(), 'Breadcrumb toolbar was not reconstructed'
    assert any(i.data['source_kind']=='branch' for i in w.source_canvas.items_by_id.values())
    assert any(i.data['source_kind']=='compare' for i in w.source_canvas.items_by_id.values())
    assert len(w.source_canvas.edge_items)>0
    # v1.0+: readable loops have *implicit* repetition. There is no
    # invented entry/repeat connector; body and completed are real exits.
    loops_demo=Path(__file__).resolve().parents[1]/'examples'/'python-v08-loop-control.py'
    assert w._open_python_source_path(loops_demo,discard_confirmed=True), "Opening loops_demo failed"
    loop_key=next(key for key,scope in w.python_doc.scopes.items() if scope.title=='countdown')
    w.navigate_source(loop_key)
    app.processEvents()
    graph=w.source_graph
    assert any(item.compact and item.data['source_kind']=='loop'
               for item in w.source_canvas.items_by_id.values())
    assert not any(' BODY' in item.data['title']
                   for item in w.source_canvas.items_by_id.values())
    assert any(item.data['title']=='-=' and item.data.get('binding_name')=='n' and item.compact
               for item in w.source_canvas.items_by_id.values())
    loops=[n for n in graph['nodes'] if n['source_kind']=='loop']
    assert len(loops)==1
    loop=loops[0]
    assert loop['loop_semantics']['condition_evaluation']=='per_iteration'
    assert not any(e['target']==loop['id'] and e['relation']=='control'
                   and e['targetPort'].endswith(':repeat') for e in graph['edges'])
    assert any(e['source']==loop['id'] and e['relation']=='control'
               and e['sourcePort'].endswith(':body') for e in graph['edges'])
    # The graph renderer must actually create all projected edges. A missing
    # port would otherwise silently disappear in GraphCanvas.update_edges().
    assert len(w.source_canvas.edge_items)==sum(e.get('relation')!='call' for e in graph['edges']), (
        len(w.source_canvas.edge_items),len(graph['edges']))
    # v1.0: the user-facing graph does not expose compiler-analysis helpers.
    assert not any(n['source_kind'] in ('entry','exit','loop_test','loop_value')
                   for n in graph['nodes'])
    assert w.source_detail=='readable'
    # A source-backed numeric input is clickable across its displayed value,
    # not only on the pin center; double-click opens the reviewed literal edit.
    upd=next(card for card in w.source_canvas.items_by_id.values()
             if card.data['source_kind']=='assignment' and
                any(p.get('source_literal_span') for p in card.data['draft_ports']['inputs']))
    lit_port=next(p for p in upd.ports if p.data.get('source_literal_span'))
    assert lit_port.shape().contains(QPointF(40,0))
    w.toggle_python_detail();app.processEvents()
    assert w.source_detail=='analysis'
    assert any(n['source_kind']=='loop_value' for n in w.source_graph['nodes'])
    w.toggle_python_detail();app.processEvents()
    assert w.source_detail=='readable'
    # v1.1: run the real Qt renderer against the source-backed variable
    # example. Compact variable cards show authored defaults; normal return
    # receives the binding's result through a real connection.
    binding_sample=Path(__file__).resolve().parents[1]/'examples'/'python-v11-bindings-and-returns.py'
    assert w._open_python_source_path(binding_sample,discard_confirmed=True), "Opening binding_sample failed"
    combine_key=next(k for k,scope in w.python_doc.scopes.items() if scope.title=='combine_strings')
    w.navigate_source(combine_key)
    app.processEvents()
    by_title={item.data['title']:item for item in w.source_canvas.items_by_id.values()}
    assert list(by_title)==['a','b','ADD','c','RETURN']
    assert 150<=by_title['a'].width<=240 and 150<=by_title['c'].width<=240
    assert any(port.data.get('source_literal_text')=='"a"' for port in by_title['a'].ports)
    assert len(w.source_canvas.edge_items)==len(w.source_graph['edges'])
    sum_key=next(k for k,scope in w.python_doc.scopes.items() if scope.title=='sum_items')
    w.navigate_source(sum_key)
    app.processEvents()
    loop=next(item.data for item in w.source_canvas.items_by_id.values()
              if item.data['source_kind']=='loop')
    assert loop['title']=='FOR item'
    assert not any(port['id'].endswith(':repeat') for port in loop['draft_ports']['inputs'])
    assert len(w.source_canvas.edge_items)==len(w.source_graph['edges'])
    # v2.31: IF and loop are operations, not implicit nested containers.
    v17=Path(__file__).resolve().parents[1]/'examples'/'python-v17-source-constructs.py'
    assert w._open_python_source_path(v17,discard_confirmed=True), "Opening v17 failed"
    w._source_expanded=set(w.python_doc.scopes)-{'module'}
    w._load_source_editor()
    w._refresh_whole_file();app.processEvents()
    conditional=next(card for card in w.source_canvas.items_by_id.values()
                     if card.data.get('source_construct')=='conditional')
    assert conditional.data['title'].startswith('IF ')
    assert conditional.surface is None and conditional.region is None
    assert conditional.interface and conditional.interface.category=='conditional'
    w.tabs.setCurrentWidget(w.source_page);app.processEvents()
    w._refresh_operation_library()
    library=[w.operation_entries.item(i) for i in range(w.operation_entries.count())]
    assert any('branch' in item.text() for item in library), 'Source operation catalog missing Branch'
    assert all('not-qualified' in item.toolTip() for item in library)
    if os.environ.get('SMI_QT_CATALOG_SCREENSHOT'):
        assert w.grab().save(os.environ['SMI_QT_CATALOG_SCREENSHOT'],'PNG')
    assert any(card.data.get('source_construct')=='augmented_assignment' and card.data['title']=='+='
               for card in w.source_canvas.items_by_id.values())
    assert w.source_editor.toPlainText()==w.python_doc.source
    assert len(w.source_canvas.edge_items)>0
    # v1.8: Qt consumes one validated descriptor contract for both authored
    # drafts and source-derived graphs. Actual inner graph boundary aliases
    # are discoverable as drag endpoints without inventing port identities.
    from .boundary_edit import parameter_source, terminal_return_target
    v18=Path(__file__).resolve().parents[1]/'examples'/'python-v18-boundary-and-layout.py'
    assert w._open_python_source_path(v18,discard_confirmed=True), "Opening v18 failed"
    w._source_expanded=set(w.python_doc.scopes)-{'module'}
    w._load_source_editor()
    w._refresh_whole_file();app.processEvents()
    descriptor=w.source_canvas.graph_contract
    assert descriptor and descriptor.origin=='source'
    assert len(descriptor.nodes)==len(w.source_graph['nodes'])
    for rendered in w.source_canvas.items_by_id.values():
        assert [(p.direction,p.data['id']) for p in rendered.ports] == [
            (p.direction,p.id) for p in rendered.descriptor.ports], (
            'Source port presentation diverged from validated descriptor',rendered.data['id'])
    chosen=next(card for card in w.source_canvas.items_by_id.values()
                if card.data.get('source_kind')=='function' and
                card.data.get('source_scope') and card.data['title'].lower().endswith('choose'))
    assert chosen.surface is not None
    param=next(p for p in chosen.inner_ports if p.direction=='inputs' and p.data['label']=='b')
    ret=next(p for p in chosen.inner_ports if p.direction=='outputs' and p.data['label']=='return')
    assert w.source_canvas.find_boundary_port(w.source_canvas.mapFromScene(param.mapToScene(QPointF(0,0)))) is param
    # The old inner return mirror still exists as a geometric alias for
    # compatibility, but is not painted as a duplicate output dot.
    assert not ret.isVisible()
    assert parameter_source(w.source_graph,chosen.data['id'],param.data['id'])
    assert terminal_return_target(w.source_graph,chosen.data['id'],ret.data['id'])
    assert len(w.source_canvas.edge_items)>0
    # v2.2: one physically anchored return dot plus its control-completion
    # facet. The inner mirror is deliberately not painted at a second x/y.
    return_outer=next(p for p in chosen.ports if p.data['label']=='return')
    assert return_outer.isVisible()
    assert not ret.isVisible()
    assert len(chosen.exit_lanes)==1
    assert chosen.exit_lanes[0].exit_spec.value_port==return_outer.data['id']
    assert abs(chosen.exit_lanes[0].pos().x()-return_outer.pos().x())<.01
    assert chosen.exit_lanes[0].pos().y()>return_outer.pos().y()
    assert w.source_canvas.find_port(
        w.source_canvas.mapFromScene(return_outer.mapToScene(QPointF(0,0)))) is return_outer
    callable_pins=[p for p in chosen.ports if p.data['label']=='callable']
    assert all(not p.isVisible() for p in callable_pins)
    # v2.6: folded final RETURN is a semantic exit, not a card or a newly
    # invented source edge. Both real data/control inputs now draw INSIDE the
    # function's child graph. Parent-scene routes were hidden by its frame.
    nested=next(card for card in w.source_canvas.items_by_id.values()
                if card.data.get('source_kind')=='function' and
                   card.data.get('title')=='NESTED_EXPRESSION')
    terminal=next(route for route in w.source_canvas.exit_routes
                  if route.owner_node==nested.data['id'])
    assert terminal.folded
    real_inbound={edge.id:edge for edge in w.source_canvas.graph_contract.edges
                  if edge.target_node==terminal.site_node}
    folded_connections={connection.edge_id:connection for connection in
                        w.source_canvas.folded_exit_connections.values()
                        if connection.route.site_node==terminal.site_node}
    assert {c.facet for c in folded_connections.values()}=={'value','control'}
    assert set(real_inbound)==set(folded_connections), 'A return edge vanished or was invented'

    def assert_folded_geometry():
        edges={item.data(0):item for item in w.source_canvas.edge_items}
        for edge_id, connection in folded_connections.items():
            visible=edges[edge_id]
            assert visible.parentItem() is nested.surface.content, 'Return path painted under function frame'
            source_edge=real_inbound[edge_id]
            src=w.source_canvas.items_by_id[source_edge.source_node]
            source_pin=next(p for p in src.ports if p.data['id']==source_edge.source_port)
            target=(next(p for p in nested.ports if p.data['id']==terminal.value_port)
                    if connection.facet=='value' else
                    next(p for p in nested.exit_lanes
                         if p.exit_spec.control_anchor_id==terminal.control_anchor))
            path=visible.path()
            start=visible.mapToScene(path.pointAtPercent(0))
            end=visible.mapToScene(path.pointAtPercent(1))
            assert (start-source_pin.mapToScene(QPointF(0,0))).manhattanLength()<.5
            assert (end-target.mapToScene(QPointF(0,0))).manhattanLength()<.5
    assert_folded_geometry()
    total=next(card for card in w.source_canvas.items_by_id.values()
               if card.data.get('binding_name')=='total' and card.isVisible())
    initial=total.pos()
    total.setPos(initial+QPointF(19,11))
    w.source_canvas.update_edges()
    assert_folded_geometry()  # real move reprojects both ends
    total.setPos(initial)
    nested.surface.pan_by(-12,0)
    w.source_canvas.update_edges()
    assert_folded_geometry()  # nested camera cannot detach the return wires
    # The earlier screenshot only captured a later loop example, which hid
    # return-interface regressions. Capture the actual return geometry here.
    return_image=os.environ.get('SMI_QT_RETURN_SCREENSHOT')
    if return_image:
        capture_node(w.source_canvas, nested, return_image, app)
        print(f'Return-boundary screenshot saved: {return_image}',flush=True)

    # Return in a nested IF exits the owning function, not the conditional.
    early=next(card for card in w.source_canvas.items_by_id.values()
               if card.data.get('source_scope') and
                  card.data.get('source_kind')=='function' and
                  card.data.get('title')=='EARLY_EXIT')
    assert early.interface is not None
    assert len(early.interface.exits[0].sites)==2
    assert len(early.exit_lanes)==1
    exit_tags={edge.data(0) for edge in w.source_canvas.edge_items
               if isinstance(edge.data(0),str) and edge.data(0).startswith('exit-')}
    assert any(tag.startswith('exit-control:') for tag in exit_tags), exit_tags
    assert any(tag.startswith('exit-value:') for tag in exit_tags), exit_tags
    # v2.3: RETURN's visible exit wires begin at actual terminal facet
    # geometry, not at arbitrary painter coordinates inside the RETURN card.
    visible_returns=[card for card in w.source_canvas.items_by_id.values()
                     if card.data.get('exit_target_owner')==early.data['id']
                     and card.isVisible()]
    assert len(visible_returns)==2
    for ret_site in visible_returns:
        assert {'control','value'} <= set(ret_site.return_facets)
        for facet in ('control','value'):
            pin=ret_site.return_facets[facet]
            assert abs(pin.pos().x()-ret_site.width)<.01
            candidates=[edge for edge in w.source_canvas.edge_items
                        if edge.data(0)=='exit-'+facet+':'+ret_site.data['id']]
            assert len(candidates)==1, (facet,ret_site.data['id'])
            path=candidates[0].path()
            start=candidates[0].mapToScene(path.pointAtPercent(0))
            actual=pin.mapToScene(QPointF(0,0))
            assert (start-actual).manhattanLength()<.5, (start,actual)
            assert candidates[0].parentItem() is early.surface.content, (
                'Nonlocal return must be drawn in owning function graph',ret_site.data['id'])
            end=candidates[0].mapToScene(path.pointAtPercent(1))
            endpoint=(next(p for p in early.ports if p.data['id']==early.interface.exits[0].value_port)
                      if facet=='value' else early.exit_lanes[0])
            assert (end-endpoint.mapToScene(QPointF(0,0))).manhattanLength()<.5
    early_image=os.environ.get('SMI_QT_EARLY_EXIT_SCREENSHOT')
    if early_image:
        capture_node(w.source_canvas, early, early_image, app)
        print(f'Early-exit screenshot saved: {early_image}',flush=True)
    inner_if=next(card for card in w.source_canvas.items_by_id.values()
                  if card.data.get('source_kind')=='branch' and
                     card.data.get('containing_scope','').startswith(early.data['source_scope']))
    assert inner_if.interface and inner_if.interface.category=='conditional'
    assert not any(p.data.get('label')=='return' for p in inner_if.ports)
    # Files/System uses the SAME QGraphicsView/NodeItem renderer, but its
    # graph is a read-only provider projection. No file is run or modified.
    with tempfile.TemporaryDirectory() as workspace_tmp:
        folder=Path(workspace_tmp)
        (folder/'sub').mkdir()
        (folder/'demo.py').write_text('def test():\n    return 3\n',encoding='utf-8')
        assert w.browse_resource(folder)
        assert w.tabs.currentWidget() is w.resource_page
        assert w.resource_canvas.graph_contract.origin=='resource'
        for rendered in w.resource_canvas.items_by_id.values():
            assert [(p.direction,p.data['id']) for p in rendered.ports] == [
                (p.direction,p.id) for p in rendered.descriptor.ports]
        assert len(w.resource_canvas.items_by_id)==2
        sub=next(n for n in w.resource_canvas.items_by_id.values() if n.data['title']=='sub')
        assert sub.compact and sub.resource_view and not sub.source_view
        assert sub.width<200 and sub.height<40, 'Resource cards should be minimal'
        assert sub._toggle_hit(QPointF(sub.width-16,14))
        # Manual positions belong to the user, never to folder expansion.
        sub.setPos(QPointF(120,140));app.processEvents()
        before_manual=(sub.data['x'],sub.data['y'])
        w.resource_canvas._activate_node_layer(sub)
        assert sub.zValue()>5
        # Inline-expand the same folder without changing the selected root.
        assert w.toggle_resource_expansion(sub.data)
        app.processEvents()
        expanded=next(n for n in w.resource_canvas.items_by_id.values()
                      if n.data['title']=='sub')
        assert expanded.surface is not None
        assert (expanded.data['x'],expanded.data['y'])==before_manual, 'Folder expansion reset manual layout'
        assert w.resource_path==folder
        assert expanded._resize_corner(QPointF(expanded.width/2,2))=='n'
        assert expanded._resize_corner(QPointF(2,expanded.height/2))=='w'
        assert expanded._resize_corner(QPointF(expanded.width-2,expanded.height/2))=='e'
        assert expanded._resize_corner(QPointF(expanded.width/2,expanded.height-2))=='s'
        assert w.toggle_resource_expansion(expanded.data)
        app.processEvents()
        sub=next(n for n in w.resource_canvas.items_by_id.values()
                 if n.data['title']=='sub')
        assert sub.surface is None
        assert (sub.data['x'],sub.data['y'])==before_manual, 'Folder collapse reset manual layout'

        w.open_resource_node(sub.data)
        assert w.resource_path==folder/'sub'
        assert w._navigate_history('resource',-1)
        assert w.resource_path==folder
        assert w._navigate_history('resource',1)
        assert w.resource_path==folder/'sub'
        # Address-mode widget is owned by the same navigation bar, not a
        # floating toolbar competing with the active graph viewport.
        w._toggle_navigation_address('resource');app.processEvents()
        assert w.resource_toolbar.findChild(__import__('PyQt6.QtWidgets',fromlist=['QLineEdit']).QLineEdit,
                                           'ResourceGraphAddress') is not None
        w._toggle_navigation_address('resource')
        w.resource_parent()
        candidate=next(n for n in w.resource_canvas.items_by_id.values() if n.data['title']=='demo.py')
        w.open_resource_node(candidate.data)
        assert w.python_doc.path==folder/'demo.py'
        assert w.tabs.currentWidget() is w.source_page
        # v2.17: the resource-open path now uses the same route resolver as
        # the source picker, and neither one creates a shadow source graph.
        resolved=resolve_graph(Route('source',str(w.python_doc.path)),
                               document=w.python_doc,detail=w.source_detail,
                               expanded_scopes=w._source_expanded,
                               collapsed_regions=w._region_collapsed)
        assert {n['id'] for n in w.source_graph['nodes']}=={n['id'] for n in resolved.graph['nodes']}
        assert w.source_canvas.graph_contract==resolved.descriptor
        assert w._view_sessions.get('source').route==resolved.route
    # v2.31: Module guard call sites remain source-backed and visible in
    # the module surface, without inventing a nested graph for the guard.
    v20=Path(__file__).resolve().parents[1]/'examples'/'python_v20_cross_file_main.py'
    assert w._open_python_source_path(v20,discard_confirmed=True), "Opening v20 failed"
    w._source_expanded=set(w.python_doc.scopes)-{'module'}
    w._load_source_editor()
    w._refresh_whole_file();app.processEvents()
    call_cards=[card for card in w.source_canvas.items_by_id.values()
                if card.data.get('call_expression')]
    assert {'print','calculate'} <= {c.data.get('call_direct_name') for c in call_cards}
    assert any(c.data.get('containing_scope')=='module' and
               c.parentItem().surface.is_root for c in call_cards)
    assert w.source_canvas.graph_contract.origin=='source'
    w.highlight_python_node(call_cards[0].data);app.processEvents()
    assert w.source_editor.textCursor().selectedText(), 'Call node must locate real Python code'
    # v2.34: user-supplied main-guard pattern. Nested call results and source
    # argument previews remain readable instead of hiding behind CALL print.
    nested_main=Path(__file__).resolve().parents[1]/'examples/python-v13-nested-main-calls.py'
    assert w._open_python_source_path(nested_main,discard_confirmed=True), "Opening nested_main failed"
    w._source_expanded=set()
    w._load_source_editor()
    w._refresh_whole_file();app.processEvents()
    calls=[c for c in w.source_canvas.items_by_id.values() if c.data.get('call_expression')]
    assert len(calls)==6, ('Expected print and its three nested call-sites',len(calls))
    guard=next(c for c in w.source_canvas.items_by_id.values() if
               c.data.get('semantic_role')=='control_operation' and
               c.data.get('source_guard_test')=="__name__ == '__main__'")
    assert any(e['source']==guard.data['id'] and e['relation']=='control'
               for e in w.source_graph['edges'])
    assert any(p.active() for c in calls for p in c.ports if
               p.data.get('source_expression_preview'))
    assert w.source_canvas.graph_contract.origin=='source'
    if os.environ.get('SMI_QT_CALL_CHAIN_SCREENSHOT'):
        w.fit_source_graph();app.processEvents()
        assert w.grab().save(os.environ['SMI_QT_CALL_CHAIN_SCREENSHOT'],'PNG')
    with tempfile.TemporaryDirectory() as workdir:
        dir_=Path(workdir)
        (dir_/'helper.py').write_text('def double(x): return x*2\n',encoding='utf-8')
        (dir_/'main.py').write_text('from helper import double\n',encoding='utf-8')
        w.resource_show_imports=False
        assert w.browse_resource(dir_,activate=False)
        assert not w.resource_graph['edges']
        w.toggle_resource_imports();app.processEvents()
        assert len(w.resource_graph['edges'])==1
        assert w.resource_graph['edges'][0]['certainty']=='local-file-candidate'
        assert w.resource_canvas.graph_contract.origin=='resource'
        assert len(w.resource_canvas.edge_items)==1
        assert w.resource_canvas.edge_items[0].toolTip(), 'Association needs evidence tooltip'
        w.toggle_resource_imports()
        assert not w.resource_graph['edges']
    # A resource file expands in the SAME graph canvas, while independently
    # opening its Python source remains a route into the existing source view.
    print('QT_STAGE resource-file-previews-and-verified-links',flush=True)
    with tempfile.TemporaryDirectory() as preview_tmp:
        directory=Path(preview_tmp)
        picture=directory/'hero.png'
        image=QImage(8,8,QImage.Format.Format_ARGB32)
        image.fill(QColor('#8bd0a7'))
        assert image.save(str(picture),'PNG')
        script=directory/'main.py'
        script.write_text("def load():\n    return open('hero.png', 'rb')\n",encoding='utf-8')
        notes=directory/'notes.md'
        notes.write_text('# Read-only preview\n\nInformation stays in the file.\n',encoding='utf-8')
        assert w.browse_resource(directory,activate=False)
        cards={node.data['title']:node for node in w.resource_canvas.items_by_id.values()}
        image_id=cards['hero.png'].data['id']
        source_id=cards['main.py'].data['id']
        notes_id=cards['notes.md'].data['id']
        assert cards['notes.md']._can_toggle_region()
        assert w.open_resource_node(cards['notes.md'].data)
        app.processEvents()
        read_only=w.resource_canvas.items_by_id[notes_id]
        assert read_only.resource_preview['kind']=='text'
        assert '# Read-only preview' in read_only.resource_preview['text']
        assert read_only.height>200
        assert notes.read_text().startswith('# Read-only preview')
        assert w.open_resource_node(read_only.data)
        assert not w.resource_canvas.items_by_id[notes_id].resource_preview
        # Resource rebuild replaces Qt scene items; never reuse a deleted
        # QGraphicsObject wrapper after expanding a different resource.
        assert w.resource_canvas.items_by_id[image_id]._can_toggle_region()
        assert w.toggle_resource_expansion(w.resource_canvas.items_by_id[image_id].data)
        app.processEvents()
        expanded=w.resource_canvas.items_by_id[image_id]
        assert expanded.resource_preview['kind']=='image'
        assert expanded.height>150
        assert not w.resource_thumbnail(expanded.data).isNull()
        assert w.toggle_resource_expansion(expanded.data)
        assert w.toggle_resource_expansion(w.resource_canvas.items_by_id[source_id].data)
        app.processEvents()
        source=w.resource_canvas.items_by_id[source_id]
        assert source.region and source.region['role']=='python-source'
        nested=[card for card in w.resource_canvas.items_by_id.values()
                if card.data.get('resource_source_path')==str(script)]
        assert any(card.data.get('source_kind')=='function' for card in nested)
        assert all(card.parentItem() is not w.resource_canvas.root_surface.content
                   for card in nested), 'Source nodes must remain inside file region'
        assert w.resource_canvas.graph_contract.origin=='resource'
        # The existing revisioned owner takes precedence over saved bytes.
        live=SourceDocumentSession.open(script)
        w._source_documents[str(script)]=live
        live.update("def changed():\n    return open('hero.png','rb')\n")
        w._refresh_resource_source_views(str(script));app.processEvents()
        assert any(card.data.get('title')=='CHANGED' for card in
                   w.resource_canvas.items_by_id.values())
        live.update('def incomplete(:\n')
        w._refresh_resource_source_views(str(script));app.processEvents()
        bad=w.resource_canvas.items_by_id[source_id]
        assert 'no qualified graph' in bad.resource_preview['status']
        assert not any(card.data.get('resource_source_path')==str(script)
                       for card in w.resource_canvas.items_by_id.values())
        live.update(script.read_text())
        w._source_documents.pop(str(script))
        w._refresh_resource_source_views(str(script));app.processEvents()
        if os.environ.get('SMI_QT_RESOURCE_PYTHON_SCREENSHOT'):
            assert w.grab().save(os.environ['SMI_QT_RESOURCE_PYTHON_SCREENSHOT'],'PNG')
        w.toggle_resource_imports();app.processEvents()
        assert any(edge['relation']=='reference' and edge['certainty']=='literal-path-candidate'
                   for edge in w.resource_graph['edges'])
        assert w.resource_canvas.graph_contract.origin=='resource'
        assert w.resource_path==directory
        assert w.toggle_resource_expansion(w.resource_canvas.items_by_id[source_id].data)
        w.toggle_resource_imports()
    print('QT_STAGE expanded-folder-live-relationship-evidence',flush=True)
    with tempfile.TemporaryDirectory() as nested_tmp:
        root=Path(nested_tmp)
        package=root/'package';package.mkdir()
        module=package/'entry.py';target=package/'helper.py'
        module.write_text('import helper\n',encoding='utf-8')
        target.write_text('def helper():pass\n',encoding='utf-8')
        assert w.browse_resource(root,activate=False)
        folder=next(n for n in w.resource_graph['nodes'] if n.get('resource_path')==str(package))
        assert w.toggle_resource_expansion(folder)
        w.toggle_resource_imports()
        app.processEvents()
        assert len(w.resource_graph['edges'])==1
        association=w.resource_graph['edges'][0]
        assert association['relation']=='imports' and association['certainty']=='local-file-candidate'
        assert w.resource_canvas.edge_items and w.resource_canvas.edge_items[0].toolTip()
        owner=SourceDocumentSession.open(module)
        w._source_documents[str(module)]=owner
        owner.update('def other():pass\n')
        w._refresh_resource_source_views(str(module));app.processEvents()
        assert not w.resource_graph['edges'], 'Resource relationships ignored authoritative unsaved text'
        owner.update('import helper\n')
        w._refresh_resource_source_views(str(module));app.processEvents()
        assert len(w.resource_graph['edges'])==1
        w._source_documents.pop(str(module))
        w.toggle_resource_imports()
    # Return to the binding example for subsequent existing smoke assertions.
    assert w._open_python_source_path(binding_sample,discard_confirmed=True), "Opening binding_sample failed"
    w._source_expanded=set(w.python_doc.scopes)-{'module'}
    w._load_source_editor()
    w.navigate_source(sum_key);app.processEvents()
    # The source view does not authorize arbitrary loop-carried edits.
    assert w.python_doc.path.read_bytes()==w.python_doc.raw
    # Exercising the source scope / expanded mode still uses one renderer.
    w.set_all_scopes(True)
    assert any(n.data['source_kind']=='loop' for n in w.source_canvas.items_by_id.values())
    w.navigate_source(sum_key)
    app.processEvents()
    # v2.24: The minimap is a sibling of the graphics view in a normal
    # QWidget layout. QGraphicsView's internally owned viewport must never
    # own an application overlay. Host containment is the invariant.
    overview=w.source_canvas.overview
    host=w.source_canvas._overview_host
    assert host.objectName()=='GraphViewportHost'
    assert overview.parentWidget() is host, 'Minimap must belong to graph host, not viewport'
    assert overview.parentWidget() is not w.source_canvas.viewport()
    layout=host.layout()
    assert layout is w.source_canvas._overview_layout
    assert layout.itemAt(0).widget() is w.source_canvas
    assert layout.itemAt(1).widget() is overview
    assert overview.isVisible() and overview.objectName()=='GraphOverview'
    assert overview.projection() is not None
    assert host.rect().contains(overview.geometry()), (
        'Minimap outside graph host',overview.geometry(),host.rect())
    # Exercise real parent-window geometry and active-tab transitions. Do not
    # manually resize the child viewport or move a layout-managed widget:
    # those operations violate Qt's layout ownership and aren't user actions.
    previous_size=w.size()
    w.resize(1170,820);app.processEvents()
    assert host.rect().contains(overview.geometry()), (
        'Minimap outside graph host after window shrink',overview.geometry(),host.rect())
    w.resize(1780,1090);app.processEvents()
    assert host.rect().contains(overview.geometry()), (
        'Minimap outside graph host after window expand',overview.geometry(),host.rect())
    w.resize(previous_size);app.processEvents()
    w.tabs.setCurrentWidget(w.resource_page);app.processEvents()
    w.tabs.setCurrentWidget(w.source_page);app.processEvents()
    assert overview.isVisible() and host.rect().contains(overview.geometry()), (
        'Minimap outside graph host after tab reactivation',overview.geometry(),host.rect())
    # Switching tabs does not alter the underlying graph identity or camera.
    assert w.tabs.currentWidget() is w.source_page
    before_nodes=set(w.source_canvas.items_by_id)
    before_edges=set(e.id for e in w.source_canvas.graph_contract.edges)
    rect=w.source_canvas._visible_root_rects()[0]
    target_x,target_y=rect[0]+rect[2]/2,rect[1]+rect[3]/2
    map_x,map_y=overview.projection().to_map(target_x,target_y)
    # A click-to-center target is independent from dragging a viewport box.
    overview._move_camera(QPointF(map_x,map_y))
    app.processEvents()
    center=w.source_canvas.mapToScene(w.source_canvas.viewport().rect().center())
    assert abs(center.x()-target_x)<60 and abs(center.y()-target_y)<60, (
        'Overview camera does not reach scene target',center,target_x,target_y)
    assert set(w.source_canvas.items_by_id)==before_nodes
    assert set(e.id for e in w.source_canvas.graph_contract.edges)==before_edges
    # The viewport's current center maps inside its rectangle: pressing
    # there must NOT jump to put the pointer at the rectangle's center.
    overview_projection=overview.projection()
    current=w.source_canvas.mapToScene(w.source_canvas.viewport().rect()).boundingRect()
    grab_scene=(current.x()+current.width()*.35,current.y()+current.height()*.4)
    grab_point=overview_projection.to_map(*grab_scene)
    center_before=w.source_canvas.mapToScene(w.source_canvas.viewport().rect().center())
    assert overview.begin_camera_drag(QPointF(*grab_point))
    app.processEvents()
    center_after=w.source_canvas.mapToScene(w.source_canvas.viewport().rect().center())
    assert abs(center_before.x()-center_after.x())<3 and abs(center_before.y()-center_after.y())<3, (
        'Viewport minimap drag jumped at grab time', center_before, center_after)
    overview._dragging=False
    overview._drag_offset=(0.0,0.0)
    w.source_canvas.set_overview_visible(False);app.processEvents()
    assert not overview.isVisible()
    w.source_canvas.set_overview_visible(True);app.processEvents()
    assert overview.isVisible()
    if os.environ.get('SMI_QT_OVERVIEW_SCREENSHOT'):
        assert w.grab().save(os.environ['SMI_QT_OVERVIEW_SCREENSHOT'],'PNG')
    if len(sys.argv)>1:
        out=sys.argv[1]
        if not w.grab().save(out,'PNG'):
            raise AssertionError(f'Unable to write screenshot: {out}')
        print(f'Screenshot saved: {out}')
    # Shared presentation state: verify a real canvas writes an independent
    # snapshot, and that a renderer rebuild doesn't clear its front selection.
    if w.resource_canvas.items_by_id:
        selected=next(iter(w.resource_canvas.items_by_id.values()))
        selected_id=selected.data['id']
        w.resource_canvas._activate_node_layer(selected)
        w.resource_canvas.rebuild();app.processEvents()
        assert w.resource_canvas.items_by_id[selected_id].zValue()==40
    document_path=str(w.python_doc.path)
    w._graph_cameras[(document_path,'host-test')]=(25.0,-4.0,1.2)
    w._graph_sizes[(document_path,'host-test')]=(440.0,240.0)
    w._save_presentation_state()
    loaded=w._presentation_store.load()
    assert any(c['path']==document_path and c['graph']=='host-test' for c in loaded['cameras'])
    assert any(size['path']==document_path and size['graph']=='host-test' for size in loaded['sizes'])
    # v2.20: Root camera state belongs to the view identity, not merely the
    # source filename. Focus and whole-file must not steal each other's zoom.
    assert w._refresh_whole_file(record_history=False)
    whole_key=w.source_canvas.graph_camera_key('@root-view')
    w.source_canvas._save_root_view()
    whole_camera=w._graph_cameras[whole_key]
    focus_key=next((key for key in w.python_doc.scopes if key!='module'),None)
    assert focus_key is not None
    assert w.navigate_source(focus_key,record_history=False)
    focused_camera_key=w.source_canvas.graph_camera_key('@root-view')
    assert w._view_sessions.get('source').route==Route(
        'source',document_path,focus_key,'focus'), 'Source session retained stale whole-file route'
    assert focused_camera_key!=whole_key, ('Focus inherited whole-file camera identity',whole_key)
    w.source_canvas._save_root_view()
    assert whole_camera==w._graph_cameras[whole_key], 'Focusing changed saved whole-file camera'
    assert w._refresh_whole_file(record_history=False)
    assert w._view_sessions.get('source').route==Route('source',document_path)
    assert w.source_canvas.graph_camera_key('@root-view')==whole_key
    # History-step navigation must also commit the destination before the
    # canvas rebuild, so its restore camera never belongs to the old route.
    assert w.navigate_source(focus_key,record_history=True)
    assert w._view_sessions.get('source').peek(-1)==Route('source',document_path)
    assert w._navigate_history('source',-1)
    assert w._view_sessions.get('source').route==Route('source',document_path)
    assert w.source_canvas.graph_camera_key('@root-view')==whole_key
    assert w._navigate_history('source',1)
    assert w._view_sessions.get('source').route.mode=='focus'
    assert w.source_canvas.graph_camera_key('@root-view')==focused_camera_key
    # v2.25: real source canvases and navigation sessions, not duplicate source
    # documents. Test switching the same file into two tabs and closing one.
    first_page=w.source_page
    first_canvas=w.source_canvas
    first_key=first_canvas.graph_camera_key('@root-view')
    first_doc=w.python_doc
    old_count=w.tabs.count()
    source_tab_ids_before=set(w._source_tabs)
    assert w.open_source_in_new_tab(first_doc.path,focus_key)
    app.processEvents()
    second_page=w.source_page
    second_canvas=w.source_canvas
    assert second_page is not first_page and second_canvas is not first_canvas
    assert w.tabs.count()==old_count+1
    assert w.python_doc is first_doc, 'Opening same file created a second source authority'
    assert w._active_source_session().route.scope==focus_key
    second_key=second_canvas.graph_camera_key('@root-view')
    assert second_key!=first_key, 'Two source tabs have the same camera identity'
    assert second_canvas.graph_contract is not None
    assert second_canvas.graph_contract.origin=='source'
    # v2.27: generic graph actions must follow the *selected* source tab,
    # not the original Python page retained by the main-window shell.
    assert w.current_canvas() is second_canvas
    assert w._graph_tab_for_page(second_page) is w._source_tabs[w._active_source_tab_id]
    w._frame_current_graph();app.processEvents()
    assert w.tabs.currentWidget() is second_page
    assert w.current_canvas() is second_canvas
    # A reload must publish one new source document to every tab displaying
    # that file; inactive projections are rebuilt only on activation.
    w.reload_python_source();app.processEvents()
    assert w.python_doc is not first_doc
    assert w._source_tabs['source'].document is w.python_doc
    assert w._source_tabs['source'].needs_rebuild
    first_doc=w.python_doc
    if os.environ.get('SMI_QT_TAB_SCREENSHOT'):
        assert w.grab().save(os.environ['SMI_QT_TAB_SCREENSHOT'],'PNG')
    w.tabs.setCurrentWidget(first_page);app.processEvents()
    assert w.source_canvas is first_canvas
    assert w.python_doc is first_doc
    assert w.source_canvas.graph_camera_key('@root-view')==first_key
    assert w._active_source_session().route.scope==focus_key
    w.tabs.setCurrentWidget(second_page);app.processEvents()
    assert w.source_canvas is second_canvas
    assert w.source_canvas.graph_camera_key('@root-view')==second_key
    index=w.tabs.indexOf(second_page)
    w._close_graph_tab(index);app.processEvents()
    assert w.tabs.count()==old_count
    assert set(w._source_tabs)==source_tab_ids_before, 'Closing a graph view leaked a tab session'
    assert w.source_canvas is first_canvas
    assert w.source_canvas.graph_camera_key('@root-view')==first_key
    assert not w.open_source_in_new_tab(first_doc.path,'missing-scope')
    assert w.tabs.count()==old_count, 'Invalid route published a ghost tab'
    print('QT_STAGE root-tab-same-provider-route-policy',flush=True)
    # v2.86: the primary source anchor and secondary source views must share
    # identical source-owner qualification and history semantics. This used
    # to reset root history through _open_python_source_path.
    with tempfile.TemporaryDirectory() as route_tmp:
        root=Path(route_tmp)
        first_target=root/'alpha.py';second_target=root/'beta.py'
        first_target.write_text('def alpha(): return 1\n')
        second_target.write_text('def beta(): return 2\n')
        root_page=w._source_tabs['source'].page
        w.tabs.setCurrentWidget(root_page);app.processEvents()
        root_session=w._view_sessions.get('source')
        previous_route=root_session.route
        assert w._open_navigation_route(Route('source',str(first_target)))
        assert root_session.route==Route('source',str(first_target))
        assert w._open_navigation_route(Route('source',str(second_target)))
        assert root_session.route==Route('source',str(second_target))
        assert root_session.peek(-1)==Route('source',str(first_target))
        assert w._navigate_history('source',-1)
        assert root_session.route==Route('source',str(first_target))
        assert w._navigate_history('source',1)
        assert root_session.route==Route('source',str(second_target))
        bad=root/'invalid.py';bad.write_text('def broken(:\n')
        history_snapshot=(root_session.route,root_session.peek(-1))
        assert not w._open_navigation_route(Route('source',str(bad)))
        assert (root_session.route,root_session.peek(-1))==history_snapshot
        print('QT_STAGE protected-root-source-refusal-atomicity',flush=True)
        # Opening source from the original resource root must prove the live
        # scope before switching the selected Qt tab or active source aliases.
        resource_root_page=w._resource_tabs['resource'].page
        w.tabs.setCurrentWidget(resource_root_page);app.processEvents()
        source_alias_before=w._active_source_tab_id
        resource_history_before=w._view_sessions.get('resource').route
        absent_scope=Route('source',str(second_target),'missing-scope','focus')
        assert not w._open_navigation_route(absent_scope)
        assert w.tabs.currentWidget() is resource_root_page
        assert w._active_source_tab_id==source_alias_before
        assert (root_session.route,root_session.peek(-1))==history_snapshot
        assert w._view_sessions.get('resource').route==resource_history_before
        assert not w._open_navigation_route(Route('source',str(bad)))
        assert w.tabs.currentWidget() is resource_root_page
        assert (root_session.route,root_session.peek(-1))==history_snapshot
        assert w._open_navigation_route(Route('source',str(second_target)))
        assert w.tabs.currentWidget() is root_page
        assert (root_session.route,root_session.peek(-1))==history_snapshot
        assert w._open_navigation_route(previous_route)
        assert root_session.route==previous_route
        assert w.tabs.currentWidget() is root_page
    print('QT_STAGE resource-visible-child-path-evidence',flush=True)
    with tempfile.TemporaryDirectory() as child_tmp:
        root=Path(child_tmp);asset_dir=root/'assets';asset_dir.mkdir()
        (root/'main.py').write_text("import helper\nopen('assets/icon.png')\n")
        (root/'helper.py').write_text('def value(): return 1\n')
        (asset_dir/'icon.png').write_bytes(b'png')
        assert w.open_resource_in_new_tab(root)
        w.resource_expanded.add(str(asset_dir))
        w.resource_show_imports=True
        assert w.browse_resource(root,activate=False)
        evidence=[e for e in w.resource_graph['edges'] if e['relation']=='reference']
        assert len(evidence)==1 and evidence[0]['certainty']=='literal-path-candidate'
        assert w.resource_graph['associations_enabled']
        print('QT_STAGE resource-relationship-layer-and-tab-isolation',flush=True)
        assert {edge['relation'] for edge in w.resource_graph['edges']}=={'imports','reference'}
        assert w.set_resource_relationship_layer('references',False)
        assert {edge['relation'] for edge in w.resource_graph['edges']}=={'imports'}
        assert w.set_resource_relationship_layer('imports',False)
        assert w.resource_graph['edges']==[]
        assert w.set_resource_relationship_layer('imports',True)
        assert w.set_resource_relationship_layer('references',True)
        assert {edge['relation'] for edge in w.resource_graph['edges']}=={'imports','reference'}
        assert w.resource_relationship_layers=={'imports','references'}
        assert w._resource_tabs['resource'].relationship_layers=={'imports','references'}
        print('QT_STAGE resource-relationship-inspector-and-actions',flush=True)
        selected_canvas=w.resource_canvas
        relation_id=evidence[0]['id']
        assert w.show_resource_relationship(selected_canvas,relation_id)
        inspect_text=[item.widget().text() for i in range(w.inspector_layout.count())
                      if (item:=w.inspector_layout.itemAt(i)) is not None
                      and isinstance(item.widget(),QLabel)]
        assert any('literal-path-candidate' in text for text in inspect_text)
        assert any('icon.png' in text for text in inspect_text)
        assert any('runtime dependency' in text for text in inspect_text)
        assert not w.show_resource_relationship(selected_canvas,'deleted-edge')
        wire=next(item for item in selected_canvas.edge_items if item.data(0)==relation_id)
        assert wire.flags() & wire.GraphicsItemFlag.ItemIsSelectable
        wire.setSelected(True)
        app.processEvents()
        assert any('FILE RELATIONSHIP' in widget.text()
                   for i in range(w.inspector_layout.count())
                   if (widget:=w.inspector_layout.itemAt(i).widget()) is not None
                   and isinstance(widget,QLabel))
        # Reproduce the v2.86 crash: this tab's validated relation existed,
        # then another tab replaced the global resource alias before a queued
        # card resize repainted its edge list. An inactive canvas must paint
        # its own render revision, not the newly selected directory's edges.
        print('QT_STAGE resource-tab-render-revision-isolation',flush=True)
        evidence_view=w._resource_tabs[w._active_resource_tab_id]
        evidence_canvas=evidence_view.canvas
        evidence_id=evidence[0]['id']
        assert evidence_canvas.graph_contract is not None
        assert evidence_id in {e.id for e in evidence_canvas.graph_contract.edges}
        card=next(item for item in evidence_canvas.items_by_id.values()
                  if item.data.get('title')=='main.py')
        card.schedule_resize()
        primary_resource=w._resource_tabs['resource']
        w.tabs.setCurrentWidget(primary_resource.page)
        app.processEvents()
        assert evidence_canvas is not w.resource_canvas
        assert not w.show_resource_relationship(evidence_canvas,evidence_id), (
            'Inactive canvas must refuse relationship inspection without changing tabs')
        # Force both direct and deferred edge refreshes on the inactive tab.
        evidence_canvas.update_edges()
        app.processEvents()
        assert evidence_id in {item.data(0) for item in evidence_canvas.edge_items}, (
            'Inactive resource tab lost its validated relationship to a different active graph')
        w.tabs.setCurrentWidget(evidence_view.page)
        app.processEvents()
        assert evidence_canvas is w.resource_canvas
        assert evidence_id in {item.data(0) for item in evidence_canvas.edge_items}
        assert w.show_resource_relationship(evidence_canvas,evidence_id)
        # Endpoint actions reuse existing history/tab routing, never the
        # window's stale raw-edge aliases or a second file editor.
        assert w.open_resource_relationship_endpoint(evidence_canvas,evidence_id,'target')
        assert w.resource_path==asset_dir
        assert w._navigate_history('resource',-1)
        assert w.resource_path==root
        w._close_graph_tab(w.tabs.currentIndex());app.processEvents()
    # v2.90: evidence jumps are revision-qualified source positions, not
    # file-open shortcuts or guesses from a stale renderer. Use a separate
    # secondary tab so this does not mutate root compatibility fixtures.
    print('QT_STAGE resource-evidence-line-and-file-framing',flush=True)
    with tempfile.TemporaryDirectory() as navigation_tmp:
        root=Path(navigation_tmp)
        (root/'assets').mkdir()
        source=root/'main.py'
        source.write_text('import helper\nopen("assets/icon.png")\n',encoding='utf-8')
        (root/'helper.py').write_text('def helper(): return 1\n',encoding='utf-8')
        asset=root/'assets'/'icon.png';asset.write_bytes(b'png')
        assert w.open_resource_in_new_tab(root)
        w.resource_expanded.add(str(asset.parent))
        w.resource_show_imports=True
        assert w.browse_resource(root,activate=False)
        resource_canvas=w.resource_canvas
        edge=next(e for e in resource_canvas.graph_contract.edges if e.relation=='reference')
        assert w.show_resource_relationship(resource_canvas,edge.id)
        button=w.findChild(QPushButton,'ResourceEvidenceLine0')
        assert button is not None and button.isEnabled()
        # Full endpoint action must frame/select the *target file*, not
        # merely open its parent folder.
        assert w.open_resource_relationship_endpoint(resource_canvas,edge.id,'target')
        assert w.resource_path==asset.parent
        assert any(node.isSelected() and node.data.get('resource_path')==str(asset)
                   for node in w.resource_canvas.items_by_id.values())
        assert w._navigate_history('resource',-1)
        assert w.resource_path==root
        # Revisiting the selected folder refreshes its exact edge revision.
        w.resource_expanded.add(str(asset.parent))
        w.resource_show_imports=True
        assert w.browse_resource(root,activate=False)
        resource_canvas=w.resource_canvas
        edge=next(e for e in resource_canvas.graph_contract.edges if e.relation=='reference')
        jumped=w.open_resource_relationship_evidence(resource_canvas,edge.id,0)
        if not jumped:
            selected=w._graph_tab_for_page(w.tabs.currentWidget())
            active=w._active_source_document()
            print('QT_DIAG resource evidence refusal',
                  'message=',w.statusBar().currentMessage(),
                  'selected=',type(selected).__name__ if selected else None,
                  'source_id=',w._active_source_tab_id,
                  'owner=',str(active.path) if active else None,
                  'loaded=',w._loaded_editor_identity,
                  'expected=',str(source),
                  'history=',w._view_sessions.get(selected.session_id).route if selected else None,
                  flush=True)
        assert jumped
        owner=w._active_source_document()
        assert owner is not None and owner.path==source
        assert w._loaded_editor_identity==(str(source),owner.revision)
        assert w.source_editor.textCursor().blockNumber()==1
        assert 'Relationship evidence:' in w.source_editor_note.text()
        assert w._navigate_history('source',-1)
        assert w.resource_path==root
        # Stale edge remains on this canvas until an explicit projection
        # refresh. The preflight must refuse it without changing history.
        w.resource_expanded.add(str(asset.parent))
        w.resource_show_imports=True
        assert w.browse_resource(root,activate=False)
        resource_canvas=w.resource_canvas
        edge=next(e for e in resource_canvas.graph_contract.edges if e.relation=='reference')
        selected=w.tabs.currentWidget()
        old_route=w._view_sessions.get(w._active_resource_tab_id).route
        owner.update('import helper\nopen("changed.png")\n')
        assert not w.open_resource_relationship_evidence(resource_canvas,edge.id,0)
        assert w.tabs.currentWidget() is selected
        assert w._view_sessions.get(w._active_resource_tab_id).route==old_route
        owner.update('import helper\nopen("assets/icon.png")\n')
        assert w.open_resource_relationship_evidence(resource_canvas,edge.id,0)
        assert w.source_editor.textCursor().blockNumber()==1
        # Restore a clean owner before automated shutdown.
        assert owner.text==source.read_text(encoding='utf-8')
        w._close_graph_tab(w.tabs.currentIndex());app.processEvents()
    # v2.91: one-hop relationship neighborhood is per-tab presentation state.
    # Exercise direction, overlay toggle, tab switching and revision isolation.
    print('QT_STAGE resource-focused-file-neighborhood-and-tab-isolation',flush=True)
    with tempfile.TemporaryDirectory() as focus_tmp:
        root=Path(focus_tmp)
        source=root/'main.py';helper=root/'helper.py';other=root/'other.py'
        source.write_text('import helper\nopen("icon.png")\n',encoding='utf-8')
        helper.write_text('import other\n',encoding='utf-8')
        other.write_text('VALUE=1\n',encoding='utf-8')
        (root/'icon.png').write_bytes(b'PNG')
        assert w.open_resource_in_new_tab(root)
        focused_view=w._resource_tabs[w._active_resource_tab_id]
        focused_canvas=focused_view.canvas
        w.resource_show_imports=True
        assert w.browse_resource(root,activate=False)
        assert len(w.resource_graph['edges'])==3
        print('QT_STAGE resource-revisioned-relationship-explorer',flush=True)
        assert w.explore_resource_relationships(focused_canvas)
        query=w.findChild(QLineEdit,'ResourceRelationshipSearch')
        assert query is not None
        count=w.findChild(QLabel,'ResourceRelationshipCount')
        assert '3 matching' in count.text()
        query.setText('icon.png');app.processEvents()
        assert '1 matching' in count.text()
        old_result=w.findChild(QPushButton,'ResourceRelationshipResult')
        query.setText('import other')
        # The textChanged callback is synchronous: check detachment before
        # any Qt event processing could destroy this Python wrapper.
        assert old_result is not None and old_result.parent() is None, \
            'Obsolete result was left in the QObject tree after refresh'
        app.processEvents()
        assert '1 matching' in count.text()
        # Search only the active result panel; Qt deleteLater() does not
        # synchronously destroy QObject descendants during a nested smoke run.
        result_panel=w.findChild(QWidget,'ResourceRelationshipResults')
        assert result_panel is not None
        matches=result_panel.findChildren(QPushButton,'ResourceRelationshipResult')
        assert len(matches)==1, ('Visible results out of sync',len(matches),count.text())
        matches[0].click();app.processEvents()
        assert any('FILE RELATIONSHIP' in widget.text()
                   for i in range(w.inspector_layout.count())
                   if (widget:=w.inspector_layout.itemAt(i).widget()) is not None
                   and isinstance(widget,QLabel))
        assert w.explore_resource_relationships(focused_canvas,focus=helper)
        app.processEvents()
        count=w.findChild(QLabel,'ResourceRelationshipCount')
        assert '2 matching' in count.text()
        directions=w.findChild(QComboBox,'ResourceRelationshipSearchDirection')
        hops=w.findChild(QComboBox,'ResourceRelationshipSearchHops')
        assert directions and hops
        directions.setCurrentIndex(2);app.processEvents()  # outgoing
        assert '1 matching' in count.text()
        directions.setCurrentIndex(0);app.processEvents()  # both directions
        hops.setCurrentIndex(1);app.processEvents()  # two visible hops
        assert '3 matching' in count.text()
        assert not w.explore_resource_relationships(focused_canvas,focus=root/'not-visible.py')
        helper_node=next(node for node in focused_canvas._render_graph['nodes']
                         if node.get('resource_path')==str(helper))
        import_edge=next(edge for edge in focused_canvas.graph_contract.edges
                         if edge.relation=='imports' and edge.target_node==helper_node['id'])
        assert w.show_resource_relationship(focused_canvas,import_edge.id)
        assert w.focus_resource_relationship_endpoint(focused_canvas,import_edge.id,'target')
        assert len(w.resource_graph['edges'])==2
        assert w.resource_relationship_focus==str(helper)
        assert w.set_resource_relationship_direction('incoming')
        assert len(w.resource_graph['edges'])==1
        assert w.set_resource_relationship_direction('outgoing')
        assert len(w.resource_graph['edges'])==1
        assert w.set_resource_relationship_direction('both')
        assert len(w.resource_graph['edges'])==2
        # Visibility toggles do not reset the focus or create a new owner.
        w.toggle_resource_imports()
        assert not w.resource_graph['edges']
        assert w.resource_relationship_focus==str(helper)
        w.toggle_resource_imports()
        assert len(w.resource_graph['edges'])==2
        assert w.open_resource_in_new_tab(root)
        other_view=w._resource_tabs[w._active_resource_tab_id]
        assert other_view.relationship_focus is None
        assert not w.resource_show_imports
        w.tabs.setCurrentWidget(focused_view.page)
        app.processEvents()
        assert w.resource_relationship_focus==str(helper)
        assert w.resource_relationship_direction=='both'
        assert {edge.id for edge in focused_canvas.graph_contract.edges if edge.relation=='imports'}
        # Existing validated descriptor remains with the inactive canvas;
        # another tab's projection may not replace it in a delayed refresh.
        focused_canvas.update_edges();app.processEvents()
        assert len(w.resource_graph['edges'])==2
        assert w.set_resource_relationship_focus(None)
        assert len(w.resource_graph['edges'])==3
        card=next(card for card in focused_canvas.items_by_id.values()
                  if card.data.get('resource_path')==str(source))
        focused_canvas.graph_scene.clearSelection()
        card.setSelected(True)
        assert w.focus_selected_resource_relationships()
        assert w.resource_relationship_focus==str(source)
        assert len(w.resource_graph['edges'])==2
        # Close the exact fixture-owned pages, not the currently selected tab:
        # Qt may select the root after closing one secondary page. The original
        # smoke accidentally deleted that root and broke all later fixtures.
        for owned_page in (focused_view.page,other_view.page):
            at=w.tabs.indexOf(owned_page)
            assert at>=0
            w._close_graph_tab(at);app.processEvents()
            assert w.tabs.indexOf(owned_page)==-1
        assert 'resource' in w._resource_tabs and 'source' in w._source_tabs
        # The root is protected even when another resource tab exists.
        assert w.open_resource_in_new_tab(root)
        root_anchor=w._resource_tabs['resource']
        root_index=w.tabs.indexOf(root_anchor.page)
        tabs_before=w.tabs.count()
        w._close_graph_tab(root_index);app.processEvents()
        assert w.tabs.count()==tabs_before
        assert w._resource_tabs['resource'] is root_anchor
        w._close_graph_tab(w.tabs.indexOf(w._resource_tabs[w._active_resource_tab_id].page))
        app.processEvents()
        assert 'resource' in w._resource_tabs
    # v2.26: filesystem tabs use the SAME navigation sessions, route resolver
    # and app-owned minimap host as source tabs. A directory tab cannot alter
    # the original directory view's path, graph projection, or camera slot.
    root_resource=w._resource_tabs['resource']
    root_resource_page=root_resource.page
    root_resource_canvas=root_resource.canvas
    original_resource_path=Path(root_resource.path)
    initial_root_camera=w._view_sessions.get('resource').camera_slot()
    resource_tab_count=w.tabs.count()
    directory=Path(__file__).resolve().parents[1]/'examples'
    print('QT_STAGE independent-resource-tab',flush=True)
    assert w.open_resource_in_new_tab(directory)
    app.processEvents()
    extra_resource=w._resource_tabs[w._active_resource_tab_id]
    extra_resource_id=extra_resource.session_id
    assert extra_resource_id!='resource'
    assert w.tabs.count()==resource_tab_count+1
    assert w.resource_canvas is extra_resource.canvas
    assert w.resource_canvas.graph_contract.origin=='resource'
    assert w._active_resource_session().route==Route('resource',str(directory))
    assert w.resource_canvas.graph_camera_key('@root-view')!=initial_root_camera
    assert extra_resource.canvas.overview.parentWidget() is extra_resource.canvas._overview_host
    assert extra_resource.canvas._overview_host.rect().contains(extra_resource.canvas.overview.geometry())
    assert w.browse_resource(directory.parent)
    app.processEvents()
    assert w._active_resource_session().peek(-1)==Route('resource',str(directory))
    assert w._navigate_history('resource',-1)
    assert w.resource_path==directory
    assert not w.browse_resource(directory/'not-a-real-folder')
    assert w.resource_path==directory
    assert w._active_resource_session().route==Route('resource',str(directory))
    w.tabs.setCurrentWidget(root_resource_page);app.processEvents()
    assert w.resource_canvas is root_resource_canvas
    assert w.resource_path==original_resource_path
    assert w._view_sessions.get('resource').camera_slot()==initial_root_camera
    assert w.current_canvas() is root_resource_canvas
    assert w._graph_tab_for_page(root_resource_page) is root_resource
    w.tabs.setCurrentWidget(extra_resource.page);app.processEvents()
    assert w.resource_path==directory
    assert w.current_canvas() is extra_resource.canvas
    assert w._graph_tab_for_page(extra_resource.page) is extra_resource
    print('QT_STAGE inactive-resource-view-close-preserves-root',flush=True)
    # Close an inactive secondary resource page. Selected root, view registry,
    # route/history and camera must stay with the actual Qt-selected root.
    w.tabs.setCurrentWidget(root_resource_page);app.processEvents()
    root_route_before=w._view_sessions.get('resource').route
    root_camera_before=w._view_sessions.get('resource').camera_slot()
    index=w.tabs.indexOf(extra_resource.page)
    assert index>=0
    w._close_graph_tab(index);app.processEvents()
    assert w.tabs.currentWidget() is root_resource_page
    assert w._resource_tabs['resource'] is root_resource
    assert w._view_sessions.get('resource').route==root_route_before
    assert w._view_sessions.get('resource').camera_slot()==root_camera_before
    assert w.tabs.count()==resource_tab_count
    assert w._view_sessions.get(extra_resource_id) is None
    assert len(w._resource_tabs)==1
    assert w.resource_canvas is root_resource_canvas
    print('QT_STAGE new-secondary-tab-staging-refusal',flush=True)
    # Both providers must build the real page and navigation chrome before
    # allocating a session, registering a view or publishing a source owner.
    from unittest.mock import patch
    with tempfile.TemporaryDirectory() as staged_dir:
        staged_root=Path(staged_dir)
        staged_source=staged_root/'staged.py'
        staged_source.write_text('def fresh():\n    return 2\n',encoding='utf-8')
        root_selection=w.tabs.currentWidget()
        original_tabs=w.tabs.count()
        resource_registry=dict(w._resource_tabs)
        source_registry=dict(w._source_tabs)
        documents=dict(w._source_documents)
        source_alias=w._active_source_tab_id
        resource_alias=w._active_resource_tab_id
        resource_next=w._next_resource_tab_number
        source_next=w._next_source_tab_number
        root_route=w._view_sessions.get('resource').route
        root_camera=w._view_sessions.get('resource').camera_slot()
        with patch.object(w,'_create_navigation_bar',
                          side_effect=RuntimeError('fixture: new resource toolbar failed')):
            assert not w.open_resource_in_new_tab(staged_root)
        with patch.object(w,'_create_navigation_bar',
                          side_effect=RuntimeError('fixture: new source toolbar failed')):
            assert not w.open_source_in_new_tab(staged_source)
        app.processEvents()
        assert w.tabs.currentWidget() is root_selection
        assert w.tabs.count()==original_tabs
        assert w._resource_tabs==resource_registry and w._source_tabs==source_registry
        assert w._source_documents==documents
        assert w._active_resource_tab_id==resource_alias
        assert w._active_source_tab_id==source_alias
        assert (w._next_resource_tab_number,w._next_source_tab_number)==(resource_next,source_next)
        assert w._view_sessions.get('resource').route==root_route
        assert w._view_sessions.get('resource').camera_slot()==root_camera
        assert all(w._view_sessions.get(sid) is not None for sid in resource_registry|source_registry)
        assert 'view unavailable' in w.statusBar().currentMessage()
        # A refused attempt must not poison subsequent real navigation.
        assert w.open_resource_in_new_tab(staged_root)
        opened_resource=w._resource_tabs[w._active_resource_tab_id]
        assert opened_resource.session_id=='resource:'+str(resource_next+1)
        w._close_graph_tab(w.tabs.indexOf(opened_resource.page));app.processEvents()
        assert w._view_sessions.get(opened_resource.session_id) is None
        persistent_fixture=Path(__file__).resolve().parents[1]/'examples/python-v11-bindings-and-returns.py'
        assert w.open_source_in_new_tab(persistent_fixture)
        opened_source=w._source_tabs[w._active_source_tab_id]
        assert opened_source.session_id=='source:'+str(source_next+1)
        assert str(persistent_fixture) in w._source_documents
        assert str(staged_source) not in w._source_documents
        w._close_graph_tab(w.tabs.indexOf(opened_source.page));app.processEvents()
        assert w._view_sessions.get(opened_source.session_id) is None
        w.tabs.setCurrentWidget(root_selection);app.processEvents()
        assert w._resource_tabs['resource'] is root_resource
    assert not w.open_resource_in_new_tab(directory/'not-a-real-folder')
    assert w.tabs.count()==resource_tab_count
    # A Python tab survives directory tab creation/removal unchanged.
    assert w._source_tabs['source'].document is first_doc
    print('QT_STAGE protected-root-source-tab-identity',flush=True)
    python_root=w._source_tabs['source']
    python_root_index=w.tabs.indexOf(python_root.page)
    root_source_route=w._view_sessions.get('source').route
    python_fixture=Path(__file__).resolve().parents[1]/'examples/python-v11-bindings-and-returns.py'
    assert w.open_source_in_new_tab(python_fixture)
    extra_source=w._source_tabs[w._active_source_tab_id]
    assert extra_source.session_id!='source'
    total_tabs=w.tabs.count()
    w._close_graph_tab(python_root_index);app.processEvents()
    assert w.tabs.count()==total_tabs and w._source_tabs['source'] is python_root
    assert w._view_sessions.get('source').route==root_source_route
    w._close_graph_tab(w.tabs.indexOf(extra_source.page));app.processEvents()
    assert w.tabs.indexOf(extra_source.page)==-1
    assert w._source_tabs['source'] is python_root
    print('QT_STAGE selected-graph-view-binding-idempotence',flush=True)
    # The Qt page is the selected authority. Rebinding the same tab through
    # the public adapter must be a no-op for histories, camera and document.
    root_resource_view=w._resource_tabs['resource']
    w.tabs.setCurrentWidget(root_resource_page);app.processEvents()
    resource_binding=(w._active_resource_tab_id,w.resource_page,w.resource_canvas)
    root_history=w._view_sessions.get('resource')
    root_route=root_history.route
    root_camera=root_history.camera_slot()
    assert w._bind_selected_graph_view(root_resource_view) is False
    assert (w._active_resource_tab_id,w.resource_page,w.resource_canvas)==resource_binding
    assert root_history.route==root_route and root_history.camera_slot()==root_camera
    w.tabs.setCurrentWidget(python_root.page);app.processEvents()
    source_binding=(w._active_source_tab_id,w.source_page,w.source_canvas)
    source_history=w._view_sessions.get('source')
    source_route=source_history.route
    source_camera=source_history.camera_slot()
    assert w._bind_selected_graph_view(python_root) is False
    assert (w._active_source_tab_id,w.source_page,w.source_canvas)==source_binding
    assert source_history.route==source_route and source_history.camera_slot()==source_camera
    assert w._source_tabs['source'].document is first_doc
    w.tabs.setCurrentWidget(root_resource_page);app.processEvents()
    print('QT_STAGE inactive-other-provider-close-preserves-foreground',flush=True)
    # Selecting a resource tab leaves the last source alias on the previously
    # active source view. Closing that *inactive* view must rebind the source
    # root without changing the actual selected resource page.
    fixture=Path(__file__).resolve().parents[1]/'examples/python-v11-bindings-and-returns.py'
    assert w.open_source_in_new_tab(fixture)
    inactive_source=w._source_tabs[w._active_source_tab_id]
    source_sid=inactive_source.session_id
    root_resource_route=w._view_sessions.get('resource').route
    root_resource_camera=w._view_sessions.get('resource').camera_slot()
    w.tabs.setCurrentWidget(root_resource_page);app.processEvents()
    assert w._active_source_tab_id==source_sid
    w._close_graph_tab(w.tabs.indexOf(inactive_source.page));app.processEvents()
    assert w.tabs.currentWidget() is root_resource_page
    assert source_sid not in w._source_tabs and w._view_sessions.get(source_sid) is None
    assert w._active_source_tab_id=='source'
    assert w._source_tabs['source'] is python_root
    assert w._view_sessions.get('resource').route==root_resource_route
    assert w._view_sessions.get('resource').camera_slot()==root_resource_camera
    # Repeat in the other direction: a last-active resource view may be
    # inactive while the user is looking at the protected Python root.
    assert w.open_resource_in_new_tab(directory)
    inactive_resource=w._resource_tabs[w._active_resource_tab_id]
    resource_sid=inactive_resource.session_id
    source_root_route=w._view_sessions.get('source').route
    source_root_camera=w._view_sessions.get('source').camera_slot()
    w.tabs.setCurrentWidget(python_root.page);app.processEvents()
    assert w._active_resource_tab_id==resource_sid
    w._close_graph_tab(w.tabs.indexOf(inactive_resource.page));app.processEvents()
    assert w.tabs.currentWidget() is python_root.page
    assert resource_sid not in w._resource_tabs and w._view_sessions.get(resource_sid) is None
    assert w._active_resource_tab_id=='resource'
    assert w._resource_tabs['resource'] is root_resource
    assert w._view_sessions.get('source').route==source_root_route
    assert w._view_sessions.get('source').camera_slot()==source_root_camera
    w.tabs.setCurrentWidget(root_resource_page);app.processEvents()
    print('QT_STAGE program-owned-navigation-refusal',flush=True)
    # A saved native ProgramWorkspace has no source/resource session_id.
    program_page=w.new_visual_program()
    assert program_page in w._program_tabs
    assert program_page.save(path=Path(directory)/'program-owned-route-v2134.smi-graph')
    assert w.tabs.indexOf(program_page)>=0
    w.tabs.setCurrentWidget(program_page);app.processEvents()
    before_tabs=w.tabs.count()
    before_owners=frozenset(w._source_documents)
    before_bindings=(w._active_source_tab_id,w._active_resource_tab_id)
    before_program=(program_page.document.revision,program_page.document.state)
    before_routes={kind:(w._view_sessions.get(kind).route,
                         w._view_sessions.get(kind).camera_slot(),
                         w._view_sessions.get(kind).peek(-1),
                         w._view_sessions.get(kind).peek(1))
                   for kind in ('source','resource')}
    assert not w._open_navigation_route(Route('resource',str(directory)))
    assert not w._open_navigation_route(Route('source',str(python_fixture)))
    app.processEvents()
    assert 'select a resource or Python graph tab' in w.statusBar().currentMessage()
    assert w.tabs.currentWidget() is program_page and w.tabs.count()==before_tabs
    assert frozenset(w._source_documents)==before_owners
    assert (w._active_source_tab_id,w._active_resource_tab_id)==before_bindings
    assert (program_page.document.revision,program_page.document.state)==before_program
    assert {kind:(w._view_sessions.get(kind).route,
                  w._view_sessions.get(kind).camera_slot(),
                  w._view_sessions.get(kind).peek(-1),
                  w._view_sessions.get(kind).peek(1))
            for kind in ('source','resource')}==before_routes
    # Explicit new-tab intent is independent of foreground provider.
    assert w._open_navigation_route(Route('resource',str(directory)),new_tab=True)
    created=w._resource_tabs[w._active_resource_tab_id]
    assert created.session_id!='resource' and w.tabs.currentWidget() is created.page
    w._close_graph_tab(w.tabs.indexOf(created.page));app.processEvents()
    assert w._view_sessions.get(created.session_id) is None
    w.tabs.setCurrentWidget(root_resource_page);app.processEvents()
    w._close_graph_tab(w.tabs.indexOf(program_page));app.processEvents()
    assert program_page not in w._program_tabs
    print('QT_STAGE uninitialized-source-root-bootstrap-refusal',flush=True)
    # A secondary resource tab can become a Python view while the protected
    # source root is still uninitialized. Refusing a subsequent root open must
    # not steal that secondary source's alias/editor/history.
    with tempfile.TemporaryDirectory() as root_tmp:
        root_dir=Path(root_tmp)
        secondary_file=root_dir/'secondary.py'
        root_file=root_dir/'root.py'
        secondary_file.write_text('def secondary():\n    return 2\n',encoding='utf-8')
        root_file.write_text('def root():\n    return 3\n',encoding='utf-8')
        other=NativeLab();other.show();app.processEvents()
        assert other._view_sessions.get('source') is None
        assert other.open_resource_in_new_tab(root_dir)
        assert other._open_navigation_route(Route('source',str(secondary_file)))
        secondary_sid=other._active_source_tab_id
        assert secondary_sid!='source'
        assert other._view_sessions.get('source') is None
        secondary_session=other._view_sessions.get(secondary_sid)
        assert secondary_session is not None
        secondary_route=secondary_session.route
        secondary_camera=secondary_session.camera_slot()
        secondary_owner=other._active_source_document()
        assert secondary_owner is not None
        resource_root_page=other._resource_tabs['resource'].page
        other.tabs.setCurrentWidget(resource_root_page);app.processEvents()
        before_editor=(other._loaded_editor_identity,other.source_editor.toPlainText())
        before_alias=(other._active_source_tab_id,other._active_resource_tab_id)
        before_owners=dict(other._source_documents)
        before_root_route=other._view_sessions.get('resource').route
        with patch('studio_native.gui.QMessageBox') as warnings:
            with patch.object(other,'_new_source_document',
                              side_effect=ValueError('fixture: first root open refused')):
                assert not other._open_navigation_route(Route('source',str(root_file)))
            warnings.warning.assert_called_once()
        app.processEvents()
        assert other.tabs.currentWidget() is resource_root_page
        assert (other._active_source_tab_id,other._active_resource_tab_id)==before_alias
        assert (other._loaded_editor_identity,other.source_editor.toPlainText())==before_editor
        assert other._source_documents==before_owners
        assert other._view_sessions.get('source') is None
        assert secondary_session.route==secondary_route
        assert secondary_session.camera_slot()==secondary_camera
        assert other._view_sessions.get('resource').route==before_root_route
        # A successful retry must initialize only the protected root without
        # resetting the independently navigable secondary source view.
        print('QT_STAGE uninitialized-source-root-focus-atomicity',flush=True)
        # Both missing and valid focus targets are checked against the same
        # live owner before publishing the first protected source root.
        missing_focus=Route('source',str(root_file),'missing-scope','focus')
        with patch('studio_native.gui.QMessageBox') as warnings:
            assert not other._open_navigation_route(missing_focus)
            warnings.warning.assert_called_once()
        app.processEvents()
        assert other.tabs.currentWidget() is resource_root_page
        assert (other._active_source_tab_id,other._active_resource_tab_id)==before_alias
        assert (other._loaded_editor_identity,other.source_editor.toPlainText())==before_editor
        assert other._source_documents==before_owners
        assert other._view_sessions.get('source') is None
        assert secondary_session.route==secondary_route
        assert secondary_session.camera_slot()==secondary_camera
        root_focus=next(key for key,scope in PythonDocument(root_file).scopes.items()
                        if scope.title=='root')
        valid_focus=Route('source',str(root_file),root_focus,'focus')
        assert other._open_navigation_route(valid_focus)
        assert other._active_source_tab_id=='source'
        assert other._view_sessions.get('source').route==valid_focus
        assert other._view_sessions.get('source').peek(-1)==Route('source',str(root_file))
        assert secondary_session.route==secondary_route
        assert other._source_documents[str(secondary_file)] is secondary_owner
        assert other.close()
        app.processEvents()
    w.activateWindow();app.processEvents()
    print('QT_STAGE source-root-resource-anchor-isolation',flush=True)
    # The last-active resource alias may be a secondary tab while Qt shows
    # the protected Python source root. Opening a directory must not navigate
    # that secondary tab or mutate it on a failed resource preflight.
    with tempfile.TemporaryDirectory() as isolated_resources:
        target_root=Path(isolated_resources)
        extra_path=target_root/'secondary'
        root_target=target_root/'root-destination'
        extra_path.mkdir();root_target.mkdir()
        assert w.open_resource_in_new_tab(extra_path)
        extra_view=w._resource_tabs[w._active_resource_tab_id]
        extra_sid=extra_view.session_id
        assert extra_sid!='resource'
        extra_history=w._view_sessions.get(extra_sid)
        extra_route=extra_history.route
        extra_camera=extra_history.camera_slot()
        resource_root=w._resource_tabs['resource']
        resource_root_session=w._view_sessions.get('resource')
        root_before=(resource_root_session.route,resource_root_session.camera_slot(),
                     resource_root_session.peek(-1),resource_root_session.peek(1))
        source_root=w._source_tabs['source'].page
        w.tabs.setCurrentWidget(source_root);app.processEvents()
        assert w._active_resource_tab_id==extra_sid
        aliases_before=(w._active_resource_tab_id,w.resource_path,
                        w.resource_canvas,w.resource_page)
        assert not w._open_navigation_route(Route('resource',str(target_root/'absent')))
        app.processEvents()
        assert w.tabs.currentWidget() is source_root
        assert (w._active_resource_tab_id,w.resource_path,
                w.resource_canvas,w.resource_page)==aliases_before
        assert (resource_root_session.route,resource_root_session.camera_slot(),
                resource_root_session.peek(-1),resource_root_session.peek(1))==root_before
        assert extra_history.route==extra_route and extra_history.camera_slot()==extra_camera
        assert w._open_navigation_route(Route('resource',str(root_target)))
        app.processEvents()
        assert w.tabs.currentWidget() is resource_root.page
        assert w._active_resource_tab_id=='resource'
        assert resource_root_session.route==Route('resource',str(root_target))
        assert extra_history.route==extra_route and extra_history.camera_slot()==extra_camera
        assert extra_view.path==extra_path
        w.tabs.setCurrentWidget(extra_view.page);app.processEvents()
        assert w.resource_path==extra_path
        assert w._active_resource_session() is extra_history
        w._close_graph_tab(w.tabs.indexOf(extra_view.page));app.processEvents()
        assert w._view_sessions.get(extra_sid) is None
        w.tabs.setCurrentWidget(resource_root.page);app.processEvents()
    print('QT_STAGE source-parent-uses-selected-graph-session',flush=True)
    # Up from a secondary Python whole-file view must return to that same
    # secondary tab's filesystem provider, preserving its history and root tabs.
    with tempfile.TemporaryDirectory() as parent_route_tmp:
        parent_dir=Path(parent_route_tmp)
        script=parent_dir/'owned.py'
        script.write_text('def value():\n    return 7\n',encoding='utf-8')
        root_source_route=w._view_sessions.get('source').route
        root_resource_route=w._view_sessions.get('resource').route
        assert w.open_resource_in_new_tab(parent_dir)
        sid=w._active_resource_tab_id
        session=w._view_sessions.get(sid)
        assert sid not in ('source','resource')
        assert w._open_navigation_route(Route('source',str(script)))
        assert session.route==Route('source',str(script))
        assert sid in w._source_tabs
        assert w.source_go_parent()
        app.processEvents()
        assert session.route==Route('resource',str(parent_dir))
        assert session.peek(-1)==Route('source',str(script))
        assert sid in w._resource_tabs and sid not in w._source_tabs
        assert w.tabs.currentWidget() is w._resource_tabs[sid].page
        assert w._view_sessions.get('resource').route==root_resource_route
        assert w._view_sessions.get('source').route==root_source_route
        assert w._navigate_history('resource',-1)
        assert session.route==Route('source',str(script))
        w._close_graph_tab(w.tabs.currentIndex());app.processEvents()
        assert w._view_sessions.get(sid) is None
        w.tabs.setCurrentWidget(w._resource_tabs['resource'].page);app.processEvents()
    # The same breadcrumb dispatcher opens both kinds through existing
    # provider/session paths. Invalid destinations must not create ghost tabs.
    breadcrumb_before=w.tabs.count()
    assert w._open_navigation_route(Route('resource',str(directory)),new_tab=True)
    app.processEvents()
    assert w.tabs.count()==breadcrumb_before+1
    assert w.current_canvas() is w.resource_canvas
    w._close_graph_tab(w.tabs.currentIndex());app.processEvents()
    assert w.tabs.count()==breadcrumb_before
    assert not w._open_navigation_route(Route('resource',str(directory/'absent')),new_tab=True)
    assert w.tabs.count()==breadcrumb_before
    # v2.28: an additional directory tab may navigate directly to a Python
    # source graph and back WITHOUT changing Qt tab identity or cloning a
    # source document. The original two root tabs remain compatibility anchors.
    fixture=Path(__file__).resolve().parents[1]/'examples/python-v11-bindings-and-returns.py'
    before=w.tabs.count()
    assert w.open_resource_in_new_tab(fixture.parent)
    app.processEvents()
    mixed_id=w._active_resource_tab_id
    mixed_session=w._view_sessions.get(mixed_id)
    mixed_resource_route=mixed_session.route
    print('QT_STAGE cross-provider-replacement-staging-refusal',flush=True)
    # A staging failure must not retire the old Qt page or mutate any view,
    # document, camera or navigation history authority. This would fail the
    # previous implementation, which deleted the old registry before building
    # the replacement toolbar.
    from unittest.mock import patch
    original_page=w.tabs.currentWidget()
    original_view=w._resource_tabs[mixed_id]
    original_history=(tuple(mixed_session.history._entries),
                      mixed_session.history._position)
    original_source_documents=dict(w._source_documents)
    original_aliases=(w._active_resource_tab_id,w.resource_page,w.resource_canvas)
    original_camera=mixed_session.camera_slot()
    with patch.object(w,'_create_navigation_bar',
                      side_effect=RuntimeError('fixture: toolbar construction failed')):
        assert not w._open_navigation_route(Route('source',str(fixture)))
    app.processEvents()
    assert w.tabs.currentWidget() is original_page
    assert w._resource_tabs[mixed_id] is original_view
    assert mixed_id not in w._source_tabs
    assert w._view_sessions.get(mixed_id) is mixed_session
    assert mixed_session.route==mixed_resource_route
    assert (tuple(mixed_session.history._entries),mixed_session.history._position)==original_history
    assert mixed_session.camera_slot()==original_camera
    assert (w._active_resource_tab_id,w.resource_page,w.resource_canvas)==original_aliases
    assert w._source_documents==original_source_documents
    assert w.tabs.indexOf(original_page)>=0
    assert 'replacement view unavailable' in w.statusBar().currentMessage()
    # The same route must succeed after a rejected attempt. Failed staging
    # must not poison subsequent source-owned navigation.
    assert w.open_resource_node({'resource_path':str(fixture),'resource_kind':'file'})
    app.processEvents()
    assert w.tabs.count()==before+1
    assert w._active_source_tab_id==mixed_id
    assert mixed_id in w._source_tabs and mixed_id not in w._resource_tabs
    assert w.current_canvas().graph_contract.origin=='source'
    assert mixed_session.route==Route('source',str(fixture))
    assert mixed_session.peek(-1)==mixed_resource_route
    assert w._navigate_history('source',-1)
    app.processEvents()
    assert w.tabs.count()==before+1
    assert mixed_id in w._resource_tabs and mixed_id not in w._source_tabs
    assert w.current_canvas().graph_contract.origin=='resource'
    assert mixed_session.route==mixed_resource_route
    assert w._navigate_history('resource',1)
    app.processEvents()
    assert mixed_id in w._source_tabs
    assert mixed_session.route==Route('source',str(fixture))
    assert w.current_canvas().graph_contract.origin=='source'
    assert w.current_canvas().overview.parentWidget() is w.current_canvas()._overview_host
    if os.environ.get('SMI_QT_UNIVERSAL_TAB_SCREENSHOT'):
        assert w.grab().save(os.environ['SMI_QT_UNIVERSAL_TAB_SCREENSHOT'],'PNG')
    assert not w._open_navigation_route(Route('resource',str(fixture.parent/'missing-dir')))
    assert mixed_session.route==Route('source',str(fixture))
    w._close_graph_tab(w.tabs.currentIndex())
    app.processEvents()
    assert w.tabs.count()==before
    assert w._view_sessions.get(mixed_id) is None
    assert 'resource' in w._resource_tabs and 'source' in w._source_tabs
    print('QT_STAGE universal-tab-live-source-and-scope',flush=True)
    # v2.82: a second resource tab must acquire exactly the existing source
    # owner on transition. Back/Forward must not read stale disk content or
    # create a second revision owner. Invalid drafts fail without moving history.
    with tempfile.TemporaryDirectory() as universal_tmp:
        root=Path(universal_tmp)
        script=root/'edited.py'
        original='def before():\n    return 1\n'
        revised='def unsaved():\n    return 2\n'
        script.write_text(original,encoding='utf-8')
        before=w.tabs.count()
        assert w.open_resource_in_new_tab(root)
        app.processEvents()
        universal_id=w._active_resource_tab_id
        universal=w._view_sessions.get(universal_id)
        root_route=universal.route
        assert w.open_resource_node({'resource_path':str(script),'resource_kind':'file'})
        app.processEvents()
        owner=w._source_documents.get(str(script))
        assert owner is not None and w._active_source_document() is owner
        assert w.source_editor.toPlainText()==original
        w.source_editor.setPlainText(revised)
        w._source_analysis_timer.stop();w._refresh_live_source()
        assert owner.dirty and owner.parsed is not None
        assert 'unsaved' in owner.parsed.source
        assert original==script.read_text(), 'Transition must not publish an unsaved draft'
        assert w._navigate_history('source',-1)
        app.processEvents()
        assert universal.route==root_route and universal_id in w._resource_tabs
        forward=universal.peek(1)
        assert forward==Route('source',str(script)), (forward,universal.route)
        assert w._navigate_history('resource',1), (
            'Universal resource Forward failed',
            w._active_resource_tab_id,
            w._graph_tab_for_page(w.tabs.currentWidget()).session_id,
            universal.route,universal.peek(1),
            w.statusBar().currentMessage())
        app.processEvents()
        assert universal_id in w._source_tabs
        assert w._active_source_document() is owner
        assert w.source_editor.toPlainText()==revised
        assert 'unsaved' in w.python_doc.source
        # A focused scope selected inside an embedded Python resource must
        # also retain its secondary tab instead of jumping to the root source.
        focus=next(k for k,v in owner.parsed.scopes.items() if v.title=='unsaved')
        assert w._navigate_history('source',-1)
        assert w.open_resource_node({'resource_source_path':str(script),
                                     'resource_source_scope':focus})
        app.processEvents()
        assert universal_id in w._source_tabs
        assert universal.route==Route('source',str(script),focus,'focus')
        assert w._active_source_document() is owner
        assert w._navigate_history('source',-1)
        owner.update('def invalid(:\n')
        assert not w._navigate_history('resource',1)
        assert universal.route==root_route
        assert universal_id in w._resource_tabs, 'Failed navigation replaced the valid tab'
        # A syntactically valid revision can still delete the historical
        # function. It MUST refuse Forward just like an invalid draft; only
        # restoring the same scope identity permits that history destination.
        owner.update(original)
        assert owner.graph_ready
        assert not w._navigate_history('resource',1)
        assert 'scope' in w.statusBar().currentMessage().lower()
        assert universal.route==root_route
        assert universal.peek(1)==Route('source',str(script),focus,'focus')
        owner.update(revised)
        assert w._navigate_history('resource',1)
        assert universal.route.mode=='focus'
        assert w._active_source_document() is owner
        assert w.source_editor.toPlainText()==revised
        w._close_graph_tab(w.tabs.currentIndex())
        app.processEvents()
        assert w.tabs.count()==before
        assert script.read_text()==original
    print('QT_STAGE universal-same-provider-and-mixed-history',flush=True)
    # Opening another .py file in the same secondary tab must keep its view
    # identity/history. An invalid target cannot alter that history or publish
    # a stale graph; unsaved edits remain with the single source owner.
    with tempfile.TemporaryDirectory() as nav_tmp:
        nav_root=Path(nav_tmp)
        first=nav_root/'first.py';second=nav_root/'second.py'
        first.write_text('def first():\n    return 1\n')
        second.write_text('def second():\n    return 2\n')
        before=w.tabs.count()
        assert w.open_source_in_new_tab(first)
        app.processEvents()
        sid=w._active_source_tab_id
        session=w._view_sessions.get(sid)
        first_route=session.route
        assert w._open_navigation_route(Route('source',str(second)))
        app.processEvents()
        assert w._active_source_tab_id==sid
        assert session.route==Route('source',str(second))
        w.source_editor.setPlainText('def second_unsaved():\n    return 3\n')
        w._source_analysis_timer.stop();w._refresh_live_source()
        second_owner=w._source_documents[str(second)]
        assert second_owner.dirty
        assert w._navigate_history('source',-1)
        app.processEvents()
        assert session.route==first_route
        assert w._navigate_history('source',1)
        app.processEvents()
        assert session.route==Route('source',str(second))
        assert w._active_source_document() is second_owner
        assert 'second_unsaved' in w.source_editor.toPlainText()
        second.write_text('def changed_on_disk():\n    return 77\n')
        # The draft is authoritative, even when the disk changes behind it.
        assert w._navigate_history('source',-1)
        assert w._navigate_history('source',1)
        assert w._active_source_document() is second_owner
        assert 'second_unsaved' in w.source_editor.toPlainText()
        assert 'changed_on_disk' in second.read_text()
        invalid=nav_root/'invalid.py'
        invalid.write_text('def invalid(:\n')
        before_route=session.route
        assert not w._open_navigation_route(Route('source',str(invalid)))
        assert session.route==before_route
        assert w._active_source_document() is second_owner
        # Every source tab remains a view; closing it leaves drafts intact.
        w._close_graph_tab(w.tabs.currentIndex())
        app.processEvents()
        assert w.tabs.count()==before
        assert w._source_documents[str(second)] is second_owner
    # v2.34: adapter-qualified create capabilities are available through the
    # existing Source Operations library, with no unapproved source writes.
    from .python_authoring import (eligible_targets, eligible_return_targets, eligible_pass_targets,
                                   propose_branch_early_return, propose_local_literal_return, propose_return_from_pass,
                                   propose_comparison_branch_return, propose_arithmetic_return_from_pass)
    from .operation_catalog import qualified_operations
    w.tabs.setCurrentWidget(w._source_tabs['source'].page);app.processEvents()
    assert w._open_python_source_path(fixture), 'Failed to load authoritative source for the qualified builders'
    app.processEvents()
    w._refresh_operation_library()
    # v2.40: the same Qt source workspace must tolerate an empty Python file.
    # The adapter's actual source-to-graph round trip stays in the headless
    # suite, while this checks QWidget state and live catalog gating.
    empty_program=Path(_test_config.name)/'qualified-new-program.py'
    empty_program.write_bytes(b'')
    assert w._open_python_source_path(empty_program)
    app.processEvents()
    w._refresh_operation_library()
    assert w.source_builder_buttons['python.create-function.v1'].isEnabled()
    assert not w.source_builder_buttons['python.create-main-entry.v1'].isEnabled()
    from .python_authoring import propose_create_function, propose_create_main_entry
    proposed=propose_create_function(w.python_doc,'start')
    assert b'def start():' in proposed.candidate
    assert empty_program.read_bytes()==b''
    assert w._open_python_source_path(fixture)
    app.processEvents()
    w._refresh_operation_library()
    # The Python adapter owns the qualified capability inventory. Never pin
    # this native smoke to yesterday's operation count: releases can add a
    # qualified operation without changing the existing UI/adapter contract.
    catalog={definition.id:definition for definition in qualified_operations('python')}
    assert catalog, 'Python adapter published an empty qualified operation catalog'
    assert set(w.source_builder_buttons)==set(catalog), (
        'Qt builder coverage disagrees with the Python adapter catalog',
        set(catalog)-set(w.source_builder_buttons),
        set(w.source_builder_buttons)-set(catalog))
    assert w.source_create_button.isEnabled(), 'Python qualified creation builder is missing'
    assert w.source_create_button.objectName()=='QualifiedPythonBranchCreator'
    assert w.source_builder_buttons['python.local-literal-return.v1'].isEnabled()
    assert w.source_builder_buttons['python.create-function.v1'].isEnabled()
    assert w.source_builder_buttons['python.add-optional-keyword-parameter.v1'].isEnabled()
    assert w.source_builder_buttons['python.comparison-branch-return.v1'].isEnabled()
    assert not w.source_builder_buttons['python.return-from-pass.v1'].isEnabled()
    names=[button.objectName() for button in w.source_builder_buttons.values()]
    assert all(name.startswith('QualifiedPython') for name in names), (
        'One or more qualified builders have missing/incorrect Qt object names', names)
    assert len(names)==len(set(names)), 'Qualified Qt builder object names must be unique'
    assert w.source_builder_buttons['python.assign-source-local.v1'].objectName()==(
        'QualifiedPythonValueAssignment'), 'New variable authoring has no identifiable Qt builder'
    # v2.49: all three function authoring actions must be reachable through
    # the real Qt catalog; the stored-call form must return a source proposal,
    # not mutate the file or fake a wire in the presentation scene.
    for op,object_name in (
        ('python.call-with-values.v1','QualifiedPythonStoredCallCreator'),
        ('python.rename-function.v1','QualifiedPythonFunctionRename'),
        ('python.rename-parameter.v1','QualifiedPythonInputRename')):
        assert w.source_builder_buttons[op].objectName()==object_name
    function_fixture=Path(_test_config.name)/'qualified-function-workflow.py'
    function_fixture.write_bytes(b'def helper(x):\n    return x + 1\n\ndef caller(value):\n    return value\n')
    assert w._open_python_source_path(function_fixture)
    app.processEvents()
    w._refresh_operation_library()
    assert all(w.source_builder_buttons[op].isEnabled() for op in (
        'python.call-with-values.v1','python.rename-function.v1','python.rename-parameter.v1'))
    from .python_authoring import eligible_composed_call_targets, eligible_parameter_renames, propose_rename_parameter
    call_scope,call_names,call_anchor,call_callees=next(
        (scope,names,anchor,callees) for scope,names,anchor,callees
        in eligible_composed_call_targets(w.python_doc)
        if w.python_doc.scopes[scope].title=='caller')
    # Test the visible QDialog, including a concrete bound parameter value.
    accepted=[]
    def accept_call_form(dialog):
        selection=dialog.findChild(QComboBox,'StoredCallInput0')
        index=selection.findData('value')
        assert index>=0, 'Function Call form has no qualified source input'
        selection.setCurrentIndex(index)
        dialog.findChild(QLineEdit,'StoredCallResult').setText('saved_call')
        accepted.append(dialog.isVisible())
        dialog.accept()
    print('QT_STAGE function-call-form',flush=True)
    call_proposal=exercise_modal(app,QDialog,'QualifiedStoredCallDialog',
        lambda:w._ask_stored_call(scope=call_scope,anchor=call_anchor,
                                  names=call_names,callees=call_callees),
        accept_call_form)
    assert accepted==[True] and call_proposal is not None
    assert b'saved_call = helper(value)' in call_proposal.candidate
    assert function_fixture.read_bytes()==w.python_doc.raw
    # My Python uses parser-owned scope identities for function and parameter
    # actions; no shadow symbol registry or direct file mutation.
    w.source_symbol_search.setText('')
    w._refresh_source_symbols()
    matched_parameters=[w.source_symbol_entries.item(i) for i in range(w.source_symbol_entries.count())
                        if getattr(w.source_symbol_entries.item(i).data(Qt.ItemDataRole.UserRole),'kind',None)=='parameter'
                        and getattr(w.source_symbol_entries.item(i).data(Qt.ItemDataRole.UserRole),'name',None)=='value']
    assert matched_parameters
    w.source_symbol_entries.setCurrentItem(matched_parameters[0]);app.processEvents()
    assert w.source_symbol_call.isEnabled() and w.source_symbol_rename.isEnabled()
    assert 'caller' in dict(eligible_parameter_renames(w.python_doc))
    rename_proposal=propose_rename_parameter(w.python_doc,'caller','value','number')
    assert b'def caller(number):' in rename_proposal.candidate
    assert function_fixture.read_bytes()==w.python_doc.raw
    assert w._open_python_source_path(fixture)
    app.processEvents()
    w._refresh_operation_library()
    scope,arguments,anchors=eligible_targets(w.python_doc)[0]
    before=w.python_doc.raw
    proposal=propose_branch_early_return(w.python_doc,scope,arguments[0],'None',anchors[0])
    assert b' is None:' in proposal.candidate and proposal.original==before
    comparison_proposal=propose_comparison_branch_return(w.python_doc,scope,arguments[0],
                                                          '<','0','None',anchors[0])
    assert b' < 0:' in comparison_proposal.candidate
    assert comparison_proposal.original==before
    comparison_pin=(f'py:{scope}|param|{arguments[0]}',
                    f'py:{scope}|param|{arguments[0]}:outputs:{arguments[0]}')
    comparison_actions=w.creation_candidates(w.current_canvas(),pin=comparison_pin)
    assert 'python.comparison-branch-return.v1' in {entry.id for entry in comparison_actions}
    assert w.python_doc.path.read_bytes()==before, 'Comparison proposal wrote source prematurely'
    local_scope,_,local_anchors=eligible_return_targets(w.python_doc)[0]
    local_proposal=propose_local_literal_return(w.python_doc,local_scope,'new_local','15',local_anchors[0])
    assert b'new_local = 15' in local_proposal.candidate
    assert w.python_doc.path.read_bytes()==before, 'Local proposal changed source without approval'
    placeholder=Path(_test_config.name)/'qualified-placeholder.py'
    placeholder.write_text('def pending(value):\n    pass\n',encoding='utf-8')
    placeholder_doc=PythonDocument(placeholder)
    placeholder_scope,pass_anchor=eligible_pass_targets(placeholder_doc)[0]
    pass_proposal=propose_return_from_pass(placeholder_doc,placeholder_scope,'None',pass_anchor)
    assert b'return None' in pass_proposal.candidate
    arithmetic_proposal=propose_arithmetic_return_from_pass(placeholder_doc,placeholder_scope,
                                                              'value','+','5',pass_anchor)
    assert b'return value + 5' in arithmetic_proposal.candidate
    assert placeholder.read_bytes()==placeholder_doc.raw
    # UI eligibility follows the selected session's resolved document path,
    # never a manually substituted or stale window-global document.
    original=w.python_doc
    w.python_doc=placeholder_doc
    w._refresh_operation_library()
    assert not any(button.isEnabled() for button in w.source_builder_buttons.values()), (
        'Unrelated source document incorrectly authorized source creation')
    w.python_doc=original
    w._refresh_operation_library()
    assert w._open_python_source_path(placeholder)
    app.processEvents()
    w._refresh_operation_library()
    assert w.library_modes.currentIndex()==1, 'Python graph should show Source operations by default'
    # v2.46: the same PythonDocument powers an on-demand symbol navigator,
    # not an independent symbol registry or a source mutation operation.
    assert w.source_library_pages.tabText(0)=='My Python'
    assert w.source_library_pages.tabText(1)=='Operations'
    assert w.source_symbol_search.objectName()=='SourceSymbolSearch'
    symbols=[w.source_symbol_entries.item(i) for i in range(w.source_symbol_entries.count())]
    assert {(x.data(Qt.ItemDataRole.UserRole).kind,x.data(Qt.ItemDataRole.UserRole).name)
            for x in symbols} >= {('function','pending'),('parameter','value')}
    w.source_symbol_search.setText('parameter value');app.processEvents()
    assert w.source_symbol_entries.count()==1
    before_navigation=placeholder.read_bytes()
    w._navigate_source_symbol(w.source_symbol_entries.item(0));app.processEvents()
    assert w.source_view_mode=='focus' and w.source_scope in w.python_doc.scopes
    assert w.source_editor.textCursor().blockNumber()==0
    assert placeholder.read_bytes()==before_navigation, 'Symbol navigation altered Python source'
    w._refresh_whole_file();w.source_symbol_search.clear();app.processEvents()
    symbol_capture=os.environ.get('SMI_QT_SYMBOL_BROWSER_SCREENSHOT')
    if symbol_capture:
        w.source_library_pages.setCurrentIndex(0)
        app.processEvents()
        assert w.library_dock.grab().save(symbol_capture,'PNG'), 'Symbol browser screenshot failed'
    assert w.source_builder_buttons['python.return-from-pass.v1'].isEnabled()
    assert w.source_builder_buttons['python.return-parameter-from-pass.v1'].isEnabled()
    assert w.source_builder_buttons['python.arithmetic-return-from-pass.v1'].isEnabled()
    assert w.source_builder_buttons['python.conditional-return-from-pass.v1'].isEnabled()
    assert w.source_builder_buttons['python.for-range-accumulate.v1'].isEnabled()
    assert w.source_builder_buttons['python.while-countdown.v1'].isEnabled()
    from .python_authoring import (eligible_flow_pass_targets,
        propose_conditional_returns_from_pass, propose_for_range_accumulate,
        propose_while_countdown)
    flow_key, _, flow_anchor=eligible_flow_pass_targets(w.python_doc)[0]
    for creator in (
        lambda:propose_conditional_returns_from_pass(w.python_doc,flow_key,
                  'value','<','0','-1','1',flow_anchor),
        lambda:propose_for_range_accumulate(w.python_doc,flow_key,
                  'value','index','total',flow_anchor),
        lambda:propose_while_countdown(w.python_doc,flow_key,
                  'value','counter','steps',flow_anchor),
    ):
        preview=creator()
        assert preview.candidate!=preview.original
        assert placeholder.read_bytes()==preview.original, 'Control-flow preview wrote source'
    assert w.source_operation_search.objectName()=='SourceLibrarySearch'
    w.source_operation_search.setText('return parameter');app.processEvents()
    assert not w.source_builder_buttons['python.return-parameter-from-pass.v1'].isHidden()
    assert w.source_builder_buttons['python.branch-early-return.v1'].isHidden()
    w.source_operation_search.clear();app.processEvents()
    scope_for_pin,anchor_for_pin=eligible_pass_targets(w.python_doc)[0]
    parameter_pin=(f'py:{scope_for_pin}|param|value',
                   f'py:{scope_for_pin}|param|value:outputs:value')
    import studio_native.authoring_actions as action_catalog
    ready=w.creation_candidates(w.current_canvas(),pin=parameter_pin)
    assert [action.id for action in ready]==[
        'python.return-parameter-from-pass.v1',
        'python.arithmetic-return-from-pass.v1',
        'python.conditional-return-from-pass.v1',
        'python.for-range-accumulate.v1',
        'python.while-countdown.v1']
    assert [a.id for a in action_catalog.search_actions(ready,'connect')]==[
        'python.return-parameter-from-pass.v1']
    assert not w.creation_candidates(w.current_canvas(),pin=('not-a-node','not-a-port'))
    menu_seen=[]
    def close_creation_search(dialog):
        from PyQt6.QtWidgets import QLineEdit, QListWidget
        search=dialog.findChild(QLineEdit,'CreationActionSearch')
        listing=dialog.findChild(QListWidget,'QualifiedCreationResults')
        assert search is not None and listing is not None
        assert listing.count()==5
        search.setText('not-matching');app.processEvents()
        assert listing.count()==0
        search.setText('connect');app.processEvents()
        assert listing.count()==1
        menu_seen.append(True)
        dialog.reject()
    print('QT_STAGE pin-creation-search',flush=True)
    exercise_modal(app,QDialog,'QualifiedGraphCreationSearch',
        lambda:w.open_creation_menu(w.current_canvas(),pin=parameter_pin),close_creation_search)
    assert menu_seen, 'Searchable pin-context creation menu was never shown'
    # v2.44: Tab opens that same adapter-owned creation chooser from a
    # focused Python canvas, not a new UI-local node registry.
    canvas=w.current_canvas()
    keyboard_menu=[]
    def dismiss_keyboard_search(dialog):
        from PyQt6.QtWidgets import QListWidget
        listing=dialog.findChild(QListWidget,'QualifiedCreationResults')
        if listing is not None and listing.count():keyboard_menu.append(True)
        dialog.reject()
    canvas.setFocus();app.processEvents()
    print('QT_STAGE keyboard-creation-search',flush=True)
    exercise_modal(app,QDialog,'QualifiedGraphCreationSearch',
        lambda:QTest.keyClick(canvas,Qt.Key.Key_Tab),dismiss_keyboard_search)
    assert keyboard_menu, 'Tab did not open the qualified Python action search'
    QTest.keyClick(canvas,Qt.Key.Key_Home)
    assert not w.source_builder_buttons['python.branch-early-return.v1'].isEnabled()
    assert not w.source_builder_buttons['python.local-literal-return.v1'].isEnabled()
    # v2.36: one adapter-owned catalog drives both call creation and pin
    # search. Qualify actual source docs rather than drawing mock call nodes.
    from .python_authoring import (eligible_call_pass_targets, eligible_call_return_targets,
        propose_call_return_from_pass, propose_call_before_return)
    call_file=Path(_test_config.name)/'qualified-call-creation.py'
    call_file.write_text('def combine(x, y):\n    return x + y\n\n'
                         'def pending(value):\n    pass\n\n'
                         'def complete(value):\n    return value\n',encoding='utf-8')
    assert w._open_python_source_path(call_file)
    app.processEvents()
    w._refresh_operation_library()
    assert w.source_builder_buttons['python.call-return-from-pass.v1'].isEnabled()
    assert w.source_builder_buttons['python.call-before-return.v1'].isEnabled()
    pass_scope,pass_anchor,_=next(x for x in eligible_call_pass_targets(w.python_doc)
                                  if 'pending' in x[0])
    ret_scope,return_anchor,_=next(x for x in eligible_call_return_targets(w.python_doc)
                                  if 'complete' in x[0])
    ready=w.creation_candidates(w.current_canvas(),pin=(
        f'py:{pass_scope}|param|value',f'py:{pass_scope}|param|value:outputs:value'))
    assert 'python.call-return-from-pass.v1' in {a.id for a in ready}
    before=w.python_doc.raw
    proposal=propose_call_return_from_pass(w.python_doc,pass_scope,'value','combine',('4',),pass_anchor)
    continuation=propose_call_before_return(w.python_doc,ret_scope,'value','combine',('4',),return_anchor)
    assert b'return combine(value, 4)' in proposal.candidate
    assert b'    combine(value, 4)\n    return value' in continuation.candidate
    assert call_file.read_bytes()==before, 'Catalog proposals wrote source prematurely'
    from .python_edit import apply_proposal
    apply_proposal(proposal)
    assert w._open_python_source_path(call_file)
    assert w.navigate_source(pass_scope)
    app.processEvents()
    calls=[n for n in w.source_graph['nodes'] if n['source_kind']=='call']
    assert len(calls)==1 and any(p['type']=='execution' for p in calls[0]['draft_ports']['outputs'])
    # v2.37: one preflight is used by the preview, drop and existing GUI
    # source-rewrite action; none may mutate Python before diff approval.
    from .source_connection import inspect_connection
    canvas=w.current_canvas()
    param=next(n for n in w.source_graph['nodes'] if n['source_kind']=='param')
    call=calls[0]
    arg1=next(p['id'] for p in call['draft_ports']['inputs']
              if p['id'].endswith(':arg1'))
    origin=(param['id'],param['draft_ports']['outputs'][0]['id'])
    existing=call_file.read_bytes()
    valid=inspect_connection(w.python_doc,*origin,call['id'],arg1)
    assert valid.allowed and b'combine(value, value)' in valid.proposal.candidate,valid.reason
    invalid=inspect_connection(w.python_doc,*origin,call['id'],
                               call['id']+':inputs:in')
    assert not invalid.allowed
    assert canvas._source_connection_check(*origin,call['id'],arg1).allowed
    assert not canvas._source_connection_check(*origin,call['id'],
                                                 call['id']+':inputs:in').allowed
    canvas.pending=(*origin,QPointF(0,0))
    canvas._start_source_compatibility_preview()
    assert canvas.connection_hints[(call['id'],arg1)].allowed
    assert not canvas.connection_hints[(call['id'],call['id']+':inputs:in')].allowed
    app.processEvents()
    if os.environ.get('SMI_QT_CONNECTION_PREVIEW_SCREENSHOT'):
        assert w.grab().save(os.environ['SMI_QT_CONNECTION_PREVIEW_SCREENSHOT'],'PNG')
    canvas.cancel_pending()
    assert not canvas.connection_hints and canvas.pending is None
    assert call_file.read_bytes()==existing, 'Preview must never change source'
    if os.environ.get('SMI_QT_CREATION_CALL_SCREENSHOT'):
        assert w.grab().save(os.environ['SMI_QT_CREATION_CALL_SCREENSHOT'],'PNG')
    # v2.38: a function-scope keyword argument is a real addressable input,
    # and constant-only operator outputs can be composed into call inputs.
    # All preview paths must remain read-only until the reviewed save.
    expression_file=Path(_test_config.name)/'expression-wiring.py'
    expression_file.write_text(
        'def caller(value):\n'
        '    constant = 2 + 3 * 4\n'
        '    return deliver(0, label="before", priority=1)\n'
        '\ndef deliver(number, *, label, priority):\n'
        '    return number\n',encoding='utf-8')
    assert w._open_python_source_path(expression_file)
    expression_scope=next(k for k,v in w.python_doc.scopes.items() if v.title=='caller')
    assert w.navigate_source(expression_scope)
    app.processEvents()
    graph=w.source_graph
    source=next(n for n in graph['nodes'] if n['source_kind']=='operation'
                and '2 + 3 * 4' in n['subtitle'])
    function_param=next(n for n in graph['nodes'] if n['source_kind']=='param')
    invocation=next(n for n in graph['nodes'] if n['source_kind']=='call')
    kw_label=next(p['id'] for p in invocation['draft_ports']['inputs']
                  if p['id'].endswith(':kw_label'))
    arg0=next(p['id'] for p in invocation['draft_ports']['inputs']
              if p['id'].endswith(':arg0'))
    from .source_connection import inspect_connection
    before=expression_file.read_bytes()
    constant_check=inspect_connection(w.python_doc,source['id'],
                                     source['id']+':outputs:result',invocation['id'],arg0)
    keyword_check=inspect_connection(w.python_doc,function_param['id'],
                                    function_param['draft_ports']['outputs'][0]['id'],
                                    invocation['id'],kw_label)
    assert constant_check.allowed and b'deliver((2 + 3 * 4)' in constant_check.proposal.candidate,constant_check.reason
    assert keyword_check.allowed and b'label=value' in keyword_check.proposal.candidate,keyword_check.reason
    canvas=w.current_canvas()
    assert canvas._source_connection_check(source['id'],
        source['id']+':outputs:result',invocation['id'],arg0).allowed
    canvas.pending=(function_param['id'],function_param['draft_ports']['outputs'][0]['id'],QPointF(0,0))
    canvas._start_source_compatibility_preview()
    assert canvas.connection_hints[(invocation['id'],kw_label)].allowed
    assert canvas.connection_hints[(invocation['id'],arg0)].allowed
    app.processEvents()
    if os.environ.get('SMI_QT_EXPRESSION_WIRING_SCREENSHOT'):
        assert w.grab().save(os.environ['SMI_QT_EXPRESSION_WIRING_SCREENSHOT'],'PNG')
    canvas.cancel_pending()
    assert not canvas.connection_hints and canvas.pending is None
    assert expression_file.read_bytes()==before, 'Connection preview changed source'
    # v2.39: an existing CALL result can be connected only through its
    # single stored local value; the preview must never duplicate execution.
    stored_file=Path(_test_config.name)/'stored-call-connection.py'
    stored_file.write_text(
        'def dispatch(value):\n'
        '    stored = calculate(value)\n'
        '    return deliver(0, label="before")\n'
        '\ndef calculate(x):\n'
        '    return x\n'
        '\ndef deliver(x, *, label):\n'
        '    return x\n',encoding='utf-8')
    assert w._open_python_source_path(stored_file)
    stored_scope=next(k for k,v in w.python_doc.scopes.items() if v.title=='dispatch')
    assert w.navigate_source(stored_scope)
    app.processEvents()
    graph=w.source_graph
    stored_source=next(n for n in graph['nodes'] if n['source_kind']=='call'
                       and n['subtitle'].startswith('calculate('))
    stored_target=next(n for n in graph['nodes'] if n['source_kind']=='call'
                       and n['subtitle'].startswith('deliver('))
    out_port=next(p['id'] for p in stored_source['draft_ports']['outputs']
                  if p['id'].endswith(':result'))
    in_port=next(p['id'] for p in stored_target['draft_ports']['inputs']
                 if p['id'].endswith(':arg0'))
    from .source_connection import inspect_connection
    stored_before=stored_file.read_bytes()
    stored_check=inspect_connection(w.python_doc,stored_source['id'],out_port,
                                    stored_target['id'],in_port)
    assert stored_check.allowed and stored_check.mode=='stored-reference',stored_check.reason
    assert stored_check.proposal.candidate.count(b'calculate(value)')==1
    assert b'deliver(stored, label=' in stored_check.proposal.candidate
    canvas=w.current_canvas()
    canvas.pending=(stored_source['id'],out_port,QPointF(0,0))
    canvas._start_source_compatibility_preview()
    assert canvas._source_connection_check(stored_source['id'],out_port,
                                           stored_target['id'],in_port).allowed
    assert canvas.connection_hints[(stored_target['id'],in_port)].allowed
    app.processEvents()
    if os.environ.get('SMI_QT_STORED_CALL_SCREENSHOT'):
        assert w.grab().save(os.environ['SMI_QT_STORED_CALL_SCREENSHOT'],'PNG')
    canvas.cancel_pending()
    assert stored_file.read_bytes()==stored_before, 'Stored Call preview changed source'
    # v2.42: adapter-backed composable values must be available from both
    # search and a *real source-projected* parameter/local value pin.
    from .authoring_contract import OperandReference, BinaryComposition
    from .python_authoring import eligible_composition_targets, propose_compose_binary_local
    composition_path=Path(_test_config.name)/'composed-value.py'
    composition_path.write_text('def compute(value):\n    stage = value + 2\n    return stage\n',encoding='utf-8')
    assert w._open_python_source_path(composition_path)
    composition_scope=next(k for k,v in w.python_doc.scopes.items() if v.title=='compute')
    assert w.navigate_source(composition_scope)
    app.processEvents()
    w._refresh_operation_library()
    assert w.source_builder_buttons['python.compose-binary-local.v1'].isEnabled()
    graph=w.source_graph
    local=next(n for n in graph['nodes'] if n['source_kind']=='assignment')
    output=next(p['id'] for p in local['draft_ports']['outputs']
                if p['id'].endswith(':outputs:value'))
    matches=[a for a in w.creation_candidates(w.current_canvas(),pin=(local['id'],output))
             if a.id=='python.compose-binary-local.v1']
    assert len(matches)==1 and matches[0].parameter=='stage'
    before=composition_path.read_bytes()
    scope,names,anchor=next(item for item in eligible_composition_targets(w.python_doc)
                             if item[0]==composition_scope)
    request=BinaryComposition(OperandReference('name','stage'),'*',
                              OperandReference('literal','3'),'total',True)
    preview=propose_compose_binary_local(w.python_doc,scope,request,anchor)
    assert b'total = stage * 3' in preview.candidate
    assert composition_path.read_bytes()==before
    if os.environ.get('SMI_QT_COMPOSED_DATAFLOW_SCREENSHOT'):
        assert w.grab().save(os.environ['SMI_QT_COMPOSED_DATAFLOW_SCREENSHOT'],'PNG')
    print('QT_STAGE variable-and-expression-forms',flush=True)
    # v2.47: My Python authoring is available only for actual, qualified
    # stored values; both authoring dialogs produce a proposal, not a write.
    from .python_authoring import eligible_value_assignment_targets
    w.source_library_pages.setCurrentIndex(0)
    w.source_symbol_search.setText('stage')
    app.processEvents()
    listing=w.source_symbol_entries
    stage_row=next(i for i in range(listing.count()) if
                   listing.item(i).data(Qt.ItemDataRole.UserRole).name=='stage')
    listing.setCurrentRow(stage_row);app.processEvents()
    assert w.source_symbol_use.isEnabled()
    selected=w._selected_qualified_symbol()
    assert selected and selected[0]==composition_scope and selected[1]=='stage'
    assert w.source_builder_buttons['python.assign-source-local.v1'].isEnabled()
    pin_matches=[a for a in w.creation_candidates(w.current_canvas(),pin=(local['id'],output))
                 if a.id=='python.assign-source-local.v1']
    assert len(pin_matches)==1 and pin_matches[0].parameter=='stage'
    from .authoring_contract import ValueAssignment
    from .python_authoring import propose_assign_source_value
    assignment_targets=eligible_value_assignment_targets(w.python_doc)
    assert any(row[0]==composition_scope for row in assignment_targets)
    def accept_variable_dialog(dialog):
        assert dialog is not None and dialog.objectName()=='QualifiedVariableAssignmentDialog'
        source=dialog.findChild(QComboBox,'VariableSource')
        assert source.currentData()=='stage' and not source.isEnabled()
        dialog.findChild(QLineEdit,'VariableName').setText('copy')
        dialog.findChild(QCheckBox,'VariableFeedReturn').setChecked(False)
        dialog.accept()
    proposal=exercise_modal(app,QDialog,'QualifiedVariableAssignmentDialog',
        lambda:w._ask_variable_assignment(composition_scope,selected[2],['value','stage'],'stage'),
        accept_variable_dialog)
    assert b'copy = stage' in proposal.candidate
    assert composition_path.read_bytes()==before
    def accept_composer_dialog(dialog):
        assert dialog is not None and dialog.objectName()=='QualifiedBinaryCompositionDialog'
        assert dialog.findChild(QComboBox,'ComposerLeft').currentText()=='stage'
        dialog.findChild(QComboBox,'ComposerOperator').setCurrentText('*')
        dialog.findChild(QLineEdit,'ComposerResult').setText('total')
        dialog.accept()
    composed=exercise_modal(app,QDialog,'QualifiedBinaryCompositionDialog',
        lambda:w._ask_binary_composition(composition_scope,anchor,['value','stage'],'stage'),
        accept_composer_dialog)
    assert b'total = stage * 2' in composed.candidate
    assert composition_path.read_bytes()==before, 'UI forms must never write source'
    if os.environ.get('SMI_QT_VARIABLE_AUTHORING_SCREENSHOT'):
        assert w.grab().save(os.environ['SMI_QT_VARIABLE_AUTHORING_SCREENSHOT'],'PNG')
    # Undo/redo through the same source transaction authority, not scene state.
    print('QT_STAGE source-input-replacement',flush=True)
    from .python_edit import replace_source_input_literal
    current=w.python_doc.scope_graph(composition_scope)
    return_node=next(n for n in current['nodes'] if n['source_kind']=='return')
    return_port=next(p['id'] for p in return_node['draft_ports']['inputs']
                     if p['id'].endswith(':value'))
    input_proposal=replace_source_input_literal(w.python_doc,composition_scope,
                                                return_node['id'],return_port,'None')
    assert b'return None' in input_proposal.candidate
    assert composition_path.read_bytes()==before
    print('QT_STAGE committed-source-history',flush=True)
    active_session=w._active_source_document()
    assert active_session is not None and active_session.saved_raw==before
    w._source_edit_history.apply(preview)
    w._publish_source_view_revision(active_session,before,preview.candidate)
    assert w._active_source_document() is active_session
    assert active_session.saved_raw==preview.candidate and not active_session.dirty
    assert b'total = stage * 3' in composition_path.read_bytes()
    assert w.undo_source_edit()
    assert composition_path.read_bytes()==before
    assert w.redo_source_edit()
    assert b'total = stage * 3' in composition_path.read_bytes()
    assert w.undo_source_edit()
    assert composition_path.read_bytes()==before
    w.dirty=False
    # Earlier native smoke versions hung here: temporary unsaved source
    # sessions legitimately trigger the production discard dialog, while the
    # unattended Qt fixture called close() and never answered it. Verify the
    # real safeguard and explicitly confirm, rather than altering closeEvent
    # or bypassing document dirty state.
    print('QT_STAGE integration-shutdown-discard-confirmation',flush=True)
    dirty=[str(doc.path) for doc in w._source_documents.values() if doc.dirty]
    assert dirty, 'Regression fixture no longer exercises unsaved shutdown confirmation'
    def confirm_test_discard(dialog):
        assert 'Unsaved Python documents' in dialog.windowTitle()
        assert 'Discard all and exit?' in dialog.text()
        yes=dialog.button(QMessageBox.StandardButton.Yes)
        assert yes is not None and yes.isEnabled()
        yes.click()
    def reject_test_discard(dialog):
        assert 'Unsaved Python documents' in dialog.windowTitle()
        no=dialog.button(QMessageBox.StandardButton.No)
        assert no is not None and no.isEnabled()
        no.click()
    assert not exercise_modal(app,QMessageBox,None,w.close,reject_test_discard,deadline_ms=5000)
    assert w.isVisible(), 'Rejected discard must preserve the window'
    assert any(doc.dirty for doc in w._source_documents.values()), 'Discard refusal lost an unsaved draft'
    assert exercise_modal(app,QMessageBox,None,w.close,confirm_test_discard,deadline_ms=5000)
    assert not w.isVisible(), 'Qualified close should retire the test window'
    app.processEvents()
    _test_config.cleanup()
    sys.excepthook=previous_excepthook
    assert not uncaught_callbacks, ('Uncaught Qt callback exception(s)',
                                    [(kind.__name__,str(value)) for kind,value in uncaught_callbacks])
    print('NATIVE_QT_SMOKE_PASS',flush=True)

if __name__=='__main__':main()
