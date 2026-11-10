"""Native PyQt6 Studio Node Lab. No HTML/WebView/browser/server is involved.

Prototype document compatible with the earlier browser Node Lab. Graph edges are
visual/type-validated only; they do not execute algorithms.
"""
from __future__ import annotations
import math
import json
import random
import sys
import hashlib
from pathlib import Path
from collections import OrderedDict
from dataclasses import dataclass, field
from PyQt6.QtCore import Qt, QPointF, QRectF, QSize, QTimer, QRect, QProcess, QEvent, QFileInfo
from PyQt6.QtGui import QColor, QBrush, QPainter, QPen, QPainterPath, QFont, QPainterPathStroker, QPolygonF, QAction, QIcon, QImage, QImageReader, QPixmap, QTextCursor, QFontMetricsF, QContextMenuEvent
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QGraphicsView, QGraphicsScene, QGraphicsObject,
    QGraphicsPathItem, QGraphicsRectItem, QGraphicsSimpleTextItem, QGraphicsProxyWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QFormLayout,
    QLabel, QPushButton, QLineEdit, QComboBox, QSlider, QCheckBox, QSpinBox,
    QDoubleSpinBox, QListWidget, QColorDialog, QFileDialog, QMessageBox,
    QInputDialog, QDockWidget, QScrollArea, QFrame, QToolButton, QTabWidget, QTabBar, QPlainTextEdit,
    QSizePolicy, QAbstractItemView, QDialog, QToolBar, QTextEdit, QFileIconProvider, QMenu,
)
from . import model as m
from .boundary_edit import parameter_source, terminal_return_target, BoundaryEditError
from .exit_routes import project_exit_routes, project_folded_exit_connections

APP_TITLE = 'Superior MI Studio · Visual Programming Lab 2.137'
from .semantic_contract import describe_graph, ContractError, canvas_graph_source, port_presentation_role, validated_port_payloads, validated_edge_payloads
from .assets import AssetIndex
from .external_icons import ExternalIconAtlas, default_icon_atlas_directory, icon_id_for_resource, icon_id_for_source
from .icon_styles import icon_hint
from .edge_presentation import edge_style, exit_edge_style
from .presentation_state import PresentationStore
from .graph_surface import GraphSurfaceState, resize_handle, resize_rectangle, frame_visible_bounds, overview_map, overview_drag_offset, overview_viewport_size, selected_pan_surface, marquee_selection, RESOURCE_COMPACT_WIDTH, RESOURCE_COMPACT_HEIGHT
from .python_graph import PythonDocument, SourceError
from .operation_catalog import observed_operations, qualified_operations
from .authoring_actions import available_actions, search_actions, qualified_composition_anchors
from .authoring_contract import OperandReference, BinaryComposition, ValueAssignment, CallComposition
from .python_authoring import (
    eligible_targets, eligible_return_targets, eligible_pass_targets, propose_branch_early_return,
    propose_local_literal_return, propose_return_from_pass,
    compatible_parameter_pin, eligible_parameter_returns, propose_return_parameter_from_pass,
    compatible_parameter_return_pin, propose_arithmetic_return_from_pass,
    propose_comparison_branch_return, qualified_callees,
    eligible_call_pass_targets, eligible_call_return_targets,
    propose_call_return_from_pass, propose_call_before_return,
    propose_create_function, propose_create_main_entry, propose_add_optional_parameter,
    eligible_entry_functions, eligible_signature_functions, eligible_flow_pass_targets,
    propose_conditional_returns_from_pass, propose_for_range_accumulate, propose_while_countdown,
    eligible_composition_targets, compatible_composition_pin, propose_compose_binary_local,
    eligible_value_assignment_targets, compatible_value_assignment_pin, propose_assign_source_value,
    eligible_composed_call_targets, compatible_composed_call_pin, propose_composed_call,
    eligible_rename_functions, propose_rename_function, eligible_parameter_renames, propose_rename_parameter,
)
from .resource_graph import ResourceError, MAX_PREVIEW_FILE_BYTES, inspect_resource_relationship, search_resource_relationships
from .source_associations import verified_evidence_line
from .python_edit import change_literal, add_constant_operand, rewire_source_operand, replace_source_input_literal, apply_proposal
from .source_connection import inspect_connection, ConnectionCheck
from .source_editor import span_to_utf16, prepare_source_change, SourceDocumentSession
from .draft_recovery import DraftRecoveryStore, _digest
from .program_graph import (ProgramGraph, ProgramGraphError, GraphConflict, view_graph,
                            NODE_TEMPLATES, template_ports, ASSIGN_OPERATIONS,
                            READ_OPERATIONS, LOCAL_OPERATIONS)
from .python_lowering import (preview_python, publish_python as publish_program_python,
                              import_generated_source_edit, LinkedPythonSource, MAX_PREVIEW_BYTES,
                              review_independent_source_function, import_independent_source_function,
                              review_independent_source_functions, import_independent_source_functions,
                              IndependentFunctionsReview)
from .python_edit import SourceEditHistory, create_source_exclusive
from .navigation import Route, GraphViewSessions, resource_crumbs, source_crumbs, shorten_crumb, visible_breadcrumbs
from .graph_routes import resolve_graph, resolve_source_session_route
from .docking import DockRegionController
from .python_highlight import PythonSyntaxHighlighter

BG='#061522'; PANEL='#0d2233'; SURFACE='#0b253a'; EDGE='#2d718d'; TEXT='#e4f3ff'; MUTED='#91b3c9'
NODE_W=390


def css():
    return '''
    QMainWindow,QWidget { background:#091b2a;color:#d8eefa;font-family:"DejaVu Sans","Segoe UI",Arial;font-size:12px; }
    QDockWidget { color:#9acee4;font-weight:700;border:1px solid #244b62; }
    QDockWidget::title { background:#0f2a41;padding:6px; }
    QLineEdit,QComboBox,QSpinBox,QDoubleSpinBox,QListWidget,QScrollArea { background:#091f31;border:1px solid #315f79;
         border-radius:5px;color:#e6f3ff;padding:4px;selection-background-color:#146487; }
    QPushButton,QToolButton { background:#18425a;border:1px solid #316a83;border-radius:4px;padding:4px 7px;color:#e0f3ff; }
    QPushButton:hover,QToolButton:hover { background:#245b75;border-color:#38ccef; }
    QPushButton:pressed,QToolButton:pressed { background:#0d354e; }
    QTabWidget::pane { border:1px solid #27617b;background:#071d2e; }
    QTabBar::tab { background:#102e45;color:#92bfd4;border:1px solid #205470;padding:5px 9px; }
    QTabBar::tab:selected { background:#1b4a63;color:#e3f6ff;border-bottom:2px solid #23ceef; }
    QScrollArea { border:0;background:transparent; }
    QMenuBar,QMenu { background:#0e2639;color:#dfedfb; }
    QMenu::item:selected { background:#236187; }
    QSlider::groove:horizontal { background:#40576a;height:5px;border-radius:2px; }
    QSlider::handle:horizontal { background:#1dd2ef;border-radius:7px;width:14px;margin:-5px 0; }
    QCheckBox::indicator:checked { background:#1dd2ef;border:1px solid #48e4ff; }
    '''


def qcolor(code, fallback='#25cbed'):
    value=QColor(code)
    return value if value.isValid() else QColor(fallback)


class PythonSourceTextEdit(QPlainTextEdit):
    """Keyboard routing for the source-session history, not an undo owner.

    QPlainTextEdit has built-in Undo/Redo handling. Attaching QShortcuts for
    those same keys can lose to the widget's shortcut override even with its
    own undo stack disabled. Intercept both the ShortcutOverride and actual
    KeyPress here, and send both commands to the revisioned document owner.
    All other text-editing keys retain Qt's normal behavior.
    """
    def __init__(self, *, undo, redo):
        super().__init__()
        self._session_undo=undo
        self._session_redo=redo

    @staticmethod
    def _draft_history_key(event):
        if event.key()!=Qt.Key.Key_Z:
            return None
        mods=event.modifiers()
        if mods==Qt.KeyboardModifier.ControlModifier:
            return 'undo'
        if mods==(Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier):
            return 'redo'
        return None

    def event(self,event):
        if (event.type()==QEvent.Type.ShortcutOverride and
                self._draft_history_key(event) is not None):
            # Prevent a parent menu, Qt's built-in editing action, or a
            # competing QShortcut from stealing this document command.
            event.accept()
            return True
        return super().event(event)

    def keyPressEvent(self,event):
        direction=self._draft_history_key(event)
        if direction is not None:
            if not event.isAutoRepeat():
                (self._session_undo if direction=='undo' else self._session_redo)()
            event.accept()
            return
        super().keyPressEvent(event)


class Waveform(QWidget):
    def __init__(self, accent):
        super().__init__()
        self.accent=accent
        self.setFixedHeight(93)
        self.setMinimumWidth(235)
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect=self.rect().adjusted(1,1,-1,-1)
        p.setPen(QPen(qcolor('#295e7a'),1));p.setBrush(qcolor('#081b2b'))
        p.drawRoundedRect(rect,6,6)
        rng=random.Random(77)
        mid=self.height()/2
        p.setPen(QPen(qcolor(self.accent),1.8))
        for i in range(110):
            x=9+(self.width()-18)*i/109
            envelope=(.1+.74*(.5+.5*math.sin(i*.16+2))**2)
            amp=envelope*rng.uniform(.12,1)*(self.height()*.43)
            p.drawLine(QPointF(x,mid-amp),QPointF(x,mid+amp))


class RowWidget(QWidget):
    def __init__(self, owner, row, *, writable=True):
        super().__init__()
        self.owner=owner;self.data=row
        layout=QHBoxLayout(self);layout.setContentsMargins(0,2,0,2);layout.setSpacing(7)
        self.setStyleSheet('background:transparent;')
        lbl=QLabel(str(row.get('label','')))
        lbl.setStyleSheet('color:#b5d4e5;')
        lbl.setFixedWidth(91)
        kind=row['kind']
        if kind=='preview':
            lbl.hide();layout.addWidget(Waveform(owner.data.get('accent','#26c7f5')),1)
        elif kind=='collection':
            lbl.hide()
            area=QWidget(); al=QVBoxLayout(area);al.setContentsMargins(0,0,0,0);al.setSpacing(4)
            self.items=QListWidget();self.items.setFixedHeight(128)
            al.addWidget(self.items)
            footer=QHBoxLayout();self.page_text=QLabel();prev=QPushButton('‹');nxt=QPushButton('›')
            prev.setFixedWidth(27);nxt.setFixedWidth(27)
            prev.clicked.connect(lambda:self._change_collection(-1))
            nxt.clicked.connect(lambda:self._change_collection(1))
            footer.addWidget(prev);footer.addWidget(self.page_text);footer.addWidget(nxt)
            al.addLayout(footer);layout.addWidget(area,1);self.update_collection()
        else:
            layout.addWidget(lbl)
            if kind=='slider':
                control=QSlider(Qt.Orientation.Horizontal);control.setRange(0,1000)
                low=float(row.get('min',0));high=float(row.get('max',1))
                control.setValue(round(1000*(float(row.get('value',low))-low)/(high-low or 1)))
                out=QLabel();out.setFixedWidth(60);out.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter)
                def update(pos):
                    row['value']=round(low+(high-low)*pos/1000,3)
                    out.setText(f'{row["value"]:.2f}{row.get("unit","")}');owner.mark_changed()
                control.valueChanged.connect(update)
                out.setText(f'{float(row.get("value",0)):.2f}{row.get("unit","")}')
                layout.addWidget(control,1);layout.addWidget(out)
            elif kind=='toggle':
                control=QCheckBox();control.setChecked(bool(row.get('value')))
                control.toggled.connect(lambda state:self._changed(bool(state)))
                layout.addWidget(control);layout.addStretch()
            elif kind=='dropdown':
                control=QComboBox();options=[str(x) for x in row.get('options',[])] or [str(row.get('value',''))]
                for opt in options:control.addItem(opt)
                ix=control.findText(str(row.get('value','')))
                if ix>=0:control.setCurrentIndex(ix)
                control.currentTextChanged.connect(self._changed)
                layout.addWidget(control,1)
            elif kind=='number':
                control=QDoubleSpinBox();control.setRange(float(row.get('min',0)),float(row.get('max',4096)))
                control.setDecimals(2);control.setValue(float(row.get('value',0)))
                control.valueChanged.connect(self._changed);layout.addWidget(control,1)
            elif kind=='text':
                control=QLineEdit(str(row.get('value','')))
                control.editingFinished.connect(lambda:self._changed(control.text()))
                layout.addWidget(control,1)
            elif kind=='color':
                control=QPushButton(str(row.get('value','#26c7f5')))
                self._style_color_button(control)
                def pick():
                    color=QColorDialog.getColor(qcolor(str(row.get('value','#26c7f5'))),self,'Choose color')
                    if color.isValid():self._changed(color.name());control.setText(color.name());self._style_color_button(control)
                control.clicked.connect(pick);layout.addWidget(control,1)
            elif kind=='label':
                val=QLabel(str(row.get('value','')));val.setWordWrap(True);layout.addWidget(val,1)
            elif kind=='button':
                control=QPushButton(str(row.get('value','Preview action')))
                control.clicked.connect(lambda:owner.window.report('Prototype button: no executable action attached'))
                layout.addWidget(control,1)
        if not writable:
            self.setEnabled(False)

    def _style_color_button(self, button):
        color=str(self.data.get('value','#26c7f5'))
        button.setStyleSheet('QPushButton { background:#17364b;border:1px solid '+color+';color:#ecf6ff; }')

    def _changed(self, value):
        self.data['value']=value
        key=self.data.get('setting_key')
        if key:self.owner.window.change_setting(key,value)
        else:self.owner.mark_changed()

    def _change_collection(self,direction):
        sec=self.owner.section_for_row(self.data['id'])
        count=max(1,min(50,sec.get('visible_rows',5)))
        pages=max(1,math.ceil(len(self.data.get('items',[]))/count))
        sec['page']=max(0,min(pages-1,sec.get('page',0)+direction))
        self.update_collection()
        self.owner.mark_changed()

    def update_collection(self):
        sec=self.owner.section_for_row(self.data['id'])
        count=max(1,min(50,int(sec.get('visible_rows',5))))
        items=self.data.get('items',[])
        pages=max(1,math.ceil(len(items)/count))
        page=max(0,min(pages-1,int(sec.get('page',0))))
        self.items.clear();self.items.addItems([str(x) for x in items[page*count:(page+1)*count]])
        self.page_text.setText(f'Page {page+1}/{pages} · {len(items)} items')


class SectionWidget(QFrame):
    def __init__(self, owner, section):
        super().__init__()
        self.owner=owner;self.data=section
        self.setObjectName('NodeSection')
        self.setStyleSheet('''QFrame#NodeSection { background:#0c2a40;border:1px solid #285b76;border-radius:8px; }
            QFrame#NodeSection QWidget { border:0; }''')
        self.layout_main=QVBoxLayout(self);self.layout_main.setContentsMargins(2,2,2,2);self.layout_main.setSpacing(0)
        self.toggle=QPushButton(self)
        self.toggle.setStyleSheet('QPushButton { background:#153c54;border:0;text-align:left;padding:8px;color:#c7e6fa;font-weight:700; }')
        self.toggle.clicked.connect(self.toggle_collapse)
        self.layout_main.addWidget(self.toggle)
        self.content=QWidget();self.body=QVBoxLayout(self.content)
        self.body.setContentsMargins(10,8,10,8);self.body.setSpacing(5)
        self.layout_main.addWidget(self.content)
        self.controls=[]
        self.populate()

    def toggle_collapse(self):
        self.data['collapsed']=not self.data.get('collapsed',False)
        self.populate();self.owner.mark_changed();self.owner.schedule_resize()

    def populate(self,filter_=''):
        while self.body.count():
            it=self.body.takeAt(0)
            if it.widget():it.widget().deleteLater()
        self.controls=[]
        rows,page,pages,total=m.paged_rows(self.data,filter_)
        self.toggle.setText(('▸ ' if self.data.get('collapsed') else '▾ ')+str(self.data['title'])+f'   ({total})')
        self.content.setVisible(not self.data.get('collapsed',False))
        if self.data.get('collapsed'):return
        for row in rows:
            w=RowWidget(self.owner,row,writable=not self.owner.source_view)
            self.controls.append(w);self.body.addWidget(w)
        if pages>1:
            nav=QWidget();line=QHBoxLayout(nav);line.setContentsMargins(0,0,0,0)
            prev=QPushButton('‹');nxt=QPushButton('›');text=QLabel(f'{page+1} / {pages}')
            for b in (prev,nxt):b.setFixedWidth(28)
            prev.clicked.connect(lambda:self.goto(page-1,filter_));nxt.clicked.connect(lambda:self.goto(page+1,filter_))
            line.addWidget(prev);line.addWidget(text);line.addWidget(nxt);self.body.addWidget(nav)
        self.body.addStretch(0)
        self.owner.schedule_resize()

    def goto(self,page,query):
        self.data['page']=page;self.populate(query);self.owner.mark_changed()


class NodeBody(QWidget):
    def __init__(self,owner):
        super().__init__()
        self.owner=owner
        self.setFixedWidth(NODE_W-38)
        self.setStyleSheet('background:transparent;')
        self.layout_main=QVBoxLayout(self)
        self.layout_main.setSpacing(9);self.layout_main.setContentsMargins(0,0,0,0)
        self.sections=[]
        self.rebuild()

    def rebuild(self):
        while self.layout_main.count():
            it=self.layout_main.takeAt(0)
            if it.widget():it.widget().deleteLater()
        self.sections=[]
        for section in self.owner.data.get('containers',[]):
            w=SectionWidget(self.owner,section);self.sections.append(w);self.layout_main.addWidget(w)
        if not self.sections:
            self.layout_main.addWidget(QLabel('No containers. Add one in Inspector.'))
        self.layout_main.addStretch(0)
        self.layout_main.invalidate()
        self.updateGeometry()
        self.owner.schedule_resize()

    def event(self, event):
        # Qt may settle a newly inserted/removed child layout one event-loop
        # turn later. Notify the owner *after* processing a LayoutRequest so
        # QGraphicsObject bounds and its background catch up automatically.
        result = super().event(event)
        if event.type() == QEvent.Type.LayoutRequest and getattr(self.owner, '_ready', False):
            self.owner.schedule_resize()
        return result

    def filter(self,query):
        for w in self.sections:w.populate(query)
        self.owner.schedule_resize()


class PortItem(QGraphicsObject):
    """One typed port with a text-sized, fully interactive contextual chip.

    Paint, hit-testing, and text elision all consult _label_geometry().
    The conservative boundingRect is constant so hover/Space toggling never
    invalidates Qt's scene index or clips a longer authored default value.
    """
    CHIP_FONT = QFont('DejaVu Sans', 9)
    CHIP_MAX_TEXT_WIDTH = 205
    CHIP_PADDING = 8
    CHIP_GAP = 15

    def __init__(self,node,port,direction):
        super().__init__(node)
        self.node=node;self.data=port;self.direction=direction
        self.setZValue(50)
        self.setAcceptHoverEvents(True)
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)
        if port.get('source_literal_span'):
            self.setToolTip('Source literal: double-click the inline value to propose an exact Python edit')
        elif port.get('source_expression_preview'):
            self.setToolTip('Python source argument: '+str(port['source_expression_preview'])+'\nEvaluation/name binding is not statically proven')
        elif port.get('unresolved_binding'):
            self.setToolTip('This name is source-backed but its current value is not statically proven')
        elif port.get('binding_mode')=='current_binding':
            self.setToolTip('Reference to the current variable binding, not a frozen value')
        if node.descriptor is not None:
            role=port_presentation_role(node.descriptor,port['id'])
            hints={
                'definition-result-interface':
                    'Function result interface · not a value produced by declaring this function; a call site supplies its runtime result',
                'definition-output':
                    'Definition-owned output · not a result from invoking this function',
                'definition-time-execution':
                    'Definition-time control (binding the name) · does not enter or execute the function body',
                'invocation-result':
                    'Call-site result · callable dispatch, effects and exceptions are not proven by a data wire',
            }
            if role in hints:self.setToolTip(hints[role])

    def boundingRect(self):
        # Maximum chip width + connector geometry on either side.
        reach=self.CHIP_MAX_TEXT_WIDTH+2*self.CHIP_PADDING+self.CHIP_GAP+6
        return QRectF(-reach,-17,2*reach,34)

    def active(self):
        # Source argument previews are part of understanding a call, not
        # decorative labels that disappear unless the node is selected.
        if (self.node.source_view and self.node.data.get('call_expression') and
                self.direction=='inputs' and self.data.get('source_expression_preview')):
            return True
        if (self.node.source_view and self.data.get('source_expression_preview') and
                self.node.data.get('semantic_role')=='control_operation'):
            return True
        return self.node.window.labels_visible(self.node)

    def _is_connected(self):
        # The canvas descriptor is the sole validated wiring projection for
        # source, resource, program and draft tabs. Inactive tabs must never
        # ask a global, currently-selected source document for their edges.
        contract=self.node.canvas.graph_contract
        if contract is None:return False
        nid=self.node.data['id'];pid=self.data['id']
        return any((edge.source_node==nid and edge.source_port==pid)
                   if self.direction=='outputs' else
                   (edge.target_node==nid and edge.target_port==pid)
                   for edge in contract.edges)

    def _label_geometry(self):
        """Return the identical text and pill rectangle for paint and hit test."""
        text=str(self.data.get('label',''))
        if self.direction=='inputs' and not self._is_connected():
            default=m.format_input_default(self.data)
            if default is not None:text+=' = '+default
            elif self.data.get('source_expression_preview'):
                text+=' ← '+str(self.data['source_expression_preview'])
        metrics=QFontMetricsF(self.CHIP_FONT)
        text=metrics.elidedText(text,Qt.TextElideMode.ElideRight,self.CHIP_MAX_TEXT_WIDTH)
        width=max(1.0,math.ceil(metrics.horizontalAdvance(text)))+2*self.CHIP_PADDING
        x=(-self.CHIP_GAP-width) if self.direction=='inputs' else self.CHIP_GAP
        return text,QRectF(x,-14,width,28)

    def shape(self):
        path=QPainterPath();path.addEllipse(QRectF(-11,-11,22,22))
        # The small in-shell default shown by a compact Python node is an
        # actual editing surface, not dead text painted behind a tiny dot.
        # One shared PortItem owns its visual geometry and interaction shape.
        if (self.direction=='inputs' and self.node.source_view and
                self.node.compact and self.data.get('source_literal_span') and
                not self._is_connected()):
            path.addRoundedRect(QRectF(11,-13,85,26),4,4)
        if self.active():
            _,rect=self._label_geometry()
            path.addRoundedRect(rect,6,6)
        return path

    def mouseDoubleClickEvent(self, event):
        if (self.direction=='inputs' and self.node.source_view and
                self.data.get('source_literal_span') and not self._is_connected()):
            self.node.window.visual_edit_literal(self.data['source_literal_span'])
            event.accept()
            return
        if self.direction=='inputs' and self.node.source_view:
            self.node.window.visual_replace_python_input(self.node.data['id'],self.data['id'])
            event.accept()
            return
        if (self.direction == 'inputs' and not self.node.source_view and
                not self.node.settings_view and not self.node.program_view):
            self.node.window.edit_input_default(self.node, self.data)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def paint(self,p,option,widget=None):
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        typ=self.data.get('type','object')
        tone=self.node.window.state['settings'].get('type_colors',{}).get(typ,m.TYPE_COLORS.get(typ,'#6bc5e0'))
        color=qcolor('#d4a16f') if self.data.get('unresolved_binding') else qcolor(tone)
        connected=self._is_connected()
        is_exec=(typ=='execution')
        p.setPen(QPen(qcolor('#f1f5fc') if is_exec else color,1.6 if is_exec else 2))
        p.setBrush(QBrush(qcolor('#edf5ff') if is_exec and connected else
                          qcolor('#152d40') if is_exec else
                          color if connected else qcolor('#082339')))
        if is_exec:
            p.drawPolygon(QPolygonF([QPointF(-6,-8),QPointF(7,0),QPointF(-6,8)]))
        else:p.drawEllipse(QRectF(-7,-7,14,14))
        # Transient qualified-source-connection preview; no draft mutation.
        key=(self.node.data['id'],self.data['id'])
        hint=self.node.canvas.connection_hints.get(key)
        if (self.direction=='inputs' and hint is not None and
                (hint.allowed or self.node.canvas._connection_hover==key)):
            p.setPen(QPen(qcolor('#6be0a3' if hint.allowed else '#d89365'),2.4))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QRectF(-11,-11,22,22))
        if self.active():
            text,rect=self._label_geometry()
            p.setPen(QPen(color,1.2));p.setBrush(QBrush(QColor(11,38,57,235)))
            p.drawRoundedRect(rect,7,7)
            p.setPen(qcolor('#e5f4ff'));p.setFont(self.CHIP_FONT)
            p.drawText(rect.adjusted(self.CHIP_PADDING,0,-self.CHIP_PADDING,0),
                       Qt.AlignmentFlag.AlignVCenter|Qt.AlignmentFlag.AlignLeft,text)


class BoundaryPortItem(QGraphicsObject):
    """Inner projection of the SAME external port, never a new source port.

    These are anchored to the child viewport, not to camera-scaled content.
    Cross-boundary edges may use this anchor when their other endpoint lives
    inside the composite. Hover reveals the already-authored port label.
    """
    def __init__(self,node,port,direction,surface):
        super().__init__(surface)
        self.node=node;self.data=port;self.direction=direction
        self.setZValue(45)
        self.setAcceptHoverEvents(True)
        # The inner mirror is a navigation/presentation anchor. Its semantic
        # port remains the external authored port; don't offer unsupported
        # source rewiring by interpreting the alias as a separate connector.
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.setToolTip((node.data.get('terminal_return_label','return')
                         if direction=='outputs' and port.get('label')=='return'
                         else str(port.get('label','')))+' · graph interface')

    def boundingRect(self):return QRectF(-12,-12,24,24)

    def paint(self,p,option,widget=None):
        t=self.data.get('type','object')
        color=qcolor('#eef5fc' if t=='execution' else
                     self.node.window.state['settings'].get('type_colors',{}).get(t,m.TYPE_COLORS.get(t,'#65c5e6')))
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(color,1.5));p.setBrush(QBrush(qcolor('#082235')))
        if t=='execution':
            p.drawPolygon(QPolygonF([QPointF(-5,-6),QPointF(6,0),QPointF(-5,6)]))
        else:p.drawEllipse(QRectF(-5,-5,10,10))


class ExitLaneItem(QGraphicsObject):
    """A normal-exit CONTROL facet of a composite interface, not an operation.

    An exit may carry two parallel facets: completion and an optional return
    value. Both refer to one ExitDescriptor, and never create an extra source
    port or executable statement. Individual return sites remain source-owned.
    This graphic is shared by all language adapters that declare a return exit.
    """
    def __init__(self, owner, exit_spec):
        super().__init__(owner)
        self.owner=owner
        self.exit_spec=exit_spec
        self.setZValue(55)
        self.setData(0,exit_spec.control_anchor_id)
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.setToolTip('Return completion inside this function · view-only exit, NOT an executable output of the definition or its call site')

    def boundingRect(self):
        return QRectF(-9,-10,19,20)

    def paint(self,p,option,widget=None):
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(qcolor('#edf6fc'),1.5))
        p.setBrush(QBrush(qcolor('#0b2639')))
        p.drawPolygon(QPolygonF([QPointF(-5,-6),QPointF(6,0),QPointF(-5,6)]))


class ReturnFacetItem(QGraphicsObject):
    """A visible RETURN site's terminal facet, not a synthetic source port.

    A source RETURN owns exactly one termination operation. Its control and
    optional value exits can be drawn at explicit right-edge anchors, while
    its source-backed EXECUTE and VALUE inputs remain on the left. Both facets
    are read-only projections of the same RETURN statement and exit contract.
    """
    def __init__(self,node,kind):
        super().__init__(node)
        self.kind=kind
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.setZValue(11)
        self.setToolTip('Return '+('completion flow' if kind=='control' else 'value')+
                        ' · exits the enclosing function')

    def boundingRect(self):
        return QRectF(-9,-9,18,18)

    def paint(self,p,option,widget=None):
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self.kind=='control':
            p.setPen(QPen(qcolor('#edf6fc'),1.5))
            p.setBrush(QBrush(qcolor('#0b2639')))
            p.drawPolygon(QPolygonF([QPointF(-5,-6),QPointF(6,0),QPointF(-5,6)]))
        else:
            p.setPen(QPen(qcolor('#e0b36e'),1.6))
            p.setBrush(QBrush(qcolor('#0b2639')))
            p.drawEllipse(QRectF(-5,-5,10,10))


class GraphContentItem(QGraphicsObject):
    """Coordinate root for nodes and edges owned by one graph surface.

    It is intentionally not a source operation and cannot be selected or
    independently moved; it only applies the owning surface's camera.
    """
    def __init__(self,surface):
        super().__init__(surface)
        self.surface=surface
        self.setZValue(0)
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)

    def boundingRect(self):
        return QRectF(0,0,self.surface.camera.content_width,
                      self.surface.camera.content_height)

    def paint(self,p,option,widget=None):
        pass


class GraphSurfaceItem(QGraphicsObject):
    """Recursive graph viewport used for both root and composite workspaces.

    Root navigation is delegated to the outer QGraphicsView so it can occupy
    the entire window. Embedded surfaces keep independent camera state, clip
    their children, and never own or mutate the underlying source model.
    """
    def __init__(self,canvas,graph_id,width,height,content_width,content_height,
                 *,parent=None,root=False):
        super().__init__(parent)
        self.canvas=canvas
        self.graph_id=graph_id
        self.is_root=root
        self.camera=GraphSurfaceState(width,height,content_width,content_height)
        self.setFlag(self.GraphicsItemFlag.ItemClipsChildrenToShape,True)
        # One navigation policy at all depths: the canvas owns pan and zoom.
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self._drag_last=None
        self.content=GraphContentItem(self)
        self.content.setZValue(0)
        self.setZValue(0)
        if not root:
            # Persist a graph camera across whole-file redraw/collapse, but
            # never write pan/zoom into Python source or node coordinates.
            state=canvas.window._graph_cameras.get(canvas.graph_camera_key(graph_id))
            if state:
                self.camera.offset_x,self.camera.offset_y,self.camera.zoom=state
                self.camera._clamp()
            else:
                self.camera.fit_contents(min_readable_zoom=.32)
        self.apply_camera()

    def boundingRect(self):
        return QRectF(0,0,self.camera.viewport_width,self.camera.viewport_height)

    def paint(self,p,option,widget=None):
        if self.is_root:return
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r=self.boundingRect()
        p.setPen(QPen(qcolor('#28617b'),.8))
        p.setBrush(QBrush(qcolor('#081c2b')))
        p.drawRect(r)
        # A very faint local grid makes it clear that each region is a
        # separate navigable workspace, without a second heavy chrome layer.
        p.setPen(QPen(qcolor('#123047'),.5))
        for x in range(0,int(r.width()),30):
            p.drawLine(x,0,x,int(r.height()))
        for y in range(0,int(r.height()),30):
            p.drawLine(0,y,int(r.width()),y)

    def apply_camera(self):
        self.content.setPos(self.camera.offset_x,self.camera.offset_y)
        self.content.setScale(self.camera.zoom)
        self.update()
        self.canvas.request_edge_refresh()

    def _save_camera(self):
        if not self.is_root:
            self.canvas.window._graph_cameras[self.canvas.graph_camera_key(self.graph_id)]=(self.camera.offset_x,self.camera.offset_y,self.camera.zoom)
            self.canvas.window._queue_presentation_save()

    def reset_readable_view(self):
        if self.is_root:return
        self.camera.fit_contents(min_readable_zoom=.32)
        self.apply_camera()
        self._save_camera()

    def pan_by(self,dx,dy):
        if self.is_root:return
        self.camera.pan(dx,dy)
        self.apply_camera();self._save_camera()

    def zoom_by(self,factor,scene_pos):
        if self.is_root:return
        position=self.mapFromScene(scene_pos)
        self.camera.zoom_at(factor,position.x(),position.y())
        self.apply_camera();self._save_camera()

    def resize_viewport(self,width,height):
        """Change presentation geometry, never source graph identity."""
        if self.is_root:return
        self.prepareGeometryChange()
        self.camera.resize_viewport(width,height)
        self.apply_camera()
        self._save_camera()

    def parent_surface(self):
        item=self.parentItem()
        while item is not None:
            if isinstance(item,GraphSurfaceItem):return item
            item=item.parentItem()
        return None

    def mouseDoubleClickEvent(self,event):
        event.accept()

    def extend_for_child(self,child):
        """Keep a moved node in the same graph, and make its new position scrollable."""
        pos=child.pos()
        self.content.prepareGeometryChange()
        self.camera.ensure_extent(pos.x()+child.width+16,pos.y()+child.height+16)
        self.apply_camera()
        self._save_camera()


class NodeItem(QGraphicsObject):
    def __init__(self,window,data,canvas,settings_view=False):
        super().__init__()
        self.window=window;self.data=data;self.canvas=canvas;self.settings_view=settings_view
        self.source_view=canvas.source_view
        self.resource_view=canvas.resource_view
        self.program_view=canvas.program_view
        # Immutable validated interface: neither the renderer nor an adapter
        # may synthesize incompatible presentation ports after validation.
        self.descriptor=canvas.descriptors_by_node.get(data['id'])
        self.interface=self.descriptor.interface if self.descriptor is not None else None
        self.appearance=self.descriptor.appearance if self.descriptor is not None else None
        # Every Python source node shares the compact source presentation.
        # Its full signature and original details remain in the inspector.
        self.compact=self.source_view or self.resource_view or self.program_view
        self.region=data.get('embedded_region') if (self.source_view or self.resource_view) else None
        self.resource_preview=data.get('resource_preview') if self.resource_view else None
        if self.region:
            saved=window._graph_sizes.get(canvas.graph_camera_key(self.region['scope']))
            if saved:
                self.region['viewport_width'],self.region['viewport_height']=saved
                self.region['width']=saved[0]+12
                self.region['height']=self.region['surface_top']+saved[1]+6
        self.definition=self.source_view and bool(data.get('source_scope'))
        if self.resource_view:
            self.setToolTip(str(data.get('resource_path',data.get('title',''))))
        elif self.descriptor is not None and self.descriptor.semantic_role=='definition':
            self.setToolTip('Function/class definition · inspectable body, not an invoked function. Runtime results belong to CALL sites.')
        elif self.descriptor is not None and self.descriptor.semantic_role=='invocation':
            self.setToolTip('Call expression · effect verification: '+self.descriptor.effect_verification+
                            '. Value connections do not guarantee execution order.')
        def visible_port(port):
            return not (self.source_view and data.get('source_kind')=='opaque' and
                        ':call:' in port.get('id','') and
                        self.window.source_detail=='readable')
        count=max(sum(visible_port(p) for p in data['draft_ports']['inputs']),
                  sum(visible_port(p) for p in data['draft_ports']['outputs']))
        basic_w=(155 if data.get('source_kind') in
                 ('param','capture','global','literal','operation','compare','loop_test','return') or data.get('visual_family')=='operator_assignment'
                 else 225)
        self.width=(self.region['width'] if self.region else (RESOURCE_COMPACT_WIDTH if self.resource_view and count==0 else basic_w)) if self.compact else NODE_W
        self.height=(self.region['height'] if self.region else (RESOURCE_COMPACT_HEIGHT if self.resource_view and count==0 else max(55,37+count*24))) if self.compact else 200
        if self.resource_preview and not self.region:
            self.width=max(self.width,360 if self.resource_preview.get('kind')=='text' else 245)
            self.height=max(self.height,self._resource_preview_height())
        self.hovered=False
        self._graph_resize_anchor=None
        self.inner_ports=[]
        self.exit_lanes=[]
        self.return_facets={}
        self.ports=[];self._resize_pending=False;self._ready=False
        # A child-owned timer is cancelled when Qt destroys its scene item.
        # Never leave a Python singleShot retaining a deleted QGraphicsObject.
        self._resize_timer=QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.timeout.connect(self.resize_now)
        self.setFlags(self.GraphicsItemFlag.ItemIsSelectable|self.GraphicsItemFlag.ItemIsMovable|
                      self.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setAcceptHoverEvents(True)
        self.setPos(float(data.get('x',100)),float(data.get('y',100)))
        self.proxy=QGraphicsProxyWidget(self)
        self.proxy.setZValue(2)
        self.panel=NodeBody(self)
        self.proxy.setWidget(self.panel)
        self.proxy.setPos(19,78)
        if self.compact:self.proxy.setVisible(False)
        self.search=QLineEdit();self.search.setPlaceholderText('⌕ Filter')
        self.search.setFixedSize(95,26)
        self.search_proxy=QGraphicsProxyWidget(self);self.search_proxy.setWidget(self.search)
        self.search_proxy.setPos(self.width-150,26);self.search_proxy.setZValue(4)
        if self.compact:self.search_proxy.setVisible(False)
        self.search.textChanged.connect(self.panel.filter)
        self.surface=None
        if self.region:
            info=self.region
            self.surface=GraphSurfaceItem(
                canvas,info['scope'],info['viewport_width'],info['viewport_height'],
                info['content_width'],info['content_height'],parent=self)
            self.surface.setPos(6,info['surface_top'])
            self.surface.setZValue(1)
        self.sync_ports()
        self._ready=True
        self.resize_now()

    def _resource_preview_height(self):
        preview=self.resource_preview or {}
        if preview.get('kind')=='image':return 193.
        if preview.get('kind')=='python-graph':return 78.
        if preview.get('kind')=='text':return 254.
        return RESOURCE_COMPACT_HEIGHT

    def section_for_row(self,id_):
        return next((s for s in self.data['containers'] if any(r['id']==id_ for r in s['rows'])),None)

    def schedule_resize(self):
        if not self._ready or self._resize_pending:return
        self._resize_pending=True
        self._resize_timer.start(0)

    def resize_now(self):
        if self._resize_timer.isActive():self._resize_timer.stop()
        self._resize_pending=False
        # An invalidated card can retain a queued resize callback even after
        # its old scene was cleared. It has no presentation left to refresh.
        if self.scene() is None:return
        if self.compact:
            no_ports=(not self.data['draft_ports']['inputs'] and
                      not self.data['draft_ports']['outputs'])
            new_height=(self.region['height'] if self.region else
                RESOURCE_COMPACT_HEIGHT if self.resource_view and no_ports else
                max(55,37+max(len(self.data['draft_ports']['inputs']),
                              len(self.data['draft_ports']['outputs']))*24))
            if self.resource_preview and not self.region:
                new_height=max(new_height,self._resource_preview_height())
        else:
            # Child layouts must settle before the outer QGraphicsObject measures
            # them; the graphics item's bounding rectangle is not a QWidget.
            for section in self.panel.sections:
                section.content.layout().invalidate()
                section.content.layout().activate()
                section.layout_main.invalidate()
                section.layout_main.activate()
                section.adjustSize()
            self.panel.layout().invalidate()
            self.panel.layout().activate();self.panel.adjustSize()
            needed=max(self.panel.sizeHint().height(),self.panel.layout().sizeHint().height())
            minimum=130+max(len(self.data['draft_ports']['inputs']),len(self.data['draft_ports']['outputs']))*33
            new_height=max(170,minimum,78+needed+39)
            # Keep the embedded QWidget and graphics proxy geometry in sync;
            # measuring alone can leave the body clipped until the next click.
            self.proxy.resize(NODE_W-38,needed)
        if abs(new_height-self.height)>.5:
            self.prepareGeometryChange();self.height=new_height
        self.proxy.setPos(19,78)
        self.update()
        # Geometry callbacks may arrive after another tab becomes active.
        # Refresh only this canvas's validated rendering revision, deferred
        # until the owner scene has finished any in-flight rebuild.
        if self.scene():self.canvas.request_edge_refresh()

    def rebuild(self):
        self.panel.rebuild();self.sync_ports();self.schedule_resize()

    def update_port_items(self):
        for p in self.ports:
            p.update()
        self.canvas.viewport().update()

    def _ports_for_view(self, side):
        # Every graph origin uses one validated identity/type/ordering contract.
        # Draft changes publish a newly validated transaction and rebuild this
        # scene; source and resource presentation never mutate their owners.
        if self.descriptor is not None:
            return validated_port_payloads(self.descriptor, self.data, side)
        return self.data['draft_ports'][side]  # settings-only synthesized node

    def sync_ports(self):
        for p in self.ports+self.inner_ports+self.exit_lanes+list(self.return_facets.values()):
            if p.scene():p.scene().removeItem(p)
            p.setParentItem(None)
        self.ports=[];self.inner_ports=[];self.exit_lanes=[];self.return_facets={}
        for side in ('inputs','outputs'):
            for ix,port in enumerate(self._ports_for_view(side)):
                it=PortItem(self,port,side)
                # A composite's public interface lives on the outer border.
                # Its one-line title never steals space from child graph nodes.
                y=(self.region['surface_top']+16+ix*22 if self.region
                   else 46+ix*24) if self.compact else 109+ix*34
                it.setPos((0 if side=='inputs' else self.width) if self.region else
                          (9 if side=='inputs' else self.width-9),y)
                self.ports.append(it)
                if self.source_view and self.data.get('source_kind')=='opaque' and ':call:' in port.get('id','') and self.window.source_detail=='readable':
                    it.setVisible(False)  # analyzer reference, not an authored input
                if self.source_view and self.definition and side=='outputs' and port.get('label')=='callable':
                    it.setVisible(False)
                # The real output PortItem is already on the composite's
                # physical frame. For RETURN, use that SAME dot for both the
                # inner wire endpoint and the outside interface; a second
                # painted mirror previously left a visible gap / duplicate.
                if self.surface:
                    inside=BoundaryPortItem(self,port,side,self.surface)
                    # Port aliases inside the graph are VIEW anchors for the
                    # exact external port, not separate parameters or results.
                    inside.setPos(self._inside_pin_x(port,side),16+ix*22)
                    if self.descriptor is not None:
                        role=port_presentation_role(self.descriptor,port['id'])
                        if role in ('definition-time-execution','definition-result-interface'):
                            # Defining a nested function has real *outer* control
                            # flow. That execution does NOT enter its body.
                            # Result is already on the shared outer return dot.
                            inside.setVisible(False)
                    if self.source_view and self.definition and side=='outputs' and port.get('label')=='callable':
                        inside.setVisible(False)
                    self.inner_ports.append(inside)
        # Every graph interface may publish exits; a normal function return
        # has a white completion triangle beside its typed data dot. IF/loop
        # regions have their own authored control pins and no fake return.
        if self.surface:
            for exit_spec in (self.interface.exits if self.interface else ()):
                if exit_spec.kind!='return':continue
                result_port=next((p for p in self.ports
                                  if p.data.get('id')==exit_spec.value_port),None)
                if result_port is None:continue
                lane=ExitLaneItem(self,exit_spec)
                lane.setPos(self.width,result_port.pos().y()+19)
                self.exit_lanes.append(lane)
        # A visible RETURN is a terminal operation. Draw its two exit facets
        # on the actual edge of that card; the renderer never starts a RETURN
        # route from an arbitrary pixel inside the node rectangle.
        if (self.source_view and self.window.source_detail=='readable' and
                self.data.get('source_kind')=='return' and
                self.data['id'] in self.canvas.visible_exit_sites):
            for ix,port in enumerate(self._ports_for_view('inputs')):
                facet='control' if port.get('type')=='execution' else 'value'
                marker=ReturnFacetItem(self,facet)
                marker.setPos(self.width,46+ix*24)
                self.return_facets[facet]=marker
        self.schedule_resize()

    def _inside_pin_x(self,port,side):
        if side=='inputs' or (self.region and self.region.get('role')=='loop_body'
                              and port.get('label') in ('body','item','element')):
            return 9
        return self.surface.camera.viewport_width-9

    def boundingRect(self):
        return QRectF(0,0,self.width,self.height)

    def paint(self,p,option,widget=None):
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r=QRectF(0,0,self.width,self.height)
        accent=qcolor(self.data.get('accent','#25cbed'))
        if self.compact:
            self.paint_compact(p,accent)
            return
        p.setPen(QPen(qcolor('#f3c96e') if self.isSelected() else accent,2 if self.isSelected() else 1.2))
        p.setBrush(QBrush(qcolor('#0a2032')));p.drawRoundedRect(r.adjusted(1,1,-1,-1),10,10)
        p.setPen(Qt.PenStyle.NoPen);p.setBrush(QBrush(qcolor('#12334b')))
        p.drawRoundedRect(QRectF(2,2,self.width-4,73),10,10)
        p.setPen(QPen(qcolor('#235779'),1));p.drawLine(QPointF(2,75),QPointF(self.width-2,75))
        p.setPen(QPen(accent,2));p.drawLine(QPointF(9,4),QPointF(self.width-9,4))
        p.setPen(QPen(accent,1));p.setBrush(QBrush(qcolor('#10344e')))
        p.drawRoundedRect(QRectF(13,17,40,41),8,8)
        icon_id=self.data.get('visual_assets',{}).get('header_icon')
        icon=self.window.sprite(icon_id) if icon_id else QPixmap()
        if not icon.isNull():
            p.drawPixmap(QRect(17,20,32,34),icon)
        else:
            p.drawEllipse(QPointF(33,37),9,9)
        p.setPen(QPen(qcolor(TEXT)));p.setFont(QFont('DejaVu Sans',11,QFont.Weight.Bold))
        p.drawText(QRectF(64,17,165,26),Qt.AlignmentFlag.AlignVCenter,str(self.data.get('title','NEW NODE'))[:21])
        p.setPen(QPen(qcolor(MUTED)));p.setFont(QFont('DejaVu Sans',8))
        p.drawText(QRectF(64,44,180,19),Qt.AlignmentFlag.AlignVCenter,str(self.data.get('subtitle',''))[:36])
        p.setPen(Qt.PenStyle.NoPen);p.setBrush(QBrush(qcolor('#2ce9b5')))
        p.drawEllipse(QPointF(self.width-18,36),5,5)
        p.setPen(QPen(qcolor('#265c77')));p.drawLine(QPointF(9,self.height-31),QPointF(self.width-9,self.height-31))
        p.setPen(QPen(qcolor('#3ddfbb')));p.setFont(QFont('DejaVu Sans',8,QFont.Weight.DemiBold))
        p.drawText(QRectF(15,self.height-28,160,23),Qt.AlignmentFlag.AlignVCenter,'● READY / DRAFT')
        p.setPen(QPen(qcolor(MUTED)))
        status=f'{len(self.data["draft_ports"]["inputs"])} IN · {len(self.data["draft_ports"]["outputs"])} OUT'
        p.drawText(QRectF(self.width-135,self.height-28,120,23),Qt.AlignmentFlag.AlignVCenter|Qt.AlignmentFlag.AlignRight,status)

    def paint_compact(self,p,accent):
        kind=self.data.get('source_kind')
        p.setPen(QPen(qcolor('#ffcf88') if self.isSelected() else accent,1.4))
        p.setBrush(QBrush(qcolor('#091c2c')))
        p.drawRoundedRect(QRectF(0,0,self.width,self.height),7,7)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(qcolor('#15334a')))
        p.drawRoundedRect(QRectF(1,1,self.width-2,29),7,7)
        p.setPen(QPen(accent,1.5))
        p.drawLine(QPointF(6,2),QPointF(self.width-6,2))
        p.setPen(QPen(qcolor('#f0f6ff')))
        is_op=kind in ('operation','compare','loop_test') or (self.appearance is not None and self.appearance.family=='operator_assignment')
        p.setFont(QFont('DejaVu Sans',15 if is_op else 9,QFont.Weight.Bold))
        title=((self.appearance.symbol if is_op else self.appearance.title)
               if self.appearance is not None else
               (self.data.get('display_symbol') if is_op else self.data.get('display_title',self.data.get('title','NODE')))) or self.data.get('title','NODE')
        title_x=32 if self.region else (32 if self.definition else 12)
        if self.resource_view:
            icon=self.window.resource_icon(self.data)
            if not icon.isNull():
                p.drawPixmap(QRectF(7,8,18,18),icon,QRectF(icon.rect()))
            title_x=30
            title=self.data.get('title','')
        if (self.region or self.definition) and not self.resource_view:
            # A single small declaration icon, rather than a double-wide
            # header icon plus redundant subtitle, filter and status footer.
            hint=icon_hint(kind,source_line=str(self.data.get('title','')))
            icon=(self.window.external_icon(hint.icon_id,tint=hint.tint)
                  if self.source_view else QPixmap())
            if not icon.isNull():
                p.drawPixmap(QRectF(9,8,15,15),icon,QRectF(icon.rect()))
            else:
                p.setPen(QPen(accent,1.4))
                p.drawRoundedRect(QRectF(9,8,15,15),4,4)
            p.setPen(QPen(qcolor('#f0f6ff')))
        available=max(18.0,self.width-title_x-(32 if self._can_toggle_region() else 12))
        title_metrics=QFontMetricsF(p.font())
        if self.resource_view:
            # Filename is never truncated in data or accessibility metadata.
            title=title_metrics.elidedText(str(title),Qt.TextElideMode.ElideRight,available)
        else:
            title=title_metrics.elidedText(str(title),Qt.TextElideMode.ElideRight,available)
        p.drawText(QRectF(title_x,4,available,24),
                   Qt.AlignmentFlag.AlignCenter if is_op else Qt.AlignmentFlag.AlignVCenter,title)
        if self._can_toggle_region():
            # Same semantic region, two presentations; one compact button.
            button=self._toggle_rect()
            p.setPen(QPen(qcolor('#8db4cb'),1.0));p.setBrush(QBrush(qcolor('#102b3c')))
            p.drawRoundedRect(button,3,3)
            mid=button.center()
            p.drawLine(QPointF(mid.x()-4,mid.y()),QPointF(mid.x()+4,mid.y()))
            if not self.region:
                p.drawLine(QPointF(mid.x(),mid.y()-4),QPointF(mid.x(),mid.y()+4))
        if self.resource_preview and not self.region:
            self._paint_resource_preview(p)
        if self.region:
            p.setPen(QPen(qcolor('#35617a'),0.8))
            p.drawLine(QPointF(7,29),QPointF(self.width-7,29))
        p.setFont(QFont('DejaVu Sans',8))
        p.setPen(QPen(qcolor('#abc4d6')))
        if not self.region and kind in ('literal','param','capture','global','loop_test','loop_value'):
            detail=self.data.get('subtitle','')
            if kind=='literal':detail=next((str(r.get('value','')) for c in self.data.get('containers',[]) for r in c.get('rows',[]) if r.get('label')=='Value'),detail)
            p.drawText(QRectF(14,self.height-27,self.width-28,22), Qt.AlignmentFlag.AlignCenter, str(detail)[:26])
        if self.region:
            p.setPen(QPen(qcolor('#608da5'),1))
            for d in (5,9,13):
                p.drawLine(QPointF(self.width-d,self.height-3),
                           QPointF(self.width-3,self.height-d))
        # Composite ports live on the boundary and show their full names on
        # hover/Space. Do not paint duplicate labels behind the child surface.
        if self.region:return
        for side in ('inputs','outputs'):
            for i,port in enumerate(self._ports_for_view(side)):
                if kind=='opaque' and self.source_view and self.window.source_detail=='readable' and ':call:' in port.get('id',''):
                    continue
                y=46+i*24
                text=str(port.get('label',''))[:14]
                if side=='inputs' and 'default' in port and not self.window.is_source_port_connected(self.data['id'],port['id']):
                    fallback=m.format_input_default(port)
                    if fallback is not None:text=(str(fallback) if port.get('binding_mode')=='source_literal' else text+' = '+str(fallback))[:14]
                flags=Qt.AlignmentFlag.AlignVCenter | (Qt.AlignmentFlag.AlignLeft if side=='inputs' else Qt.AlignmentFlag.AlignRight)
                x=22 if side=='inputs' else self.width-96
                p.drawText(QRectF(x,y-13,74,26),flags,text)

    def _paint_resource_preview(self,p):
        preview=self.resource_preview
        p.setPen(QPen(qcolor('#abc4d6')))
        p.setFont(QFont('DejaVu Sans',8))
        status=str(preview.get('status',''))
        if status:
            p.drawText(QRectF(17,36,self.width-34,21),Qt.AlignmentFlag.AlignVCenter,
                       QFontMetricsF(p.font()).elidedText(status,Qt.TextElideMode.ElideRight,self.width-34))
        if preview.get('kind')=='image' and not status:
            thumb=self.window.resource_thumbnail(self.data)
            if not thumb.isNull():
                target=QRectF((self.width-thumb.width())/2,55,thumb.width(),thumb.height())
                p.drawPixmap(target,thumb,QRectF(thumb.rect()))
            else:p.drawText(QRectF(18,70,self.width-36,30),Qt.AlignmentFlag.AlignCenter,
                            'Image preview unavailable')
        elif preview.get('kind')=='text' and not preview.get('status','').startswith(('Not valid','Binary','Not a regular')):
            p.setPen(QPen(qcolor('#d7e8f5')))
            p.setFont(QFont('DejaVu Sans Mono',8))
            p.drawText(QRectF(16,60,self.width-32,self.height-68),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
                       str(preview.get('text','')))

    def _can_toggle_region(self):
        if self.source_view:
            return bool(self.data.get('child_region_key') or self.data.get('collapsed_region_key'))
        return bool(self.resource_view and (self.data.get('resource_kind')=='directory' or
                   self.data.get('preview_kind') not in (None,'none')))

    def _toggle_rect(self):
        return QRectF(self.width-25,6,17,17)

    def _toggle_hit(self,pos):
        return self._can_toggle_region() and self._toggle_rect().contains(pos)

    def toggle_region(self):
        if self.source_view:
            key=self.data.get('child_region_key') or self.data.get('collapsed_region_key')
            if key:self.window.toggle_source_region(key)
        elif self.resource_view and self._can_toggle_region():
            self.window.toggle_resource_expansion(self.data)

    def _resize_corner(self,pos):
        # Historic name kept for callers; it now returns all 8 resize grips.
        if not (self.region and self.surface):return None
        return resize_handle(pos.x(),pos.y(),self.width,self.height)

    def _at_graph_resize_grip(self,pos):
        return bool(self._resize_corner(pos))

    def hoverMoveEvent(self,event):
        corner=self._resize_corner(event.pos())
        if corner:
            cursor=(Qt.CursorShape.SizeHorCursor if corner in ('w','e') else
                    Qt.CursorShape.SizeVerCursor if corner in ('n','s') else
                    Qt.CursorShape.SizeFDiagCursor if corner in ('nw','se') else Qt.CursorShape.SizeBDiagCursor)
            self.setCursor(cursor)
        else:self.unsetCursor()
        super().hoverMoveEvent(event)

    def _resize_graph_to(self,width,height):
        if not self.region or not self.surface:return
        width=max(180.0,min(4000.0,float(width)))
        height=max(90.0,min(3000.0,float(height)))
        if (abs(width-self.region['viewport_width'])<.5 and
                abs(height-self.region['viewport_height'])<.5):return
        self.prepareGeometryChange()
        self.region['viewport_width']=width
        self.region['viewport_height']=height
        self.region['width']=self.width=width+12
        self.region['height']=self.height=self.region['surface_top']+height+6
        self.surface.resize_viewport(width,height)
        for port in self.ports:
            if port.direction=='outputs':port.setPos(self.width,port.pos().y())
        for lane in self.exit_lanes:
            lane.setPos(self.width,lane.pos().y())
        for port in self.inner_ports:
            port.setPos(self._inside_pin_x(port.data,port.direction),port.pos().y())
        self.window._graph_sizes[self.canvas.graph_camera_key(self.region['scope'])]=(width,height)
        self.window._queue_presentation_save()
        if isinstance(self.parentItem(),GraphContentItem) and not self.parentItem().surface.is_root:
            self.parentItem().surface.extend_for_child(self)
        self.update()
        if self.scene():self.canvas.request_edge_refresh()

    def mousePressEvent(self,event):
        if self.program_view and event.button()==Qt.MouseButton.LeftButton:
            self._program_start=(self.data.get('x'),self.data.get('y'))
        if event.button()==Qt.MouseButton.LeftButton:
            self.canvas._activate_node_layer(self)
            if self._toggle_hit(event.pos()):
                self.toggle_region();event.accept();return
        corner=self._resize_corner(event.pos())
        if event.button()==Qt.MouseButton.LeftButton and corner:
            # Keep the opposite corner stationary even when resizing from
            # top-left. Capture coordinates in the parent graph's own space.
            parent=self.parentItem()
            mouse=parent.mapFromScene(event.scenePos()) if parent else event.scenePos()
            self._graph_resize_anchor=(corner,mouse,self.pos(),
                                       self.region['viewport_width'],
                                       self.region['viewport_height'])
            event.accept();return
        super().mousePressEvent(event)
        if (event.button()==Qt.MouseButton.LeftButton and self.source_view
                and self.data.get('source_span')):
            # Qt selectionChanged only fires when selection identity changes.
            # Re-clicking the same source node should still restore the editor
            # caret/scroll position after the user has scrolled elsewhere.
            self.window.highlight_python_node(self.data)

    def mouseMoveEvent(self,event):
        if self._graph_resize_anchor is not None:
            corner,anchor,origin,width,height=self._graph_resize_anchor
            parent=self.parentItem()
            now=parent.mapFromScene(event.scenePos()) if parent else event.scenePos()
            dx=now.x()-anchor.x();dy=now.y()-anchor.y()
            new_w,new_h,shift_x,shift_y=resize_rectangle(corner,width,height,dx,dy)
            self._resize_graph_to(new_w,new_h)
            new_x=origin.x()+shift_x
            new_y=origin.y()+shift_y
            self.setPos(QPointF(new_x,new_y))
            event.accept();return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self,event):
        if self._graph_resize_anchor is not None and event.button()==Qt.MouseButton.LeftButton:
            self._graph_resize_anchor=None
            self.unsetCursor()
            event.accept();return
        super().mouseReleaseEvent(event)
        if self.program_view and event.button()==Qt.MouseButton.LeftButton:
            start=getattr(self,'_program_start',None)
            self._program_start=None
            if start is not None and start!=(self.data.get('x'),self.data.get('y')):
                self.canvas.program_workspace.move_node(self.data['id'],self.data['x'],self.data['y'])

    def itemChange(self,change,value):
        if (change==self.GraphicsItemChange.ItemPositionChange and self._ready and
                isinstance(self.parentItem(),GraphContentItem) and
                not self.parentItem().surface.is_root):
            # The same graph remains the sole owner. A child may expand its
            # logical extent to the right/bottom, but never cross the content
            # origin into the containing graph's border/header.
            return QPointF(max(0.0,value.x()),max(0.0,value.y()))
        result=super().itemChange(change,value)
        if change==self.GraphicsItemChange.ItemPositionHasChanged and self._ready and not self.canvas._rebuilding:
            self.data['x']=round(self.pos().x()+(self.canvas.graph_scene.sceneRect().x() if
                            isinstance(self.parentItem(),GraphContentItem) and self.parentItem().surface.is_root else 0),1)
            self.data['y']=round(self.pos().y()+(self.canvas.graph_scene.sceneRect().y() if
                            isinstance(self.parentItem(),GraphContentItem) and self.parentItem().surface.is_root else 0),1)
            if self.program_view:
                # Positions here belong to the disposable renderer payload.
                # The ProgramGraph transaction is published on mouse release.
                pass
            if self.settings_view:
                self.window._setting_positions[self.data['id']]=(self.data['x'],self.data['y'])
            if self.source_view:
                self.window._source_positions[self.window._source_position_key(self.window.source_view_mode if self.window.source_view_mode=='whole' else self.window.source_scope,self.data['id'])]=(self.data['x'],self.data['y'])
            if self.resource_view:
                self.window._resource_positions[self.data['id']]=(self.data['x'],self.data['y'])
            if not self.program_view:
                self.window._queue_presentation_save()
            if self.scene():
                graph=self.parentItem()
                if isinstance(graph,GraphContentItem) and not graph.surface.is_root:
                    graph.surface.extend_for_child(self)
                else:
                    self.canvas.request_edge_refresh()
                if not self.source_view and not self.resource_view:self.window.mark_changed(self.settings_view)
        return result

    def contextMenuEvent(self,event):
        if self.program_view:
            self.canvas.program_workspace.context_menu(event.screenPos(),node_id=self.data['id'])
            event.accept()
            return
        if self.resource_view and self.data.get('resource_kind')=='file':
            menu=QMenu()
            focus=menu.addAction('Focus this file’s relationships')
            show=menu.addAction('Show all visible relationships')
            show.setEnabled(self.window.resource_relationship_focus is not None)
            explore=menu.addAction('Explore visible relationships for this file…')
            frame=menu.addAction('Frame this file')
            action=menu.exec(event.screenPos())
            event.accept()
            if action is focus:self.window.set_resource_relationship_focus(self.data['resource_path'])
            elif action is show:self.window.set_resource_relationship_focus(None)
            elif action is explore:self.window.explore_resource_relationships(self.canvas,focus=self.data['resource_path'])
            elif action is frame:self.canvas.frame_node(self)
            return
        if not self.source_view:
            super().contextMenuEvent(event)
            return
        menu=QMenu()
        focus=expand=new_tab=None
        key=self.data.get('source_scope') or self.data.get('child_region_key')
        if key and self.window.python_doc and key in self.window.python_doc.scopes:
            focus=menu.addAction('Focus scope in current tab')
            new_tab=menu.addAction('Open scope in new graph tab')
            if self.window.source_view_mode=='whole':
                expand=menu.addAction('Expand / collapse scope')
        frame=menu.addAction('Frame this node')
        reset=menu.addAction('Reset inner graph to readable zoom') if self.surface else None
        action=menu.exec(event.screenPos())
        event.accept()  # The following actions may destroy this item on rebuild.
        if action is focus and focus is not None:self.window.navigate_source(key)
        elif action is new_tab and new_tab is not None:self.window.open_source_in_new_tab(self.window.python_doc.path,key)
        elif action is expand and expand is not None:self.window.open_source_scope(self)
        elif action is frame:self.canvas.frame_node(self)
        elif action is reset and reset is not None:self.surface.reset_readable_view()

    def mouseDoubleClickEvent(self,event):
        if self.resource_view and self._can_toggle_region():
            # One expand gesture for directories and preview-capable files.
            if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                self.window.open_resource_node(self.data,new_tab=True)
            else:self.window.toggle_resource_expansion(self.data)
        elif self.resource_view:
            self.window.open_resource_node(self.data,new_tab=bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier))
        elif (self.source_view and self.data.get('source_scope') and
              event.modifiers() & Qt.KeyboardModifier.ControlModifier):
            # Ctrl+double-click is always a new graph-view session; even a
            # composite source node may carry a child-region descriptor.
            self.window.open_source_scope(self,focus=True)
        elif self.source_view and (self.data.get('child_region_key') or self.data.get('collapsed_region_key')):
            self.window.toggle_source_region(self.data.get('child_region_key') or self.data['collapsed_region_key'])
        elif self.source_view and self.data.get('source_scope'):
            self.window.open_source_scope(self,focus=False)
        elif self.program_view:
            self.canvas.program_workspace.edit_literal(self.data['id'])
        else:self.window.show_inspector(self)
        event.accept()

    def mark_changed(self):
        if not self.source_view and not self.resource_view and not self.program_view:
            self.window.mark_changed(self.settings_view)


class GraphOverview(QWidget):
    """Camera-only overview for any graph canvas, independent of its producer."""
    def __init__(self, canvas):
        super().__init__()
        self.canvas=canvas
        self.setObjectName('GraphOverview')
        # Preferred size only; the viewport placement policy may shrink it.
        # setFixedSize would prevent setGeometry from honoring a small dock/tab.
        self.resize(228,154)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setToolTip('Graph overview: click or drag to reposition the main camera')
        self.setCursor(Qt.CursorShape.CrossCursor)
        self._dragging=False
        self._drag_offset=(0.0,0.0)
        self._model=None

    def sizeHint(self):
        # The graph page's layout owns geometry; the overlay only states its
        # desired size. Small viewports may impose a smaller maximum.
        return QSize(228,154)

    def projection(self):
        return overview_map(self.canvas._visible_root_rects(), self.width(), self.height())

    def paintEvent(self,event):
        p=QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(qcolor('#40728b'),1))
        p.setBrush(qcolor('#0a2030'))
        p.drawRoundedRect(self.rect().adjusted(1,1,-2,-2),7,7)
        p.setPen(qcolor('#b3d5e8'))
        font=p.font();font.setPixelSize(10);p.setFont(font)
        p.drawText(11,15,'OVERVIEW')
        model=self.projection()
        self._model=model
        if model is None:return
        p.save()
        p.setClipRect(self.rect().adjusted(3,19,-3,-3))
        p.setPen(QPen(qcolor('#448aaa'),.8))
        p.setBrush(QBrush(qcolor('#1a4960')))
        for rectangle in self.canvas._visible_root_rects():
            x,y,w,h=model.project_rect(rectangle)
            p.drawRect(QRectF(x,y,max(2,w),max(2,h)))
        # Main viewport is projected through the SAME graph scene/camera.
        visible=self.canvas.mapToScene(self.canvas.viewport().rect()).boundingRect()
        x,y,w,h=model.project_rect((visible.x(),visible.y(),visible.width(),visible.height()))
        p.setPen(QPen(qcolor('#ffffff'),1.6))
        p.setBrush(QBrush(QColor(205,235,255,24)))
        p.drawRect(QRectF(x,y,w,h))
        p.restore()

    def begin_camera_drag(self,pos):
        """A viewport-box drag keeps its grab offset; elsewhere click-to-center."""
        model=self.projection()
        if model is None:return False
        visible=self.canvas.mapToScene(self.canvas.viewport().rect()).boundingRect()
        self._drag_offset=overview_drag_offset(
            model,(visible.x(),visible.y(),visible.width(),visible.height()),
            (pos.x(),pos.y()))
        self._dragging=True
        self._move_camera(pos)
        return True

    def _move_camera(self,pos):
        model=self.projection()
        if model is None:return
        cx,cy=model.to_scene(pos.x(),pos.y())
        dx,dy=self._drag_offset
        self.canvas.centerOn(cx+dx,cy+dy)
        self.canvas._save_root_view()
        self.update()

    def mousePressEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton:
            self.begin_camera_drag(event.position())
            event.accept()
        else:super().mousePressEvent(event)

    def mouseMoveEvent(self,event):
        if self._dragging:
            self._move_camera(event.position())
            event.accept()
        else:super().mouseMoveEvent(event)

    def mouseReleaseEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton and self._dragging:
            self._dragging=False
            self._drag_offset=(0.0,0.0)
            event.accept()
        else:super().mouseReleaseEvent(event)


class GraphCanvas(QGraphicsView):
    def __init__(self,window,settings_view=False,source_view=False,resource_view=False,program_view=False):
        super().__init__()
        self.window=window;self.settings_view=settings_view;self.source_view=source_view
        self.resource_view=resource_view
        self.program_view=program_view
        self.program_workspace=None
        self.graph_scene=QGraphicsScene(self)
        self.graph_scene.setSceneRect(-2000,-1200,8500,6000)
        self.setScene(self.graph_scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.BoundingRectViewportUpdate)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setBackgroundBrush(qcolor(BG))
        self.setMouseTracking(True);self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        # A new/temporarily unloaded tab is a valid empty graph surface.
        # Qt can deliver tab-change signals before the first rebuild().
        self.graph_contract=None
        # Read-only presentation reference: the one graph supplied to the
        # most recent rebuild. Never fetch a different tab's window aliases
        # from asynchronous callbacks (resize, hover, minimap, pan).
        self._render_graph=None
        self.descriptors_by_node={};self.interfaces_by_node={};self.appearance_by_node={}
        self.exit_routes=();self.visible_exit_sites=set();self.folded_exit_connections={}
        self.items_by_id={};self.edge_items=[];self.pending=None;self.preview_path=None
        self.connection_hints={};self._connection_hover=None
        self.space_held=False;self.middle_pan=None;self.right_pan=None;self.marquee=None;self.last_hover=None
        self._suppress_native_context=False
        self.corner_resize=None
        self.root_surface=None
        self.surfaces={}
        self._rebuilding=False
        self._edge_refresh_pending=False
        self.graph_scene.selectionChanged.connect(self.selection_changed)
        self.overview_visible=True
        self.overview=GraphOverview(self)
        self._overview_host=None
        self._overview_layout=None
        self.session_id=('source' if source_view else 'resource' if resource_view else '')

    def attach_overview_host(self,host,layout):
        """Attach one minimap to the ordinary Qt graph-page layout.

        The QGraphicsView viewport is managed by QAbstractScrollArea and must
        never own application overlay widgets. The page layout is the single
        geometry authority for both the graph and its minimap.
        """
        if self._overview_host is not None:
            raise RuntimeError('A graph canvas already has an overview host')
        self._overview_host=host
        self._overview_layout=layout
        layout.addWidget(self.overview,0,0,
                         Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom)
        self._place_overview()

    def _place_overview(self):
        """Set only size policy and visibility, never position or coordinates."""
        if self._overview_host is None:
            return
        available=overview_viewport_size(self._overview_host.width(),
                                         self._overview_host.height(),margin=24)
        visible=self.overview_visible and available is not None
        if available is not None:
            size=QSize(*available)
            if self.overview.maximumSize()!=size:
                self.overview.setMaximumSize(size)
        self.overview.setVisible(visible)
        if visible:
            self.overview.raise_()

    def resizeEvent(self,event):
        super().resizeEvent(event)
        self._place_overview()
        self.overview.update()

    def set_overview_visible(self,visible):
        self.overview_visible=bool(visible)
        self._place_overview()

    def _visible_root_rects(self):
        if self.root_surface is None:return []
        root=self.root_surface.content
        rects=[]
        for card in self.items_by_id.values():
            if card.parentItem() is root and card.isVisible() and not card.data.get('presentation_hidden'):
                rect=card.sceneBoundingRect()
                rects.append((rect.x(),rect.y(),rect.width(),rect.height()))
        return rects

    def graph_camera_key(self,graph_id):
        if self.program_view and self.program_workspace is not None:
            document=self.program_workspace.document
            return (str(document.path or document.state['id']),
                    '@program:'+str(self.program_workspace.current_function)+':'+graph_id)
        # Use exact source path so two files with identically named functions
        # never accidentally inherit one another's camera state.
        # Resolve identities from this canvas's own session, not whichever
        # source/resource tab the window most recently activated. The window
        # keeps temporary editing aliases, but these never own camera keys.
        session=(self.window._view_sessions.get(self.session_id)
                 if self.source_view or self.resource_view else None)
        path=(session.route.path if session is not None else
              'settings-graph' if self.settings_view else
              str(self.window.resource_path) if self.resource_view else
              str(self.window.python_doc.path) if self.source_view and self.window.python_doc else
              'source-unloaded' if self.source_view else 'node-workspace')
        if graph_id=='@root-view' and (self.source_view or self.resource_view):
            # Each graph-view session/route owns its root camera identity.
            # Keep the existing presentation store as the single owner of
            # camera values. The current Qt canvas still has one source page;
            # separate Qt canvases will each receive their session ID later.
            kind='source' if self.source_view else 'resource'
            session=self.window._view_sessions.get(self.session_id or kind)
            if session is not None:
                return session.camera_slot()
        if (self.source_view or self.resource_view) and self.session_id:
            # Child-region cameras are session-owned for source and resources.
            # A second tab never borrows the first tab's nested camera.
            return (path,'@session:'+self.session_id+':'+graph_id)
        return (path,graph_id)

    def request_edge_refresh(self):
        # Camera/child movement must not recursively rebuild edges while the
        # scene hierarchy is being constructed.
        if self._rebuilding or self._edge_refresh_pending:return
        self._edge_refresh_pending=True
        QTimer.singleShot(0,self._flush_edge_refresh)

    def _flush_edge_refresh(self):
        self._edge_refresh_pending=False
        if not self._rebuilding and self.scene() is self.graph_scene:
            self.update_edges()
            self.overview.update()

    def navigation_surface(self,view_pos,modifiers=Qt.KeyboardModifier.NoModifier):
        """Pan drag targets a selected region, otherwise its selected ancestor.

        The region's existing NodeItem selection owns activation. Hovering an
        expanded but unselected graph must not steal panning from its parent.
        Ctrl explicitly targets the root; Shift targets the hovered parent.
        Neither creates a separate active-region preference or source change.
        """
        if self.root_surface is None:return None  # Unloaded tabs remain valid.
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            return self.root_surface
        candidate=self.nested_surface_at(view_pos) or self.root_surface
        if modifiers & Qt.KeyboardModifier.ShiftModifier:
            return candidate.parent_surface() or self.root_surface
        return selected_pan_surface(
            candidate,
            lambda surface: surface.parent_surface(),
            lambda surface: surface.is_root or (
                isinstance(surface.parentItem(),NodeItem)
                and surface.parentItem().isSelected()))

    def nested_surface_at(self,view_pos):
        # The deepest visible graph owns wheel and middle-drag input.
        scene_pos=self.mapToScene(view_pos)
        for item in self.items(view_pos):
            current=item
            while current is not None:
                if isinstance(current,GraphSurfaceItem) and not current.is_root:
                    if current.boundingRect().contains(current.mapFromScene(scene_pos)):
                        return current
                current=current.parentItem()
        return None

    def drawBackground(self,p,rect):
        p.fillRect(rect,qcolor('#071827'))
        if not self.window.state['settings'].get('show_grid',True):return
        left=int(math.floor(rect.left()/35)*35);top=int(math.floor(rect.top()/35)*35)
        p.setPen(QPen(qcolor('#123045'),.6))
        for x in range(left,int(rect.right())+35,35):p.drawLine(x,int(rect.top()),x,int(rect.bottom()))
        for y in range(top,int(rect.bottom())+35,35):p.drawLine(int(rect.left()),y,int(rect.right()),y)

    def rebuild(self):
        # Both source-derived and authored workspaces pass the same immutable
        # descriptor/edge-endpoint contract before Qt constructs anything.
        # No semantic data is copied back from this presentation snapshot.
        # Only the owner canvas supplies a document. Source and resource canvases
        # are EMPTY before their file/directory is loaded, never draft fallbacks.
        if self.program_view:
            workspace=self.program_workspace
            graph=(view_graph(workspace.document.state,workspace.current_function)
                   if workspace.current_function else None)
            origin='program' if graph is not None else None
        else:
            graph,origin=canvas_graph_source(
                source_view=self.source_view,resource_view=self.resource_view,
                settings_view=self.settings_view,state=self.window.state,
                source_graph=self.window.source_graph,resource_graph=self.window.resource_graph)
        # Capture the provider's render revision before creating Qt items.
        # This is a non-owning presentation view, not a writable graph store.
        contract=describe_graph(graph,origin=origin) if graph is not None else None
        self._render_graph=graph
        self.graph_contract=contract
        self.descriptors_by_node=({desc.id:desc for desc in self.graph_contract.nodes}
                                  if self.graph_contract else {})
        self.interfaces_by_node={nid:desc.interface for nid,desc in self.descriptors_by_node.items()}
        self.appearance_by_node={nid:desc.appearance for nid,desc in self.descriptors_by_node.items()}
        self.exit_routes=(project_exit_routes(self.graph_contract)
                          if self.source_view and self.graph_contract else ())
        self.visible_exit_sites={route.site_node for route in self.exit_routes if not route.folded}
        self.folded_exit_connections={connection.edge_id:connection for connection in
            project_folded_exit_connections(self.graph_contract,self.exit_routes)} if self.exit_routes else {}
        # Clearing the scene destroys its native C++ graphics items. Never
        # retain a hovered/selected wrapper across a rebuild.
        self.last_hover=None
        self._rebuilding=True
        self.graph_scene.clear();self.items_by_id={};self.edge_items=[];self.pending=None;self.preview_path=None
        self.surfaces={}
        bounds=self.graph_scene.sceneRect()
        self.root_surface=GraphSurfaceItem(self,'root',bounds.width(),bounds.height(),
                                           bounds.width(),bounds.height(),root=True)
        self.root_surface.setPos(bounds.topLeft())
        self.graph_scene.addItem(self.root_surface)
        self.surfaces['root']=self.root_surface
        nodes=(graph['nodes'] if graph is not None else
               self.window.settings_nodes() if self.settings_view else [])
        # Structural membership/order now comes from the validated shared
        # descriptor. Legacy source/draft dictionaries supply only presentation
        # details (position, style, Qt widget controls); they cannot invent
        # additional rendered nodes outside the contract.
        if self.graph_contract is not None:
            lookup={n['id']:n for n in nodes}
            missing=[d.id for d in self.graph_contract.nodes if d.id not in lookup]
            if missing:
                raise ContractError('Renderer node source differs from validated graph: '+', '.join(missing[:3]))
            nodes=[lookup[d.id] for d in self.graph_contract.nodes]
        if self.source_view and graph is not None:
            for group in graph.get('scope_regions',[]):
                rect=QGraphicsRectItem(QRectF(group['x'],group['y'],group['w'],group['h']))
                rect.setPen(QPen(qcolor('#326e91'),1.5,Qt.PenStyle.DashLine))
                rect.setBrush(QBrush(QColor(18,52,73,20)))
                rect.setZValue(-12);self.graph_scene.addItem(rect)
                label=QGraphicsSimpleTextItem(str(group['label']))
                label.setFont(QFont('DejaVu Sans',11,QFont.Weight.Bold))
                label.setBrush(QBrush(qcolor('#9ac9e6')))
                label.setPos(group['x']+15,group['y']+10)
                label.setZValue(-11);self.graph_scene.addItem(label)
        if ((self.source_view or self.resource_view) and graph is not None
                and graph.get('presentation')=='composite'):
            # Parent each node directly to the ONE authoritative definition's
            # graphic. A child position is in its owner's local coordinates.
            # Reparenting is Qt's native scene-graph composition, not a
            # nested graphics view or duplicate semantic graph.
            ordered=sorted(nodes,key=lambda n:n.get('containing_scope','module').count('/'))
            owner_item={}
            for data in ordered:
                card=NodeItem(self.window,data,self,self.settings_view)
                card.setZValue(5)  # Source cards sit above their scope's wires.
                owner=owner_item.get(data.get('containing_scope'))
                surface=owner.surface if owner is not None and owner.surface is not None else self.root_surface
                card.setParentItem(surface.content)
                if data.get('presentation_hidden'):card.setVisible(False)
                # Root content coordinates are local to the root item's scene
                # origin; parent-local coordinates are those of the child graph.
                if surface.is_root:
                    card.setPos(float(data['x'])-bounds.x(),float(data['y'])-bounds.y())
                else:
                    card.setPos(float(data['x']),float(data['y']))
                self.items_by_id[data['id']]=card
                if card.surface:
                    owner_item[card.surface.graph_id]=card
                    self.surfaces[card.surface.graph_id]=card.surface
        else:
            for data in nodes:
                card=NodeItem(self.window,data,self,self.settings_view)
                card.setParentItem(self.root_surface.content)
                card.setPos(float(data.get('x',100))-bounds.x(),float(data.get('y',100))-bounds.y())
                self.items_by_id[data['id']]=card
        for card in self.items_by_id.values():
            parent=card.parentItem()
            if isinstance(parent,GraphContentItem):
                surface=parent.surface
                key=self.graph_camera_key(surface.graph_id)
                if self.window._front_nodes.get(key)==card.data['id']:
                    card.setZValue(40)
        self._rebuilding=False
        self.update_edges()
        self.graph_scene.update()
        self.overview.update()  # The visible node extent may change on any route/rebuild.
        if self.source_view and hasattr(self.window,'operation_entries') and self.window.current_canvas() is self:
            self.window._refresh_operation_library()

    def update_edges(self):
        for item in self.edge_items:
            if item.scene():item.scene().removeItem(item)
        self.edge_items=[]
        if self.settings_view:return
        # The descriptor, node items and raw edge metadata must all come
        # from the SAME rebuild revision. Window-level resource/source aliases
        # may point at another tab by the time Qt delivers a resize callback.
        edges=(self._render_graph['edges'] if self._render_graph is not None else [])
        # Use the normalized descriptors as the canonical edge membership,
        # relation, and provenance source. Legacy dicts retain layout-only
        # details, such as the preexisting explicit loopback hint.
        if self.graph_contract is not None:
            edges=validated_edge_payloads(self.graph_contract,self._render_graph)
            verified_by_id={d.id:d for d in self.graph_contract.edges}
        else:
            verified_by_id={}
        for edge in edges:
            # A definition-to-call reference is not a runtime output wire.
            # Retain it in analysis; don't paint it as a normal data edge.
            if self.source_view and edge.get('relation')=='call' and self.window.source_detail=='readable':
                continue
            a=self.items_by_id.get(edge['source']);b=self.items_by_id.get(edge['target'])
            if not a or not b:continue
            folded=self.folded_exit_connections.get(edge['id'])
            if not b.isVisible() and folded is None:continue
            # A folded RETURN has no card. Only validated incoming source
            # edges may be redirected to the function's existing interface.
            if b.data.get('terminal_boundary_owner') and folded is None:continue
            # The only hidden node allowed to source a visible connection is
            # a formal parameter with an exact inner boundary-port mirror.
            # All other hidden nodes belong to collapsed code regions.
            hidden_parameter=(a.data.get('presentation_hidden') and
                              a.data.get('source_kind')=='param' and
                              a.data.get('containing_scope') in self.surfaces)
            if not a.isVisible() and not hidden_parameter:continue
            src=next((p for p in a.ports if p.data['id']==edge['sourcePort']),None)
            dst=next((p for p in b.ports if p.data['id']==edge['targetPort']),None)
            if not src or not dst:continue
            if folded is not None:
                owner=self.items_by_id.get(folded.route.owner_node)
                if owner is None or owner.surface is None:continue
                if folded.facet=='value':
                    dst=next((p for p in owner.ports if
                              p.data['id']==folded.route.value_port),None)
                else:
                    dst=next((lane for lane in owner.exit_lanes if
                              lane.exit_spec.control_anchor_id==folded.route.control_anchor),None)
                if dst is None:continue
            if a.data.get('presentation_hidden') and a.data.get('source_kind')=='param':
                parent_surface=self.surfaces.get(a.data.get('containing_scope'))
                owner=parent_surface.parentItem() if parent_surface else None
                if isinstance(owner,NodeItem):
                    label=src.data.get('label')
                    src=next((p for p in owner.inner_ports
                              if p.direction=='inputs' and p.data.get('label')==label),src)
            def is_inside(node,surface):
                item=node.parentItem()
                while item is not None:
                    if item is surface.content:return True
                    item=item.parentItem()
                return False
            # Cross a composite interface at its INNER port mirror whenever
            # the edge's other endpoint belongs to that composite's body.
            # Both mirrors represent the exact same source port identity.
            if a.surface and is_inside(b,a.surface):
                src=next((p for p in a.inner_ports if p.data['id']==edge['sourcePort']),src)
            if b.surface and is_inside(a,b.surface):
                dst=next((p for p in b.inner_ports if p.data['id']==edge['targetPort']),dst)
            p1=src.mapToScene(QPointF(0,0));p2=dst.mapToScene(QPointF(0,0))
            def graph_ancestors(item):
                current=item
                while current is not None:
                    if isinstance(current,BoundaryPortItem):
                        # Inner boundary anchors belong visually to the graph
                        # CONTENT for wiring, while remaining geometrically
                        # fixed on the unscaled viewport edge.
                        yield current.parentItem().content
                    if isinstance(current,GraphContentItem):yield current
                    current=current.parentItem()
            a_graphs=list(graph_ancestors(src));b_graphs=set(graph_ancestors(dst))
            # A folded RETURN belongs to the function's CHILD graph. The
            # root/parent layer paints under the composite's solid background
            # and made both real return wires disappear in v2.5.
            common=(owner.surface.content if folded is not None else
                    next((graph for graph in a_graphs if graph in b_graphs),None))
            if common is not None:
                p1=common.mapFromScene(p1)
                p2=common.mapFromScene(p2)
            path=(self.make_loopback_curve(p1,p2) if
                  self.source_view and edge.get('relation')=='control' and
                  edge.get('targetPort','').endswith(':repeat') else self.make_curve(p1,p2))
            item=QGraphicsPathItem(path,common) if common is not None else QGraphicsPathItem(path)
            # All relation styling comes from ONE graph-independent resolver.
            # Cross-surface wires remain visible but never paint over node cards.
            same_graph=(folded is not None or
                        next(graph_ancestors(src),None) is next(graph_ancestors(dst),None))
            style=(exit_edge_style(folded.facet) if folded is not None else
                   edge_style(edge.get('relation','data'),crosses_surface=not same_graph))
            item.setPen(QPen(qcolor(style.color),style.width,
                             Qt.PenStyle.DashLine if style.dashed else Qt.PenStyle.SolidLine))
            item.setOpacity(style.opacity)
            item.setZValue(style.z)
            item.setFlag(item.GraphicsItemFlag.ItemIsSelectable,not self.source_view)
            item.setData(0,edge['id'])
            descriptor=verified_by_id.get(edge['id'])
            if descriptor is not None and descriptor.evidence:
                import html
                evidence='\n'.join(f"{p.path}:{p.line}: {p.syntax}"
                                   for p in descriptor.evidence[:6])
                item.setToolTip('<pre>'+html.escape(
                    descriptor.relation+' · '+descriptor.certainty+'\n'+evidence)+'</pre>')
            if item.scene() is None:self.graph_scene.addItem(item)
            self.edge_items.append(item)
        # Normal function returns are one semantic exit with two separately
        # drawn facets. Each visible RETURN card owns the actual right-edge
        # anchors; all route ownership and target identities come from the
        # validated, immutable descriptor, not heuristics in the renderer.
        if (self.source_view and self.window.source_detail=='readable' and
                self.graph_contract is not None):
            for route in self.exit_routes:
                if route.folded:continue
                owner=self.items_by_id.get(route.owner_node)
                site=self.items_by_id.get(route.site_node)
                if owner is None or site is None or not owner.isVisible() or not site.isVisible():
                    continue
                lane=next((x for x in owner.exit_lanes if
                           x.exit_spec.control_anchor_id==route.control_anchor),None)
                if lane is None:continue
                facets=(('control',site.return_facets.get('control'),lane),
                        ('value',site.return_facets.get('value'),
                         next((p for p in owner.ports if p.data['id']==route.value_port),None)))
                for facet_kind,source_pin,destination_pin in facets:
                    if source_pin is None or destination_pin is None:continue
                    start=source_pin.mapToScene(QPointF(0,0))
                    finish=destination_pin.mapToScene(QPointF(0,0))
                    # A return's owning function graph (not the root scene)
                    # paints this source-backed nonlocal route. A nested IF
                    # is a different child viewport; its nonlocal exit must
                    # remain legible over that viewport, not under its frame.
                    common=owner.surface.content
                    start=common.mapFromScene(start)
                    finish=common.mapFromScene(finish)
                    item=QGraphicsPathItem(self.make_curve(start,finish),common)
                    cross_region=(site.parentItem() is not common)
                    style=exit_edge_style(facet_kind,crosses_region=cross_region)
                    item.setPen(QPen(qcolor(style.color),style.width))
                    item.setOpacity(style.opacity)
                    item.setZValue(style.z)
                    item.setToolTip('RETURN · '+('completion' if facet_kind=='control' else 'typed result')+
                                    ' · source-backed exit')
                    item.setData(0,'exit-'+facet_kind+':'+route.site_node)
                    item.setFlag(item.GraphicsItemFlag.ItemIsSelectable,False)
                    if item.scene() is None:self.graph_scene.addItem(item)
                    self.edge_items.append(item)

    @staticmethod
    def make_curve(a,b):
        path=QPainterPath(a);spread=max(60,abs(b.x()-a.x())*.4)
        path.cubicTo(a+QPointF(spread,0),b-QPointF(spread,0),b)
        return path

    @staticmethod
    def make_loopback_curve(a,b):
        """Route repeat flow around nodes, not through their centers.

        Same graph/control relationship; this is presentation only. The
        detour recalculates when either node moves and uses no extra node.
        """
        top=min(a.y(),b.y())-max(85,min(190,abs(a.x()-b.x())*.22+65))
        path=QPainterPath(a)
        path.cubicTo(QPointF(a.x()+55,a.y()),QPointF(a.x()+65,top),QPointF(a.x()+5,top))
        path.lineTo(QPointF(b.x()-70,top))
        path.cubicTo(QPointF(b.x()-95,top),QPointF(b.x()-75,b.y()),b)
        return path

    def find_port(self,pos):
        for item in self.items(pos):
            if isinstance(item,PortItem) and item.shape().contains(item.mapFromScene(self.mapToScene(pos))):return item
        return None

    def find_boundary_port(self,pos):
        # A boundary anchor is the very same semantic port as its external
        # mirror. The mapping module decides whether it is an editable Python
        # parameter/return; the Qt renderer only performs hit testing.
        for item in self.items(pos):
            if (isinstance(item,BoundaryPortItem) and
                    item.boundingRect().contains(item.mapFromScene(self.mapToScene(pos)))):
                return item
        return None

    def _pan_drag(self,surface,previous,current):
        # One camera owner for right/middle drags at every graph depth.
        if surface is not None and not surface.is_root:
            previous_local=surface.mapFromScene(self.mapToScene(previous))
            current_local=surface.mapFromScene(self.mapToScene(current))
            surface.pan_by(current_local.x()-previous_local.x(),
                           current_local.y()-previous_local.y())
        else:
            delta=current-previous
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value()-delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value()-delta.y())
            self._save_root_view()

    def _blank_graph_at(self,pos):
        """Return the graph for blank-space dragging, excluding actual nodes.

        An expanded function's body belongs to the INNER graph, but its
        header/border belongs to the parent graph. No ad hoc node-type rules.
        """
        graph=self.nested_surface_at(pos) or self.root_surface
        scene_pos=self.mapToScene(pos)
        for item in self.items(pos):
            if isinstance(item,PortItem):return None
            if isinstance(item,NodeItem):
                if item.parentItem() is graph.content:
                    return None
                # This is the enclosing composite under the child viewport;
                # treat the background as part of the child graph.
                if (item.surface is graph and
                        graph.boundingRect().contains(graph.mapFromScene(scene_pos))):
                    continue
                return None
            if isinstance(item,QGraphicsPathItem) and item.flags() & item.GraphicsItemFlag.ItemIsSelectable:
                return None
        return graph

    def _corner_target(self,pos):
        if self.find_port(pos) is not None or self.find_boundary_port(pos) is not None:
            return None
        scene=self.mapToScene(pos)
        for item in self.items(pos):
            if not isinstance(item,NodeItem) or not item.region:continue
            corner=item._resize_corner(item.mapFromScene(scene))
            if corner:return item,corner
        return None

    def _show_graph_context(self,pos,global_pos):
        # Qt item context menus retain ownership of node-specific commands.
        # Blank Python space uses the existing adapter-qualified search.
        if self.program_view:
            self.program_workspace.context_menu(global_pos,
                node_id=next((n.data['id'] for n in self.items(pos) if isinstance(n,NodeItem)),None),
                edge_id=next((item.data(0) for item in self.items(pos)
                              if isinstance(item,QGraphicsPathItem) and item.data(0)),None),
                scene_pos=self.mapToScene(pos))
            return
        if self.resource_view and self.graph_contract is not None:
            edge_id=next((item.data(0) for item in self.items(pos)
                          if isinstance(item,QGraphicsPathItem) and item.data(0)),None)
            if edge_id is not None:
                menu=QMenu(self)
                menu.addAction('Inspect file relationship',
                    lambda eid=edge_id:self.window.show_resource_relationship(self,eid))
                menu.addAction('Open source file',
                    lambda eid=edge_id:self.window.open_resource_relationship_endpoint(self,eid,'source'))
                menu.addAction('Open target file',
                    lambda eid=edge_id:self.window.open_resource_relationship_endpoint(self,eid,'target'))
                menu.addSeparator()
                menu.addAction('Focus relationships of source',
                    lambda eid=edge_id:self.window.focus_resource_relationship_endpoint(self,eid,'source'))
                menu.addAction('Focus relationships of target',
                    lambda eid=edge_id:self.window.focus_resource_relationship_endpoint(self,eid,'target'))
                menu.exec(global_pos)
                return
        if self.source_view and self.find_port(pos) is None and not any(
                isinstance(item,NodeItem) for item in self.items(pos)):
            self.window.open_creation_menu(self,screen_pos=global_pos)
            return
        context=QContextMenuEvent(QContextMenuEvent.Reason.Mouse,pos,global_pos)
        super().contextMenuEvent(context)

    def contextMenuEvent(self,event):
        # Some platforms generate context-menu events on right press, others
        # on right release. Do not let either open a menu during pan drag.
        # Actual click menus are dispatched exactly once at mouse release.
        if self.right_pan is not None or (self._suppress_native_context and
                event.reason()==QContextMenuEvent.Reason.Mouse):
            event.accept();return
        self._show_graph_context(event.pos(),event.globalPos())
        event.accept()

    def _source_connection_check(self,source_id,source_port,target_id,target_port):
        """One actual AST lowering determines whether a Python wire can land."""
        if (not self.source_view or self is not self.window.current_canvas()
                or not self.window._qualified_source_context()):
            return ConnectionCheck(False,'Select the owning saved Python source tab')
        return inspect_connection(self.window.python_doc,source_id,source_port,
                                  target_id,target_port)

    def _drag_target(self,pos):
        """Normalize a visible pin or return boundary to an authored input."""
        target=self.find_port(pos)
        if target is not None and target.direction=='inputs':
            return (target.node.data['id'],target.data['id'],target)
        if not self.source_view or self.window.source_graph is None:return None
        boundary=self.find_boundary_port(pos)
        if boundary is not None and boundary.direction=='outputs':
            try:
                node_id,port=terminal_return_target(self.window.source_graph,
                        boundary.node.data['id'],boundary.data['id'])
            except BoundaryEditError:return None
            return node_id,port,None
        if target is not None and target.direction=='outputs' and any(
                route.kind=='return' and route.value_port==target.data['id']
                for route in (target.node.interface.exits if target.node.interface else ())):
            try:
                node_id,port=terminal_return_target(self.window.source_graph,
                        target.node.data['id'],target.data['id'])
            except BoundaryEditError:return None
            return node_id,port,None
        return None

    def _start_source_compatibility_preview(self):
        """Preflight visible inputs once per gesture, not per mouse movement."""
        self.connection_hints.clear();self._connection_hover=None
        if not self.pending or not self.source_view:return
        source_id,source_port,_=self.pending
        # A bounded batch keeps huge documents interactive. Remaining
        # destinations are checked once on first hover and then cached.
        for card in self.items_by_id.values():
            if not card.isVisible():continue
            for port in card.ports:
                if port.direction!='inputs':continue
                if len(self.connection_hints)>=24:break
                key=(card.data['id'],port.data['id'])
                self.connection_hints[key]=self._source_connection_check(
                    source_id,source_port,*key)
            if len(self.connection_hints)>=24:break
        self.update_port_appearance()

    def _update_source_compatibility_hover(self,pos):
        if not self.source_view or not self.pending:return
        destination=self._drag_target(pos)
        if destination is None:
            self._connection_hover=None
            return
        node_id,port_id,_=destination
        key=(node_id,port_id)
        if key!=self._connection_hover:
            self._connection_hover=key
            if key not in self.connection_hints:
                self.connection_hints[key]=self._source_connection_check(
                    self.pending[0],self.pending[1],*key)
                self.update_port_appearance()
            result=self.connection_hints[key]
            self.setToolTip(('Compatible: ' if result.allowed else 'Not connectable: ')+result.reason)
            self.window.statusBar().showMessage(
                ('Python source connection: ' if result.allowed else 'Python connection refused: ')
                +result.reason,3000)

    def mousePressEvent(self,event):
        if event.button()==Qt.MouseButton.RightButton:
            # Blueprint convention: right-drag pans; right-click opens a menu.
            # Use the same selected-region camera routing as middle-pan.
            self._suppress_native_context=False
            self.right_pan=(self.navigation_surface(event.pos(),event.modifiers()),
                            event.pos(),event.pos(),False)
            event.accept();return
        if event.button()==Qt.MouseButton.LeftButton:
            scene=self.mapToScene(event.pos())
            for hit in self.items(event.pos()):
                if isinstance(hit,NodeItem) and hit._toggle_hit(hit.mapFromScene(scene)):
                    self._activate_node_layer(hit)
                    hit.toggle_region();event.accept();return
            # Selection and expansion lift the current composite AND its
            # ancestors; they never shift any neighboring node positions.
            for hit in self.items(event.pos()):
                if isinstance(hit,NodeItem):
                    self._activate_node_layer(hit);break
                if isinstance(hit,PortItem):
                    self._activate_node_layer(hit.node);break
            target=self._corner_target(event.pos())
            if target:
                card,corner=target
                parent=card.parentItem()
                start=parent.mapFromScene(self.mapToScene(event.pos())) if parent else self.mapToScene(event.pos())
                self.corner_resize=(card,corner,start,card.pos(),
                                    card.region['viewport_width'],card.region['viewport_height'])
                event.accept();return
        if event.button()==Qt.MouseButton.MiddleButton:
            self.middle_pan=(self.navigation_surface(event.pos(),event.modifiers()),event.pos())
            event.accept();return
        if event.button()==Qt.MouseButton.LeftButton and self.source_view and self.window.source_graph:
            anchor=self.find_boundary_port(event.pos())
            if anchor is not None and anchor.direction=='inputs':
                try:
                    source_id,source_port=parameter_source(self.window.source_graph,
                        anchor.node.data['id'],anchor.data['id'])
                except BoundaryEditError:
                    pass  # A loop/body port is not a function parameter.
                else:
                    self.pending=(source_id,source_port,anchor.mapToScene(QPointF(0,0)))
                    self.preview_path=QGraphicsPathItem()
                    self.preview_path.setPen(QPen(qcolor('#f8ca6c'),2,Qt.PenStyle.DashLine))
                    self.preview_path.setZValue(-1);self.graph_scene.addItem(self.preview_path)
                    self._start_source_compatibility_preview()
                    self.update_port_appearance();event.accept();return
        if event.button()==Qt.MouseButton.LeftButton and not self.settings_view and not self.resource_view:
            item=self.find_port(event.pos())
            if item and item.direction=='outputs' and (
                not self.source_view or item.node.data.get('source_kind') in ('literal','param') or
                (item.node.data.get('source_kind')=='assignment' and
                 item.node.data.get('binding_write_mode') in ('initial','reassign'))):
                self.pending=(item.node.data['id'],item.data['id'],item.mapToScene(QPointF(0,0)))
                self.preview_path=QGraphicsPathItem()
                self.preview_path.setPen(QPen(qcolor('#f8ca6c'),2,Qt.PenStyle.DashLine))
                self.preview_path.setZValue(-1);self.graph_scene.addItem(self.preview_path)
                self._start_source_compatibility_preview()
                self.update_port_appearance();event.accept();return
        if event.button()==Qt.MouseButton.LeftButton:
            graph=self._blank_graph_at(event.pos())
            if graph is not None:
                # Blueprint convention: ordinary left-drag selects. Shift adds,
                # Ctrl toggles; neither mutates the source/graph contract.
                origin=graph.content.mapFromScene(self.mapToScene(event.pos()))
                band=QGraphicsRectItem(QRectF(origin,origin),graph.content)
                band.setZValue(90)
                band.setPen(QPen(qcolor('#53cae9'),1,Qt.PenStyle.DashLine))
                band.setBrush(QBrush(QColor(48,155,205,45)))
                modifier=('toggle' if event.modifiers() & Qt.KeyboardModifier.ControlModifier else
                          'add' if event.modifiers() & Qt.KeyboardModifier.ShiftModifier else 'replace')
                self.marquee=(graph,origin,band,modifier)
                event.accept();return
        super().mousePressEvent(event)

    def mouseMoveEvent(self,event):
        if self.right_pan is not None:
            graph,start,previous,dragged=self.right_pan
            moved=(event.pos()-start).manhattanLength()>=QApplication.startDragDistance()
            if dragged or moved:
                self._pan_drag(graph,previous if dragged else start,event.pos())
                dragged=True
            self.right_pan=(graph,start,event.pos(),dragged)
            event.accept();return
        if self.corner_resize is not None:
            card,corner,start,origin,width,height=self.corner_resize
            parent=card.parentItem()
            scene=self.mapToScene(event.pos())
            now=parent.mapFromScene(scene) if parent else scene
            dx=now.x()-start.x();dy=now.y()-start.y()
            new_w,new_h,shift_x,shift_y=resize_rectangle(corner,width,height,dx,dy)
            card._resize_graph_to(new_w,new_h)
            card.setPos(QPointF(origin.x()+shift_x,origin.y()+shift_y))
            event.accept();return
        if self.marquee is not None:
            graph,start,band,modifier=self.marquee
            current=graph.content.mapFromScene(self.mapToScene(event.pos()))
            band.setRect(QRectF(start,current).normalized())
            event.accept();return
        if self.middle_pan is not None:
            surface,previous=self.middle_pan
            self.middle_pan=(surface,event.pos())
            self._pan_drag(surface,previous,event.pos())
            event.accept();return
        if self.pending:
            self._update_source_compatibility_hover(event.pos())
            self.preview_path.setPath(self.make_curve(self.pending[2],self.mapToScene(event.pos())))
            event.accept();return
        # Qt's own hit-testing respects the clipping boundaries of nested
        # GraphSurfaceItems. Scanning raw node rectangles doesn't, and would
        # reveal hidden pin labels from nodes outside their viewport.
        active=next((item for item in self.items(event.pos())
                     if isinstance(item,NodeItem)),None)
        if active is not self.last_hover:
            if self.last_hover:self.last_hover.hovered=False;self.last_hover.update();self.last_hover.update_port_items()
            self.last_hover=active
            if active:active.hovered=True;active.update();active.update_port_items()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self,event):
        if self.right_pan is not None and event.button()==Qt.MouseButton.RightButton:
            graph,start,previous,dragged=self.right_pan
            self.right_pan=None
            if (event.pos()-start).manhattanLength()>=QApplication.startDragDistance():
                if not dragged:self._pan_drag(graph,start,event.pos())
                dragged=True
            # Suppress a subsequent platform-generated native mouse context
            # event. The next right press resets this transient gesture flag.
            self._suppress_native_context=True
            if not dragged:self._show_graph_context(event.pos(),event.globalPosition().toPoint())
            event.accept();return
        if self.corner_resize is not None and event.button()==Qt.MouseButton.LeftButton:
            self.corner_resize=None;event.accept();return
        if self.marquee is not None and event.button()==Qt.MouseButton.LeftButton:
            graph,start,band,modifier=self.marquee
            rect=band.rect()
            # Selection is scoped to one canvas graph and its immediate nodes.
            # An expanded child's internal nodes cannot be hit through its
            # enclosing surface, even where their rectangles overlap.
            hits={card for card in self.items_by_id.values()
                  if card.isVisible() and card.parentItem() is graph.content and
                  rect.intersects(card.boundingRect().translated(card.pos()))}
            selected=marquee_selection(set(self.graph_scene.selectedItems()),hits,modifier)
            self.graph_scene.removeItem(band)
            self.marquee=None
            for item in tuple(self.graph_scene.selectedItems()):
                if item not in selected:item.setSelected(False)
            for item in hits:
                if item in selected:item.setSelected(True)
            event.accept();return
        if self.middle_pan is not None and event.button()==Qt.MouseButton.MiddleButton:
            self.middle_pan=None;event.accept();return
        if self.pending and event.button()==Qt.MouseButton.LeftButton:
            src,out,_=self.pending
            target=self.find_port(event.pos())
            boundary=(self.find_boundary_port(event.pos()) if self.source_view else None)
            # Remove the preview path before opening a modal source diff, or a
            # successful save/reload could destroy the C++ scene items it owns.
            self.cancel_pending()
            if self.source_view:
                destination=self._drag_target(event.pos())
                if destination is None:
                    self.window.open_creation_menu(self,pin=(src,out),
                        screen_pos=event.globalPosition().toPoint())
                else:
                    node_id,port_id,_=destination
                    check=self._source_connection_check(src,out,node_id,port_id)
                    if check.allowed:
                        # Identical AST proposal as hover, with mandatory diff
                        # review and stale-file checks before the atomic save.
                        self.window.review_source_proposal(check.proposal)
                    else:
                        self.window.report('Python connection refused: '+check.reason)
            elif self.program_view:
                if target and target.direction=='inputs':
                    self.program_workspace.connect(src,out,target.node.data['id'],target.data['id'])
                else:
                    self.program_workspace.report('Drag onto an input pin to connect')
            elif target and target.direction=='inputs':
                if self.window.commit_draft_change(
                        lambda draft: m.connect(draft,src,out,target.node.data['id'],target.data['id']),
                        inspector_node=None):
                    self.window.report('Connection created')
            else:
                self.window.report('Drag an output to a compatible input pin or its label chip')
            self.update_edges();event.accept();return
        super().mouseReleaseEvent(event)

    def cancel_pending(self):
        if self.preview_path is not None and self.preview_path.scene():self.graph_scene.removeItem(self.preview_path)
        self.pending=None;self.preview_path=None
        self.connection_hints.clear();self._connection_hover=None
        self.setToolTip('')
        self.update_port_appearance()

    def update_port_appearance(self):
        for node in self.items_by_id.values():node.update_port_items()

    def frame_node(self, card):
        if not isinstance(card,NodeItem) or not card.scene() or not card.isVisible():
            return False
        rect=card.sceneBoundingRect()
        return self._frame_rects([(rect.x(),rect.y(),rect.width(),rect.height())],min_zoom=.4)

    def frame_visible_nodes(self):
        # Frame and overview use the same top-level visible node set.
        return self._frame_rects(self._visible_root_rects())

    def _frame_rects(self, rects, *, min_zoom=.3):
        view=self.viewport().rect()
        target=frame_visible_bounds(rects,view.width(),view.height(),min_zoom=min_zoom)
        if target is None:
            return False
        cx,cy,zoom,fully_fits=target
        self.resetTransform()
        self.scale(zoom,zoom)
        self.centerOn(cx,cy)
        self._save_root_view()
        if not fully_fits:
            self.window.report('Large graph: framed at readable zoom. Focus a scope (Ctrl+double-click) to inspect its nodes.')
        return True

    def _save_root_view(self):
        center=self.mapToScene(self.viewport().rect().center())
        self.window._graph_cameras[self.graph_camera_key('@root-view')]=(
            center.x(),center.y(),self.transform().m11())
        self.window._queue_presentation_save()
        self.overview.update()

    def _stored_root_view(self):
        camera_key=self.graph_camera_key('@root-view')
        view=self.window._graph_cameras.get(camera_key)
        if view is None and (self.resource_view or (self.source_view and
                self.window.source_view_mode=='whole')):
            # Read the legacy whole-file/directory camera when migrating. All
            # new saves use the session-qualified key; no second state owner.
            view=self.window._graph_cameras.get((camera_key[0],'@root-view'))
        return view

    def has_saved_root_view(self):
        return self._stored_root_view() is not None

    def restore_root_view(self):
        view=self._stored_root_view()
        if view:
            self.resetTransform()
            # Old Fit Graph saved extreme zoom values that made wheel zoom
            # unresponsive; clamp these presentation-only legacy cameras.
            zoom=max(.25,min(2.25,view[2]))
            self.scale(zoom,zoom)
            self.centerOn(view[0],view[1])

    def wheelEvent(self,event):
        fac=1.12 if event.angleDelta().y()>0 else 1/1.12
        nested=self.nested_surface_at(event.position().toPoint())
        if nested is not None:
            nested.zoom_by(fac,self.mapToScene(event.position().toPoint()))
        elif .25<=self.transform().m11()*fac<=2.25:
            self.scale(fac,fac)
            self._save_root_view()
        event.accept()

    def focusNextPrevChild(self,next):
        # Qt normally consumes Tab for focus traversal before keyPressEvent.
        # Reserve it for creation only on a qualified, focused Python canvas.
        if (next and self.source_view and
                self.window._qualified_source_context()):
            return False
        return super().focusNextPrevChild(next)

    def keyPressEvent(self,event):
        if self.program_view:
            workspace=self.program_workspace
            if event.key()==Qt.Key.Key_Z and event.modifiers() in (
                    Qt.KeyboardModifier.ControlModifier,
                    Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier):
                if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:workspace.redo()
                else:workspace.undo()
                event.accept();return
            if event.key()==Qt.Key.Key_Delete:
                workspace.delete_selected()
                event.accept();return
            if event.key()==Qt.Key.Key_Tab:
                workspace.choose_node()
                event.accept();return
        # Same camera authority as the toolbar's 'Frame visible nodes'.
        # A selected node is the preferred target, mirroring Blueprint Home.
        if (self.source_view and event.key()==Qt.Key.Key_Z and
                event.modifiers() in (Qt.KeyboardModifier.ControlModifier,
                                      Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)):
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self.window.redo_source_edit()
            else:
                self.window.undo_source_edit()
            event.accept();return
        if event.key()==Qt.Key.Key_Home:
            selection=[i for i in self.graph_scene.selectedItems() if isinstance(i,NodeItem)]
            if selection and self.frame_node(selection[-1]):
                event.accept();return
            self.frame_visible_nodes();event.accept();return
        # Quick creation uses the *existing* adapter-filtered search and
        # source-diff pipeline. No Qt-defined operation catalog is introduced.
        if (event.key()==Qt.Key.Key_Tab and self.source_view and
                self.window._qualified_source_context()):
            self.window.open_creation_menu(self)
            event.accept();return
        if event.key()==Qt.Key.Key_Space and not event.isAutoRepeat():
            self.space_held=True;self.update_port_appearance();event.accept();return
        if event.key()==Qt.Key.Key_Escape and self.pending:self.cancel_pending();event.accept();return
        if event.key()==Qt.Key.Key_Delete and not self.settings_view and not self.source_view and not self.resource_view:
            selected=list(self.graph_scene.selectedItems())
            node_ids={item.data['id'] for item in selected if isinstance(item,NodeItem)}
            edge_ids={item.data(0) for item in selected
                      if isinstance(item,QGraphicsPathItem) and item.data(0)}
            if node_ids or edge_ids:
                def remove_selected(draft):
                    for node_id in node_ids:m.remove_node(draft,node_id)
                    draft['edges'][:]=[e for e in draft['edges'] if e['id'] not in edge_ids]
                self.window.commit_draft_change(remove_selected,inspector_node=None)
            event.accept();return
        super().keyPressEvent(event)

    def keyReleaseEvent(self,event):
        if event.key()==Qt.Key.Key_Space and not event.isAutoRepeat():
            self.space_held=False;self.update_port_appearance();event.accept();return
        super().keyReleaseEvent(event)

    def focusOutEvent(self,event):
        self.space_held=False;self.update_port_appearance();super().focusOutEvent(event)

    def _activate_node_layer(self,card):
        # All graph depths use one stacking policy. Raise only the selected
        # sibling and each containing composite; never auto-arrange neighbors.
        current=card
        while isinstance(current,NodeItem):
            container=current.parentItem()
            if isinstance(container,GraphContentItem):
                for sibling in container.childItems():
                    if isinstance(sibling,NodeItem):
                        sibling.setZValue(40 if sibling is current else 5)
                surface=container.surface
                self.window._front_nodes[self.graph_camera_key(surface.graph_id)]=current.data['id']
                self.window._queue_presentation_save()
                current=surface.parentItem() if not surface.is_root else None
            else:break

    def selection_changed(self):
        cards=[i for i in self.graph_scene.selectedItems() if isinstance(i,NodeItem)]
        if self.program_view:
            if cards:
                self.program_workspace.report('Selected '+cards[-1].data['title'])
            return
        if cards:
            card=cards[-1]
            self._activate_node_layer(card)
            self.window.show_inspector(card)
        elif self.resource_view and not self._rebuilding:
            edges=[i for i in self.graph_scene.selectedItems()
                   if isinstance(i,QGraphicsPathItem) and i.data(0)]
            if edges:
                self.window.show_resource_relationship(self,edges[-1].data(0))


@dataclass
class GraphTabView:
    """One Qt view surface; routing and camera identity live in GraphViewSession.

    Resource and source tabs share this *presentation* contract. Neither owns
    source bytes or invents a second provider/graph document.
    """
    session_id: str
    page: QWidget
    canvas: GraphCanvas
    toolbar: QToolBar | None = None


@dataclass
class SourceTabView(GraphTabView):
    """Source-specific view preferences; PythonDocument remains authoritative."""
    document: PythonDocument | None = None
    graph: dict | None = None
    detail: str = 'readable'
    expanded: set[str] = field(default_factory=set)
    collapsed: set[str] = field(default_factory=set)
    selected_node: str | None = None
    needs_rebuild: bool = False


@dataclass
class ResourceTabView(GraphTabView):
    """Directory presentation, resolved through the existing resource provider."""
    path: Path | None = None
    graph: dict | None = None
    offset: int = 0
    expanded: set[str] = field(default_factory=set)
    imports: bool = False
    relationship_layers: set[str] = field(default_factory=lambda: {'imports','references'})
    relationship_focus: str | None = None
    relationship_direction: str = 'both'


class ProgramPythonEditDialog(QDialog):
    """Transient generated-source candidate; never a second program authority.

    A real .py opened elsewhere remains owned by SourceDocumentSession. This
    temporary editor holds only a proposed edit against an exact graph revision.
    Import is a proof-gated ProgramGraph transaction; export is an explicit
    exclusive write of unconverted text, never a replacement for graph saving.
    """
    def __init__(self, workspace, source: str, revision: int):
        super().__init__(workspace)
        self.workspace=workspace
        self.base_source=source
        self.base_revision=revision
        self.setObjectName('ProgramPythonEditDialog')
        self.setWindowTitle('Edit generated Python · explicit graph import')
        self.resize(850,610)
        layout=QVBoxLayout(self)
        info=QLabel(f'Graph revision {revision} · generated Python candidate · '
                    'only mapped, supported edits can be imported',self)
        info.setWordWrap(True)
        layout.addWidget(info)
        self.editor=QPlainTextEdit(self)
        self.editor.setObjectName('ProgramPythonEditText')
        self.editor.setPlainText(source)
        self.highlighter=PythonSyntaxHighlighter(self.editor.document())
        layout.addWidget(self.editor,1)
        self.feedback=QLabel('Edit text, then explicitly import or export your draft.',self)
        self.feedback.setWordWrap(True)
        self.feedback.setObjectName('ProgramPythonEditFeedback')
        layout.addWidget(self.feedback)
        buttons=QHBoxLayout()
        for label,object_name,callback in (
                ('Import into Graph','ProgramImportPython',self.import_candidate),
                ('Export Draft As…','ProgramExportPythonDraft',self.export_draft),
                ('Close','ProgramClosePythonEdit',self.reject)):
            button=QPushButton(label,self)
            button.setObjectName(object_name)
            button.clicked.connect(callback)
            buttons.addWidget(button)
        layout.addLayout(buttons)

    def import_candidate(self,checked=False):
        try:
            changed=import_generated_source_edit(
                self.workspace.document,self.base_source,self.editor.toPlainText(),
                expected_revision=self.base_revision)
        except (ProgramGraphError,TypeError,ValueError) as exc:
            self.feedback.setText('Import refused; draft retained: '+str(exc))
            return False
        if changed:
            self.workspace.refresh()
            self.workspace.report('Imported qualified generated-Python edit into graph')
        self.accept()
        return changed

    def export_draft(self,checked=False,*,path=None):
        """Save unsupported/invalid Python without changing graph or existing .py."""
        if path is None:
            path=self.workspace.window._choose_file(
                title='Export generated Python draft as NEW file',
                filters='Python source (*.py)',save=True,
                proposed=Path.home()/'generated-python-draft.py')
            if not path:return False
        candidate=self.editor.toPlainText().encode('utf-8')
        if not candidate or len(candidate)>MAX_PREVIEW_BYTES:
            self.feedback.setText('Export refused: draft is empty or exceeds Python preview limit')
            return False
        try:
            published=create_source_exclusive(Path(path),candidate)
        except (OSError,ValueError) as exc:
            self.feedback.setText('Export refused; draft retained: '+str(exc))
            return False
        self.feedback.setText('Draft exported without graph import: '+str(published))
        return True

    def reject(self):
        if self.editor.toPlainText()!=self.base_source:
            response=QMessageBox.question(self,'Discard generated Python draft?',
                 'This generated Python draft has unimported edits. '
                 'Export it to a new .py file first, or discard the draft?',
                 QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,
                 QMessageBox.StandardButton.No)
            if response!=QMessageBox.StandardButton.Yes:return
        super().reject()


class ProgramWorkspace(QWidget):
    """Thin graph-owned Qt tab. ProgramGraph alone owns edits and persistence."""
    def __init__(self,window,document: ProgramGraph):
        super().__init__(window)
        self.window=window
        self.document=document
        self.current_function=None
        self._source_link=None  # Explicit association, never a competing text owner.
        self._independent_review=None  # Ephemeral UI receipt, NOT a source/graph authority.
        layout=QVBoxLayout(self);layout.setContentsMargins(0,0,0,0);layout.setSpacing(0)
        controls=QHBoxLayout()
        self.functions=QComboBox();self.functions.setObjectName('ProgramFunctionSelector')
        self.functions.currentIndexChanged.connect(self.select_function)
        controls.addWidget(QLabel('Function'))
        controls.addWidget(self.functions,1)
        for text,callback in [('New Function',self.new_function),('Function…',self.function_menu),('Add Node',self.choose_node),
                              ('Undo',self.undo),('Redo',self.redo),('Preview Python',self.preview_python),('Edit Python',self.edit_generated_python),('Link open .py',self.link_python_source),('Review open .py',self.review_linked_python_source),('Import open .py',self.import_linked_python_source),('Publish Python',self.publish_python),('Save',self.save)]:
            button=QPushButton(text,self)
            button.setObjectName('Program'+text.replace(' ',''))
            button.clicked.connect(callback)
            controls.addWidget(button)
        layout.addLayout(controls)
        self.canvas=GraphCanvas(window,program_view=True)
        self.canvas.program_workspace=self
        layout.addWidget(window._graph_page(self.canvas),1)
        self.status=QLabel(self)
        self.status.setObjectName('ProgramGraphStatus')
        layout.addWidget(self.status)
        self.refresh()

    def report(self,message):
        self.window.statusBar().showMessage(str(message),7000)

    def refresh(self):
        functions=self.document.state['functions']
        ids={f['id'] for f in functions}
        if self.current_function not in ids:
            self.current_function=functions[0]['id'] if functions else None
        self.functions.blockSignals(True)
        try:
            self.functions.clear()
            for f in functions:
                signature=', '.join(p['name'] for p in f['parameters'])
                self.functions.addItem(f"{f['name']}({signature})",f['id'])
            index=self.functions.findData(self.current_function)
            self.functions.setCurrentIndex(index)
        finally:
            self.functions.blockSignals(False)
        self.canvas.rebuild()
        state=self.document.state
        issues=sum(1 for item in state['nodes'] if item['function']==self.current_function)
        self.status.setText(f'Graph-owned draft · revision {self.document.revision} · '
                            f'{issues} node(s) · explicit qualification required · '
                            f'{"unsaved" if self.document.dirty else "saved"}')
        if hasattr(self.window,'program_library_entries') and self.window.tabs.currentWidget() is self:
            self.window._refresh_program_library()
        index=self.window.tabs.indexOf(self)
        if index>=0:
            label=self.document.path.name if self.document.path else 'Untitled visual program'
            self.window.tabs.setTabText(index,label+('*' if self.document.dirty else ''))

    def select_function(self,index):
        self.current_function=self.functions.itemData(index) if index>=0 else None
        self.refresh()
        self.canvas.frame_visible_nodes()

    def edit(self,action,*,redraw=True,**kwargs):
        try:
            changed=self.document.edit(self.document.revision,action,**kwargs)
        except (ProgramGraphError,KeyError,TypeError,ValueError) as exc:
            self.report('Graph edit refused: '+str(exc));return False
        if changed and redraw:
            self.refresh()
        return changed

    def new_function(self,checked=False,*,name=None):
        if name is None:
            name,accepted=QInputDialog.getText(self,'Create visual function','Function name:')
            if not accepted:return False
        if self.edit('add_function',name=name):
            self.current_function=self.document.state['functions'][-1]['id']
            self.refresh();return True
        return False

    def function_menu(self,checked=False):
        if self.current_function is None:
            self.report('Create a function first');return False
        menu=QMenu(self)
        actions={menu.addAction(label):action for label,action in (
            ('Rename function','rename'),('Add input parameter','add'),
            ('Rename input parameter','rename_parameter'),
            ('Remove input parameter','remove_parameter'),
            ('Declare integer input','parameter_int'),
            ('Declare Boolean input','parameter_bool'),
            ('Declare integer return','return_int'),
            ('Declare Boolean return','return_bool'),
            ('Review independent .py function','review_independent'),
            ('Review all graph functions in .py','review_independent_all'),
            ('Import reviewed function(s)','import_independent'))}
        chosen=menu.exec(self.mapToGlobal(self.rect().center()))
        action=actions.get(chosen)
        if action=='rename':return self.rename_function()
        if action=='add':return self.add_parameter()
        if action=='review_independent':return self.review_independent_python_function()
        if action=='review_independent_all':return self.review_independent_python_function(function='*')
        if action=='import_independent':return self.import_independent_python_function()
        if action=='rename_parameter':return self.edit_parameter('rename_parameter')
        if action=='remove_parameter':return self.edit_parameter('remove_parameter')
        if action in ('return_int','return_bool'):
            return self.edit('set_return_type',function=self.current_function,
                             type='py:bool' if action=='return_bool' else 'py:int')
        if action in ('parameter_int','parameter_bool'):
            return self.edit_parameter('set_parameter_type',
                     kind='py:bool' if action=='parameter_bool' else 'py:int')
        return False

    def rename_function(self,*,name=None):
        if self.current_function is None:return False
        function=next(f for f in self.document.state['functions'] if f['id']==self.current_function)
        if name is None:
            name,ok=QInputDialog.getText(self,'Rename visual function','Name:',text=function['name'])
            if not ok:return False
        return self.edit('rename_function',function=self.current_function,name=name)

    def add_parameter(self,*,name=None,kind='py:int'):
        if self.current_function is None:return False
        if name is None:
            name,ok=QInputDialog.getText(self,'Add visual function input','Parameter name:')
            if not ok:return False
        return self.edit('add_parameter',function=self.current_function,name=name,type=kind)

    def edit_parameter(self,action,*,parameter=None,name=None,kind='py:int'):
        if self.current_function is None:return False
        function=next(f for f in self.document.state['functions'] if f['id']==self.current_function)
        parameters=function['parameters']
        if not parameters:
            self.report('Function has no parameters');return False
        if parameter is None:
            labels=[p['name'] for p in parameters]
            chosen,ok=QInputDialog.getItem(self,'Function input','Parameter:',labels,0,False)
            if not ok:return False
            parameter=next(p['id'] for p in parameters if p['name']==chosen)
        if action=='rename_parameter':
            selected=next((p for p in parameters if p['id']==parameter),None)
            if selected is None:
                self.report('Missing parameter');return False
            if name is None:
                name,ok=QInputDialog.getText(self,'Rename input','Name:',text=selected['name'])
                if not ok:return False
            return self.edit(action,function=self.current_function,parameter=parameter,name=name)
        if action=='remove_parameter':
            return self.edit(action,function=self.current_function,parameter=parameter)
        if action=='set_parameter_type':
            return self.edit(action,function=self.current_function,parameter=parameter,type=kind)
        self.report('Unsupported function edit');return False

    def edit_literal(self,node_id,*,value_json=None):
        node=next((n for n in self.document.state['nodes'] if n['id']==node_id),None)
        if node is None or node['function']!=self.current_function or node['operation']!='python.literal':
            self.report('Only a draft Literal node can be edited here');return False
        if value_json is None:
            initial=json.dumps(node['properties'].get('value',None),ensure_ascii=False)
            value_json,ok=QInputDialog.getText(self,'Edit literal draft value',
                 'JSON primitive (number, string, true, false, null):',text=initial)
            if not ok:return False
        try:
            value=json.loads(value_json)
        except (ValueError,TypeError) as exc:
            self.report('Invalid JSON primitive: '+str(exc));return False
        if type(value) not in (str,int,float,bool,type(None)):
            self.report('Literal draft accepts only a JSON primitive');return False
        return self.edit('set_property',node=node_id,key='value',value=value)

    def choose_node(self,checked=False,*,operation=None,scene_pos=None,parameter_id=None,callee_id=None,local_id=None):
        if self.current_function is None:
            self.report('Create a function first');return False
        if operation is None:
            operation,accepted=QInputDialog.getItem(self,'New visual operation',
                    'Draft operation:',list(NODE_TEMPLATES),0,False)
            if not accepted:return False
        state=self.document.state
        props={}
        if operation=='python.parameter':
            function=next(f for f in state['functions'] if f['id']==self.current_function)
            if not function['parameters']:
                self.report('Add a function input before creating a Parameter node');return False
            if parameter_id is None:
                labels=[p['name'] for p in function['parameters']]
                name,accepted=QInputDialog.getItem(self,'Parameter reference','Input:',labels,0,False)
                if not accepted:return False
                parameter_id=next(p['id'] for p in function['parameters'] if p['name']==name)
            if not any(p['id']==parameter_id for p in function['parameters']):
                self.report('Unknown function input');return False
            props={'parameter_id':parameter_id}
        elif operation in ('python.call', 'python.call_exec'):
            functions=state['functions']
            if not functions:
                self.report('Create a function before adding a call');return False
            if callee_id is None:
                labels=[f['name'] for f in functions]
                name,accepted=QInputDialog.getItem(self,'Call graph function','Callee:',labels,0,False)
                if not accepted:return False
                callee_id=next(f['id'] for f in functions if f['name']==name)
            target=next((f for f in functions if f['id']==callee_id),None)
            if target is None:
                self.report('Unknown graph function');return False
            if operation=='python.call_exec' and any(p['name']=='exec' for p in target['parameters']):
                self.report('Execution call cannot use a parameter named exec');return False
            props={'callee_id':target['id']}
        elif operation in ASSIGN_OPERATIONS | READ_OPERATIONS:
            required = 'python.local_int' if operation.endswith('_int') else 'python.local_bool'
            options = [node for node in state['nodes'] if
                       node['function'] == self.current_function and node['operation'] == required]
            if not options:
                self.report('Declare a compatible local node first');return False
            if local_id is None:
                labels = [node['id'] for node in options]
                selected, accepted = QInputDialog.getItem(
                    self, 'Local variable reference', 'Local declaration:', labels, 0, False)
                if not accepted:return False
                local_id = selected
            if not any(node['id'] == local_id for node in options):
                self.report('Local declaration belongs to another function or has the wrong type');return False
            props={'local_id':local_id}
        try:
            if operation in ('python.call', 'python.call_exec'):
                ports={'inputs':([{'name':'exec','type':'execution'}] if operation=='python.call_exec' else []) +
                        [{'name':p['name'],'type':p['type']} for p in target['parameters']],
                       'outputs':([{'name':'then','type':'execution','required':False}] if operation=='python.call_exec' else []) +
                        [{'name':'result','type':target['return_type'],'required':False}]}
            else:
                ports=template_ports(operation)
        except ProgramGraphError as exc:
            self.report(str(exc));return False
        position=(scene_pos if scene_pos is not None else QPointF(
            120+len(state['nodes'])*65,120))
        return self.edit('add_node',function=self.current_function,
                         operation=operation,x=round(position.x(),1),y=round(position.y(),1),
                         properties=props,**ports)

    def preview_python(self,checked=False,*,show=True):
        """Explicit, read-only qualification. Never writes or runs generated code."""
        result=preview_python(self.document.state)
        if not show:
            return result
        if result.source is None:
            QMessageBox.warning(self,'Python generation unavailable',
                '\n'.join(result.issues))
            return result
        dialog=QDialog(self)
        dialog.setWindowTitle('Qualified Python preview · not executed or saved')
        dialog.setObjectName('ProgramPythonPreview')
        dialog.resize(800,560)
        layout=QVBoxLayout(dialog)
        editor=QPlainTextEdit(dialog)
        editor.setReadOnly(True)
        editor.setPlainText(result.source)
        editor.setObjectName('GeneratedPythonPreview')
        layout.addWidget(editor)
        close=QPushButton('Close',dialog)
        close.clicked.connect(dialog.accept)
        layout.addWidget(close)
        dialog.exec()
        return result

    def create_python_edit_dialog(self):
        """Bind generated source to the graph revision visible at editor launch."""
        result=preview_python(self.document.state)
        if result.source is None:
            return None
        return ProgramPythonEditDialog(self,result.source,self.document.revision)

    def edit_generated_python(self,checked=False):
        """Open the bounded text-to-graph editor; failed imports keep draft text."""
        dialog=self.create_python_edit_dialog()
        if dialog is None:
            result=preview_python(self.document.state)
            QMessageBox.warning(self,'Generated Python editing unavailable',
                                '\n'.join(result.issues))
            return False
        return dialog.exec()==QDialog.DialogCode.Accepted

    def link_python_source(self,checked=False,*,session=None):
        """Associate an existing, clean .py session with an exact graph baseline.

        The source text stays under SourceDocumentSession. No conversion,
        source overwrite, or automatic import occurs when linking.
        """
        if session is None:
            open_sources=list(self.window._source_documents.values())
            if not open_sources:
                self.report('Open the exact generated .py file in the Python editor first')
                return False
            if len(open_sources)==1:
                session=open_sources[0]
            else:
                names=[str(item.path) for item in open_sources]
                choice,accepted=QInputDialog.getItem(
                    self,'Link open Python document',
                    'Select the source-owned .py document:',names,0,False)
                if not accepted:return False
                session=open_sources[names.index(choice)]
        try:
            link=LinkedPythonSource.attach(self.document,session)
        except (ProgramGraphError,ValueError,TypeError) as exc:
            self.report('Python link refused: '+str(exc))
            return False
        self._source_link=link
        self.report('Linked Python source '+str(session.path)+'; future edits require explicit import')
        self.refresh()
        return True

    def review_linked_python_source(self,checked=False):
        """Display compiler-qualified, read-only proposed changes before import."""
        link=self._source_link
        if link is None:
            self.report('Review refused: link an exact generated .py source first')
            return False
        try:
            review=link.review_edits()
        except (ProgramGraphError,ValueError,TypeError) as exc:
            self.report('Python review refused; source retained: '+str(exc))
            return False
        lines=['Source-to-graph preflight · no files or graphs modified',
               'Source: '+str(link.session.path),
               'Graph revision: '+str(review.graph_revision),
               'The compiler verifies the complete candidate before any import.', '']
        if not review.changes:
            lines.append('No graph operation changes. Source-only comments and formatting stay in the text editor.')
        else:
            lines.append(str(len(review.changes))+' proposed operations:')
            for change in review.changes:
                lines.append('  '+change.function+' / '+change.node_id+' · '+change.action+
                             ' · '+str(change.before)+' → '+str(change.after))
        lines += ['', 'Review is informational. Use Import open .py to requalify and commit atomically.']
        QMessageBox.information(self,'Qualified Python reconciliation review','\n'.join(lines))
        return True

    def import_linked_python_source(self,checked=False):
        """Explicitly reconcile a linked source draft into the graph owner."""
        link=self._source_link
        if link is None:
            self.report('Import refused: link an exact open .py source first')
            return False
        try:
            changed=link.import_edits()
        except (ProgramGraphError,ValueError,TypeError) as exc:
            self.report('Python source import refused; source text retained: '+str(exc))
            return False
        if changed:
            self.refresh()
            self.report('Linked Python edits imported into graph; save source and graph separately')
        else:
            self.report('No new linked Python edits to import')
        return changed

    def review_independent_python_function(self,checked=False,*,session=None,
                                           function=None,show=True):
        """Review explicit graph function(s) from source without creating a link.

        A '*' request means all currently graph-owned function names, with
        zero implicit source matches. Every nonselected source region stays
        opaque. Import requires explicit confirmation and another compiler proof.
        """
        self._independent_review=None
        if session is None:
            available=list(self.window._source_documents.values())
            if not available:
                self.report('Open an independently authored .py document first')
                return False
            if len(available)==1:
                session=available[0]
            else:
                names=[str(owner.path) for owner in available]
                choice,accepted=QInputDialog.getItem(self,'Independent Python function',
                    'Source-owned Python document:',names,0,False)
                if not accepted:return False
                session=available[names.index(choice)]
        if function is None or function=='*':
            names=sorted({item['name'] for item in self.document.state['functions']})
            if not names:
                self.report('Graph has no functions to review')
                return False
            if function=='*':
                function=tuple(names)
            elif len(names)==1:
                function=names[0]
            else:
                choice,accepted=QInputDialog.getItem(self,'Independent Python function',
                    'Graph function to reconcile:',names,0,False)
                if not accepted:return False
                function=choice
        try:
            if isinstance(function,tuple):
                receipt=review_independent_source_functions(self.document,session,function,
                    expected_graph_revision=self.document.revision)
            else:
                receipt=review_independent_source_function(self.document,session,function,
                    expected_graph_revision=self.document.revision)
        except (ProgramGraphError,GraphConflict,TypeError,ValueError) as exc:
            self.report('Independent function review refused: '+str(exc))
            return False
        self._independent_review=(session,receipt)
        if show:
            regions=(receipt.regions if isinstance(receipt,IndependentFunctionsReview)
                     else ((receipt.function,receipt.start_line,receipt.end_line),))
            lines=['Read-only independent Python reconciliation review',
                   'Source: '+str(session.path),
                   'Selected graph functions: '+str(len(regions)),
                   *('  '+name+f' (lines {start}-{end})' for name,start,end in regions),
                   'Other source top-level statements: '+str(receipt.unmodeled_top_level),
                   'Unmodeled source is NOT represented by the graph and will not change.',
                   '',str(len(receipt.changes))+' compiler-proven changes:']
            qualified_lines={(fn,node):line for fn,node,line in receipt.change_lines}
            spans={(fn,node):(line,col,end_line,end_col)
                   for fn,node,line,col,end_line,end_col in receipt.change_spans}
            for change in receipt.changes:
                identity=(change.function,change.node_id)
                line=qualified_lines.get(identity)
                span=spans.get(identity)
                location=(f' · source line {span[0]}, columns {span[1]}-{span[3]}'
                          if span is not None and span[0]==span[2] else
                          (f' · source lines {span[0]}:{span[1]} to {span[2]}:{span[3]}'
                           if span is not None else
                           (f' · source line {line}' if line is not None else '')))
                lines.append('  '+change.function+' / '+change.node_id+location+
                             ' · '+change.action+(f' [{change.input_port}]' if change.input_port else '')+
                             ' · '+str(change.before)+' → '+str(change.after))
            lines += ['', 'Import rechecks both owners and requires confirmation.',
                      'One atomic graph edit; Python source remains untouched.']
            QMessageBox.information(self,'Independent function reconciliation','\n'.join(lines))
        return receipt

    def import_independent_python_function(self,checked=False,*,confirm=True):
        pending=self._independent_review
        if pending is None:
            self.report('Review one independent .py function before importing it')
            return False
        session,receipt=pending
        if confirm:
            answer=QMessageBox.question(self,'Import reviewed Python function?',
                 'Apply supported edits to ProgramGraph function(s) '+
                (', '.join(receipt.functions) if isinstance(receipt,IndependentFunctionsReview)
                 else receipt.function)+'?\n' 
                'Unmodeled Python source is not imported, rewritten or linked.\n'
                'The source file stays unchanged. Graph undo remains available.',
                QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if answer!=QMessageBox.StandardButton.Yes:return False
        # One-time UI receipt. Neither review nor import stores a second owner.
        self._independent_review=None
        try:
            if isinstance(receipt,IndependentFunctionsReview):
                changed=import_independent_source_functions(self.document,session,receipt.functions,
                    expected_graph_revision=receipt.graph_revision,
                    expected_source_revision=receipt.source_revision,
                    expected_source_sha256=receipt.source_sha256)
            else:
                changed=import_independent_source_function(self.document,session,receipt.function,
                    expected_graph_revision=receipt.graph_revision,
                    expected_source_revision=receipt.source_revision,
                    expected_source_sha256=receipt.source_sha256)
        except (ProgramGraphError,GraphConflict,TypeError,ValueError) as exc:
            self.report('Independent function import refused; source retained: '+str(exc))
            return False
        if changed:
            self.refresh()
            self.report('Imported qualified function edits atomically; Python source not modified')
        else:self.report('Selected source function has no graph changes')
        return changed

    def publish_python(self,checked=False,*,path=None):
        """Explicit source artifact creation, never an automatic graph save."""
        if path is None:
            path=self.window._choose_file(title='Publish qualified Python as NEW file',
                filters='Python source (*.py)',save=True,
                proposed=Path.home()/'generated-program.py')
            if not path:return False
        try:
            receipt=publish_program_python(self.document,path,
                                            expected_revision=self.document.revision)
        except (OSError,ValueError,ProgramGraphError) as exc:
            QMessageBox.warning(self,'Python publication refused',str(exc))
            return False
        self.report('Published qualified Python '+receipt.path)
        return True

    def connect(self,source,source_port,target,target_port):
        # A new pin drag onto an occupied input atomically replaces its single
        # existing wire, not disconnect+connect as separate undo steps.
        occupied=any(e['target']==target and e['target_port']==target_port
                     for e in self.document.state['edges'])
        # Edge relation is determined by the *authoritative* port contract,
        # never by a GUI gesture or a caller-supplied default.
        nodes={n['id']:n for n in self.document.state['nodes']}
        producer=next((p for p in nodes.get(source,{}).get('ports',{}).get('outputs',())
                       if p['id']==source_port),None)
        consumer=next((p for p in nodes.get(target,{}).get('ports',{}).get('inputs',())
                       if p['id']==target_port),None)
        relation=('control' if producer and consumer and
                  producer['type']==consumer['type']=='execution' else 'data')
        changed=self.edit('replace_input' if occupied else 'connect',
                          redraw=False,source=source,source_port=source_port,
                          target=target,target_port=target_port,relation=relation)
        if changed:
            # A pin event may still be dispatched to an item in the scene.
            # Do not destroy C++ graphics objects before the event unwinds.
            QTimer.singleShot(0,self.refresh)
        return changed

    def move_node(self,node,x,y):
        if self.edit('move_node',redraw=False,node=node,x=x,y=y):
            # Scene deletion must not happen inside NodeItem.mouseReleaseEvent.
            QTimer.singleShot(0,self.refresh)

    def delete_selected(self):
        selection=self.canvas.graph_scene.selectedItems()
        nodes={i.data['id'] for i in selection if isinstance(i,NodeItem)}
        edges={i.data(0) for i in selection
               if isinstance(i,QGraphicsPathItem) and i.data(0)}
        if nodes or edges:self.edit('remove_selection',nodes=sorted(nodes),edges=sorted(edges))

    def undo(self,checked=False):
        if self.document.undo(self.document.revision):self.refresh()

    def redo(self,checked=False):
        if self.document.redo(self.document.revision):self.refresh()

    def save(self,checked=False,*,path=None):
        if path is None:
            path=self.document.path
        if path is None:
            path=self.window._choose_file(title='Save visual program',
                filters='Superior MI Graph (*.smi-graph)',save=True,
                proposed=Path.home()/'visual-program.smi-graph')
            if not path:return False
        try:
            self.document.save(path)
        except (OSError,ProgramGraphError) as exc:
            QMessageBox.warning(self,'Graph save refused',str(exc))
            return False
        self.refresh();self.report('Saved graph '+str(path));return True

    def save_as(self,checked=False,*,path=None):
        if path is None:
            path=self.window._choose_file(title='Save visual program as new document',
                    filters='Superior MI Graph (*.smi-graph)',save=True,
                    proposed=Path.home()/'visual-program-copy.smi-graph')
            if not path:return False
        try:
            fork=self.document.save_as(path)
        except (OSError,ProgramGraphError) as exc:
            QMessageBox.warning(self,'Graph Save As refused',str(exc));return False
        # The old file and its history remain untouched. The active tab now
        # owns the saved fork with a different root identity and a fresh history.
        self.document=fork
        self.refresh();self.report('Saved independent visual program '+str(path))
        return True

    def confirm_close(self):
        if not self.document.dirty:return True
        return QMessageBox.question(self,'Unsaved visual program',
             'Discard unsaved visual programming changes?',
             QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)==QMessageBox.StandardButton.Yes

    def context_menu(self,screen_pos,*,node_id=None,edge_id=None,scene_pos=None):
        menu=QMenu(self)
        creations={menu.addAction('Create '+name):name for name in NODE_TEMPLATES}
        literal=menu.addAction('Edit literal…') if node_id and any(
            n['id']==node_id and n['operation']=='python.literal'
            for n in self.document.state['nodes']) else None
        erase=menu.addAction('Delete node') if node_id else None
        disconnect=menu.addAction('Disconnect wire') if edge_id else None
        menu.addSeparator()
        back=menu.addAction('Undo graph edit')
        forward=menu.addAction('Redo graph edit')
        chosen=menu.exec(screen_pos)
        if chosen in creations:
            self.choose_node(operation=creations[chosen],scene_pos=scene_pos)
        elif chosen is literal and literal is not None:
            self.edit_literal(node_id)
        elif chosen is erase and erase is not None:
            self.edit('remove_node',node=node_id)
        elif chosen is disconnect and disconnect is not None:
            self.edit('disconnect',edge=edge_id)
        elif chosen is back:self.undo()
        elif chosen is forward:self.redo()


class NativeLab(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.resize(1510,920)
        self.state=m.new_state();self.current_path=None;self.dirty=False
        self._presentation_store=PresentationStore()
        self._presentation_timer=QTimer(self)
        self._presentation_timer.setSingleShot(True)
        self._presentation_timer.setInterval(450)
        self._presentation_timer.timeout.connect(self._save_presentation_state)
        saved_view=self._presentation_store.load()
        self._presentation_documents=saved_view['documents']
        self._dock_modes=saved_view['dock_modes']
        self._dock_regions={}
        self._front_nodes={(item['path'],item['graph']):item['node'] for item in saved_view['front']}
        self.active_item=None
        self._setting_positions={item['node']:(item['x'],item['y']) for item in saved_view['setting_positions']}
        self._source_positions={(item['path'],item['view'],item['node']):(item['x'],item['y']) for item in saved_view['source_positions']}
        self._resource_positions={item['node']:(item['x'],item['y']) for item in saved_view['resource_positions']}  # presentation only
        self._graph_cameras={(r['path'],r['graph']):(r['x'],r['y'],r['zoom']) for r in saved_view['cameras']}
        self._graph_sizes={(r['path'],r['graph']):(r['width'],r['height']) for r in saved_view['sizes']}
        self.python_doc=None;self.source_graph=None;self.source_scope='module'
        self.resource_path=Path(saved_view['resource_path'])
        if not self.resource_path.is_dir():
            self.resource_path=(Path.home()/'Projects' if (Path.home()/'Projects').is_dir() else Path.home())
        self.resource_graph=None;self.resource_offset=0;self.resource_show_imports=False
        self.resource_relationship_layers={'imports','references'}
        self.resource_relationship_focus=None
        self.resource_relationship_direction='both'
        # Navigation history is view-only, not another source or filesystem authority.
        # Each graph tab owns a navigation session; resource and Python views use the same registry.
        # No cloned documents or graphs: sessions store routes/history only.
        self._view_sessions=GraphViewSessions()
        self._view_sessions.open('resource',Route('resource',str(self.resource_path)))
        self._nav_address_mode={'resource':False,'source':False}
        self.resource_expanded=set(saved_view['resource_expanded'])
        self.source_detail='readable'
        self.source_view_mode='whole';self._source_expanded=set();self._region_collapsed=set()
        self._python_process=None;self._python_run_dialog=None
        self._source_editor_loading=False;self._source_editor_dirty=False
        # One revisioned text owner per source identity; Qt is a view only.
        self._source_documents={}
        self._source_analysis_timer=QTimer(self)
        self._source_analysis_timer.setSingleShot(True)
        self._source_analysis_timer.setInterval(280)
        self._source_analysis_timer.timeout.connect(self._refresh_live_source)
        # Autosave only recovery receipts, never Python source itself. A separate
        # debounce prevents routine typing from issuing synchronous disk writes.
        self._draft_recovery=DraftRecoveryStore()
        self._draft_recovery_timer=QTimer(self)
        self._draft_recovery_timer.setSingleShot(True)
        self._draft_recovery_timer.setInterval(950)
        self._draft_recovery_timer.timeout.connect(self._flush_source_recovery)
        self._source_edit_history=SourceEditHistory()
        self._loaded_editor_identity=None
        self._presentation_loading=True
        self.atlas=AssetIndex(Path(__file__).resolve().parents[1]/'packs'/'sci-fi')
        self.external_atlas=ExternalIconAtlas.discover(default_icon_atlas_directory())
        self._external_icon_sheets=OrderedDict()
        self._external_icon_pixmaps=OrderedDict()
        self._os_icon_provider=QFileIconProvider()
        self._sheet_cache={}
        self._sprite_cache={}
        self.tabs=QTabWidget();self.tabs.setDocumentMode(True)
        self.tabs.setMovable(True);self.tabs.setUsesScrollButtons(True)
        self.tabs.setTabsClosable(False)
        self.setCentralWidget(self.tabs)
        self.canvas=GraphCanvas(self);self.settings_canvas=GraphCanvas(self,True)
        self.source_canvas=GraphCanvas(self,source_view=True)
        self.resource_canvas=GraphCanvas(self,resource_view=True)
        # One canvas per distinct authority. Tab-local controls belong inside
        # its own page, not in the QMainWindow global toolbar strip.
        self.source_page=self._graph_page(self.source_canvas)
        self.resource_page=self._graph_page(self.resource_canvas)
        self.tabs.addTab(self.resource_page,'FILES / SYSTEM')
        self.tabs.addTab(self.source_page,'PYTHON SOURCE GRAPH')
        self._resource_tabs={'resource':ResourceTabView('resource',self.resource_page,self.resource_canvas,
                            path=self.resource_path,offset=self.resource_offset,
                            expanded=set(self.resource_expanded),imports=self.resource_show_imports,
                            relationship_layers=set(self.resource_relationship_layers),
                            relationship_focus=self.resource_relationship_focus,
                            relationship_direction=self.resource_relationship_direction)}
        self._active_resource_tab_id='resource'
        self._next_resource_tab_number=1
        self._source_tabs={'source':SourceTabView('source',self.source_page,self.source_canvas)}
        self._program_tabs={}
        self._active_source_tab_id='source'
        self._next_source_tab_number=1
        self._switching_source_tab=False
        # Retain the old prototype canvases as inspectable developer tools.
        # They are not normal workspace destinations.
        self._legacy_tabs=((self.canvas,'Node workspace'),
                           (self.settings_canvas,'Studio settings graph'))
        self._legacy_pages={}
        self.tabs.currentChanged.connect(self._workspace_tab_changed)
        self._build_library();self._build_inspector();self._build_source_editor()
        self._build_dock_regions();self._build_menu()
        self._build_source_toolbar()
        self._source_tabs['source'].toolbar=self.source_toolbar
        self._build_resource_toolbar()
        self._resource_tabs['resource'].toolbar=self.resource_toolbar
        self.canvas.rebuild();self.settings_canvas.rebuild();self.source_canvas.rebuild()
        self.browse_resource(self.resource_path,activate=False)
        self._presentation_loading=False
        if self._presentation_store.error:
            self.statusBar().showMessage('Presentation preferences not loaded: '+self._presentation_store.error)
        self.statusBar().showMessage('Native Qt lab · Ctrl+double-click a scope to focus (Ctrl+Alt+O opens file) · Parsed source does not execute automatically')
        QTimer.singleShot(90,self._restore_initial_canvas_views)
        QTimer.singleShot(140,self._restore_dock_regions)

    def _active_resource_session(self):
        return self._view_sessions.get(self._active_resource_tab_id)

    def _store_active_resource_view(self):
        view=self._resource_tabs.get(self._active_resource_tab_id)
        if view is None:return
        view.path=self.resource_path
        view.graph=self.resource_graph
        view.offset=self.resource_offset
        view.expanded=set(self.resource_expanded)
        view.imports=self.resource_show_imports
        view.relationship_layers=set(self.resource_relationship_layers)
        view.relationship_focus=self.resource_relationship_focus
        view.relationship_direction=self.resource_relationship_direction

    def _activate_resource_view(self,view,*,reproject=True):
        """Bind temporary Qt compatibility aliases from the selected tab.

        Resource paths and graphs are supplied by the existing provider. These
        aliases are not a second persisted resource registry.
        """
        self._active_resource_tab_id=view.session_id
        self.resource_page=view.page
        self.resource_canvas=view.canvas
        self.resource_toolbar=view.toolbar
        self.resource_path=view.path
        self.resource_graph=view.graph
        self.resource_offset=view.offset
        self.resource_expanded=set(view.expanded)
        self.resource_show_imports=view.imports
        self.resource_relationship_layers=set(view.relationship_layers)
        self.resource_relationship_focus=view.relationship_focus
        self.resource_relationship_direction=view.relationship_direction
        # A tab is a view of current source sessions, not a frozen AST copy.
        # Inactive resource tabs are refreshed on activation; their cameras
        # remain owned by the existing GraphCanvas presentation store.
        if reproject and (view.imports or any(path in self._source_documents for path in view.expanded)):
            resolved=resolve_graph(Route('resource',str(view.path)),
                resource_offset=view.offset,resource_imports=view.imports,
                resource_relationship_kinds=view.relationship_layers,
                resource_relationship_focus=view.relationship_focus,
                resource_relationship_direction=view.relationship_direction,
                resource_expanded=view.expanded,source_documents=self._source_documents)
            view.graph=self.resource_graph=resolved.graph
            view.canvas.rebuild()
        if reproject:self._refresh_navigation('resource')

    def _refresh_resource_source_views(self, path):
        """Reproject opened source's active revision into expanded file cards.

        No new parser or tab authority: resolve through current resource tabs,
        and only rebuild their active canvas. Other views rebuild on activation.
        """
        view=self._resource_tabs.get(self._active_resource_tab_id)
        if view is None or (str(path) not in view.expanded and not view.imports):return
        resolved=resolve_graph(Route('resource',str(view.path)),
            resource_offset=view.offset,resource_imports=view.imports,
                resource_relationship_kinds=view.relationship_layers,
            resource_relationship_focus=view.relationship_focus,
            resource_relationship_direction=view.relationship_direction,
            resource_expanded=view.expanded,source_documents=self._source_documents)
        view.graph=self.resource_graph=resolved.graph
        view.canvas.rebuild()

    def _resource_tab_title(self,route):
        path=Path(route.path)
        return path.name or str(path)

    def _update_resource_tab_title(self):
        view=self._resource_tabs.get(self._active_resource_tab_id)
        if view is None:return
        index=self.tabs.indexOf(view.page)
        if index>=0:
            self.tabs.setTabText(index,self._resource_tab_title(self._active_resource_session().route))
            self.tabs.setTabToolTip(index,str(self.resource_path))

    def _add_tab_close_button(self,page,index):
        """Same Qt tab close mechanism for source and resource views."""
        button=QToolButton(self.tabs)
        button.setText('×')
        button.setToolTip('Close graph view (does not modify any file)')
        button.setFixedSize(20,20)
        button.clicked.connect(lambda checked=False,p=page:
            self._close_graph_tab(self.tabs.indexOf(p)) if self.tabs.indexOf(p)>=0 else None)
        self.tabs.tabBar().setTabButton(index,QTabBar.ButtonPosition.RightSide,button)

    def open_resource_in_new_tab(self,path):
        """Ctrl+open directory: own camera/history/canvas, same provider."""
        try:
            resolved=resolve_graph(Route('resource',str(Path(path).expanduser().absolute())))
        except (OSError,ResourceError,ValueError) as exc:
            self.report('Cannot open directory graph tab: '+str(exc));return False
        # A new secondary tab must be constructed before it enters either
        # registry or the shared navigation history. Reuse the same staged
        # page/toolbar boundary as a cross-provider tab replacement.
        sid='resource:'+str(self._next_resource_tab_number+1)
        page=None
        try:
            canvas=GraphCanvas(self,resource_view=True)
            canvas.session_id=sid
            page=self._graph_page(canvas)
            view=ResourceTabView(sid,page,canvas,path=Path(resolved.route.path),graph=resolved.graph)
            view.toolbar=self._create_navigation_bar(page,'ResourceNavigationBar')
        except (RuntimeError,ValueError) as exc:
            if page is not None:page.deleteLater()
            self.report('Cannot open directory graph tab: view unavailable: '+str(exc))
            return False
        self._store_active_resource_view()
        self._next_resource_tab_number+=1
        self._resource_tabs[sid]=view
        # Publish the provider's resolved route, never a reconstructed path.
        self._view_sessions.open(sid,resolved.route)
        index=self.tabs.addTab(page,self._resource_tab_title(resolved.route))
        self._add_tab_close_button(page,index)
        self.tabs.setCurrentWidget(page)
        if self._active_resource_tab_id!=sid:self._activate_resource_view(view)
        canvas.rebuild()
        if canvas.has_saved_root_view():canvas.restore_root_view()
        else:canvas.frame_visible_nodes()
        self._update_resource_tab_title()
        self.report('Opened independent directory graph: '+resolved.route.path)
        return True

    def _active_source_session(self):
        return self._view_sessions.get(self._active_source_tab_id)

    def _store_active_source_view(self):
        view=self._source_tabs.get(self._active_source_tab_id)
        if view is None:return
        view.document=self.python_doc
        view.graph=self.source_graph
        view.detail=self.source_detail
        view.expanded=set(self._source_expanded)
        view.collapsed=set(self._region_collapsed)
        chosen=next((card.data['id'] for card in view.canvas.graph_scene.selectedItems()
                     if isinstance(card,NodeItem) and card.source_view),None)
        view.selected_node=chosen

    def _activate_source_view(self,view):
        """Bind the active Qt view to its own source/session projection.

        Legacy window fields are ephemeral active-view aliases. They are never
        used to store a second copy of a Python program or tab history.
        """
        self._active_source_tab_id=view.session_id
        self.source_page=view.page
        self.source_canvas=view.canvas
        self.source_toolbar=view.toolbar
        self.python_doc=view.document
        self.source_graph=view.graph
        session=self._view_sessions.get(view.session_id)
        # The permanent source anchor exists before its first Python file is
        # opened. It is the only legitimate source view without a route yet.
        if session is None and (view.session_id!='source' or view.document is not None):
            raise RuntimeError('Source tab has no navigation session')
        route=session.route if session is not None else None
        self.source_scope=route.scope if route is not None else 'module'
        self.source_view_mode=route.mode if route is not None else 'whole'
        self.source_detail=view.detail
        self._source_expanded=set(view.expanded)
        self._region_collapsed=set(view.collapsed)
        active=self._source_documents.get(route.path) if route is not None else None
        if active is not None:
            active.inspect_external()
            # Switching views reads one document session, never an old tab cache.
            if self._loaded_editor_identity!=(route.path,active.revision):
                self._load_source_editor()
            self.python_doc=active.parsed
            self._source_editor_dirty=active.dirty
            self.source_editor.setEnabled(True)
            self._set_source_editor_label()
        if view.needs_rebuild:
            view.canvas.rebuild()
            view.needs_rebuild=False
        self._refresh_navigation('source')
        if view.selected_node and view.selected_node in view.canvas.items_by_id:
            item=view.canvas.items_by_id[view.selected_node]
            if item.isVisible():item.setSelected(True)

    def _graph_tab_for_page(self,page):
        """The only tab-to-canvas registry lookup, independent of provider kind.

        Qt's QTabWidget owns page membership. These dictionaries hold only
        provider-specific view preferences and never reconstruct the graph.
        """
        for views in (self._resource_tabs,self._source_tabs):
            for view in views.values():
                if view.page is page:
                    return view
        return self._program_tabs.get(page)

    def _bind_selected_graph_view(self,view):
        """Synchronize legacy active-view aliases from the selected Qt page.

        The provider-specific views and GraphViewSessions remain authoritative.
        This idempotent adapter is shared by the Qt tab-change signal and
        explicit navigation/history (which may run without a new signal).
        """
        if isinstance(view,ResourceTabView):
            if self._active_resource_tab_id==view.session_id:return False
            self._store_active_resource_view()
            self._activate_resource_view(view)
            return True
        if isinstance(view,SourceTabView):
            if self._active_source_tab_id==view.session_id:return False
            if self._source_analysis_timer.isActive():
                self._source_analysis_timer.stop()
                self._refresh_live_source()
            self._store_active_source_view()
            self._activate_source_view(view)
            return True
        return False

    def _workspace_tab_changed(self,_index):
        if self._switching_source_tab:return
        if self._draft_recovery_timer.isActive():
            self._draft_recovery_timer.stop()
            self._flush_source_recovery()
        incoming=self._graph_tab_for_page(self.tabs.currentWidget())
        self._bind_selected_graph_view(incoming)
        self.refresh_inspector()
        self._sync_library_mode()
        self._refresh_operation_library()
        canvas=self.current_canvas()
        if isinstance(canvas,GraphCanvas):canvas._place_overview()

    def _source_tab_title(self,route):
        label=Path(route.path).name
        if route.mode=='focus':
            return label+' / '+route.scope.rsplit('/',1)[-1].split(':')[1] if ':' in route.scope else label+' / '+route.scope
        return label

    def _update_source_tab_title(self):
        view=self._source_tabs.get(self._active_source_tab_id)
        if view is None:return
        index=self.tabs.indexOf(view.page)
        if index>=0:
            route=self._active_source_session().route
            self.tabs.setTabText(index,self._source_tab_title(route))
            self.tabs.setTabToolTip(index,route.path)

    def open_source_in_new_tab(self,path,scope='module'):
        """Ctrl+open: distinct Qt canvas/session; shared source document identity.

        A file with unsaved editor changes cannot be silently reinterpreted.
        Resolve the new route before publishing a tab or changing active state.
        """
        if self._source_analysis_timer.isActive():
            self._source_analysis_timer.stop()
            self._refresh_live_source()
        requested=Path(path).expanduser().absolute()
        # Do not manufacture a blank extra tab if the initial source workspace
        # has never loaded a file. Materialize that first view instead.
        first=self._source_tabs.get('source')
        if first is not None and first.document is None and self._active_source_document() is None:
            try:
                pending=self._new_source_document(requested)
                doc=pending.parsed
                if scope!='module' and doc is None:
                    raise SourceError('Cannot focus invalid Python source')
                if doc is not None:
                    target=Route('source',str(doc.path),scope,'focus') if scope!='module' else Route('source',str(doc.path))
                    resolve_graph(target,document=doc)
            except (OSError,ValueError) as exc:
                self.report('Cannot open graph tab: '+str(exc));return False
            if not self._open_python_source_path(requested):return False
            return self.navigate_source(scope) if scope!='module' else True
        try:
            requested=PythonDocument._validated_path(requested)
            source=self._source_documents.get(str(requested))
            if source is None:
                if len(self._source_documents)>=32:
                    raise SourceError('At most 32 source documents can be open at once; close/restart after saving drafts')
                source=self._new_source_document(requested)
            document=source.parsed
            if scope!='module' and document is None:
                raise SourceError('Cannot focus a function in invalid Python source')
            route=Route('source',str(requested),scope,'focus') if scope!='module' else Route('source',str(requested))
            graph=(resolve_graph(route,document=document).graph if document else None)
        except (OSError,ValueError) as exc:
            self.report('Cannot open graph tab: '+str(exc));return False
        # Resolve source syntax first, but publish the shared document and
        # secondary view only after page/navigation chrome construction works.
        # Failed staging must not consume a tab ID or create a ghost session.
        sid='source:'+str(self._next_source_tab_number+1)
        page=None
        try:
            canvas=GraphCanvas(self,source_view=True)
            canvas.session_id=sid
            page=self._graph_page(canvas)
            view=SourceTabView(sid,page,canvas,document=document,graph=graph)
            view.toolbar=self._create_navigation_bar(page,'PythonNavigationBar')
        except (RuntimeError,ValueError) as exc:
            if page is not None:page.deleteLater()
            self.report('Cannot open graph tab: view unavailable: '+str(exc))
            return False
        self._source_documents[str(requested)]=source
        self._store_active_source_view()
        self._next_source_tab_number+=1
        self._source_tabs[sid]=view
        self._view_sessions.open(sid,route)
        index=self.tabs.addTab(page,self._source_tab_title(route))
        self._add_tab_close_button(page,index)
        self.tabs.setCurrentWidget(page)
        # Signal activates the view before Qt builds its scene. Source graph
        # projections remain separate, while both views share one .py authority.
        if self._active_source_tab_id!=sid:self._activate_source_view(view)
        if graph is not None:self._apply_saved_source_positions(graph,'whole' if route.mode=='whole' else route.scope)
        canvas.rebuild()
        if canvas.has_saved_root_view():canvas.restore_root_view()
        else:canvas.frame_visible_nodes()
        self._update_source_tab_title()
        self.report('Opened independent graph tab: '+str(requested))
        return True

    def _close_graph_tab(self,index):
        if index<0 or index>=self.tabs.count():return
        page=self.tabs.widget(index)
        # Provider-local active aliases track the last view of that kind,
        # which need not be the foreground Qt page. Closing such an inactive
        # tab may rebind its provider root, but must not steal foreground focus.
        closing_selected=self.tabs.currentWidget() is page
        # The same Qt page-to-view lookup used by tab activation and routing
        # owns close dispatch too. Never re-scan provider maps independently:
        # active window aliases can refer to a different selected provider.
        view=self._graph_tab_for_page(page)
        if isinstance(view,ProgramWorkspace):
            if not view.confirm_close():return
            del self._program_tabs[page]
            self.tabs.removeTab(index)
            view.deleteLater()
            return
        if isinstance(view,ResourceTabView):
            resource=view
            if resource.session_id=='resource' or len(self._resource_tabs)==1:
                self.report('The original filesystem graph tab is a protected compatibility anchor')
                return
            if resource.session_id==self._active_resource_tab_id:self._store_active_resource_view()
            resource.canvas._save_root_view()
            del self._resource_tabs[resource.session_id]
            self._view_sessions.close(resource.session_id)
            self._switching_source_tab=True
            try:self.tabs.removeTab(index)
            finally:self._switching_source_tab=False
            resource.page.deleteLater()
            if resource.session_id==self._active_resource_tab_id:
                target=next(iter(self._resource_tabs.values()))
                self._activate_resource_view(target)
                if closing_selected:self.tabs.setCurrentWidget(target.page)
            self._queue_presentation_save()
            return
        if not isinstance(view,SourceTabView):
            return  # Legacy development view, not an ordinary graph tab.
        if view.session_id=='source' or len(self._source_tabs)==1:
            self.report('The original Python graph tab is a protected compatibility anchor')
            return
        # Closing a graph view never destroys the shared document draft.
        if view.session_id==self._active_source_tab_id:self._store_active_source_view()
        view.canvas._save_root_view()
        del self._source_tabs[view.session_id]
        self._view_sessions.close(view.session_id)
        self._switching_source_tab=True
        try:self.tabs.removeTab(index)
        finally:self._switching_source_tab=False
        view.page.deleteLater()
        if view.session_id==self._active_source_tab_id:
            target=next(iter(self._source_tabs.values()))
            self._activate_source_view(target)
            if closing_selected:self.tabs.setCurrentWidget(target.page)
        self._queue_presentation_save()

    def _source_position_key(self,view,node_id):
        path=str(self.python_doc.path) if self.python_doc else '<unloaded>'
        return (path,view,node_id)

    def _remember_document_view(self):
        if self.python_doc:
            self._presentation_documents[str(self.python_doc.path)]={
                'expanded':sorted(self._source_expanded),
                'collapsed':sorted(self._region_collapsed),
            }

    def _restore_document_view(self,doc):
        prefs=self._presentation_documents.get(str(doc.path))
        if prefs:
            return (set(prefs['expanded']) & set(doc.scopes),
                    set(prefs['collapsed']))
        return ({k for k,scope in doc.scopes.items() if k!='module' and scope.parent=='module'},set())

    def _queue_presentation_save(self):
        if not getattr(self,'_presentation_loading',True):
            self._presentation_timer.start()

    def _capture_presentation_state(self):
        self._remember_document_view()
        return {
            'version':1,
            'source_positions':[{'path':p,'view':v,'node':n,'x':x,'y':y}
                for (p,v,n),(x,y) in sorted(self._source_positions.items())],
            'resource_positions':[{'node':n,'x':x,'y':y}
                for n,(x,y) in sorted(self._resource_positions.items())],
            'setting_positions':[{'node':n,'x':x,'y':y}
                for n,(x,y) in sorted(self._setting_positions.items())],
            'cameras':[{'path':p,'graph':g,'x':x,'y':y,'zoom':z}
                for (p,g),(x,y,z) in sorted(self._graph_cameras.items())],
            'sizes':[{'path':p,'graph':g,'width':w,'height':h}
                for (p,g),(w,h) in sorted(self._graph_sizes.items())],
            'front':[{'path':p,'graph':g,'node':node}
                for (p,g),node in sorted(self._front_nodes.items())],
            'documents':self._presentation_documents,
            'resource_expanded':sorted(self.resource_expanded),
            'resource_path':str(self.resource_path),
            'dock_modes':self._dock_modes,
        }

    def _save_presentation_state(self):
        if getattr(self,'_presentation_loading',True):return
        try:self._presentation_store.save(self._capture_presentation_state())
        except (OSError,ValueError,TypeError) as exc:
            self.statusBar().showMessage('View preferences were not saved: '+str(exc))

    def _apply_saved_source_positions(self,graph,view='whole'):
        for node in graph['nodes']:
            position=self._source_positions.get((str(self.python_doc.path),view,node['id']))
            if position is not None:node['x'],node['y']=position

    def _restore_initial_canvas_views(self):
        for canvas,default in ((self.canvas,(660,370)),
                               (self.settings_canvas,(560,350)),
                               (self.source_canvas,(740,400)),
                               (self.resource_canvas,(510,285))):
            if canvas.has_saved_root_view():
                canvas.restore_root_view()
            else:canvas.centerOn(*default)

    def resource_icon(self,data):
        # OS icon first, optional manifest-backed atlas fallback. Neither is
        # authoritative for file type or needed to launch Studio.
        path=str(data.get('resource_path',''))
        kind=str(data.get('resource_kind','file'))
        cache_key=('resource',path,kind)
        icon=self._external_icon_pixmaps.get(cache_key)
        if icon is not None:return icon
        result=QPixmap()
        if path:
            try:
                result=self._os_icon_provider.icon(QFileInfo(path)).pixmap(24,24)
            except (OSError,RuntimeError,ValueError):pass
        if result.isNull() and self.external_atlas:
            candidate=icon_id_for_resource(kind,Path(path).suffix.lower())
            result=self.external_icon(candidate,tint=icon_hint(kind,candidate).tint)
        self._external_icon_pixmaps[cache_key]=result
        if len(self._external_icon_pixmaps)>512:
            self._external_icon_pixmaps.popitem(last=False)
        return result

    def resource_thumbnail(self,data):
        """Decode a bounded visible image on demand; never cache full-size pixels.

        A reader dimension and file-size limit are essential when viewing an
        untrusted repository. Qt scaled reads are not executable content.
        """
        path=Path(str(data.get('resource_path','')))
        if data.get('resource_kind')!='file' or data.get('preview_kind')!='image':
            return QPixmap()
        try:
            if path.is_symlink() or not path.is_file():return QPixmap()
            stat=path.stat()
            if stat.st_size>MAX_PREVIEW_FILE_BYTES:return QPixmap()
        except OSError:return QPixmap()
        key=('preview',str(path),stat.st_mtime_ns,stat.st_size)
        cached=self._external_icon_pixmaps.get(key)
        if cached is not None:return cached
        reader=QImageReader(str(path))
        dimensions=reader.size()
        result=QPixmap()
        if (dimensions.isValid() and 0<dimensions.width()<=4096 and
                0<dimensions.height()<=4096):
            scaled=dimensions.scaled(QSize(202,114),Qt.AspectRatioMode.KeepAspectRatio)
            reader.setScaledSize(scaled)
            content=reader.read()
            if not content.isNull():result=QPixmap.fromImage(content)
        self._external_icon_pixmaps[key]=result
        if len(self._external_icon_pixmaps)>512:self._external_icon_pixmaps.popitem(last=False)
        return result

    def external_icon(self,icon_id,tint=None):
        cache_key=('atlas',icon_id,tint)
        cached=self._external_icon_pixmaps.get(cache_key)
        if cached is not None:return cached
        result=QPixmap()
        pack=self.external_atlas
        if pack:
            location=pack.lookup(icon_id)
            if location:
                filename,rect=location
                if filename not in self._external_icon_sheets:
                    self._external_icon_sheets[filename]=QImage(str(filename))
                    if len(self._external_icon_sheets)>2:
                        self._external_icon_sheets.popitem(last=False)
                sheet=self._external_icon_sheets[filename]
                x,y,w,h=rect
                if not sheet.isNull() and x>=0 and y>=0 and x+w<=sheet.width() and y+h<=sheet.height():
                    result=QPixmap.fromImage(sheet.copy(x,y,w,h))
                    if tint and QColor(tint).isValid():
                        colored=QPixmap(result.size())
                        colored.fill(Qt.GlobalColor.transparent)
                        painter=QPainter(colored)
                        painter.drawPixmap(0,0,result)
                        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
                        painter.fillRect(colored.rect(),qcolor(tint))
                        painter.end()
                        result=colored
        self._external_icon_pixmaps[cache_key]=result
        if len(self._external_icon_pixmaps)>512:
            self._external_icon_pixmaps.popitem(last=False)
        return result

    def sprite(self,asset_id):
        if not asset_id or asset_id not in self.atlas.entries:return QPixmap()
        if asset_id in self._sprite_cache:return self._sprite_cache[asset_id]
        entry=self.atlas.entries[asset_id]
        if entry['sheet'] not in self._sheet_cache:
            self._sheet_cache[entry['sheet']]=QImage(str(self.atlas.sheets[entry['sheet']]))
        image=self._sheet_cache[entry['sheet']]
        x,y,w,h=entry['rect']
        if image.isNull() or image.width()<x+w or image.height()<y+h:return QPixmap()
        pix=QPixmap.fromImage(image.copy(x,y,w,h))
        self._sprite_cache[asset_id]=pix
        return pix

    def open_asset_picker(self,item):
        dialog=QDialog(self);dialog.setWindowTitle('Choose node icon · Atlas Assets')
        dialog.resize(430,550)
        layout=QVBoxLayout(dialog)
        search=QLineEdit();search.setPlaceholderText('Search icon assets…')
        listing=QListWidget();listing.setIconSize(QSize(40,40))
        layout.addWidget(QLabel('Manifest-backed ui.icon assets'))
        layout.addWidget(search);layout.addWidget(listing,1)
        def populate():
            listing.clear()
            for entry in self.atlas.find('ui.icon',search.text()):
                from PyQt6.QtWidgets import QListWidgetItem
                icon=QIcon(self.sprite(entry['id']))
                list_item=QListWidgetItem(icon,entry['id'])
                listing.addItem(list_item)
        search.textChanged.connect(populate)
        def chosen(list_item):
            item.data.setdefault('visual_assets',{})['header_icon']=list_item.text()
            item.update();self.mark_changed(False)
            dialog.accept()
        listing.itemDoubleClicked.connect(chosen)
        layout.addWidget(QLabel('Double-click to assign. The selected asset is stored by manifest ID.'))
        populate();dialog.exec()

    def _build_library(self):
        """One library dock: editable draft templates and source-backed census.

        A parsed operation is NOT a creatable node until the language adapter
        qualifies a source transaction. No parallel operation registry lives
        in Qt; the inventory is derived from the active validated descriptor.
        """
        dock=QDockWidget('NODE LIBRARY',self);dock.setObjectName('LibraryDock')
        tabs=QTabWidget(dock);tabs.setObjectName('NodeLibraryModes')
        draft=QWidget();layout=QVBoxLayout(draft)
        layout.addWidget(QLabel('Draft templates · editable prototype graph'))
        listing=QListWidget();listing.addItems(['Audio Mix','Signal Processor','Asset Collection','String Constant','Custom Node'])
        listing.itemDoubleClicked.connect(lambda item:self.create_node(['audio','fx','folder','string','custom'][listing.row(item)]))
        layout.addWidget(listing,1)
        for kind,title in [('audio','+ Audio Mix'),('string','+ String Constant'),('folder','+ Asset Collection'),('custom','+ Custom Node')]:
            button=QPushButton(title)
            button.clicked.connect(lambda checked=False,k=kind:self.create_node(k))
            layout.addWidget(button)
        help_text=QLabel('Draft nodes are not Python source edits.\n\nDrag between compatible draft pins; source edits require the language adapter.')
        help_text.setWordWrap(True);help_text.setStyleSheet('color:#84abc1;')
        layout.addWidget(help_text)
        tabs.addTab(draft,'Draft templates')
        source=QWidget();source_layout=QVBoxLayout(source)
        source_layout.setContentsMargins(5,5,5,5)
        self.source_library_pages=QTabWidget(source)
        self.source_library_pages.setObjectName('SourceLibraryPages')
        # My Blueprint-style navigation from the existing PythonDocument AST
        # and symtable; it does not introduce a second symbol registry.
        symbols=QWidget();symbols_layout=QVBoxLayout(symbols)
        symbols_layout.addWidget(QLabel('Functions and lexical bindings · read-only'))
        self.source_symbol_search=QLineEdit()
        self.source_symbol_search.setObjectName('SourceSymbolSearch')
        self.source_symbol_search.setPlaceholderText('Find functions, parameters, variables…')
        self.source_symbol_search.textChanged.connect(self._refresh_source_symbols)
        symbols_layout.addWidget(self.source_symbol_search)
        self.source_symbol_entries=QListWidget()
        self.source_symbol_entries.setObjectName('SourceSymbolEntries')
        self.source_symbol_entries.itemDoubleClicked.connect(self._navigate_source_symbol)
        self.source_symbol_entries.currentItemChanged.connect(lambda current,previous:self._update_symbol_authoring())
        symbols_layout.addWidget(self.source_symbol_entries,1)
        self.source_symbol_use=QPushButton('Store selected value as a new variable')
        self.source_symbol_use.setObjectName('SourceSymbolUseValue')
        self.source_symbol_use.setEnabled(False)
        self.source_symbol_use.clicked.connect(self._create_from_selected_symbol)
        symbols_layout.addWidget(self.source_symbol_use)
        self.source_symbol_call=QPushButton('Call function with selected value')
        self.source_symbol_call.setObjectName('SourceSymbolCallValue')
        self.source_symbol_call.setEnabled(False)
        self.source_symbol_call.clicked.connect(self._call_from_selected_symbol)
        symbols_layout.addWidget(self.source_symbol_call)
        self.source_symbol_rename=QPushButton('Rename selected function / input')
        self.source_symbol_rename.setObjectName('SourceSymbolRenameInterface')
        self.source_symbol_rename.setEnabled(False)
        self.source_symbol_rename.clicked.connect(self._rename_from_selected_symbol)
        symbols_layout.addWidget(self.source_symbol_rename)
        symbol_help=QLabel('Double-click to navigate. Qualified symbols can create values, '
                           'feed Calls, or rename function interfaces. All source writes '
                           'require reviewing a proposed diff.')
        symbol_help.setWordWrap(True)
        symbol_help.setStyleSheet('color:#84abc1;')
        symbols_layout.addWidget(symbol_help)
        self.source_library_pages.addTab(symbols,'My Python')
        operations=QWidget();ops_layout=QVBoxLayout(operations)
        ops_layout.addWidget(QLabel('Qualified builders + observed source operations'))
        self.source_operation_search=QLineEdit()
        self.source_operation_search.setObjectName('SourceLibrarySearch')
        self.source_operation_search.setPlaceholderText('Search operations and builders…')
        self.source_operation_search.textChanged.connect(self._refresh_operation_library)
        ops_layout.addWidget(self.source_operation_search)
        self.operation_entries=QListWidget()
        self.operation_entries.setObjectName('ObservedSourceOperations')
        self.operation_entries.setToolTip('Derived from the current graph contract; not a code-generation palette')
        self.operation_entries.itemDoubleClicked.connect(self._select_observed_operation)
        ops_layout.addWidget(self.operation_entries,1)
        info=QLabel('Double-click to locate an observed operation. Builders below '
                    'use adapter-qualified source edits and explicit save.')
        info.setWordWrap(True);info.setStyleSheet('color:#84abc1;')
        ops_layout.addWidget(info)
        # Keep all existing builder widgets, but make their tall set scrollable
        # instead of clipping both the observed list and the dock buttons.
        builders=QWidget();builder_layout=QVBoxLayout(builders)
        builder_layout.setContentsMargins(0,0,0,0)
        builder_scroll=QScrollArea()
        builder_scroll.setWidgetResizable(True)
        builder_scroll.setMaximumHeight(240)
        ops_layout.addWidget(builder_scroll)
        self.source_builder_buttons={}
        for definition in qualified_operations('python'):
            button=QPushButton('+ '+definition.title)
            button.setObjectName({'python.branch-early-return.v1':'QualifiedPythonBranchCreator',
                                  'python.local-literal-return.v1':'QualifiedPythonLocalReturnCreator',
                                  'python.return-from-pass.v1':'QualifiedPythonPlaceholderReturnCreator',
                                  'python.return-parameter-from-pass.v1':'QualifiedPythonParameterReturnCreator',
                                  'python.arithmetic-return-from-pass.v1':'QualifiedPythonArithmeticReturnCreator',
                                  'python.comparison-branch-return.v1':'QualifiedPythonComparisonBranchCreator',
                                  'python.call-return-from-pass.v1':'QualifiedPythonCallReturnCreator',
                                  'python.call-before-return.v1':'QualifiedPythonCallContinueCreator',
                                  'python.create-function.v1':'QualifiedPythonFunctionCreator',
                                  'python.create-main-entry.v1':'QualifiedPythonProgramEntryCreator',
                                  'python.add-optional-keyword-parameter.v1':'QualifiedPythonFunctionInputCreator',
                                  'python.conditional-return-from-pass.v1':'QualifiedPythonConditionalReturnCreator',
                                  'python.for-range-accumulate.v1':'QualifiedPythonForLoopCreator',
                                  'python.while-countdown.v1':'QualifiedPythonWhileLoopCreator',
                                  'python.compose-binary-local.v1':'QualifiedPythonBinaryComposer',
                                  'python.assign-source-local.v1':'QualifiedPythonValueAssignment',
                                  'python.call-with-values.v1':'QualifiedPythonStoredCallCreator',
                                  'python.rename-function.v1':'QualifiedPythonFunctionRename',
                                  'python.rename-parameter.v1':'QualifiedPythonInputRename'}[definition.id])
            button.setToolTip('Adapter-qualified source transformation: reviewed diff and explicit save required.')
            button.setEnabled(False)
            button.clicked.connect(lambda checked=False,op=definition.id:self._create_qualified_operation(op))
            builder_layout.addWidget(button)
            self.source_builder_buttons[definition.id]=button
        # Legacy public reference is retained for existing native Qt smoke.
        self.source_create_button=self.source_builder_buttons['python.branch-early-return.v1']
        builder_layout.addStretch()
        builder_scroll.setWidget(builders)
        self.source_library_pages.addTab(operations,'Operations')
        source_layout.addWidget(self.source_library_pages,1)
        tabs.addTab(source,'Python tools')
        program=QWidget()
        program_layout=QVBoxLayout(program)
        program_layout.addWidget(QLabel('Graph-owned functions and draft operations'))
        self.program_library_entries=QListWidget()
        self.program_library_entries.setObjectName('ProgramLibraryEntries')
        self.program_library_entries.itemDoubleClicked.connect(self._program_library_selected)
        program_layout.addWidget(self.program_library_entries,1)
        hint=QLabel('Double-click a function to focus it, or an operation to create '
                    'an incomplete node. These templates cannot execute or generate Python yet.')
        hint.setWordWrap(True)
        program_layout.addWidget(hint)
        tabs.addTab(program,'Visual program')
        dock.setWidget(tabs);self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea,dock)
        self.library_dock=dock
        self.library_modes=tabs
        self._sync_library_mode()

    def _sync_library_mode(self):
        """Follow the active graph authority, not an unrelated prototype tab.

        A Python tab opens its Python source catalog; the prototype canvas
        opens Draft templates. Switching display modes never changes code.
        The user can still inspect either tab manually within a workspace.
        """
        if not hasattr(self,'library_modes'):return
        canvas=self.current_canvas() if hasattr(self,'tabs') else None
        desired=(2 if isinstance(canvas,GraphCanvas) and canvas.program_view else
                 1 if isinstance(canvas,GraphCanvas) and canvas.source_view else 0)
        if self.library_modes.currentIndex()!=desired:
            self.library_modes.setCurrentIndex(desired)
        self._refresh_program_library()

    def _refresh_program_library(self):
        if not hasattr(self,'program_library_entries'):return
        listing=self.program_library_entries
        listing.clear()
        panel=self._program_tabs.get(self.tabs.currentWidget())
        if panel is None:return
        from PyQt6.QtWidgets import QListWidgetItem
        for func in panel.document.state['functions']:
            item=QListWidgetItem('Function · '+func['name']+'('+
                              ', '.join(p['name'] for p in func['parameters'])+')')
            item.setData(Qt.ItemDataRole.UserRole,('function',func['id']))
            listing.addItem(item)
        for operation in NODE_TEMPLATES:
            item=QListWidgetItem('Create · '+operation)
            item.setData(Qt.ItemDataRole.UserRole,('operation',operation))
            listing.addItem(item)

    def _program_library_selected(self,item):
        panel=self._program_tabs.get(self.tabs.currentWidget())
        if panel is None:return
        entry=item.data(Qt.ItemDataRole.UserRole)
        if not entry:return
        kind,value=entry
        if kind=='function':
            panel.current_function=value
            panel.refresh()
        elif kind=='operation':
            panel.choose_node(operation=value)

    def _qualified_source_context(self):
        """Creation is authorized only by the selected Python view's own route."""
        canvas=self.current_canvas() if hasattr(self,'tabs') else None
        if (not isinstance(canvas,GraphCanvas) or not canvas.source_view or
                self._source_editor_dirty or self.python_doc is None or
                not (self._active_source_document() and self._active_source_document().graph_ready)):
            return False
        session=self._view_sessions.get(canvas.session_id)
        return bool(session and session.route.kind=='source' and
                    Path(session.route.path).resolve()==self.python_doc.path.resolve())

    def _refresh_operation_library(self):
        self._refresh_source_symbols()
        if not hasattr(self,'operation_entries'):return
        listing=self.operation_entries
        listing.clear()
        query=(self.source_operation_search.text().strip().casefold()
               if hasattr(self,'source_operation_search') else '')
        canvas=self.current_canvas() if hasattr(self,'tabs') else None
        if hasattr(self,'source_builder_buttons'):
            # The language adapter is the sole creation-eligibility authority.
            # In particular an unloaded resource/legacy tab has no PythonDocument.
            source_ready=self._qualified_source_context()
            actions=available_actions(self.python_doc) if source_ready else ()
            enabled_ids={action.id for action in actions}
            catalog={entry.id:entry for entry in qualified_operations('python')}
            for operation_id,button in self.source_builder_buttons.items():
                definition=catalog[operation_id]
                button.setVisible(not query or query in
                    (definition.title+' '+operation_id+' '+' '.join(definition.operation_kinds)).casefold())
                button.setEnabled(operation_id in enabled_ids)
                button.setToolTip(('Choose a qualified Python function/anchor and review a source diff before saving.'
                                   if operation_id in enabled_ids else
                                   'Open a qualifying Python function in the selected source tab; save unsaved text edits first.'))
        contract=(canvas.graph_contract if isinstance(canvas,GraphCanvas) else None)
        if contract is None or contract.origin!='source':return
        for entry in observed_operations(contract):
            if query and query not in (entry.kind+' '+entry.id).casefold():continue
            from PyQt6.QtWidgets import QListWidgetItem
            item=QListWidgetItem(f'{entry.kind}  ({len(entry.occurrences)})')
            item.setData(Qt.ItemDataRole.UserRole,entry.occurrences)
            item.setToolTip(entry.id+'\nRead-only: '+entry.authoring)
            listing.addItem(item)

    def _refresh_source_symbols(self):
        if not hasattr(self,'source_symbol_entries'):return
        listing=self.source_symbol_entries
        listing.clear()
        canvas=self.current_canvas() if hasattr(self,'tabs') else None
        if not isinstance(canvas,GraphCanvas) or not canvas.source_view or self.python_doc is None:
            return
        session=self._view_sessions.get(canvas.session_id)
        if (session is None or session.route.kind!='source' or
                Path(session.route.path).resolve()!=self.python_doc.path.resolve()):
            return
        query=self.source_symbol_search.text().strip().casefold()
        from PyQt6.QtWidgets import QListWidgetItem
        for symbol in self.python_doc.browse_symbols():
            scope_label=('module' if symbol.scope=='module' else
                         ' / '.join(self.python_doc.scopes[key].title for key in
                                  self._symbol_scope_path(symbol.scope)))
            label=f'{symbol.kind.upper()}  {symbol.name}  ·  {scope_label}  ·  L{symbol.line}'
            if query and not all(term in label.casefold() for term in query.split()):continue
            item=QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole,symbol)
            item.setToolTip('Saved Python symbol · navigate only, no source modification')
            listing.addItem(item)
        self._update_symbol_authoring()

    def _selected_qualified_symbol(self):
        """Resolve browser selection against current source and adapter eligibility."""
        if (not self._qualified_source_context() or
                not hasattr(self,'source_symbol_entries')):
            return None
        item=self.source_symbol_entries.currentItem()
        symbol=item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        if symbol is None or symbol.kind not in ('variable','parameter'):
            return None
        for scope,names,anchor in eligible_value_assignment_targets(self.python_doc):
            if scope==symbol.scope and symbol.name in names:
                return (scope,symbol.name,anchor)
        return None

    def _selected_qualified_interface(self):
        if not self._qualified_source_context() or not hasattr(self,'source_symbol_entries'):
            return None
        item=self.source_symbol_entries.currentItem()
        symbol=item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        if symbol is None or symbol.scope not in self.python_doc.scopes:return None
        scope=self.python_doc.scopes[symbol.scope]
        if scope.kind!='function' or scope.parent!='module':return None
        function_name=scope.ast_node.name
        if symbol.kind=='function' and function_name in eligible_rename_functions(self.python_doc):
            return ('python.rename-function.v1',function_name,None)
        if symbol.kind=='parameter' and symbol.name in dict(eligible_parameter_renames(self.python_doc)).get(function_name,()):
            return ('python.rename-parameter.v1',function_name,symbol.name)
        return None

    def _update_symbol_authoring(self):
        selected=self._selected_qualified_symbol()
        if hasattr(self,'source_symbol_use'):
            self.source_symbol_use.setEnabled(selected is not None)
        if hasattr(self,'source_symbol_call'):
            self.source_symbol_call.setEnabled(selected is not None and any(
                scope==selected[0] and anchor==selected[2]
                for scope,_,anchor,_ in eligible_composed_call_targets(self.python_doc)))
        if hasattr(self,'source_symbol_rename'):
            self.source_symbol_rename.setEnabled(self._selected_qualified_interface() is not None)

    def _call_from_selected_symbol(self):
        value=self._selected_qualified_symbol()
        if value is None:return
        self._create_qualified_operation('python.call-with-values.v1',preferred_value=value)

    def _rename_from_selected_symbol(self):
        target=self._selected_qualified_interface()
        if target is None:return
        self._create_qualified_operation(target[0],preferred_symbol=target[1:])

    def _create_from_selected_symbol(self):
        candidate=self._selected_qualified_symbol()
        if candidate is None:
            self.report('Selected symbol is not a qualified local source value')
            return
        self._create_qualified_operation('python.assign-source-local.v1',preferred_value=candidate)

    def _symbol_scope_path(self,scope_key):
        # Existing lexical parent chain is the only hierarchy authority.
        keys=[]
        while scope_key!='module':
            keys.append(scope_key)
            scope_key=self.python_doc.scopes[scope_key].parent
        return reversed(keys)

    def _navigate_source_symbol(self,item):
        canvas=self.current_canvas()
        if not isinstance(canvas,GraphCanvas) or not canvas.source_view or self.python_doc is None:
            return
        symbol=item.data(Qt.ItemDataRole.UserRole)
        active=self._active_source_document()
        if symbol is None or active is None or not active.graph_ready:
            self.report('Python source must be parseable before navigating symbols')
            return
        if symbol.scope not in self.python_doc.scopes:return
        if not self.navigate_source(symbol.scope):return
        # Parameter nodes have a stable adapter ID. Don't guess that an
        # arbitrary source statement is the exact visual node for a binding.
        if symbol.kind=='parameter':
            identity=f'py:{symbol.scope}|param|{symbol.name}'
            node=self.source_canvas.items_by_id.get(identity)
            if node is not None and node.isVisible():
                self.source_canvas.graph_scene.clearSelection()
                node.setSelected(True)
                self.source_canvas.frame_node(node)
        # Even when no graph node is visible (opaque/large source), navigating
        # to the exact lexical source line remains reliable and read-only.
        if self._loaded_editor_identity==(str(active.path),active.revision):
            block=self.source_editor.document().findBlockByNumber(symbol.line-1)
            if block.isValid():
                cursor=self.source_editor.textCursor()
                cursor.setPosition(block.position())
                cursor.select(QTextCursor.SelectionType.LineUnderCursor)
                self.source_editor.setTextCursor(cursor)
                self.source_editor.centerCursor()
        self.report(f'{symbol.kind.title()}: {symbol.name} · line {symbol.line}')

    def _select_observed_operation(self,item):
        canvas=self.current_canvas()
        if not isinstance(canvas,GraphCanvas) or not canvas.source_view:return
        for identity in item.data(Qt.ItemDataRole.UserRole) or ():
            target=canvas.items_by_id.get(identity)
            if target is not None and target.isVisible():
                canvas.graph_scene.clearSelection()
                target.setSelected(True)
                canvas.frame_node(target)
                self.highlight_python_node(target.data)
                return
        self.statusBar().showMessage('Operation is present in source but not visible in this graph view')

    def creation_candidates(self, canvas=None, pin=None):
        """One adapter-owned registry for library, blank-graph and output-pin search."""
        canvas=canvas or self.current_canvas()
        if not isinstance(canvas,GraphCanvas):return ()
        if canvas.source_view:
            return (available_actions(self.python_doc,pin=pin) if
                    canvas is self.current_canvas() and self._qualified_source_context() else ())
        if canvas.resource_view or canvas.settings_view:return ()
        # Draft templates remain a distinct, non-Python prototype authority.
        return ()

    def open_creation_menu(self,canvas=None,*,pin=None,screen_pos=None):
        """Blueprint-style searchable menu, never an unqualified source editor.

        The selected action ID is passed to the SAME diff proposal path as
        the library button. A pin-drop advertises only adapter-verified links.
        """
        canvas=canvas or self.current_canvas()
        choices=self.creation_candidates(canvas,pin)
        if not choices:
            if pin is not None:
                self.report('No adapter-qualified creation accepts this source pin yet')
            else:
                self.report('Open a supported Python function with saved text to create code')
            return
        dialog=QDialog(self)
        dialog.setObjectName('QualifiedGraphCreationSearch')
        dialog.setWindowTitle('Create Python operation · context sensitive')
        dialog.resize(390,300)
        layout=QVBoxLayout(dialog);layout.setContentsMargins(9,9,9,9);layout.setSpacing(5)
        search=QLineEdit(dialog);search.setObjectName('CreationActionSearch')
        search.setPlaceholderText('Search qualified operations…')
        listing=QListWidget(dialog);listing.setObjectName('QualifiedCreationResults')
        message=QLabel('Only adapter-qualified source changes appear. A diff is reviewed before saving.')
        message.setWordWrap(True);message.setStyleSheet('color:#83b1cb;')
        layout.addWidget(search);layout.addWidget(listing,1);layout.addWidget(message)
        selected=[None]
        def fill(query):
            listing.clear()
            for entry in search_actions(choices,query):
                from PyQt6.QtWidgets import QListWidgetItem
                item=QListWidgetItem(entry.title+'   ·   '+entry.category)
                item.setToolTip(entry.description)
                item.setData(Qt.ItemDataRole.UserRole,entry)
                listing.addItem(item)
            if listing.count():listing.setCurrentRow(0)
        def accept():
            item=listing.currentItem()
            if item is not None:
                selected[0]=item.data(Qt.ItemDataRole.UserRole)
                dialog.accept()
        search.textChanged.connect(fill)
        search.returnPressed.connect(accept)
        listing.itemDoubleClicked.connect(lambda _:accept())
        fill('')
        if screen_pos is not None:dialog.move(screen_pos)
        search.setFocus()
        if dialog.exec()==QDialog.DialogCode.Accepted and selected[0] is not None:
            action=selected[0]
            self._create_qualified_operation(action.id,pin=pin,qualified_action=action)

    def _ask_variable_assignment(self,scope,anchor,names,preselected=None):
        """One complete Blueprint-style assignment transaction, no chained prompts.

        Only the adapter lowers this intent. Existing source values must be
        from the qualified scope; an empty name list still permits literals.
        """
        dialog=QDialog(self)
        dialog.setObjectName('QualifiedVariableAssignmentDialog')
        dialog.setWindowTitle('Create variable · qualified Python source')
        layout=QVBoxLayout(dialog)
        form=QFormLayout()
        source=QComboBox(dialog);source.setObjectName('VariableSource')
        source.addItem('Primitive literal',None)
        for name in names:source.addItem(name,name)
        if preselected is not None:
            index=source.findData(preselected)
            if index<0:raise SourceError('Selected source value is no longer qualified')
            source.setCurrentIndex(index)
            source.setEnabled(False)
        literal=QLineEdit('0',dialog);literal.setObjectName('VariableLiteral')
        literal.setPlaceholderText('0, True, None, "text", ...')
        variable=QLineEdit('new_value',dialog);variable.setObjectName('VariableName')
        connect=QCheckBox('Connect new variable to final Return',dialog)
        connect.setObjectName('VariableFeedReturn')
        if source.currentData() is not None:literal.setEnabled(False)
        source.currentIndexChanged.connect(lambda _:literal.setEnabled(source.currentData() is None))
        form.addRow('Source value',source)
        form.addRow('Literal',literal)
        form.addRow('Fresh variable name',variable)
        layout.addLayout(form);layout.addWidget(connect)
        explain=QLabel('Creates a new local from a proven existing value or literal. '
                       'Review the exact source diff before saving.',dialog)
        explain.setWordWrap(True);layout.addWidget(explain)
        buttons=QHBoxLayout();cancel=QPushButton('Cancel',dialog);create=QPushButton('Review source diff',dialog)
        cancel.clicked.connect(dialog.reject);create.clicked.connect(dialog.accept)
        buttons.addStretch();buttons.addWidget(cancel);buttons.addWidget(create)
        layout.addLayout(buttons)
        if dialog.exec()!=QDialog.DialogCode.Accepted:return None
        selection=source.currentData()
        operand=(OperandReference('name',selection) if selection is not None else
                 OperandReference('literal',literal.text()))
        return propose_assign_source_value(self.python_doc,scope,
                    ValueAssignment(operand,variable.text(),connect.isChecked()),anchor)

    def _ask_binary_composition(self,scope,anchor,names,preselected=None):
        """A single composer form, using the existing guarded Python lowering."""
        dialog=QDialog(self);dialog.setObjectName('QualifiedBinaryCompositionDialog')
        dialog.setWindowTitle('Compose expression · qualified Python source')
        layout=QVBoxLayout(dialog);form=QFormLayout()
        left=QComboBox(dialog);left.setObjectName('ComposerLeft')
        left.addItems(names)
        if preselected is not None:
            index=left.findText(preselected)
            if index<0:raise SourceError('Source pin is no longer available')
            left.setCurrentIndex(index);left.setEnabled(False)
        op=QComboBox(dialog);op.setObjectName('ComposerOperator')
        op.addItems(('+','-','*','==','!=','<','<=','>','>='))
        right=QComboBox(dialog);right.setObjectName('ComposerRight')
        right.addItem('Primitive literal',None)
        for name in names:right.addItem(name,name)
        literal=QLineEdit('2',dialog);literal.setObjectName('ComposerLiteral')
        right.currentIndexChanged.connect(lambda _:literal.setEnabled(right.currentData() is None))
        variable=QLineEdit('computed',dialog);variable.setObjectName('ComposerResult')
        connect=QCheckBox('Connect new variable to final Return',dialog)
        connect.setObjectName('ComposerFeedReturn');connect.setChecked(True)
        for title,field in (('Left value',left),('Operation',op),('Right value',right),
                            ('Right literal',literal),('New result variable',variable)):
            form.addRow(title,field)
        layout.addLayout(form);layout.addWidget(connect)
        explain=QLabel('Reads stored source values; does not re-execute their producers. '
                       'Only a reviewed source diff can change the file.',dialog)
        explain.setWordWrap(True);layout.addWidget(explain)
        actions=QHBoxLayout();cancel=QPushButton('Cancel',dialog);review=QPushButton('Review source diff',dialog)
        cancel.clicked.connect(dialog.reject);review.clicked.connect(dialog.accept)
        actions.addStretch();actions.addWidget(cancel);actions.addWidget(review);layout.addLayout(actions)
        if dialog.exec()!=QDialog.DialogCode.Accepted:return None
        choice=right.currentData()
        operand=(OperandReference('name',choice) if choice is not None else
                 OperandReference('literal',literal.text()))
        return propose_compose_binary_local(self.python_doc,scope,
                BinaryComposition(OperandReference('name',left.currentText()),op.currentText(),
                                  operand,variable.text(),connect.isChecked()),anchor)

    def _ask_stored_call(self,*,scope,anchor,names,callees,preselected=None):
        """Blueprint-style call parameter form, all inputs explicitly bound."""
        dialog=QDialog(self);dialog.setObjectName('QualifiedStoredCallDialog')
        dialog.setWindowTitle('Function Call · bind inputs and store result')
        layout=QVBoxLayout(dialog);form=QFormLayout()
        selector=QComboBox(dialog);selector.setObjectName('StoredCallCallee')
        for function,signature in callees:
            selector.addItem(f'{function}({", ".join(signature)})',function)
        form.addRow('Call function',selector)
        rows=[]
        for index in range(max(len(signature) for _,signature in callees)):
            choice=QComboBox(dialog);choice.setObjectName(f'StoredCallInput{index}')
            choice.addItem('Primitive literal',None)
            for name in names:choice.addItem(name,name)
            if preselected is not None and index==0:
                pos=choice.findData(preselected)
                if pos<0:raise SourceError('Source pin is no longer a qualified input')
                choice.setCurrentIndex(pos)
                choice.setEnabled(False)
            literal=QLineEdit('0',dialog);literal.setObjectName(f'StoredCallLiteral{index}')
            choice.currentIndexChanged.connect(lambda _,c=choice,l=literal:l.setEnabled(c.currentData() is None))
            container=QWidget(dialog);horizontal=QHBoxLayout(container)
            horizontal.setContentsMargins(0,0,0,0);horizontal.addWidget(choice);horizontal.addWidget(literal)
            form.addRow('Argument '+str(index+1),container)
            rows.append((container,choice,literal))
        result=QLineEdit('call_result',dialog);result.setObjectName('StoredCallResult')
        form.addRow('New result variable',result)
        feed=QCheckBox('Use result as final Return value',dialog);feed.setChecked(True)
        feed.setObjectName('StoredCallFeedReturn')
        layout.addLayout(form);layout.addWidget(feed)
        info=QLabel('This is an explicit function invocation, which may have side effects. '
                    'Only source-qualified bindings are offered. Review the diff before saving.',dialog)
        info.setWordWrap(True);layout.addWidget(info)
        controls=QHBoxLayout();cancel=QPushButton('Cancel',dialog);review=QPushButton('Review source diff',dialog)
        cancel.clicked.connect(dialog.reject);review.clicked.connect(dialog.accept)
        controls.addStretch();controls.addWidget(cancel);controls.addWidget(review);layout.addLayout(controls)
        def update_rows(_=None):
            count=len(dict(callees)[selector.currentData()])
            for i,(container,_,_) in enumerate(rows):
                container.setVisible(i<count)
        selector.currentIndexChanged.connect(update_rows);update_rows()
        if dialog.exec()!=QDialog.DialogCode.Accepted:return None
        inputs=[]
        for _,choice,literal in rows[:len(dict(callees)[selector.currentData()])]:
            inputs.append(OperandReference('name',choice.currentData()) if choice.currentData() is not None
                          else OperandReference('literal',literal.text()))
        return propose_composed_call(self.python_doc,scope,
                CallComposition(selector.currentData(),tuple(inputs),result.text(),feed.isChecked()),anchor)

    def _create_qualified_branch(self):
        """Compatibility entry point; the adapter owns the actual operation."""
        self._create_qualified_operation('python.branch-early-return.v1')

    def _create_qualified_operation(self, operation_id: str, *, pin=None, qualified_action=None,
                                    preferred_value=None, preferred_symbol=None):
        """Present adapter-qualified inputs; all source writes use the existing review path."""
        canvas=self.current_canvas()
        if not self._qualified_source_context():
            self.report('Select a Python graph and save text edits before creating operations')
            return
        definitions={entry.id:entry for entry in qualified_operations('python')}
        if operation_id not in definitions:
            self.report('No qualified adapter creator for the requested operation')
            return
        # Module/function interface operations do not require an existing Return
        # or Pass anchor. This path makes initially empty Python files eligible
        # for visual authoring, using the very same source proposal review.
        if operation_id in ('python.create-function.v1',
                            'python.create-main-entry.v1',
                            'python.add-optional-keyword-parameter.v1',
                            'python.rename-function.v1',
                            'python.rename-parameter.v1'):
            if pin is not None:
                self.report('Function definitions and module entry points are not pin-drop operations')
                return
            try:
                if operation_id=='python.create-function.v1':
                    name,ok=QInputDialog.getText(self,'Create Python function',
                        'New function name:',text='new_function')
                    if not ok:return
                    parameters,ok=QInputDialog.getText(self,'Function inputs',
                        'Comma-separated parameter names (empty for none):',text='')
                    if not ok:return
                    proposal=propose_create_function(self.python_doc,name,parameters)
                elif operation_id=='python.rename-parameter.v1':
                    eligible=eligible_parameter_renames(self.python_doc)
                    names=[name for name,_ in eligible]
                    if preferred_symbol is not None:
                        function_name,old=preferred_symbol
                        if function_name not in names or old not in dict(eligible)[function_name]:
                            raise SourceError('Selected input is no longer qualified')
                    else:
                        function_name,ok=QInputDialog.getItem(self,'Rename Python input',
                            'Choose qualified function:',names,0,False)
                        if not ok:return
                        inputs=dict(eligible)[function_name]
                        old,ok=QInputDialog.getItem(self,'Rename Python input',
                            'Choose existing function input:',list(inputs),0,False)
                        if not ok:return
                    replacement,ok=QInputDialog.getText(self,'Rename Python input',
                        'New parameter name (in-file keyword calls will be synchronized):',text=old+'_new')
                    if not ok:return
                    proposal=propose_rename_parameter(self.python_doc,function_name,old,replacement)
                elif operation_id=='python.rename-function.v1':
                    names=eligible_rename_functions(self.python_doc)
                    if preferred_symbol is not None:
                        previous=preferred_symbol[0]
                        if previous not in names:raise SourceError('Selected function is no longer qualified')
                    else:
                        previous,ok=QInputDialog.getItem(self,'Rename Python function',
                            'Select a local function with qualified direct calls:',list(names),0,False)
                        if not ok:return
                    replacement,ok=QInputDialog.getText(self,'Rename function interface',
                        'New function name (direct local callers will be updated):',text=previous+'_new')
                    if not ok:return
                    proposal=propose_rename_function(self.python_doc,previous,replacement)
                elif operation_id=='python.create-main-entry.v1':
                    functions=eligible_entry_functions(self.python_doc)
                    function_name,ok=QInputDialog.getItem(self,'Create main program entry',
                        'Call a zero-argument module function from __main__:',list(functions),0,False)
                    if not ok:return
                    proposal=propose_create_main_entry(self.python_doc,function_name)
                else:
                    functions=eligible_signature_functions(self.python_doc)
                    function_name,ok=QInputDialog.getItem(self,'Add function input',
                        'Select module function:',list(functions),0,False)
                    if not ok:return
                    parameter,ok=QInputDialog.getText(self,'New function input',
                        'New optional keyword-only parameter:',text='enabled')
                    if not ok:return
                    default,ok=QInputDialog.getText(self,'Function input default',
                        'Primitive default (None, 0, True, "text"):',text='None')
                    if not ok:return
                    proposal=propose_add_optional_parameter(self.python_doc,function_name,
                                   parameter,default,update_local_calls=True)
            except (OSError,ValueError) as exc:
                QMessageBox.warning(self,'Source creation refused',str(exc))
                return
            self.review_source_proposal(proposal)
            return
        is_compose=operation_id=='python.compose-binary-local.v1'
        is_value=operation_id=='python.assign-source-local.v1'
        is_stored_call=operation_id=='python.call-with-values.v1'
        is_parameter_return=operation_id=='python.return-parameter-from-pass.v1'
        is_arithmetic=operation_id=='python.arithmetic-return-from-pass.v1'
        is_comparison=operation_id=='python.comparison-branch-return.v1'
        is_call_pass=operation_id=='python.call-return-from-pass.v1'
        is_call_continue=operation_id=='python.call-before-return.v1'
        is_call=is_call_pass or is_call_continue
        is_flow=operation_id in ('python.conditional-return-from-pass.v1',
                                 'python.for-range-accumulate.v1',
                                 'python.while-countdown.v1')
        is_placeholder=operation_id in ('python.return-from-pass.v1',
                                        'python.return-parameter-from-pass.v1',
                                        'python.arithmetic-return-from-pass.v1') or is_flow
        entries=[]
        if is_compose or is_value or is_stored_call:
            candidates=qualified_composition_anchors(self.python_doc,operation_id)
            for scope,names,anchor in candidates:
                if preferred_value is not None and (scope,anchor)!=(preferred_value[0],preferred_value[2]):
                    continue
                if preferred_value is not None and preferred_value[1] not in names:
                    continue
                if pin is not None and not any(
                        route==scope and name==qualified_action.parameter and matched==anchor
                        for route,name,matched in (compatible_composition_pin(self.python_doc,*pin)
                            if is_compose else compatible_composed_call_pin(self.python_doc,*pin)
                            if is_stored_call else compatible_value_assignment_pin(self.python_doc,*pin))):
                    continue
                label=self.python_doc.scopes[scope].title
                entries.append((f'{label} · return line {anchor["line"]} [{scope}]',scope,names,anchor))
        elif is_placeholder:
            for scope,anchor in eligible_pass_targets(self.python_doc):
                if is_call_pass and not qualified_callees(self.python_doc,scope):
                    continue
                if pin is not None and is_call_pass and not any(
                    route==scope and matched==anchor for route,_,matched in
                    compatible_parameter_pin(self.python_doc,*pin)):
                    continue
                if is_flow and not any(key==scope and candidate==anchor
                                      for key,_,candidate in eligible_flow_pass_targets(self.python_doc)):
                    continue
                if (is_parameter_return or is_arithmetic) and not any(
                    route==scope and matched==anchor for route,_,matched in
                    (compatible_parameter_pin(self.python_doc,*pin) if pin else
                     eligible_parameter_returns(self.python_doc))):
                    continue
                name=self.python_doc.scopes[scope].title
                entries.append((f'{name} · pass line {anchor["line"]} [{scope}]',scope,(),anchor))
        else:
            for scope,parameters,returns in (eligible_targets(self.python_doc)
                    if operation_id in ('python.branch-early-return.v1',
                                        'python.comparison-branch-return.v1') else eligible_return_targets(self.python_doc)):
                name=self.python_doc.scopes[scope].title
                for anchor in returns:
                    if is_call_continue and not qualified_callees(self.python_doc,scope):
                        continue
                    if pin is not None and (is_comparison or is_call_continue) and (
                            scope,qualified_action.parameter,anchor) not in compatible_parameter_return_pin(self.python_doc,*pin):
                        continue
                    entries.append((f'{name} · return line {anchor["line"]} [{scope}]',scope,parameters,anchor))
        if not entries:
            self.report('No qualified function anchor for this Python operation')
            return
        active=self.source_scope if isinstance(self.source_scope,str) else ''
        default=next((i for i,row in enumerate(entries) if row[1]==active),0)
        choices=[row[0] for row in entries]
        if len(entries)==1:
            chosen=entries[0]
        else:
            label,ok=QInputDialog.getItem(self,'Choose Python function',
                    ('Replace placeholder:' if is_placeholder else 'Insert before / rewrite Return:'),
                    choices,default,False)
            if not ok:return
            chosen=entries[choices.index(label)]
        try:
            if is_value:
                names=list(chosen[2])
                if pin is not None:
                    source_name=qualified_action.parameter
                    if (chosen[1],source_name,chosen[3]) not in compatible_value_assignment_pin(
                            self.python_doc,*pin):
                        raise SourceError('Dragged pin is not a currently qualified value')
                elif preferred_value is not None:
                    source_name=preferred_value[1]
                    if (chosen[1],source_name,chosen[3]) != preferred_value:
                        raise SourceError('Selected source symbol changed before authoring')
                else:
                    source_name=None
                proposal=self._ask_variable_assignment(chosen[1],chosen[3],names,source_name)
                if proposal is None:return
            elif is_stored_call:
                names=list(chosen[2]);name_set=set(names)
                if pin is not None:
                    first_name=qualified_action.parameter
                    if first_name not in name_set or (chosen[1],first_name,chosen[3]) not in compatible_composed_call_pin(self.python_doc,*pin):
                        raise SourceError('Call source pin is no longer a qualified value producer')
                else:first_name=preferred_value[1] if preferred_value is not None else None
                callees=dict(qualified_callees(self.python_doc,chosen[1]))
                if not callees:raise SourceError('No qualified callees remain')
                proposal=self._ask_stored_call(scope=chosen[1],anchor=chosen[3],names=names,
                                               callees=tuple(callees.items()),preselected=first_name)
                if proposal is None:return
            elif is_compose:
                names=list(chosen[2]);name_set=set(names)
                if pin is not None:
                    left_name=qualified_action.parameter
                    if left_name not in name_set or (chosen[1],left_name,chosen[3]) not in compatible_composition_pin(self.python_doc,*pin):
                        raise SourceError('Composer source pin is no longer a qualified value producer')
                else:
                    left_name=None
                proposal=self._ask_binary_composition(chosen[1],chosen[3],names,left_name)
                if proposal is None:return
            elif is_flow:
                fn=self.python_doc.scopes[chosen[1]].ast_node
                parameters=list(a.arg for a in (*fn.args.posonlyargs,*fn.args.args,*fn.args.kwonlyargs))
                if fn.args.vararg:parameters.append(fn.args.vararg.arg)
                if fn.args.kwarg:parameters.append(fn.args.kwarg.arg)
                if pin is not None:
                    parameter=qualified_action.parameter
                    if (chosen[1],parameter,chosen[3]) not in compatible_parameter_pin(
                            self.python_doc,*pin):
                        raise SourceError('Selected flow input no longer matches this parameter pin')
                else:
                    parameter,ok=QInputDialog.getItem(self,'Flow input',
                        'Select a function parameter:',parameters,0,False)
                    if not ok:return
                if operation_id=='python.conditional-return-from-pass.v1':
                    operator,ok=QInputDialog.getItem(self,'Branch condition',
                        'Compare parameter using:',list(('==','!=','<','<=','>','>=')),0,False)
                    if not ok:return
                    compared,ok=QInputDialog.getText(self,'Condition operand',
                        'Primitive literal for comparison:',text='0')
                    if not ok:return
                    true,ok=QInputDialog.getText(self,'True Return',
                        'Primitive returned by True path:',text='-1')
                    if not ok:return
                    false,ok=QInputDialog.getText(self,'False Return',
                        'Primitive returned by False path:',text='1')
                    if not ok:return
                    proposal=propose_conditional_returns_from_pass(self.python_doc,
                        chosen[1],parameter,operator,compared,true,false,chosen[3])
                elif operation_id=='python.for-range-accumulate.v1':
                    index,ok=QInputDialog.getText(self,'For-loop index',
                        'Fresh loop index:',text='index')
                    if not ok:return
                    total,ok=QInputDialog.getText(self,'For-loop accumulator',
                        'Fresh result variable:',text='total')
                    if not ok:return
                    proposal=propose_for_range_accumulate(self.python_doc,chosen[1],
                        parameter,index,total,chosen[3])
                else:
                    counter,ok=QInputDialog.getText(self,'While-loop counter',
                        'Fresh local counter:',text='current')
                    if not ok:return
                    steps,ok=QInputDialog.getText(self,'While-loop steps',
                        'Fresh local steps variable:',text='steps')
                    if not ok:return
                    proposal=propose_while_countdown(self.python_doc,chosen[1],
                        parameter,counter,steps,chosen[3])
            elif operation_id=='python.branch-early-return.v1':
                parameter,ok=QInputDialog.getItem(self,'Branch condition',
                    'Parameter is None:',list(chosen[2]),0,False)
                if not ok:return
                literal,ok=QInputDialog.getText(self,'Early Return',
                    'Primitive returned on True (None, 0, "missing"):',text='None')
                if not ok:return
                proposal=propose_branch_early_return(self.python_doc,chosen[1],parameter,literal,chosen[3])
            elif is_comparison:
                if pin is not None:
                    parameter=qualified_action.parameter
                    if (chosen[1],parameter,chosen[3]) not in compatible_parameter_return_pin(self.python_doc,*pin):
                        raise SourceError('Comparison source pin is no longer qualified')
                else:
                    parameter,ok=QInputDialog.getItem(self,'Comparison input',
                        'Function parameter:',list(chosen[2]),0,False)
                    if not ok:return
                operator,ok=QInputDialog.getItem(self,'Comparison operator',
                    'Python comparison:',list(('==','!=','<','<=','>','>=')),0,False)
                if not ok:return
                operand,ok=QInputDialog.getText(self,'Comparison operand',
                    'Primitive compared with the parameter:',text='0')
                if not ok:return
                result,ok=QInputDialog.getText(self,'True-path Return',
                    'Primitive returned if comparison is True:',text='None')
                if not ok:return
                proposal=propose_comparison_branch_return(self.python_doc,chosen[1],
                            parameter,operator,operand,result,chosen[3])
            elif is_call:
                if pin is not None:
                    matches=(compatible_parameter_pin(self.python_doc,*pin)
                             if is_call_pass else compatible_parameter_return_pin(self.python_doc,*pin))
                    parameter=qualified_action.parameter
                    if (chosen[1],parameter,chosen[3]) not in matches:
                        raise SourceError('Call source pin is no longer qualified')
                else:
                    fn=self.python_doc.scopes[chosen[1]].ast_node
                    parameters=[p.arg for p in (*fn.args.posonlyargs,*fn.args.args,*fn.args.kwonlyargs)]
                    if fn.args.vararg:parameters.append(fn.args.vararg.arg)
                    if fn.args.kwarg:parameters.append(fn.args.kwarg.arg)
                    parameter,ok=QInputDialog.getItem(self,'Connect Call input',
                        'Caller parameter for the first argument:',parameters,0,False)
                    if not ok:return
                callees=qualified_callees(self.python_doc,chosen[1])
                names=[f'{name}({", ".join(signature)})' for name,signature in callees]
                label,ok=QInputDialog.getItem(self,'Create source-backed Call',
                    'Choose a uniquely defined Python function:',names,0,False)
                if not ok:return
                callee,signature=callees[names.index(label)]
                literal_arguments=[]
                for index,arg in enumerate(signature[1:],2):
                    literal,ok=QInputDialog.getText(self,'Call argument',
                        f'Primitive value for argument {index} ({arg}):',text='0')
                    if not ok:return
                    literal_arguments.append(literal)
                if is_call_pass:
                    proposal=propose_call_return_from_pass(self.python_doc,chosen[1],parameter,
                                              callee,tuple(literal_arguments),chosen[3])
                else:
                    proposal=propose_call_before_return(self.python_doc,chosen[1],parameter,
                                              callee,tuple(literal_arguments),chosen[3])
            elif is_arithmetic:
                if pin is not None:
                    parameter=qualified_action.parameter
                    if (chosen[1],parameter,chosen[3]) not in compatible_parameter_pin(self.python_doc,*pin):
                        raise SourceError('Arithmetic source pin is no longer qualified')
                else:
                    fn=self.python_doc.scopes[chosen[1]].ast_node
                    declared=[a.arg for a in (*fn.args.posonlyargs,*fn.args.args,*fn.args.kwonlyargs)]
                    if fn.args.vararg:declared.append(fn.args.vararg.arg)
                    if fn.args.kwarg:declared.append(fn.args.kwarg.arg)
                    parameter,ok=QInputDialog.getItem(self,'Arithmetic input',
                        'Function parameter:',declared,0,False)
                    if not ok:return
                operator,ok=QInputDialog.getItem(self,'Arithmetic operation',
                    'Python arithmetic:',list(('+','-','*')),0,False)
                if not ok:return
                operand,ok=QInputDialog.getText(self,'Numeric operand',
                    'Finite integer or float:',text='1')
                if not ok:return
                proposal=propose_arithmetic_return_from_pass(self.python_doc,chosen[1],
                                            parameter,operator,operand,chosen[3])
            elif operation_id=='python.local-literal-return.v1':
                name,ok=QInputDialog.getText(self,'Create local binding',
                    'New local variable name (must not already exist):',text='result')
                if not ok:return
                literal,ok=QInputDialog.getText(self,'Local literal value',
                    'Primitive assigned to the local (0, True, "text"):',text='0')
                if not ok:return
                proposal=propose_local_literal_return(self.python_doc,chosen[1],name,literal,chosen[3])
            elif is_parameter_return:
                if pin is not None:
                    matches=compatible_parameter_pin(self.python_doc,*pin)
                    selected=next((parameter for scope,parameter,anchor in matches if
                                   scope==chosen[1] and anchor==chosen[3]),None)
                    if selected is None:raise SourceError('Source pin no longer matches the function placeholder')
                else:
                    fn=self.python_doc.scopes[chosen[1]].ast_node
                    declared=[a.arg for a in (*fn.args.posonlyargs,*fn.args.args,*fn.args.kwonlyargs)]
                    if fn.args.vararg:declared.append(fn.args.vararg.arg)
                    if fn.args.kwarg:declared.append(fn.args.kwarg.arg)
                    selected,ok=QInputDialog.getItem(self,'Connect Return input',
                        'Choose a real parameter output:',declared,0,False)
                    if not ok:return
                proposal=propose_return_parameter_from_pass(self.python_doc,chosen[1],selected,chosen[3])
            else:
                literal,ok=QInputDialog.getText(self,'Create Return',
                    'Primitive returned instead of pass:',text='None')
                if not ok:return
                proposal=propose_return_from_pass(self.python_doc,chosen[1],literal,chosen[3])
        except (OSError,ValueError) as exc:
            QMessageBox.warning(self,'Source creation refused',str(exc))
            return
        self.review_source_proposal(proposal)

    def _build_inspector(self):
        self.inspector_dock=QDockWidget('NODE INSPECTOR',self)
        self.inspector_dock.setObjectName('InspectorDock')
        self.inspector_scroll=QScrollArea();self.inspector_scroll.setWidgetResizable(True)
        self.inspector_content=QWidget();self.inspector_layout=QVBoxLayout(self.inspector_content)
        self.inspector_scroll.setWidget(self.inspector_content)
        self.inspector_dock.setWidget(self.inspector_scroll)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea,self.inspector_dock)
        self.inspector_dock.resize(345,650)
        self.inspector_dock.hide()
        self.refresh_inspector()

    def _new_source_document(self,path):
        """Open source, then offer exact-preimage recovery without auto-merging."""
        session=SourceDocumentSession.open(path)
        record=self._draft_recovery.latest(session.path)
        if record is None or record.text==session.text:
            return session
        if record.base_sha256 != _digest(session.saved_raw):
            QMessageBox.warning(self,'Source recovery conflict',
                'An unsaved recovery draft exists, but the source file changed '
                'since that draft was recorded. It will not be merged or discarded. '
                'The recovery journal remains at: '+str(self._draft_recovery.root))
            return session
        decision=QMessageBox.question(self,'Recover unsaved Python draft',
            'An unsaved draft of '+session.path.name+' was found after a previous '
            'session. Recover it into the current editor?\n'
            'No keeps the recovery record available; the Python file is unchanged.',
            QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if decision==QMessageBox.StandardButton.Yes:
            session.restore_recovery(record)
            # A confirmed recovery is a document revision, never just a
            # dialog result or view-local text update.
            if session.text!=record.text or not session.dirty:
                raise SourceError('Recovery approval failed to publish the source draft')
            self.report('Recovered unsaved source draft without writing to disk')
        return session

    def _flush_source_recovery(self):
        """Flush every open draft, including documents not in the active tab."""
        for session in tuple(self._source_documents.values()):
            try:
                session.snapshot_recovery(self._draft_recovery)
            except (OSError,ValueError) as exc:
                self.report('Cannot preserve source recovery for '+str(session.path)+': '+str(exc))

    def _active_source_document(self):
        view=self._source_tabs.get(self._active_source_tab_id)
        route=self._view_sessions.get(view.session_id) if view else None
        return self._source_documents.get(route.route.path) if route else None

    def _refresh_live_source(self):
        """Publish exactly one analyzed revision to all views of this file.

        Invalid text is retained as text, with no old graph presented as new.
        Tab routes/cameras are independent; the parsed AST is shared.
        """
        session=self._active_source_document()
        if session is None:return
        self._store_active_source_view()
        session.qualify()
        self._source_editor_dirty=session.dirty
        self.python_doc=session.parsed
        identity=str(session.path)
        for sid,view in self._source_tabs.items():
            route_session=self._view_sessions.get(sid)
            if route_session is None or route_session.route.path!=identity:continue
            route=route_session.route
            if session.graph_ready:
                if route.mode=='focus' and route.scope not in session.parsed.scopes:
                    route=Route('source',identity)
                    route_session.activate(route,record_history=False)
                try:
                    result=resolve_graph(route,document=session.parsed,detail=view.detail,
                                         expanded_scopes=view.expanded.intersection(session.parsed.scopes),
                                         collapsed_regions=view.collapsed)
                except (ValueError,SourceError) as exc:
                    view.document=None;view.graph=None
                    session.diagnostic=str(exc)
                else:
                    view.document=result.document
                    view.graph=result.graph
            else:
                view.document=None
                view.graph=None
            if sid==self._active_source_tab_id:
                self.python_doc=view.document
                self.source_graph=view.graph
                self.source_scope=route.scope
                self.source_view_mode=route.mode
                view.canvas.rebuild()
                self._update_source_tab_title()
            else:
                view.needs_rebuild=True
        self._set_source_editor_label()
        self._refresh_operation_library()
        if not session.graph_ready:
            self.source_editor_note.setText('Source graph unavailable for revision '+str(session.revision)+
                ': '+str(session.diagnostic))
        else:
            self.source_editor_note.setText('Graph reflects unsaved revision '+str(session.revision)+
                ('. Save to publish source edits.' if session.dirty else '.'))
        self._refresh_resource_source_views(identity)

    def _build_source_editor(self):
        """The right panel is the REAL source document, not an HTML preview.

        It does not own parsed graph state; saving validated source and reloading
        the PythonDocument is the only authority-changing operation.
        """
        self.source_editor_dock=QDockWidget('PYTHON SOURCE · TEXT EDITOR',self)
        self.source_editor_dock.setObjectName('SourceEditorDock')
        outer=QWidget();layout=QVBoxLayout(outer)
        layout.setContentsMargins(5,5,5,5);layout.setSpacing(5)
        buttons=QHBoxLayout();buttons.setContentsMargins(0,0,0,0)
        open_button=QPushButton('Open .py');open_button.clicked.connect(self.open_python_file)
        save_button=QPushButton('Save Python');save_button.clicked.connect(self.save_python_editor)
        revert_button=QPushButton('Reload from disk');revert_button.clicked.connect(self.reload_python_source)
        buttons.addWidget(open_button);buttons.addWidget(save_button);buttons.addWidget(revert_button)
        layout.addLayout(buttons)
        self.source_file_label=QLabel('No Python file open')
        self.source_file_label.setWordWrap(True);self.source_file_label.setStyleSheet('color:#9dcae1;')
        layout.addWidget(self.source_file_label)
        self.source_editor=PythonSourceTextEdit(undo=self.undo_source_draft, redo=self.redo_source_draft)
        self.source_editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.source_editor.setTabStopDistance(QFontMetricsF(QFont('DejaVu Sans Mono',10)).horizontalAdvance(' ')*4)
        self.source_editor.setFont(QFont('DejaVu Sans Mono',10))
        self.source_editor.setStyleSheet('QPlainTextEdit { background:#061522; color:#e5eff9; border:1px solid #29506b; selection-background-color:#2a647d; }')
        self.source_editor.setPlaceholderText('Open a .py file to see and edit its actual source. Select a graph node to jump to its definition.')
        self.source_editor.setEnabled(False)
        # Qt owns selection/typing, but SourceDocumentSession owns history.
        # PythonSourceTextEdit intercepts Undo/Redo before Qt's own shortcuts.
        self.source_editor.setUndoRedoEnabled(False)
        self._syntax_highlighter=PythonSyntaxHighlighter(self.source_editor.document())
        self.source_editor.textChanged.connect(self._source_editor_changed)
        layout.addWidget(self.source_editor,1)
        self.source_editor_note=QLabel('Edit Python freely. Valid revisions update the graph; incomplete Python can be saved with its graph unavailable.')
        self.source_editor_note.setWordWrap(True);self.source_editor_note.setStyleSheet('color:#89b2c9;')
        layout.addWidget(self.source_editor_note)
        self.source_editor_dock.setWidget(outer)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea,self.source_editor_dock)
        self.source_editor_dock.resize(420,680)
        self.source_editor_dock.show()

    def _source_editor_changed(self):
        if self._source_editor_loading:return
        session=self._active_source_document()
        if session is None:return
        if session.update(self.source_editor.toPlainText(),parse=False):
            self._source_editor_dirty=session.dirty
            self._loaded_editor_identity=(str(session.path),session.revision)
            # Analysis is debounced; no synchronous AST work per keystroke.
            # Until it finishes, the displayed graph is explicitly unavailable.
            if self.source_graph is not None:
                self.source_graph=None
                self.source_canvas.rebuild()
            # A live edit immediately invalidates any older embedded source
            # projection; the existing debounce later publishes a qualified
            # replacement. A resource tab outside this file is unaffected.
            self._refresh_resource_source_views(str(session.path))
            self._source_analysis_timer.start()
            self._draft_recovery_timer.start()
        self._set_source_editor_label()

    def _set_source_editor_label(self):
        session=self._active_source_document()
        if session is None:
            self.source_file_label.setText('No Python file open');return
        status=(' · UNSAVED' if session.dirty else ' · saved')
        if session.external_state!='current':
            status+=' · DISK '+session.external_state.upper()+' (draft retained)'
        if not session.graph_ready:
            status+=' · graph unavailable'
        self.source_file_label.setText(str(session.path)+status)

    def check_python_external_change(self):
        session=self._active_source_document()
        if session is None:return None
        status=session.inspect_external()
        self._set_source_editor_label()
        self.report('Python disk revision: '+status+
                    ('. Source text preserved; explicitly reload to accept disk contents.'
                     if status!='current' else ''))
        return status

    def _navigate_draft_history(self, *, redo: bool):
        session=self._active_source_document()
        if session is None:return False
        if self._source_analysis_timer.isActive():
            self._source_analysis_timer.stop()
        try:
            changed=(session.redo_draft(parse=False) if redo
                     else session.undo_draft(parse=False))
        except SourceError as exc:
            self.report('Python draft history refused: '+str(exc))
            return False
        if not changed:return False
        # Rehydrate Qt from the one source-session authority, never use its
        # destroyed/previous-tab QTextDocument undo stack.
        old_cursor=self.source_editor.textCursor().position()
        self._load_source_editor()
        cursor=self.source_editor.textCursor()
        # QTextCursor positions are UTF-16 code units, not Python codepoints.
        # The rebuilt Qt document already knows its exact cursor bounds.
        cursor.setPosition(min(old_cursor,self.source_editor.document().characterCount()-1))
        self.source_editor.setTextCursor(cursor)
        self._refresh_live_source()
        self._draft_recovery_timer.start()
        return True

    def undo_source_draft(self):
        return self._navigate_draft_history(redo=False)

    def redo_source_draft(self):
        return self._navigate_draft_history(redo=True)

    def _load_source_editor(self):
        session=self._active_source_document()
        if session is None:return
        self._source_editor_loading=True
        try:
            self.source_editor.setPlainText(session.text)
            self.source_editor.setEnabled(True)
            self._source_editor_dirty=session.dirty
            self._loaded_editor_identity=(str(session.path),session.revision)
            self.source_editor.setExtraSelections([])
        finally:self._source_editor_loading=False
        self._set_source_editor_label()

    def highlight_python_node(self,node):
        """Source-backed node selection follows its exact span (UTF-8 -> UTF-16)."""
        if not self.python_doc or not node.get('source_span'):return
        session=self._active_source_document()
        if (session is None or session.parsed is not self.python_doc or
                self._loaded_editor_identity!=(str(session.path),session.revision)):
            return
        try:start,end=span_to_utf16(self.python_doc.source,node['source_span'])
        except (SourceError,KeyError,ValueError):return
        cursor=self.source_editor.textCursor()
        cursor.setPosition(start)
        cursor.setPosition(end,QTextCursor.MoveMode.KeepAnchor)
        highlight=QTextEdit.ExtraSelection()
        highlight.cursor=cursor
        highlight.format.setBackground(qcolor('#345a77'))
        highlight.format.setForeground(qcolor('#ffffff'))
        self.source_editor.setExtraSelections([highlight])
        self.source_editor.setTextCursor(cursor)
        self.source_editor.centerCursor()
        self.source_editor_note.setText('Source selection: lines '+str(node['source_span']['line'])+
                                         '–'+str(node['source_span']['end_line']))

    def confirm_source_editor_discard(self):
        if not self._source_editor_dirty:return True
        return QMessageBox.question(self,'Unsaved Python source',
            'Unsaved changes in the Python text editor will be discarded. Continue?',
            QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)==QMessageBox.StandardButton.Yes

    def save_python_editor(self):
        session=self._active_source_document()
        if session is None:
            self.report('Open a Python file first');return False
        if self._source_analysis_timer.isActive():
            self._source_analysis_timer.stop()
            self._refresh_live_source()
        if not session.dirty:
            self.report('Python source already saved');return True
        try:
            backup=session.commit(history=self._source_edit_history)
        except (OSError,ValueError) as exc:
            session.inspect_external()
            self._set_source_editor_label()
            QMessageBox.warning(self,'Python source not saved',str(exc));return False
        try:
            session.clear_recovery(self._draft_recovery)
        except (OSError, ValueError) as exc:
            # A successful source save must not be reported as a failed save
            # simply because cleanup of an optional recovery record failed.
            self.report('Source saved; recovery cleanup needs attention: '+str(exc))
        self._source_editor_dirty=False
        self._set_source_editor_label()
        self.report('Python source saved'+(' (graph unavailable until syntax is repaired)' if not session.graph_ready else ', graph reflects saved revision')+
                    ('. Backup: '+str(backup) if backup else ''))
        return True

    def _build_dock_regions(self):
        """Native Qt docks own placement. A region owns visibility behavior.

        The right region includes editor and inspector, so their dock policy
        follows the area rather than being independently patched into editors.
        Content ownership and source-editing behavior remain untouched.
        """
        self._managed_docks=[]
        left=DockRegionController(self,'left',Qt.DockWidgetArea.LeftDockWidgetArea)
        right=DockRegionController(self,'right',Qt.DockWidgetArea.RightDockWidgetArea)
        left.register(self.library_dock)
        right.register(self.source_editor_dock)
        right.register(self.inspector_dock)
        self._dock_regions={'left':left,'right':right}

    def _restore_dock_regions(self):
        for name,region in self._dock_regions.items():
            region.set_mode(self._dock_modes.get(name,'pinned'),save=False)

    def _build_menu(self):
        file=self.menuBar().addMenu('File')
        for label,callback,shortcut in [('New graph',self.new_graph,'Ctrl+N'),('Open JSON graph…',self.open_graph,'Ctrl+O'),
                                        ('Save',self.save_current_document,'Ctrl+S'),('Save as…',self.save_as,'Ctrl+Shift+S')]:
            action=QAction(label,self);action.triggered.connect(callback);action.setShortcut(shortcut);file.addAction(action)
        file.addSeparator()
        new_python=QAction('New Python source file…',self)
        new_python.setShortcut('Ctrl+Alt+N')
        new_python.triggered.connect(self.new_python_source_file)
        file.addAction(new_python)
        python_action=QAction('Open Python file as graph…',self)
        python_action.setShortcut('Ctrl+Alt+O');python_action.triggered.connect(self.open_python_file)
        file.addAction(python_action)
        file.addAction('Browse files as graph…',self.choose_resource_folder)
        file.addAction('Go up one file directory',self.resource_parent)
        file.addAction('Refresh file graph',self.refresh_resources)
        file.addAction('Next file graph page',lambda:self.page_resource(1))
        file.addAction('Previous file graph page',lambda:self.page_resource(-1))
        file.addAction('Reload Python source',self.reload_python_source)
        file.addAction('Check Python disk changes',self.check_python_external_change)
        close_tab=QAction('Close active graph tab',self)
        close_tab.setShortcut('Ctrl+W')
        close_tab.triggered.connect(lambda:self._close_graph_tab(self.tabs.currentIndex()))
        file.addAction(close_tab)
        py_save=QAction('Save Python text',self);py_save.setShortcut('Ctrl+Alt+S')
        py_save.triggered.connect(self.save_python_editor);file.addAction(py_save)
        file.addSeparator()
        file.addAction('New visual program (.smi-graph)',self.new_visual_program)
        file.addAction('Open visual program (.smi-graph)…',self.open_visual_program)
        edit_menu=self.menuBar().addMenu('Edit')
        # Committed edits have a separate explicit history/shortcut.
        edit_menu.addAction('Undo unsaved Python text',self.undo_source_draft)
        edit_menu.addAction('Redo unsaved Python text',self.redo_source_draft)
        self.source_undo_action=QAction('Undo committed Python source edit',self)
        self.source_undo_action.setShortcut('Ctrl+Alt+Z')
        self.source_undo_action.triggered.connect(self.undo_source_edit)
        edit_menu.addAction(self.source_undo_action)
        self.source_redo_action=QAction('Redo committed Python source edit',self)
        self.source_redo_action.setShortcut('Ctrl+Alt+Shift+Z')
        self.source_redo_action.triggered.connect(self.redo_source_edit)
        edit_menu.addAction(self.source_redo_action)
        file.addAction('Check Python syntax (no execution)',self.check_python_syntax)
        file.addAction('Run Python file (explicit, native interpreter)…',self.run_python_source)
        file.addSeparator();file.addAction('Exit',self.close)
        view=self.menuBar().addMenu('View')
        dock_view=view.addMenu('Dock regions')
        for name,region in self._dock_regions.items():
            group=dock_view.addMenu(name.title()+' region')
            for mode,label in [('pinned','Pinned'),('collapsed','Collapsed'),('auto-hide','Auto-hide')]:
                group.addAction(label,lambda checked=False,r=region,m=mode:r.set_mode(m))
        panes=view.addMenu('Dock windows')
        panes.addAction(self.library_dock.toggleViewAction())
        panes.addAction(self.source_editor_dock.toggleViewAction())
        panes.addAction(self.inspector_dock.toggleViewAction())
        legacy=view.addMenu('Legacy / Dev')
        self._legacy_actions={}
        for canvas,label in self._legacy_tabs:
            action=legacy.addAction(label)
            action.setCheckable(True)
            action.toggled.connect(lambda visible,c=canvas,l=label:
                                   self.toggle_legacy_graph(c,l,visible))
            self._legacy_actions[canvas]=action
        graph=self.menuBar().addMenu('Graph')
        graph.addAction('Add String Constant',lambda:self.create_node('string'))
        graph.addAction('Add Custom Node',lambda:self.create_node('custom'))
        graph.addAction('Reset zoom',self.reset_current_zoom)
        graph.addAction('Open Python scope graph',self.activate_source_tab)
        graph.addAction('Open current source in new tab',lambda:self.open_source_in_new_tab(self.python_doc.path,self.source_scope if self.source_view_mode=='focus' else 'module') if self.python_doc else None)
        graph.addAction('Open Files / System graph',self.activate_resource_tab)
        graph.addAction('Open current directory in new tab',
                        lambda:self.open_resource_in_new_tab(self.resource_path))
        toggle=QAction('Python: Whole file / focus toggle',self)
        toggle.setShortcut('Ctrl+Alt+G');toggle.triggered.connect(self.toggle_source_view);graph.addAction(toggle)
        graph.addAction('Python: Readable / Analysis view',self.toggle_python_detail)
        graph.addAction('Python: Expand all scopes',lambda:self.set_all_scopes(True))
        graph.addAction('Python: Collapse all scopes',lambda:self.set_all_scopes(False))
        graph.addAction('Go to Python module graph',lambda:self.navigate_source('module'))
        graph.addAction('Go to enclosing Python scope',self.source_go_parent)
        help_=self.menuBar().addMenu('Help')
        help_.addAction('Prototype scope',lambda:QMessageBox.information(self,'Scope','Native Qt lab: graph authoring, Python source projection and guarded source edits.\nPython sources are not executed on open.\nOnly Run Python explicitly launches real code with host permissions.\nSource graphs are not yet an executable visual language.'))

    def new_visual_program(self,checked=False):
        return self._open_program_document(ProgramGraph())

    def open_visual_program(self,checked=False,*,path=None):
        if path is None:
            path=self._choose_file(title='Open visual program',
                     filters='Superior MI Graph (*.smi-graph)')
            if not path:return None
        try:
            document=ProgramGraph.open(path)
        except (OSError,ProgramGraphError) as exc:
            QMessageBox.warning(self,'Visual program open refused',str(exc));return None
        return self._open_program_document(document)

    def _open_program_document(self,document):
        if document.path:
            for panel in self._program_tabs.values():
                if panel.document.path==document.path:
                    self.tabs.setCurrentWidget(panel)
                    return panel
        panel=ProgramWorkspace(self,document)
        self._program_tabs[panel]=panel
        index=self.tabs.addTab(panel,'Visual program')
        self._add_tab_close_button(panel,index)
        self.tabs.setCurrentWidget(panel)
        panel.refresh()
        return panel

    def _graph_page(self,canvas):
        page=QWidget(self)
        layout=QVBoxLayout(page)
        layout.setContentsMargins(0,0,0,0)
        layout.setSpacing(0)
        host=QWidget(page)
        host.setObjectName('GraphViewportHost')
        overlay_layout=QGridLayout(host)
        # The page, not QGraphicsView's managed viewport, owns the overlay.
        # Reserve scrollbar space while preserving the visible graph area.
        overlay_layout.setContentsMargins(0,0,0,0)
        overlay_layout.setSpacing(0)
        overlay_layout.addWidget(canvas,0,0)
        canvas.attach_overview_host(host,overlay_layout)
        layout.addWidget(host,1)
        return page

    def _build_source_toolbar(self):
        self.source_toolbar=self._create_navigation_bar(self.source_page,'PythonNavigationBar')
        self._refresh_navigation('source')

    def _build_resource_toolbar(self):
        self.resource_toolbar=self._create_navigation_bar(self.resource_page,'ResourceNavigationBar')
        self._refresh_navigation('resource')

    def _create_navigation_bar(self,page,name):
        """One reusable navigation chrome; its destinations stay adapter-owned."""
        bar=QToolBar('Graph location',page)
        bar.setObjectName(name)
        bar.setStyleSheet('QToolBar { spacing:1px; background:#0b253a; border:0; } '
                          'QToolBar QToolButton { padding:1px 5px; margin:0; border-radius:3px; }')
        bar.setMovable(False)
        bar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        page.layout().insertWidget(0,bar)
        return bar

    def _navigation_route(self,kind):
        if kind=='resource':return Route('resource',str(self.resource_path))
        if self.python_doc:
            return Route('source',str(self.python_doc.path),
                         self.source_scope if self.source_view_mode=='focus' else 'module',
                         self.source_view_mode)
        return None

    def _refresh_navigation(self,kind):
        bar=getattr(self,kind+'_toolbar',None)
        if bar is None:return
        old_actions=bar.actions()
        bar.clear()
        # Actions are ephemeral view controls, never navigation authority.
        for old in old_actions:
            if old.parent() is bar:old.deleteLater()
        session=self._view_sessions.get(self._active_source_tab_id if kind=='source' else self._active_resource_tab_id)
        history=session.history if session else None
        def action(label,callback,tip='',enabled=True):
            item=bar.addAction(label)
            item.setEnabled(enabled)
            if tip:item.setToolTip(tip)
            item.triggered.connect(lambda checked=False:callback())
            return item

        # All contextual commands, including frame and path mode, have one
        # predictable home at the far left of each navigation bar.
        display=QToolButton(bar);display.setText('⋯')
        display.setObjectName(kind.title()+'GraphMenu')
        display.setToolTip('Graph navigation and view options')
        display.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu=QMenu(display)
        menu.addAction('Show breadcrumbs' if self._nav_address_mode[kind] else 'Show address',
                       lambda:self._toggle_navigation_address(kind))
        menu.addAction('Frame visible nodes',self._frame_current_graph)
        menu.addAction('Open this location in a new tab',
            lambda k=kind:self._open_navigation_route(self._navigation_route(k),new_tab=True))
        active_canvas=self.source_canvas if kind=='source' else self.resource_canvas
        overview_action=menu.addAction('Overview minimap')
        overview_action.setCheckable(True)
        overview_action.setChecked(active_canvas.overview_visible)
        overview_action.toggled.connect(active_canvas.set_overview_visible)
        menu.addSeparator()
        if kind=='source':
            menu.addAction('Whole-file overview',self.show_source_overview)
            menu.addAction('Focus selected',self.focus_selected_scope)
            menu.addAction('Readable / Analysis',self.toggle_python_detail)
            menu.addSeparator()
            menu.addAction('Expand all scopes',lambda:self.set_all_scopes(True))
            menu.addAction('Collapse all scopes',lambda:self.set_all_scopes(False))
            menu.addAction('Reload Python source',self.reload_python_source)
        else:
            menu.addAction('Browse directory…',self.choose_resource_folder)
            menu.addAction('Refresh',self.refresh_resources)
            menu.addAction('Previous page',lambda:self.page_resource(-1))
            menu.addAction('Next page',lambda:self.page_resource(1))
            toggle=menu.addAction('Show file relationships',self.toggle_resource_imports)
            toggle.setCheckable(True);toggle.setChecked(self.resource_show_imports)
            self.resource_import_action=toggle
            for layer,label in (('imports','Import candidates'),
                                ('references','Literal file references')):
                item=menu.addAction(label)
                item.setCheckable(True)
                item.setChecked(layer in self.resource_relationship_layers)
                item.toggled.connect(lambda enabled,k=layer:self.set_resource_relationship_layer(k,enabled))
            menu.addSeparator()
            menu.addAction('Explore visible file relationships…',self.explore_resource_relationships)
            focus_action=menu.addAction('Focus relationships of selected file',self.focus_selected_resource_relationships)
            menu.aboutToShow.connect(lambda: focus_action.setEnabled(bool(self._selected_resource_file_path())))
            clear_action=menu.addAction('Show relationships of all visible files',
                                        lambda:self.set_resource_relationship_focus(None))
            menu.aboutToShow.connect(lambda: clear_action.setEnabled(self.resource_relationship_focus is not None))
            directions=menu.addMenu('Focused relationship direction')
            for direction,label in (('both','Incoming and outgoing'),
                                    ('incoming','Incoming to focused file'),
                                    ('outgoing','Outgoing from focused file')):
                item=directions.addAction(label)
                item.setCheckable(True)
                item.setChecked(direction==self.resource_relationship_direction)
                item.triggered.connect(lambda checked=False,d=direction:
                                       self.set_resource_relationship_direction(d))
        display.setMenu(menu)
        bar.addWidget(display)
        for item in (
            action('‹',lambda:self._navigate_history(kind,-1),'Back',bool(history and history.peek(-1))),
            action('›',lambda:self._navigate_history(kind,1),'Forward',bool(history and history.peek(1))),
            action('↑',self.resource_parent if kind=='resource' else self.source_go_parent,
                   'Go to parent resource or source scope')):
            bar.widgetForAction(item).setFixedWidth(27)
        bar.addSeparator()
        if kind=='resource':
            crumbs=resource_crumbs(self.resource_path)
        else:
            location=self._navigation_route('source')
            crumbs=(source_crumbs(self.python_doc,location.scope,location.mode)
                    if self.python_doc else ())
        if not crumbs:
            action('Open Python…',self.open_python_file)
        elif self._nav_address_mode[kind]:
            location=self._navigation_route(kind)
            address=QLineEdit(location.path if kind=='resource' else
                location.path+' :: '+(self.python_doc.scopes[location.scope].title
                                     if location.mode=='focus' else 'Whole file'))
            address.setObjectName(kind.title()+'GraphAddress')
            address.setMinimumWidth(220)
            if kind=='source':
                address.setReadOnly(True)
                address.setToolTip('File and source-scope identities are distinct. Select a breadcrumb to navigate.')
            else:
                address.returnPressed.connect(lambda:self._navigate_address(address.text()))
            bar.addWidget(address)
        else:
            display_crumbs,hidden=visible_breadcrumbs(crumbs)
            for index,crumb in enumerate(display_crumbs):
                if crumb is None:
                    more=QToolButton(bar)
                    more.setObjectName('GraphCrumbOverflow')
                    more.setText('…')
                    more.setToolTip('Other parent locations')
                    more.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
                    ancestors=QMenu(more)
                    for ancestor in hidden:
                        item=ancestors.addAction(shorten_crumb(ancestor.text,32))
                        item.setToolTip(ancestor.text+'\n'+ancestor.route.path)
                        item.triggered.connect(lambda checked=False,c=ancestor:self._open_breadcrumb(c.route))
                    more.setMenu(ancestors)
                    more.setFixedWidth(27)
                    bar.addWidget(more)
                else:
                    # Elide presentation only. The QAction retains the exact
                    # Crumb.route, including full resource and source identities.
                    label=shorten_crumb(crumb.text)
                    item=action(('› ' if index else '')+label,
                                lambda c=crumb:self._open_breadcrumb(c.route),
                                crumb.text+'\n'+crumb.route.path)
                    if crumb==crumbs[-1]:item.setEnabled(False)
                    bar.widgetForAction(item).setMaximumWidth(182)

    def _toggle_navigation_address(self,kind):
        self._nav_address_mode[kind]=not self._nav_address_mode[kind]
        self._refresh_navigation(kind)

    def _navigate_address(self,address):
        if self.browse_resource(address):
            self._nav_address_mode['resource']=False
            self._refresh_navigation('resource')

    def _resolve_live_source_route(self,route,*,detail='readable',view=None):
        """Qualify a graph destination against its sole live text owner.

        File identity, active revision and focused scope are one preflight for
        both provider transitions and within-provider navigation. History and
        tab membership must not move when a draft is invalid or a scope was
        removed by an otherwise valid source edit. A newly opened owner is
        published only after its route qualifies.
        """
        requested=PythonDocument._validated_path(route.path)
        owner=self._source_documents.get(str(requested))
        if owner is None:
            if len(self._source_documents)>=32:
                raise SourceError('At most 32 source documents can be open at once')
            owner=self._new_source_document(requested)
        elif not owner.dirty and requested.read_bytes()!=owner.saved_raw:
            owner.discard_and_reload()
        if owner.parsed is None:
            raise SourceError('Current Python source revision has no qualified graph: '
                              +str(owner.diagnostic))
        if view is not None and view.document is not None and str(view.document.path)==str(requested):
            expanded=set(view.expanded) & set(owner.parsed.scopes)
            collapsed=set(view.collapsed)
        else:
            expanded,collapsed=self._restore_document_view(owner.parsed)
        resolved=resolve_source_session_route(route,owner,detail=detail,
                                              expanded_scopes=expanded,collapsed_regions=collapsed)
        return owner,resolved,expanded,collapsed

    def _transition_graph_tab(self,route,*,history_direction=None):
        """Change a secondary graph tab's provider without changing its identity.

        The existing session owns cross-provider history and camera identities;
        the resource and source adapters resolve *before* any Qt mutation.
        The original root tabs remain available as compatibility anchors while
        older window-global active-view aliases are retired incrementally.
        """
        if self._source_analysis_timer.isActive():
            self._source_analysis_timer.stop()
            self._refresh_live_source()
        old=self._graph_tab_for_page(self.tabs.currentWidget())
        if old is None or old.session_id in ('source','resource'):
            self.report('Universal navigation refused: select a secondary graph tab')
            return False
        if route.kind not in ('source','resource'):
            self.report('Unsupported graph-view destination')
            return False
        old_kind='source' if isinstance(old,SourceTabView) else 'resource'
        if old_kind==route.kind:
            self.report('Universal navigation refused: unchanged graph provider')
            return False  # Existing provider navigation owns same-kind transitions.
        source_session=None
        try:
            if route.kind=='source':
                source_session,resolved,expanded,collapsed=self._resolve_live_source_route(route)
            else:
                resolved=resolve_graph(route,source_documents=self._source_documents)
        except (OSError,ValueError,ResourceError) as exc:
            self.report('Graph navigation refused: '+str(exc))
            return False
        session=self._view_sessions.get(old.session_id)
        if session is None:raise RuntimeError('Graph tab has no session')
        if history_direction is not None and session.peek(history_direction)!=resolved.route:
            self.report('Universal history refused: resolved destination changed')
            return False
        # A route can qualify while its selected Qt page is being retired.
        # Confirm actual membership before touching any source/view registry,
        # camera, alias or history. Failed navigation must leave them intact.
        index=self.tabs.indexOf(old.page)
        if index<0:
            self.report('Graph navigation refused: selected tab is no longer present')
            return False
        # Prepare the replacement Qt page BEFORE mutating the outgoing view,
        # graph registry, source-owner map, camera or history. A failed widget
        # construction must leave the selected tab entirely intact. This uses
        # the existing provider-specific view types, not a second tab owner.
        page=None
        try:
            canvas=GraphCanvas(self,source_view=route.kind=='source',
                               resource_view=route.kind=='resource')
            canvas.session_id=old.session_id
            page=self._graph_page(canvas)
            if route.kind=='source':
                view=SourceTabView(old.session_id,page,canvas,document=resolved.document,
                                   graph=resolved.graph,expanded=expanded,collapsed=collapsed)
                view.toolbar=self._create_navigation_bar(page,'PythonNavigationBar')
                label=self._source_tab_title(resolved.route)
            else:
                view=ResourceTabView(old.session_id,page,canvas,
                                     path=Path(resolved.route.path),graph=resolved.graph)
                view.toolbar=self._create_navigation_bar(page,'ResourceNavigationBar')
                label=self._resource_tab_title(resolved.route)
        except (RuntimeError,ValueError) as exc:
            if page is not None:page.deleteLater()
            self.report('Graph navigation refused: replacement view unavailable: '+str(exc))
            return False
        # The staged view is complete. Only now may the established
        # transaction publish source identity, outgoing camera and new route.
        if source_session is not None:
            self._source_documents[str(source_session.path)]=source_session
        old.canvas._save_root_view()
        if old_kind=='source':
            self._store_active_source_view()
            self._remember_document_view()
            self._activate_source_view(self._source_tabs['source'])
            del self._source_tabs[old.session_id]
        else:
            self._store_active_resource_view()
            self._activate_resource_view(self._resource_tabs['resource'])
            del self._resource_tabs[old.session_id]
        # Outgoing provider decides what to RETIRE; the destination provider
        # independently decides which existing registry receives the new view.
        # These differ on every cross-provider route. Never register the new
        # SourceTabView in _resource_tabs (or the reverse).
        if route.kind=='source':
            self._source_tabs[old.session_id]=view
        else:
            self._resource_tabs[old.session_id]=view
        session.activate(resolved.route,record_history=history_direction is None,
                         history_direction=history_direction)
        self._switching_source_tab=True
        try:
            self.tabs.removeTab(index)
            self.tabs.insertTab(index,page,label)
            self._add_tab_close_button(page,index)
            # Membership is identified by the actual page, not its transient
            # index during a remove/insert provider transition.
            self.tabs.setCurrentWidget(page)
        finally:
            self._switching_source_tab=False
        old.page.deleteLater()
        if route.kind=='source':
            self._activate_source_view(view)
            self._apply_saved_source_positions(resolved.graph,
                'whole' if resolved.route.mode=='whole' else resolved.route.scope)
        else:
            self._activate_resource_view(view)
        canvas.rebuild()
        if canvas.has_saved_root_view():canvas.restore_root_view()
        else:canvas.frame_visible_nodes()
        if route.kind=='source':
            self._store_active_source_view()
            self._update_source_tab_title()
        else:
            self._store_active_resource_view()
            self._update_resource_tab_title()
        self.refresh_inspector()
        self._queue_presentation_save()
        self.report('Graph tab navigated: '+resolved.route.path)
        return True

    def _navigate_source_document_in_tab(self,route,*,history_direction=None,root_anchor=False):
        """Resolve and commit one source route without a premature tab switch.

        A source-document session owns revisions, not the tab. Both a selected
        source view and an already-loaded protected root source view qualify
        the same live text and scope before changing Qt selection or history.
        No second editor, source cache or source-route compiler is created.
        """
        view=(self._source_tabs['source'] if root_anchor else
              self._graph_tab_for_page(self.tabs.currentWidget()))
        if not isinstance(view,SourceTabView):return False
        if self.tabs.indexOf(view.page)<0:
            self.report('Python navigation refused: target tab is no longer present')
            return False
        if self._source_analysis_timer.isActive():
            self._source_analysis_timer.stop()
            self._refresh_live_source()
        try:
            owner,resolved,expanded,collapsed=self._resolve_live_source_route(
                route,detail=view.detail,view=view)
            requested=owner.path
            session=self._view_sessions.get(view.session_id)
            if session is None:
                raise ValueError('Selected source tab has no navigation session')
            if history_direction is not None and session.peek(history_direction)!=resolved.route:
                raise ValueError('History destination no longer matches the source route')
        except (OSError,ValueError,SourceError) as exc:
            self.report('Python navigation refused: '+str(exc))
            return False
        self._source_documents[str(requested)]=owner
        if root_anchor:
            # Original resource-root opens a source in the protected source
            # root. This selection happens only AFTER source/scope preflight;
            # an invalid or deleted focus must leave the resource page and
            # both histories untouched. The tab-change handler binds aliases.
            if self._active_source_tab_id!=view.session_id:
                self._store_active_source_view()
            self.tabs.setCurrentWidget(view.page)
            if self._active_source_tab_id!=view.session_id:
                self._activate_source_view(view)
        self._store_active_source_view()
        self._remember_document_view()
        view.canvas._save_root_view()
        view.document=resolved.document
        view.graph=resolved.graph
        view.expanded=set(expanded)
        view.collapsed=set(collapsed)
        view.selected_node=None
        view.needs_rebuild=False
        session.activate(resolved.route,record_history=history_direction is None,
                         history_direction=history_direction)
        self._activate_source_view(view)
        self._apply_saved_source_positions(resolved.graph,
            'whole' if resolved.route.mode=='whole' else resolved.route.scope)
        self._load_source_editor()
        view.canvas.rebuild()
        if view.canvas.has_saved_root_view():view.canvas.restore_root_view()
        else:view.canvas.frame_visible_nodes()
        self._store_active_source_view()
        self._update_source_tab_title()
        self._queue_presentation_save()
        self.report('Python source: '+resolved.route.path)
        return True

    def _open_navigation_route(self,route,*,new_tab=False):
        """Route an open gesture through its selected page and source owner.

        Secondary tabs may cross providers; the original root tabs remain
        compatibility anchors. An already-loaded source tab (root *or*
        secondary) uses the same source-session preflight and history commit.
        Never let a global active-view alias choose the history destination.
        """
        try:
            if not isinstance(route,Route):raise ValueError('Invalid breadcrumb route')
            selected=self._graph_tab_for_page(self.tabs.currentWidget())
            if route.kind not in ('source','resource'):
                self.report('Unsupported graph destination')
                return False
            if new_tab:
                return (self.open_resource_in_new_tab(route.path) if route.kind=='resource' else
                        self.open_source_in_new_tab(route.path,
                            route.scope if route.mode=='focus' else 'module'))
            # ProgramWorkspace has no source/resource GraphViewSession ID.
            # Refuse an in-place route before accessing provider-only state;
            # explicit new-tab navigation retains its existing earlier path.
            if not isinstance(selected,(ResourceTabView,SourceTabView)):
                self.report('Graph navigation refused: select a resource or Python graph tab')
                return False
            if (selected.session_id not in ('source','resource') and
                    ((isinstance(selected,SourceTabView) and route.kind=='resource') or
                     (isinstance(selected,ResourceTabView) and route.kind=='source'))):
                return self._transition_graph_tab(route)
            if route.kind=='resource':
                if isinstance(selected,ResourceTabView):
                    self._bind_selected_graph_view(selected)
                    return self.browse_resource(route.path)
                # The original source anchor navigates to the original resource
                # anchor, never the last-active secondary resource alias.
                return self.browse_resource(route.path,root_anchor=True)
            # A source tab has its own identity even when the selected source
            # file matches one in another tab. Do not reset root history through
            # _open_python_source_path or accidentally navigate a stale alias.
            if isinstance(selected,SourceTabView):
                self._bind_selected_graph_view(selected)
                if self._view_sessions.get(selected.session_id) is not None:
                    return self._navigate_source_document_in_tab(route)
            # Compatibility anchor: opening from the original resource
            # root targets the protected source root, not a secondary alias.
            if self._view_sessions.get('source') is not None:
                return self._navigate_source_document_in_tab(route,root_anchor=True)
            # Only the never-opened source root needs the original file-open
            # adapter, which also supports invalid Python for text diagnostics.
            # The first source-root open must prove a requested focus scope
            # before publishing the whole-file root and then visiting focus.
            # An invalid scope cannot leave a newly initialized root behind.
            if not self._open_python_source_path(
                    route.path,bootstrap_root=True,
                    focus_scope=route.scope if route.mode=='focus' else None):
                return False
            return (self.navigate_source(route.scope) if route.mode=='focus' else True)
        except (OSError,ValueError,SourceError,ResourceError) as exc:
            self.report('Graph location refused: '+str(exc))
            return False

    def _open_breadcrumb(self,route):
        # Read modifiers at the actual QAction trigger; regular click remains
        # ordinary navigation. The context menu exposes a keyboard alternative.
        separate=bool(QApplication.keyboardModifiers() & Qt.KeyboardModifier.ControlModifier)
        return self._open_navigation_route(route,new_tab=separate)

    def _navigate_history(self,kind,direction):
        # Qt's currently selected page, NOT a window-global provider alias, is
        # the authority for history. Cross-provider tab replacement temporarily
        # activates root compatibility views; those aliases are not navigation
        # destinations and may have an unrelated history cursor.
        selected=self._graph_tab_for_page(self.tabs.currentWidget())
        if (not isinstance(selected,(ResourceTabView,SourceTabView)) or
                (isinstance(selected,SourceTabView) != (kind=='source'))):
            self.report('History navigation refused: selected graph provider changed')
            return False
        session=self._view_sessions.get(selected.session_id)
        destination=session.peek(direction) if session else None
        if destination is None:return False
        if destination.kind != kind:
            return self._transition_graph_tab(destination,history_direction=direction)
        self._bind_selected_graph_view(selected)
        if kind=='resource':
            ok=self.browse_resource(destination.path,record_history=False,
                                    history_direction=direction)
        else:
            ok=self._navigate_source_document_in_tab(destination,history_direction=direction)
        return bool(ok)

    def show_source_overview(self):
        return self._refresh_whole_file(record_history=True)

    def activate_source_tab(self):
        self.tabs.setCurrentWidget(self.source_page)

    def activate_resource_tab(self):
        self.tabs.setCurrentWidget(self.resource_page)

    def open_legacy_graph(self,canvas,label):
        page=self._legacy_pages.get(canvas)
        if page is None:
            page=self._graph_page(canvas)
            self._legacy_pages[canvas]=page
        if self.tabs.indexOf(page)<0:
            self.tabs.addTab(page,label.upper())
        action=self._legacy_actions.get(canvas)
        if action is not None:
            action.setChecked(True)
        self.tabs.setCurrentWidget(page)

    def toggle_legacy_graph(self,canvas,label,visible):
        if visible:
            self.open_legacy_graph(canvas,label)
        else:
            page=self._legacy_pages.get(canvas)
            index=self.tabs.indexOf(page) if page is not None else -1
            if index>=0:
                self.tabs.removeTab(index)
            self.activate_source_tab()

    def focus_selected_scope(self):
        if not self.python_doc:
            self.report('Open a Python file first')
            return
        card=next((item for item in self.source_canvas.graph_scene.selectedItems()
                   if isinstance(item,NodeItem) and item.source_view),None)
        if card is not None:
            key=card.data.get('source_scope') or card.data.get('child_region_key')
            if not key:
                key=card.data.get('containing_scope')
        else:
            key=self.source_scope if self.source_view_mode=='focus' else None
        if key and key in self.python_doc.scopes:
            self.navigate_source(key)
        else:
            self.report('Select a function or scope first, or Ctrl+double-click it to focus')

    def fit_source_graph(self):
        if not self.python_doc:return
        self.activate_source_tab()
        self.source_canvas.frame_visible_nodes()

    def current_canvas(self):
        """Qt's selected page, not last-active global source/resource aliases.

        All graph controls (including zoom, minimap and framing) must address
        the selected tab, even if it is the third view of the same Python file.
        """
        page=self.tabs.currentWidget()
        view=self._graph_tab_for_page(page)
        if isinstance(view,ProgramWorkspace):return view.canvas
        if view is not None:return view.canvas
        for canvas,legacy_page in self._legacy_pages.items():
            if page is legacy_page:return canvas
        return None

    def _frame_current_graph(self):
        canvas=self.current_canvas()
        if isinstance(canvas,GraphCanvas):canvas.frame_visible_nodes()

    def reset_current_zoom(self):
        canvas=self.current_canvas()
        if not isinstance(canvas,GraphCanvas):return
        canvas.resetTransform();canvas.centerOn(550,320)
        canvas._save_root_view()

    def labels_visible(self,node):
        mode=self.state['settings'].get('port_label_mode','contextual')
        if mode=='hidden':return False
        if mode=='always':return True
        return node.hovered or node.canvas.space_held or bool(node.canvas.pending)

    def is_port_connected(self,node_id,port_id):
        return any((e['source']==node_id and e['sourcePort']==port_id) or
                   (e['target']==node_id and e['targetPort']==port_id) for e in self.state['edges'])

    def report(self,text):self.statusBar().showMessage(text,7000)
    def mark_changed(self,settings_view=False):
        if settings_view:return
        self.dirty=True
        self.setWindowTitle(APP_TITLE + ' *')

    def create_node(self,kind):
        self.open_legacy_graph(self.canvas,'Node workspace')
        offset=len(self.state['nodes'])*35
        node=m.make_node(kind,390+offset,190+offset)
        if self.commit_draft_change(lambda draft: draft['nodes'].append(node),
                                    inspector_node=node['id']):
            self.report(f'{node["title"]} created')

    def settings_nodes(self):
        def cfg(kind,label,key,options=None):
            r=m.row(kind,label);r['setting_key']=key;r['id']='setting:'+key
            if key.startswith('type_colors.'):
                r['value']=self.state['settings'].get('type_colors',{}).get(key.split('.',1)[1],r.get('value'))
            else:
                r['value']=self.state['settings'].get(key,r.get('value'))
            if options:r['options']=options
            return r
        a=m.make_node('custom',140,115)
        a.update(id='settings:appearance',kind='settings',title='GRAPH APPEARANCE',subtitle='Live · settings authority',accent='#25d2f3',
                 draft_ports={'inputs':[],'outputs':[]},containers=[m.section('CANVAS',[
                     cfg('toggle','Show grid','show_grid'),
                     cfg('dropdown','Pin label chips','port_label_mode',['contextual','always','hidden']),
                     cfg('number','Visible rows','default_visible_rows')])])
        b=m.make_node('custom',645,120)
        b.update(id='settings:colors',kind='settings',title='PORT TYPE COLORS',subtitle='One shared palette',accent='#af81f0',
                 draft_ports={'inputs':[],'outputs':[]},containers=[m.section('PALETTE',[
                     cfg('color',typ,f'type_colors.{typ}') for typ in ('audio','string','image','f32','object','bool')])])
        for node in (a,b):
            node['x'],node['y']=self._setting_positions.get(node['id'],(node['x'],node['y']))
        return [a,b]

    def change_setting(self,key,value):
        if key.startswith('type_colors.'):
            typ=key.split('.',1)[1]
            if not isinstance(value,str) or not QColor(value).isValid():return
            self.state['settings'].setdefault('type_colors',dict(m.TYPE_COLORS))[typ]=value
        elif key=='port_label_mode':
            if value not in ('hidden','contextual','always'):return
            self.state['settings'][key]=value
        elif key=='show_grid':self.state['settings'][key]=bool(value)
        elif key=='default_visible_rows':self.state['settings'][key]=max(1,min(50,int(value)))
        else:return
        self.canvas.viewport().update();self.settings_canvas.viewport().update()
        self.canvas.update_port_appearance();self.settings_canvas.update_port_appearance()
        self.mark_changed(False);self.report(f'Updated setting: {key}')

    def check_python_syntax(self):
        active=self._active_source_document()
        if active is not None and not active.graph_ready:
            QMessageBox.warning(self,'Syntax check failed',active.diagnostic or 'Source is not graph-ready');return
        if self.python_doc is None:
            self.report('Open a Python file first');return
        try:
            if self._source_editor_dirty:
                # Check the actual unsaved source buffer without writing it.
                prepare_source_change(self.python_doc,self.source_editor.toPlainText())
            else:
                compile(self.python_doc.tree,str(self.python_doc.path),'exec',dont_inherit=True)
        except (SyntaxError,ValueError,TypeError) as exc:
            QMessageBox.warning(self,'Syntax check failed',str(exc));return
        self.report('Python syntax compiled successfully (not executed)'+
                    (' · unsaved draft' if self._source_editor_dirty else ''))

    def run_python_source(self):
        """Explicit opt-in ordinary Python execution. NOT a sandbox."""
        active=self._active_source_document()
        if active is not None and not active.graph_ready:
            QMessageBox.warning(self,'Invalid Python source','Fix source errors before running Python.');return
        if self.python_doc is None:
            self.report('Open a Python file first');return
        if self._source_editor_dirty:
            QMessageBox.warning(self,'Unsaved Python source',
                'Save the text editor before running Python. The graph still represents the saved source.')
            return
        if self._python_process and self._python_process.state()!=QProcess.ProcessState.NotRunning:
            self.report('A Python run is already active');return
        current=self.python_doc.path
        if not current.exists() or current.is_symlink():
            self.report('Python source path is no longer a regular file');return
        if hashlib.sha256(current.read_bytes()).hexdigest()!=self.python_doc.sha256:
            QMessageBox.warning(self,'Python changed','Source was modified on disk. Reload it before running.')
            return
        msg=('This will execute the selected Python file with the NORMAL Python interpreter and the\n'
             'current operating-system permissions. Imports and code may modify your system.\n\n'
             'Only run code you trust. Continue?')
        if QMessageBox.question(self,'Execute local Python (not sandboxed)',msg,
             QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)!=QMessageBox.StandardButton.Yes:
            return
        dlg=QDialog(self);dlg.setWindowTitle('Python run · '+current.name);dlg.resize(800,480)
        lay=QVBoxLayout(dlg)
        lay.addWidget(QLabel('Normal Python process · 8-second time limit · 64 KiB output cap · Not sandboxed'))
        output=QPlainTextEdit(dlg);output.setReadOnly(True);lay.addWidget(output,1)
        stop=QPushButton('Stop process',dlg);lay.addWidget(stop)
        process=QProcess(self)
        process.setProgram(sys.executable);process.setArguments(['-u',str(current)])
        process.setWorkingDirectory(str(current.parent))
        process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self._python_process=process;self._python_run_dialog=dlg
        output.setPlainText('Executing '+str(current)+'\n\n')
        def drain():
            if process.state()==QProcess.ProcessState.NotRunning and process.bytesAvailable()==0:return
            chunk=bytes(process.readAllStandardOutput()).decode('utf-8',errors='replace')
            if output.toPlainText().__len__()+len(chunk)>65536:
                output.appendPlainText('\n[Output limit exceeded; process stopped]')
                if process.state()!=QProcess.ProcessState.NotRunning:process.kill()
                return
            if chunk:
                output.moveCursor(QTextCursor.MoveOperation.End)
                output.insertPlainText(chunk)
        def finished(code,status):
            drain()
            output.appendPlainText(f'\n\nProcess ended: exit {code} ({status.name})')
            stop.setEnabled(False)
            if self._python_process is process:self._python_process=None
        def error(err):
            output.appendPlainText(f'\nProcess error: {err.name}')
        def timeout():
            if process.state()!=QProcess.ProcessState.NotRunning:
                output.appendPlainText('\n[Timeout: process killed]')
                process.kill()
        process.readyReadStandardOutput.connect(drain)
        process.finished.connect(finished);process.errorOccurred.connect(error)
        stop.clicked.connect(process.kill)
        timer=QTimer(process);timer.setSingleShot(True);timer.setInterval(8000)
        timer.timeout.connect(timeout)
        process.start();timer.start()
        dlg.show()

    def source_nodes(self):
        return self.source_graph['nodes'] if self.source_graph else []

    def is_source_port_connected(self,node_id,port_id):
        return bool(self.source_graph and any(
            (e['source']==node_id and e['sourcePort']==port_id) or
            (e['target']==node_id and e['targetPort']==port_id)
            for e in self.source_graph['edges']))

    def _choose_file(self, *, title, filters, save=False, proposed=None):
        """Use Qt's own filesystem picker, bypassing broken Linux desktop portals.

        Some Mint/Wayland/X11 systems hand native dialogs to a nonresponsive
        portal. The Qt widget dialog remains a real file explorer on both OSes.
        It is modal and stays owned by this main window.
        """
        dialog=QFileDialog(self, title, str(proposed or Path.home()), filters)
        dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)
        dialog.setFileMode(QFileDialog.FileMode.AnyFile if save else QFileDialog.FileMode.ExistingFile)
        dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave if save else QFileDialog.AcceptMode.AcceptOpen)
        dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
        dialog.setMinimumSize(740, 520)
        if save:
            dialog.setDefaultSuffix('json')
        self.report('Choose a file in the Studio file picker…')
        if dialog.exec() != QDialog.DialogCode.Accepted:
            self.report('File selection cancelled')
            return ''
        selection=dialog.selectedFiles()
        return selection[0] if selection else ''

    def _selected_resource_file_path(self):
        view=self._graph_tab_for_page(self.tabs.currentWidget())
        if not isinstance(view,ResourceTabView):return None
        for card in view.canvas.graph_scene.selectedItems():
            if (isinstance(card,NodeItem) and card.resource_view and
                    card.data.get('resource_kind')=='file' and card.isVisible()):
                return card.data.get('resource_path')
        return None

    def focus_selected_resource_relationships(self):
        path=self._selected_resource_file_path()
        return self.set_resource_relationship_focus(path) if path else False

    def set_resource_relationship_focus(self,path):
        # View-only, one-hop evidence focus. No filesystem scan or new index.
        selected=self._graph_tab_for_page(self.tabs.currentWidget())
        if not isinstance(selected,ResourceTabView):return False
        if path is not None:
            candidate=Path(path).expanduser().absolute()
            # The selected canvas's OWN validated graph is the only source of
            # eligible file identities, never a string passed from elsewhere.
            if (selected.canvas.graph_contract is None or
                    not any(n.get('resource_kind')=='file' and
                            n.get('resource_path')==str(candidate)
                            for n in (selected.canvas._render_graph or {}).get('nodes',()))):
                self.report('Cannot focus a file outside this visible resource snapshot')
                return False
            path=str(candidate)
        previous=(self.resource_relationship_focus,self.resource_show_imports)
        self.resource_relationship_focus=path
        if path is not None:self.resource_show_imports=True
        if not self.browse_resource(self.resource_path,activate=False,offset=self.resource_offset):
            self.resource_relationship_focus,self.resource_show_imports=previous
            return False
        self.refresh_inspector()  # Old evidence actions refer to a prior render revision.
        self.report(('Focused on '+str(path)+' ('+self.resource_relationship_direction+')')
                    if path else 'Showing all visible file relationships')
        return True

    def set_resource_relationship_direction(self,direction):
        if direction not in ('both','incoming','outgoing'):return False
        previous=self.resource_relationship_direction
        self.resource_relationship_direction=direction
        if self.browse_resource(self.resource_path,activate=False,offset=self.resource_offset):
            self.report('Relationship direction: '+direction)
            return True
        self.resource_relationship_direction=previous
        return False

    def set_resource_relationship_layer(self,kind,enabled):
        """Filter only presentation edges, never alter source or graph owners."""
        if kind not in ('imports','references'):return False
        previous=set(self.resource_relationship_layers)
        if enabled:self.resource_relationship_layers.add(kind)
        else:self.resource_relationship_layers.discard(kind)
        if self.browse_resource(self.resource_path,activate=False,offset=self.resource_offset):
            self.report('Relationship layers: '+(', '.join(sorted(self.resource_relationship_layers)) or 'none'))
            return True
        self.resource_relationship_layers=previous
        return False

    def toggle_resource_imports(self):
        """Switch provenance-backed candidate overlays, never modify files."""
        self.resource_show_imports=not self.resource_show_imports
        if self.browse_resource(self.resource_path,activate=False,offset=self.resource_offset):
            self.report('Local file relationship candidates '+
                        ('visible' if self.resource_show_imports else 'hidden')+
                        ' · syntactic associations only, not runtime resolution')

    def browse_resource(self,path,*,activate=True,offset=0,record_history=True,
                        history_direction=None,root_anchor=False):
        try:
            resolved=Path(path).expanduser().absolute()
            # A protected-root navigation must project using the target root's
            # preferences, not a secondary tab's last-active compatibility aliases.
            # No alias, canvas or history changes until this resolution succeeds.
            root=self._resource_tabs['resource'] if root_anchor else None
            prior_path=root.path if root is not None else self.resource_path
            prior_offset=root.offset if root is not None else self.resource_offset
            expanded=(set() if resolved!=prior_path else set(
                root.expanded if root is not None else self.resource_expanded))
            imports=root.imports if root is not None else self.resource_show_imports
            layers=root.relationship_layers if root is not None else self.resource_relationship_layers
            focus=root.relationship_focus if root is not None else self.resource_relationship_focus
            direction=root.relationship_direction if root is not None else self.resource_relationship_direction
            graph=resolve_graph(Route('resource',str(resolved)),
                                resource_offset=offset,resource_imports=imports,
                                resource_relationship_kinds=layers,
                                resource_relationship_focus=(
                                    focus if resolved==prior_path and offset==prior_offset else None),
                                resource_relationship_direction=direction,
                                resource_expanded=expanded,
                                source_documents=self._source_documents).graph
        except (OSError,ResourceError,ValueError) as exc:
            self.report('Filesystem browse refused: '+str(exc))
            return False
        # The graph is already qualified. Bind the protected root only now,
        # skipping an unnecessary read of its former (possibly stale) path.
        if root_anchor and self._active_resource_tab_id!='resource':
            self._store_active_resource_view()
            self._activate_resource_view(self._resource_tabs['resource'],reproject=False)
        previous_resource_path=self.resource_path
        self.resource_expanded=expanded
        self.resource_relationship_focus=graph['relationship_focus']
        self.resource_path=Path(graph['path'])
        self.resource_offset=offset
        self.resource_graph=graph
        self._active_resource_session().activate(
            Route('resource',str(self.resource_path)),
            record_history=record_history,history_direction=history_direction)
        self._refresh_navigation('resource')
        for resource in graph['nodes']:
            position=self._resource_positions.get(resource['id'])
            if position:resource['x'],resource['y']=position
        self.resource_canvas.rebuild()
        self._store_active_resource_view()
        self._update_resource_tab_title()
        self._queue_presentation_save()
        if self.resource_path != previous_resource_path or activate:
            if self.resource_canvas.has_saved_root_view():
                self.resource_canvas.restore_root_view()
            else:self.resource_canvas.centerOn(510,285)
        if activate:self.activate_resource_tab()
        self.report('Files: '+str(self.resource_path)+
                    (' · listing capped; narrow the directory' if graph['truncated'] else ''))
        return True

    def toggle_resource_expansion(self,node):
        """Expand a directory or supported file preview on the same resource canvas.

        Preview data is always a read-only bounded projection of the resource.
        No file is executed or given another editable document authority.
        """
        path=Path(node.get('resource_path','')).absolute()
        kind=node.get('resource_kind')
        if path.is_symlink():return False
        if kind=='directory':
            if not path.is_dir():return False
        elif kind=='file' and node.get('preview_kind') not in (None,'none'):
            if not path.is_file():return False
        else:return False
        value=str(path)
        previous=set(self.resource_expanded)
        if value in self.resource_expanded:self.resource_expanded.remove(value)
        else:self.resource_expanded.add(value)
        if self.browse_resource(self.resource_path,activate=False,offset=self.resource_offset):return True
        self.resource_expanded=previous
        return False

    def choose_resource_folder(self):
        dialog=QFileDialog(self,'Browse directory as graph',str(self.resource_path))
        dialog.setOption(QFileDialog.Option.DontUseNativeDialog,True)
        dialog.setFileMode(QFileDialog.FileMode.Directory)
        if dialog.exec()==QDialog.DialogCode.Accepted and dialog.selectedFiles():
            self.browse_resource(dialog.selectedFiles()[0])

    def refresh_resources(self):
        self.browse_resource(self.resource_path,offset=self.resource_offset)

    def page_resource(self,direction):
        if not self.resource_graph:return
        if direction>0 and not self.resource_graph.get('truncated'):return
        if direction<0 and not self.resource_graph.get('has_previous'):return
        offset=max(0,self.resource_offset+(72 if direction>0 else -72))
        self.browse_resource(self.resource_path,offset=offset)

    def resource_parent(self):
        parent=self.resource_path.parent
        if parent!=self.resource_path:self.browse_resource(parent)

    def _open_python_source_path(self,path,*,frame=False,discard_confirmed=False,
                                 bootstrap_root=False,focus_scope=None):
        """One source-opening transaction for file resources and the file picker.

        Resolve before replacing the active document. Existing unsaved-editor
        guards and presentation identity mapping remain the single owners.
        """
        # Opening a second view never discards text owned by another session.
        if self._source_analysis_timer.isActive():
            self._source_analysis_timer.stop()
            self._refresh_live_source()
        try:
            requested=PythonDocument._validated_path(path)
            session=self._source_documents.get(str(requested))
            if session is None:
                if len(self._source_documents)>=32:
                    raise SourceError('At most 32 source documents can be open at once; close/restart after saving drafts')
                session=self._new_source_document(requested)
            elif not session.dirty and requested.read_bytes()!=session.saved_raw:
                session.discard_and_reload()
            doc=session.parsed
            if doc is not None:
                expanded,collapsed=self._restore_document_view(doc)
                # A never-initialized source root may be opened while a
                # secondary source view is last-active. Use the target root's
                # presentation detail without swapping aliases before proof.
                detail=(self._source_tabs['source'].detail if bootstrap_root else self.source_detail)
                resolved=resolve_graph(Route('source',str(doc.path)),document=doc,
                                       detail=detail,
                                       expanded_scopes=expanded,collapsed_regions=collapsed)
                graph=resolved.graph
                if focus_scope is not None:
                    # Reuse the existing live-document route qualifier for the
                    # exact same source revision. No new compiler or owner.
                    resolve_source_session_route(
                        Route('source',str(doc.path),focus_scope,'focus'),
                        session,detail=detail,expanded_scopes=expanded,
                        collapsed_regions=collapsed)
            else:
                if focus_scope is not None:
                    raise SourceError('Cannot focus invalid Python source')
                expanded,collapsed=set(),set()
                graph=None
        except (OSError,ValueError) as exc:
            QMessageBox.warning(self,'Python source graph not opened',str(exc))
            return False
        self._source_documents[str(requested)]=session
        self._refresh_resource_source_views(str(requested))
        self._remember_document_view()
        # The caller's protected root selection is committed only once the
        # existing file/source preflight has succeeded. Refused opens must
        # leave a secondary source provider's alias and editor intact.
        if bootstrap_root and self._active_source_tab_id!='source':
            self._store_active_source_view()
            self._activate_source_view(self._source_tabs['source'])
        self._source_expanded=expanded;self._region_collapsed=collapsed
        self.python_doc=doc
        self.source_scope='module';self.source_view_mode='whole'
        self.source_graph=graph
        route=Route('source',str(requested))
        if self._active_source_session() is None:
            self._view_sessions.open(self._active_source_tab_id,route)
        else:
            self._view_sessions.replace(self._active_source_tab_id,route)
        self._refresh_navigation('source')
        if graph is not None:self._apply_saved_source_positions(graph)
        self._load_source_editor();self.source_canvas.rebuild()
        self._store_active_source_view();self._update_source_tab_title()
        if frame:
            if self.source_canvas.has_saved_root_view():
                self.source_canvas.restore_root_view()
            else:self.source_canvas.centerOn(650,350)
        self.activate_source_tab()
        self.report('Python source: '+str(requested)+(' · graph unavailable (syntax diagnostics)' if doc is None else ''))
        return True

    def open_resource_node(self,node,*,new_tab=False):
        # Embedded source nodes and standalone file cards share one route
        # dispatcher. Ctrl+open creates a view, ordinary open stays in a
        # secondary universal tab, and the existing root tabs stay anchors.
        if node.get('resource_source_path'):
            path=Path(node['resource_source_path']).expanduser().absolute()
            scope=node.get('resource_source_scope')
            route=(Route('source',str(path),scope,'focus') if scope and scope!='module' else
                   Route('source',str(path)))
            return self._open_navigation_route(route,new_tab=new_tab)
        path=Path(node.get('resource_path','')).expanduser().absolute()
        kind=node.get('resource_kind')
        if kind=='directory':
            return self._open_navigation_route(Route('resource',str(path)),new_tab=new_tab)
        if kind=='file' and path.suffix.lower()=='.py':
            return self._open_navigation_route(Route('source',str(path)),new_tab=new_tab)
        # File-type capabilities are owned by the existing resource preview
        # adapter. Do not manufacture a generic editor or writable document.
        if kind=='file' and node.get('preview_kind') not in (None,'none'):
            if new_tab:
                self.report('Separate editor view unavailable for this read-only file type')
                return False
            return self.toggle_resource_expansion(node)
        self.report('Read-only resource: '+str(path)+' (unsupported files are not executed or parsed)')
        return False

    def new_python_source_file(self):
        """Create an exclusively new empty Python file, then open its source graph.

        No existing file is overwritten. The adapter's qualified function
        creator then works on the empty document through the reviewed diff.
        """
        selected,_=QFileDialog.getSaveFileName(self,'Create empty Python source',
                         str(Path.home()/'Projects'/'new_program.py'),
                         'Python Source (*.py)')
        if not selected:return False
        path=Path(selected).expanduser()
        if path.suffix.lower()!='.py':
            QMessageBox.warning(self,'New Python source refused',
                                'Choose a .py filename for a Python source file')
            return False
        try:
            with path.open('xb') as stream:
                stream.flush()
        except (OSError,ValueError) as exc:
            QMessageBox.warning(self,'New Python source refused',str(exc))
            return False
        return self._open_python_source_path(path,frame=True,discard_confirmed=True)

    def open_python_file(self):
        path=self._choose_file(title='Open Python source', filters='Python Source (*.py);;All Files (*)')
        if not path:return False
        return self._open_python_source_path(path,frame=True)

    def reload_python_source(self):
        session=self._active_source_document()
        if session is None:return
        if not self.confirm_source_editor_discard():return
        try:
            # Keep the existing document identity shared by every source tab.
            # The user has already approved discarding this revision above.
            session.discard_and_reload(discard_unsaved=session.dirty)
            session.clear_recovery(self._draft_recovery)
        except (OSError,ValueError) as exc:
            QMessageBox.warning(self,'Cannot reload Python',str(exc));return
        self._source_analysis_timer.stop()
        self._load_source_editor()
        self._refresh_live_source()
        self._queue_presentation_save()
        self.report('Python source reloaded')

    def _display_source_route(self,route,*,record_history,frame,history_direction=None):
        """One validated route-to-view transaction for whole and focused scopes.

        Navigation is presentation only. Resolve before committing; the source
        document and AST remain untouched. This is the future per-tab view seam,
        not a second graph producer or an additional program model.
        """
        if not self.python_doc:return False
        try:
            resolved=resolve_graph(route,document=self.python_doc,detail=self.source_detail,
                                   expanded_scopes=self._source_expanded,
                                   collapsed_regions=self._region_collapsed)
        except (OSError,ValueError) as exc:
            self.report(str(exc));return False
        prior_route=self._navigation_route('source')
        self.source_scope=resolved.route.scope
        self.source_view_mode=resolved.route.mode
        self.source_graph=resolved.graph
        self._apply_saved_source_positions(
            resolved.graph,'whole' if resolved.route.mode=='whole' else resolved.route.scope)
        session=self._active_source_session()
        if session is None:
            raise RuntimeError('Source view has no navigation session')
        # Commit the resolved route before rebuilding: camera lookup, labels,
        # and breadcrumbs must all observe exactly the graph being displayed.
        session.activate(resolved.route,record_history=record_history,
                         history_direction=history_direction)
        self.source_canvas.rebuild()
        self.activate_source_tab()
        # Switching routes restores that route's own camera. Updating the
        # same scope (e.g. changing expansion or analysis mode) does not
        # inadvertently pull a different camera into the current viewport.
        if prior_route!=resolved.route:
            if self.source_canvas.has_saved_root_view():
                self.source_canvas.restore_root_view()
            else:
                self.source_canvas.frame_visible_nodes()
        elif frame:
            self.source_canvas.frame_visible_nodes()
        self._store_active_source_view()
        self._update_source_tab_title()
        self._queue_presentation_save()
        self._refresh_navigation('source')
        if resolved.route.mode=='focus':
            self.report('Python scope: '+resolved.graph['title'])
        else:
            self.report('Python whole-file view · double-click definition to expand/collapse · Ctrl+double-click to focus')
        return True

    def navigate_source(self,key,*,record_history=True,frame=True):
        if not self.python_doc:return False
        return self._display_source_route(
            Route('source',str(self.python_doc.path),key,'focus'),
            record_history=record_history,frame=frame)

    def _refresh_whole_file(self,*,record_history=False):
        if not self.python_doc:return False
        return self._display_source_route(
            Route('source',str(self.python_doc.path)),
            record_history=record_history,frame=False)

    def toggle_python_detail(self):
        """Switch visualization only; the .py source and analysis stay unchanged."""
        if not self.python_doc:return
        self.source_detail=('analysis' if self.source_detail=='readable' else 'readable')
        if self.source_view_mode=='whole':self._refresh_whole_file()
        else:self.navigate_source(self.source_scope)
        self.report('Python display: '+self.source_detail)

    def toggle_source_region(self,region_key):
        """Expand/collapse a source block without changing its semantic graph."""
        if not self.python_doc:return
        if region_key in self._region_collapsed:self._region_collapsed.remove(region_key)
        else:self._region_collapsed.add(region_key)
        if self.source_view_mode=='focus':
            self.navigate_source(self.source_scope,record_history=False,frame=False)
            self._queue_presentation_save()
        else:self._refresh_whole_file()

    def toggle_source_view(self):
        if not self.python_doc:return
        if self.source_view_mode=='focus':
            self._refresh_whole_file()
        else:self.navigate_source(self.source_scope)

    def set_all_scopes(self,expand):
        if not self.python_doc:return
        self._source_expanded=(set(self.python_doc.scopes)-{'module'} if expand else set())
        self._refresh_whole_file()

    def open_source_scope(self,item,focus=False):
        key=item.data.get('source_scope')
        if not key:return
        if focus:
            self.open_source_in_new_tab(self.python_doc.path,key)
        elif self.source_view_mode!='whole':
            self.navigate_source(key)
        else:
            if key in self._source_expanded:
                self._source_expanded.difference_update({k for k in self._source_expanded if k==key or k.startswith(key+'/')})
            else:
                self._source_expanded.add(key)
                self._source_expanded.update(self.python_doc._ancestors(key))
            self._refresh_whole_file()

    def source_go_parent(self):
        if not self.python_doc:return
        if self.source_view_mode=='whole':
            return self.browse_resource(self.python_doc.path.parent)
        parent=self.python_doc.scopes[self.source_scope].parent
        if parent is not None:return self.navigate_source(parent)
        return self.show_source_overview()

    def show_source_inspector(self,item):
        n=item.data
        self._clear_inspector();self.active_item=item
        title=QLabel('PYTHON · '+str(n.get('title','')))
        title.setStyleSheet('color:#76d2ef;font-weight:800;font-size:14px')
        self.inspector_layout.addWidget(title)
        self.inspector_layout.addWidget(QLabel('Static analysis · source-backed graph projection'))
        edit_hint=QLabel('Visual edit: drag a literal, parameter or provably preceding variable output onto an operand, call argument, simple assignment, or return input. SET values inside the same conditional arm are supported. Review the exact diff before saving. Loop and unknown effect edges remain read-only.')
        edit_hint.setWordWrap(True);edit_hint.setStyleSheet('color:#75c7de')
        self.inspector_layout.addWidget(edit_hint)
        hint=QLabel('Double-click a definition to expand/collapse in Whole File; Ctrl+double-click to focus it.')
        hint.setWordWrap(True);hint.setStyleSheet('color:#91b3c9')
        self.inspector_layout.addWidget(hint)
        run=QPushButton('Run Python file (explicit)…')
        run.clicked.connect(self.run_python_source);self.inspector_layout.addWidget(run)
        path=self.python_doc.path if self.python_doc else None
        info=QLabel(f'{path.name if path else ""} · {n.get("source_kind", "node")}')
        info.setWordWrap(True);self.inspector_layout.addWidget(info)
        span=n.get('source_span')
        if span:
            loc=QLabel(f'Lines {span["line"]}-{span["end_line"]}')
            self.inspector_layout.addWidget(loc)
            view=QPlainTextEdit();view.setReadOnly(True);view.setMaximumHeight(150)
            source_lines=self.python_doc.source.splitlines()
            snippet='\n'.join(source_lines[span['line']-1:min(span['end_line'],span['line']+10)])
            view.setPlainText(snippet)
            self.inspector_layout.addWidget(view)
        if n.get('source_scope'):
            b=QPushButton('Open nested scope →')
            b.clicked.connect(lambda:self.open_source_scope(item));self.inspector_layout.addWidget(b)
        if self.source_scope!='module':
            b=QPushButton('← Enclosing scope')
            b.clicked.connect(self.source_go_parent);self.inspector_layout.addWidget(b)
        if span and n.get('source_kind')=='literal':
            b=QPushButton('Edit this Python literal…')
            b.clicked.connect(lambda:self.visual_edit_literal(span));self.inspector_layout.addWidget(b)
        if span and (n.get('source_kind')=='return' or
                     n.get('binding_write_mode') in ('initial','reassign')):
            b=QPushButton('Add numeric operand to expression…')
            b.clicked.connect(lambda:self.visual_add_operand(span));self.inspector_layout.addWidget(b)
        if self.source_graph:
            for warn in self.source_graph.get('warnings',[]):
                note=QLabel('• '+warn);note.setWordWrap(True);note.setStyleSheet('color:#9dabb8')
                self.inspector_layout.addWidget(note)
        self.inspector_layout.addStretch()

    def rewire_python_input(self,source_id,source_port,target_id,target_port):
        """Legacy entry point and canvas drag share a single adapter preflight."""
        if not self._qualified_source_context():
            self.report('Save text edits and select the owning Python graph before rewiring')
            return
        check=inspect_connection(self.python_doc,source_id,source_port,
                                 target_id,target_port)
        if not check.allowed:
            self.report('Python edit refused: '+check.reason)
            return
        self.review_source_proposal(check.proposal)

    def visual_replace_python_input(self,node_id,port_id):
        """Change one qualified source input; no separate graph mutation path."""
        if not self._qualified_source_context():
            self.report('Save pending Python text before editing graph inputs')
            return
        scope=max((key for key,info in self.python_doc.scopes.items()
                   if info.kind=='function' and node_id.startswith('py:'+key+'|')),
                  key=len,default=None)
        if scope is None or not any(n['id']==node_id for n in self.python_doc.scope_graph(scope)['nodes']):
            self.report('Input is not owned by a current Python function')
            return
        literal,ok=QInputDialog.getText(self,'Replace Python input',
            'Primitive literal to substitute for this input (for example: 0, None, True):',text='0')
        if not ok:return
        try:
            proposal=replace_source_input_literal(self.python_doc,scope,
                                                  node_id,port_id,literal)
        except (OSError,ValueError) as exc:
            QMessageBox.warning(self,'Source-backed input edit refused',str(exc))
            return
        self.review_source_proposal(proposal)

    def visual_edit_literal(self,span):
        if not self.python_doc:return
        literal,ok=QInputDialog.getText(self,'Edit Python literal',
            'Enter a Python literal (example: 42, 3.14, "hello", True):')
        if not ok:return
        try:proposal=change_literal(self.python_doc,span,literal)
        except (OSError,ValueError) as exc:
            QMessageBox.warning(self,'Visual edit refused',str(exc));return
        self.review_source_proposal(proposal)

    def visual_add_operand(self,span):
        if not self.python_doc:return
        operand,ok=QInputDialog.getText(self,'Add numeric operand',
            'Value to add to this assignment or return expression:',text='10')
        if not ok:return
        try:proposal=add_constant_operand(self.python_doc,span,operand)
        except (OSError,ValueError) as exc:
            QMessageBox.warning(self,'Visual edit refused',str(exc));return
        self.review_source_proposal(proposal)

    def undo_source_edit(self):
        return self._navigate_source_history(redo=False)

    def redo_source_edit(self):
        return self._navigate_source_history(redo=True)

    def _publish_source_view_revision(self, session, original, published):
        """One post-write view synchronization, without a second save/reload dialog.

        The commit owner already checked the source preimage. If a separate
        process changes the file before adoption, retain the previous view
        and report the conflict rather than presenting unrelated disk content.
        """
        session.adopt_committed_revision(original,published)
        try:
            session.clear_recovery(self._draft_recovery)
        except (OSError,ValueError) as exc:
            self.report('Source committed; recovery cleanup needs attention: '+str(exc))
        self._source_analysis_timer.stop()
        self._load_source_editor()
        self._refresh_live_source()
        self._queue_presentation_save()

    def _navigate_source_history(self,*,redo):
        session=self._active_source_document()
        if session is None:
            self.report('Open a Python file before editing history');return False
        if session.dirty:
            self.report('Save or discard unsaved source text before using graph history');return False
        if session.inspect_external()!='current':
            self._set_source_editor_label()
            self.report('Committed history refused: source changed externally; review or reload first')
            return False
        original=session.saved_raw
        try:
            backup,published=self._source_edit_history.transition(session.path,redo=redo)
        except (OSError,ValueError) as exc:
            self.report('Python source history refused: '+str(exc));return False
        try:
            self._publish_source_view_revision(session,original,published)
        except (OSError,ValueError) as exc:
            session.inspect_external()
            self._set_source_editor_label()
            self.report('Source history committed, but the view did not adopt a changed disk revision: '+str(exc))
            return False
        self.report(('Redid' if redo else 'Undid')+' committed Python source edit. Backup: '+str(backup))
        return True

    def review_source_proposal(self,proposal):
        session=self._active_source_document()
        if session is None or session.dirty or str(session.path)!=str(proposal.path):
            self.report('Open the matching clean Python source before applying a graph transformation');return
        if session.saved_raw!=proposal.original:
            self.report('Source proposal no longer matches this document revision');return
        dialog=QDialog(self);dialog.setWindowTitle('Review Python source transformation')
        dialog.resize(820,580)
        lay=QVBoxLayout(dialog)
        lay.addWidget(QLabel('Only the displayed source change will be applied. A backup is written first. Syntax is checked, not runtime behavior.'))
        editor=QPlainTextEdit();editor.setReadOnly(True);editor.setPlainText(proposal.diff)
        lay.addWidget(editor,1)
        actions=QHBoxLayout();cancel=QPushButton('Cancel');save=QPushButton('Apply change to .py')
        actions.addWidget(cancel);actions.addWidget(save)
        cancel.clicked.connect(dialog.reject);save.clicked.connect(dialog.accept)
        lay.addLayout(actions)
        if dialog.exec()!=QDialog.DialogCode.Accepted:return
        # The dialog may have opened a nested event loop. Recheck the same
        # document and revision immediately before publishing.
        if (self._active_source_document() is not session or session.dirty or
                session.saved_raw!=proposal.original):
            self.report('Source changed while the proposal was open; review it again');return
        try:
            backup=self._source_edit_history.apply(proposal)
        except (OSError,ValueError) as exc:
            QMessageBox.warning(self,'Python save refused',str(exc));return
        try:
            self._publish_source_view_revision(session,proposal.original,proposal.candidate)
        except (OSError,ValueError) as exc:
            session.inspect_external()
            self._set_source_editor_label()
            QMessageBox.warning(self,'Source view synchronization refused',
                'Source change was committed, but a new disk revision prevented its view update: '+str(exc))
            return
        self.report('Saved Python source. Backup: '+str(backup))

    @staticmethod
    def _detach_inspector_widgets(layout):
        """Remove obsolete controls from Qt's object tree *synchronously*.

        deleteLater schedules C++ destruction only when the event loop regains
        control. A smoke test (or another callback) can query/activate an old
        button between clear and deferred destruction unless it is unparented.
        """
        while layout.count():
            item=layout.takeAt(0)
            if item.widget():
                widget=item.widget()
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
            elif item.layout():
                NativeLab._detach_inspector_widgets(item.layout())

    def _clear_inspector(self):
        self._detach_inspector_widgets(self.inspector_layout)
        self.active_item=None

    def refresh_inspector(self):
        self._clear_inspector()
        title=QLabel('Select a node');title.setStyleSheet('font-size:17px;font-weight:bold;color:#85dfff')
        self.inspector_layout.addWidget(title)
        self.inspector_layout.addWidget(QLabel('Use a graph node to select and edit its definition.'))
        self.inspector_layout.addStretch()

    def _qualified_resource_relationship(self,canvas,edge_id):
        """Check selected-canvas identity before exposing any navigation action."""
        selected=self._graph_tab_for_page(self.tabs.currentWidget())
        if (not isinstance(selected,ResourceTabView) or selected.canvas is not canvas or
                canvas.graph_contract is None):
            raise ContractError('Resource relationship belongs to an inactive tab')
        return inspect_resource_relationship(canvas.graph_contract,canvas._render_graph,edge_id)

    def explore_resource_relationships(self,canvas=None,*,focus=None):
        """Search only the selected resource canvas's validated snapshot.

        The Inspector is a read-only browser, not a dependency index. Search
        and action callbacks refuse an inactive or replaced render revision.
        """
        selected=self._graph_tab_for_page(self.tabs.currentWidget())
        if not isinstance(selected,ResourceTabView):return False
        canvas=canvas or selected.canvas
        if canvas is not selected.canvas or canvas.graph_contract is None:
            self.report('Relationship explorer refused: inactive resource tab')
            return False
        contract=canvas.graph_contract
        graph=canvas._render_graph
        try:
            results=search_resource_relationships(contract,graph,focus=focus)
        except (ContractError,ValueError) as exc:
            self.report('Relationship explorer refused: '+str(exc))
            return False
        self._clear_inspector()
        heading=QLabel('VISIBLE FILE RELATIONSHIPS · READ ONLY')
        heading.setStyleSheet('color:#76d2ef;font-weight:800;font-size:13px')
        self.inspector_layout.addWidget(heading)
        context=QLabel(('File: '+str(focus)+'\n' if focus else '')+
            'Only currently visible, static candidate edges. Not runtime dependencies.')
        context.setTextFormat(Qt.TextFormat.PlainText)
        context.setWordWrap(True)
        self.inspector_layout.addWidget(context)
        search=QLineEdit()
        search.setObjectName('ResourceRelationshipSearch')
        search.setPlaceholderText('Find file, import, path or source statement…')
        search.setMaxLength(128)
        self.inspector_layout.addWidget(search)
        direction_control=hop_control=None
        if focus is not None:
            direction_control=QComboBox()
            direction_control.setObjectName('ResourceRelationshipSearchDirection')
            for label,value in (('Incoming + outgoing','both'),('Incoming','incoming'),
                                ('Outgoing','outgoing')):
                direction_control.addItem(label,value)
            self.inspector_layout.addWidget(direction_control)
            hop_control=QComboBox()
            hop_control.setObjectName('ResourceRelationshipSearchHops')
            hop_control.addItem('Direct connections',1)
            hop_control.addItem('Up to two visible hops',2)
            self.inspector_layout.addWidget(hop_control)
        count_label=QLabel()
        count_label.setObjectName('ResourceRelationshipCount')
        self.inspector_layout.addWidget(count_label)
        panel=QWidget()
        panel.setObjectName('ResourceRelationshipResults')
        panel_layout=QVBoxLayout(panel)
        panel_layout.setContentsMargins(0,0,0,0)
        panel_layout.setSpacing(4)
        self.inspector_layout.addWidget(panel)
        def update(text):
            if (self._graph_tab_for_page(self.tabs.currentWidget()) is not selected or
                    canvas.graph_contract is not contract or canvas._render_graph is not graph):
                count_label.setText('Graph revision changed; reopen explorer.')
                search.setEnabled(False)
                self._detach_inspector_widgets(panel_layout)
                return
            try:found=search_resource_relationships(contract,graph,query=text,focus=focus,
                        direction=(direction_control.currentData() if direction_control else 'both'),
                        hops=(hop_control.currentData() if hop_control else 1))
            except (ContractError,ValueError) as exc:
                count_label.setText('Relationship search refused: '+str(exc))
                search.setEnabled(False)
                return
            self._detach_inspector_widgets(panel_layout)
            count_label.setText(f'{found.total} matching · {found.imports} imports · '
                                f'{found.references} file references'
                                +(' · first '+str(found.limit)+' shown' if found.total>found.limit else ''))
            for item in found.results:
                button=QPushButton(item.source.name+' → '+item.target.name+' · '+item.relation+
                                   ' ('+str(len(item.evidence))+' evidence)')
                button.setObjectName('ResourceRelationshipResult')
                button.setToolTip(str(item.source)+' → '+str(item.target))
                button.clicked.connect(lambda checked=False,eid=item.edge_id:
                                       self._inspect_resource_search_result(canvas,contract,graph,eid,panel))
                panel_layout.addWidget(button)
        search.textChanged.connect(update)
        if direction_control:
            direction_control.currentIndexChanged.connect(lambda index:update(search.text()))
            hop_control.currentIndexChanged.connect(lambda index:update(search.text()))
        update('')
        self.inspector_layout.addStretch()
        self.report('Exploring visible relationship candidates ('+str(results.total)+')')
        return True

    def _inspect_resource_search_result(self,canvas,contract,graph,edge_id,panel):
        """Search actions require their exact *visible* Inspector revision."""
        selected=self._graph_tab_for_page(self.tabs.currentWidget())
        if (self.inspector_layout.indexOf(panel)<0 or
                not isinstance(selected,ResourceTabView) or selected.canvas is not canvas or
                canvas.graph_contract is not contract or canvas._render_graph is not graph):
            self.report('Stale relationship result: reopen the explorer')
            return False
        return self.show_resource_relationship(canvas,edge_id)

    def show_resource_relationship(self,canvas,edge_id):
        """Render existing immutable edge evidence in the normal Inspector dock."""
        try:
            item=self._qualified_resource_relationship(canvas,edge_id)
        except (ContractError,ValueError) as exc:
            self.report('Relationship inspection refused: '+str(exc))
            return False
        self._clear_inspector()
        title=QLabel('FILE RELATIONSHIP · READ ONLY')
        title.setStyleSheet('color:#76d2ef;font-weight:800;font-size:13px')
        self.inspector_layout.addWidget(title)
        def line(text):
            label=QLabel(str(text))
            label.setTextFormat(Qt.TextFormat.PlainText)
            label.setWordWrap(True)
            self.inspector_layout.addWidget(label)
        line('Relation: '+item.relation+' · '+item.certainty)
        line('Static source evidence only. This is not proof of a runtime dependency.')
        line('From: '+str(item.source))
        line('To: '+str(item.target))
        for role,label in (('source','Focus connections from source'),
                           ('target','Focus connections at target')):
            button=QPushButton(label)
            button.clicked.connect(lambda checked=False,k=role,c=canvas,eid=edge_id:
                self.focus_resource_relationship_endpoint(c,eid,k))
            self.inspector_layout.addWidget(button)
        for role,label in (('source','Open source file'),('target','Open target file')):
            button=QPushButton(label)
            button.clicked.connect(lambda checked=False,k=role,c=canvas,eid=edge_id:
                self.open_resource_relationship_endpoint(c,eid,k))
            self.inspector_layout.addWidget(button)
        line('Evidence ('+str(len(item.evidence))+'):')
        for index,evidence in enumerate(item.evidence[:24]):
            line(str(evidence.path)+':'+str(evidence.line)+'  '+evidence.syntax[:220])
            # Only true Python evidence can be focused. Synthetic declaration
            # annotations remain visible as provenance, not editable locations.
            if (evidence.path in (str(item.source),str(item.target)) and
                    Path(evidence.path).suffix.lower()=='.py'):
                button=QPushButton('Go to evidence · '+Path(evidence.path).name+':'+str(evidence.line))
                button.setObjectName('ResourceEvidenceLine'+str(index))
                button.clicked.connect(lambda checked=False,c=canvas,eid=edge_id,i=index:
                    self.open_resource_relationship_evidence(c,eid,i))
                self.inspector_layout.addWidget(button)
        if len(item.evidence)>24:line('Additional evidence omitted from display.')
        self.inspector_layout.addStretch()
        self.report('Inspected '+item.relation+' candidate · '+item.source.name+' → '+item.target.name)
        return True

    def focus_resource_relationship_endpoint(self,canvas,edge_id,which):
        """Focus an inspected endpoint without navigating or reading new files."""
        if which not in ('source','target'):return False
        try:
            evidence=self._qualified_resource_relationship(canvas,edge_id)
        except (ContractError,ValueError) as exc:
            self.report('Cannot focus stale relationship: '+str(exc))
            return False
        path=evidence.source if which=='source' else evidence.target
        return self.set_resource_relationship_focus(str(path))

    def open_resource_relationship_endpoint(self,canvas,edge_id,which):
        """Reuse existing file/directory route policy; never invent an editor."""
        if which not in ('source','target'):
            self.report('Unknown relationship endpoint')
            return False
        try:
            item=self._qualified_resource_relationship(canvas,edge_id)
        except (ContractError,ValueError) as exc:
            self.report('Relationship navigation refused: '+str(exc))
            return False
        path=item.source if which=='source' else item.target
        if not path.is_file() or path.is_symlink():
            self.report('Relationship endpoint disappeared or changed: '+str(path))
            return False
        if path.suffix.lower()=='.py':
            return self._open_navigation_route(Route('source',str(path)))
        if not self._open_navigation_route(Route('resource',str(path.parent))):
            return False
        return self._frame_visible_resource_file(path)

    def _frame_visible_resource_file(self,path):
        """Select an already-visible resource card in the current tab only."""
        view=self._graph_tab_for_page(self.tabs.currentWidget())
        if not isinstance(view,ResourceTabView):return False
        canvas=view.canvas
        card=next((node for node in canvas.items_by_id.values()
                   if node.data.get('resource_kind')=='file' and
                   node.data.get('resource_path')==str(path) and node.isVisible()),None)
        if card is None:
            self.report('Resource target not visible in selected folder: '+str(path))
            return False
        canvas.graph_scene.clearSelection()
        card.setSelected(True)
        if not canvas.frame_node(card):
            return False
        self.report('Selected resource: '+str(path))
        return True

    def open_resource_relationship_evidence(self,canvas,edge_id,index):
        """Exact-line navigation after evidence and live-owner preflight.

        An invalid revision or shifted/deleted statement must not advance
        history, switch tabs or highlight unrelated source text.
        """
        try:
            item=self._qualified_resource_relationship(canvas,edge_id)
            if type(index) is not int or not 0<=index<len(item.evidence):
                raise ValueError('Unknown relationship evidence index')
            evidence=item.evidence[index]
            path=Path(evidence.path).absolute()
            if (path not in (item.source,item.target) or path.suffix.lower()!='.py' or
                    path.is_symlink() or not path.is_file()):
                raise ValueError('Evidence has no qualified Python source endpoint')
            if self._source_analysis_timer.isActive():
                self._source_analysis_timer.stop()
                self._refresh_live_source()
            route=Route('source',str(path))
            owner,_,_,_=self._resolve_live_source_route(route)
            if verified_evidence_line(owner.text,evidence.line,evidence.syntax) is None:
                raise ValueError('Evidence no longer matches this source revision')
            # Make the same validated SourceDocumentSession available to the
            # normal navigation dispatcher. Without this, opening a previously
            # unseen file could prompt for recovery twice and create two
            # temporary owners with different identities.
            revision=owner.revision
            self._source_documents.setdefault(str(path),owner)
        except (ContractError,ValueError,SourceError,OSError) as exc:
            self.report('Source evidence navigation refused: '+str(exc))
            return False
        if not self._open_navigation_route(route):return False
        active=self._active_source_document()
        if (active is not owner or active.revision!=revision or
                self._loaded_editor_identity!=(str(path),revision)):
            self.report('Source evidence revision changed during navigation')
            return False
        block=self.source_editor.document().findBlockByNumber(evidence.line-1)
        if not block.isValid():return False
        cursor=self.source_editor.textCursor()
        cursor.setPosition(block.position())
        cursor.select(QTextCursor.SelectionType.LineUnderCursor)
        self.source_editor.setTextCursor(cursor)
        self.source_editor.centerCursor()
        self.source_editor_note.setText('Relationship evidence: '+path.name+
                                         ' · line '+str(evidence.line)+' (syntactic candidate)')
        self.report('Source evidence: '+str(path)+':'+str(evidence.line))
        return True

    def show_inspector(self,item):
        if not isinstance(item,NodeItem):return
        if item.resource_view:
            self.report(item.data.get('resource_kind','resource')+': '+item.data.get('resource_path',''))
            return
        if item.source_view:
            self.highlight_python_node(item.data)
        if item.source_view:
            self.show_source_inspector(item);return
        self._clear_inspector();self.active_item=item;n=item.data
        title=QLabel('NODE DEFINITION' if not item.settings_view else 'SETTINGS PROJECTION')
        title.setStyleSheet('color:#76d2ef;font-weight:800;font-size:13px');self.inspector_layout.addWidget(title)
        if item.settings_view:
            lbl=QLabel('Settings are edited through their node controls and applied immediately.');lbl.setWordWrap(True)
            self.inspector_layout.addWidget(lbl)
            self.inspector_layout.addStretch();return
        for key,label in [('title','Node title'),('subtitle','Description')]:
            self.inspector_layout.addWidget(QLabel(label))
            edit=QLineEdit(str(n.get(key,'')))
            def update_field(k=key,w=edit):
                new_text=w.text()[:100]
                if new_text==n.get(k,''):return
                self.commit_draft_change(
                    lambda draft: m.find_node(draft,n['id']).__setitem__(k,new_text),
                    inspector_node=n['id'])
            edit.editingFinished.connect(update_field)
            self.inspector_layout.addWidget(edit)
        accent=QPushButton(f'Accent {n["accent"]}')
        def pick_color():
            color=QColorDialog.getColor(qcolor(n['accent']),self,'Node accent')
            if color.isValid():
                self.commit_draft_change(
                    lambda draft: m.find_node(draft,n['id']).__setitem__('accent',color.name()),
                    inspector_node=n['id'])
        accent.clicked.connect(pick_color);self.inspector_layout.addWidget(accent)
        asset=QPushButton('Choose icon from atlas…')
        asset.clicked.connect(lambda:self.open_asset_picker(item))
        self.inspector_layout.addWidget(asset)
        for side in ('inputs','outputs'):
            group=QLabel(side.upper());group.setStyleSheet('margin-top:12px;color:#68cfea;font-weight:800')
            self.inspector_layout.addWidget(group)
            for p in list(n['draft_ports'][side]):
                row_=QWidget();lay=QHBoxLayout(row_);lay.setContentsMargins(0,0,0,0)
                edit=QLineEdit(p['label']);edit.setMinimumWidth(55)
                edit.editingFinished.connect(lambda p=p,e=edit:self.update_port(item,p,label=e.text()))
                combo=QComboBox();combo.addItems(m.TYPES);combo.setCurrentText(p['type'])
                combo.setFixedWidth(80);combo.currentTextChanged.connect(lambda typ,p=p:self.update_port(item,p,type_=typ))
                remove=QPushButton('×');remove.setFixedWidth(28)
                remove.clicked.connect(lambda checked=False,p=p:self.delete_port(item,p))
                lay.addWidget(edit,1);lay.addWidget(combo);lay.addWidget(remove)
                self.inspector_layout.addWidget(row_)
                if side=='inputs' and p['type'] in ('i32','u32','f32','f64','bool','string'):
                    default_row=QWidget();default_layout=QHBoxLayout(default_row)
                    default_layout.setContentsMargins(3,0,0,0)
                    current=m.format_input_default(p)
                    default_label=QLabel('Fallback: '+('not set' if current is None else str(current)[:45]))
                    set_button=QPushButton('Edit')
                    set_button.clicked.connect(lambda checked=False,p=p:self.edit_input_default(item,p))
                    clear_button=QPushButton('Clear')
                    clear_button.setEnabled('default' in p)
                    clear_button.clicked.connect(lambda checked=False,p=p:self.clear_input_default(item,p))
                    default_layout.addWidget(default_label,1)
                    default_layout.addWidget(set_button)
                    default_layout.addWidget(clear_button)
                    self.inspector_layout.addWidget(default_row)
            add=QPushButton('+ Add '+side[:-1]+' pin')
            add.clicked.connect(lambda checked=False,side=side:self.add_port(item,side))
            self.inspector_layout.addWidget(add)
        self.inspector_layout.addWidget(QLabel('CONTAINERS / CONTROL ROWS'))
        for s in list(n.get('containers',[])):
            frame=QFrame();f=QVBoxLayout(frame);f.setContentsMargins(5,5,5,5)
            frame.setStyleSheet('QFrame {border:1px solid #285778;border-radius:6px;}')
            head=QHBoxLayout();rename=QPushButton(s['title']);rename.clicked.connect(lambda checked=False,s=s:self.rename_section(item,s))
            trash=QPushButton('×');trash.setFixedWidth(27);trash.clicked.connect(lambda checked=False,s=s:self.delete_section(item,s))
            head.addWidget(rename,1);head.addWidget(trash);f.addLayout(head)
            visible=QSpinBox();visible.setRange(1,50);visible.setValue(s.get('visible_rows',5))
            visible.setPrefix('Visible rows: ')
            visible.valueChanged.connect(lambda value,s=s:self.update_visible_rows(item,s,value))
            f.addWidget(visible)
            for r in list(s['rows']):
                line=QHBoxLayout();label=QLabel(f'{r["kind"]}: {r["label"]}')
                rename_row=QPushButton('✎');rename_row.setFixedWidth(28)
                rename_row.clicked.connect(lambda checked=False,r=r:self.rename_row(item,r))
                delete=QPushButton('×');delete.setFixedWidth(28)
                delete.clicked.connect(lambda checked=False,s=s,r=r:self.delete_row(item,s,r))
                line.addWidget(label,1);line.addWidget(rename_row);line.addWidget(delete)
                f.addLayout(line)
            addrow=QPushButton('+ Add control')
            addrow.clicked.connect(lambda checked=False,s=s:self.add_row(item,s));f.addWidget(addrow)
            self.inspector_layout.addWidget(frame)
        btn=QPushButton('+ Add container');btn.clicked.connect(lambda:self.add_section(item))
        self.inspector_layout.addWidget(btn)
        delete_node=QPushButton('Delete selected node');delete_node.clicked.connect(lambda:self.delete_node(item))
        self.inspector_layout.addWidget(delete_node);self.inspector_layout.addStretch()

    def commit_draft_change(self,edit,*,inspector_node=None):
        """One draft mutation gate: validate before publish; repaint from snapshot."""
        try:
            candidate=m.transaction(self.state,edit)
        except (ValueError,KeyError,TypeError) as exc:
            self.report('Draft edit refused: '+str(exc))
            return False
        self.state=candidate
        self.canvas.rebuild()
        self.mark_changed(False)
        if inspector_node is not None and inspector_node in self.canvas.items_by_id:
            self.show_inspector(self.canvas.items_by_id[inspector_node])
        else:
            self.refresh_inspector()
        return True

    def _sync_edit(self,item,refresh=True):
        # Non-port controls keep their existing in-place UI lifecycle. Changes
        # affecting graph identity/ports/edges use commit_draft_change instead.
        item.rebuild();self.canvas.update_edges();self.canvas.update_port_appearance();self.mark_changed(False)
        if refresh:self.show_inspector(item)

    def add_port(self,item,side):
        label,ok=QInputDialog.getText(self,'New port','Port label:')
        if ok and label.strip():
            node_id=item.data['id']
            new_port=m.port(label.strip()[:45],'f32')
            self.commit_draft_change(lambda draft: m.find_node(draft,node_id)['draft_ports'][side].append(new_port),
                                     inspector_node=node_id)

    def update_port(self,item,p,label=None,type_=None):
        if ((label is None or p['label']==label[:45]) and
                (type_ is None or p['type']==type_)):
            return
        node_id,port_id=item.data['id'],p['id']
        def change(draft):
            node=m.find_node(draft,node_id)
            edited=next(port for side in ('inputs','outputs')
                        for port in node['draft_ports'][side] if port['id']==port_id)
            if label is not None:edited['label']=label[:45]
            if type_ is not None:
                if type_!=edited['type'] and 'default' in edited:
                    try:edited['default']=m.parse_input_default(type_,m.format_input_default(edited))
                    except ValueError:edited.pop('default',None)
                edited['type']=type_
            draft['edges'][:]=[edge for edge in draft['edges'] if self._edge_compatible(draft,edge)]
        self.commit_draft_change(change,inspector_node=node_id)

    @staticmethod
    def _edge_compatible(state,e):
        src=m.find_port(m.find_node(state,e['source']),'outputs',e['sourcePort'])
        dst=m.find_port(m.find_node(state,e['target']),'inputs',e['targetPort'])
        return bool(src and dst and src['type']==dst['type'])

    def edit_input_default(self,item,p):
        if p not in item.data['draft_ports']['inputs']:
            self.report('Only unconnected input ports can have local fallback values')
            return
        if item.source_view or item.settings_view:
            self.report('Source and settings graph pins are derived, not independently editable')
            return
        current=m.format_input_default(p)
        value,ok=QInputDialog.getText(self,'Edit unconnected input default',
            f'{p["label"]} ({p["type"]}) — inline fallback if no wire is connected:',
            text=current or '')
        if not ok:return
        node_id,port_id=item.data['id'],p['id']
        def change(draft):
            port=next(port for port in m.find_node(draft,node_id)['draft_ports']['inputs']
                      if port['id']==port_id)
            port['default']=m.parse_input_default(port['type'],value)
        self.commit_draft_change(change,inspector_node=node_id)

    def clear_input_default(self,item,p):
        node_id,port_id=item.data['id'],p['id']
        def change(draft):
            port=next(port for port in m.find_node(draft,node_id)['draft_ports']['inputs']
                      if port['id']==port_id)
            port.pop('default',None)
        self.commit_draft_change(change,inspector_node=node_id)

    def delete_port(self,item,p):
        node_id,port_id=item.data['id'],p['id']
        self.commit_draft_change(lambda draft: m.remove_port(draft,node_id,port_id),
                                 inspector_node=node_id)

    def add_section(self,item):
        name,ok=QInputDialog.getText(self,'Add container','Name:')
        if ok and name.strip():
            created=m.section(name.strip()[:50])
            created['visible_rows']=int(self.state['settings'].get('default_visible_rows',5))
            item.data['containers'].append(created)
            self._sync_edit(item)

    def delete_section(self,item,sec):item.data['containers'].remove(sec);self._sync_edit(item)
    def rename_section(self,item,sec):
        name,ok=QInputDialog.getText(self,'Rename container','Name:',text=sec['title'])
        if ok and name.strip():sec['title']=name.strip()[:50];self._sync_edit(item)

    def update_visible_rows(self,item,sec,value):sec['visible_rows']=value;self._sync_edit(item,False)

    def add_row(self,item,sec):
        kind,ok=QInputDialog.getItem(self,'Add control','Type:',list(m.ROW_TYPES),0,False)
        if ok:
            name,accepted=QInputDialog.getText(self,'Control label','Label:',text=kind.capitalize())
            if accepted:sec['rows'].append(m.row(kind,name.strip()[:55] or kind.capitalize()));self._sync_edit(item)

    def rename_row(self,item,row):
        name,ok=QInputDialog.getText(self,'Rename control','Label:',text=row['label'])
        if ok and name.strip():row['label']=name.strip()[:55];self._sync_edit(item)

    def delete_row(self,item,sec,row):sec['rows'].remove(row);self._sync_edit(item)

    def delete_node(self,item):
        self.commit_draft_change(lambda draft: m.remove_node(draft,item.data['id']),inspector_node=None)

    def new_graph(self):
        if not self.confirm_discard():return
        self.state=m.new_state();self.current_path=None;self.dirty=False
        self.canvas.rebuild();self.settings_canvas.rebuild();self.refresh_inspector()
        self.setWindowTitle(APP_TITLE)

    def confirm_discard(self):
        if not self.dirty:return True
        return QMessageBox.question(self,'Unsaved graph','Discard unsaved changes?',QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)==QMessageBox.StandardButton.Yes

    def open_graph(self):
        if not self.confirm_discard():return
        path=self._choose_file(title='Open dynamic node graph',filters='Node Lab Graph (*.json);;All Files (*)')
        if not path:return
        try:loaded=m.read_state(path)
        except (OSError,ValueError) as exc:QMessageBox.warning(self,'Invalid graph',str(exc));return
        self.state=loaded;self.current_path=Path(path);self.dirty=False
        self.canvas.rebuild();self.settings_canvas.rebuild();self.refresh_inspector();self.report(f'Opened {path}')
        self.setWindowTitle(APP_TITLE)

    def save_current_document(self):
        # Ctrl+S follows the source document even when its AST is invalid.
        program=self._program_tabs.get(self.tabs.currentWidget())
        if program is not None:return program.save()
        if self._active_source_document() and (self.tabs.currentWidget() is self.source_page or self.source_editor.hasFocus()):
            return self.save_python_editor()
        return self.save_graph()

    def save_graph(self):
        if not self.current_path:return self.save_as()
        try:m.write_state(self.current_path,self.state)
        except (OSError,ValueError) as exc:QMessageBox.warning(self,'Save refused',str(exc));return
        self.dirty=False;self.setWindowTitle(APP_TITLE);self.report(f'Saved {self.current_path}')

    def save_as(self):
        program=self._program_tabs.get(self.tabs.currentWidget())
        if program is not None:
            return program.save_as()
        path=self._choose_file(title='Save dynamic node graph',filters='Node Lab Graph (*.json);;All Files (*)',save=True,proposed=Path.home()/'node-lab.json')
        if not path:return
        candidate=Path(path)
        try:m.write_state(candidate,self.state)
        except (OSError,ValueError) as exc:
            QMessageBox.warning(self,'Save refused',str(exc))
            return
        self.current_path=candidate
        self.dirty=False
        self.setWindowTitle(APP_TITLE)
        self.report(f'Saved {candidate}')

    def closeEvent(self,event):
        pending=[str(doc.path) for doc in self._source_documents.values() if doc.dirty]
        sources_ok=(not pending or QMessageBox.question(self,'Unsaved Python documents',
            'Unsaved Python text exists in '+str(len(pending))+' document(s). Discard all and exit?',
            QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)==QMessageBox.StandardButton.Yes)
        if sources_ok and self.confirm_discard() and all(
                program.confirm_close() for program in self._program_tabs.values()):
            # A confirmed discard must retire recovery snapshots, while an
            # interrupted or rejected shutdown must retain them.
            try:
                self._draft_recovery_timer.stop()
                for session in self._source_documents.values():
                    session.clear_recovery(self._draft_recovery)
            except (OSError,ValueError) as exc:
                QMessageBox.warning(self,'Cannot clear recovery journal',str(exc))
                event.ignore()
                return
            if self._python_process and self._python_process.state()!=QProcess.ProcessState.NotRunning:
                self._python_process.kill()
            self._store_active_resource_view()
            self._store_active_source_view()
            for canvas in (self.canvas,self.settings_canvas,
                           *(view.canvas for view in self._resource_tabs.values()),
                           *(view.canvas for view in self._source_tabs.values())):
                canvas._save_root_view()
            self._presentation_timer.stop()
            self._save_presentation_state()
            event.accept()
        else:event.ignore()


def launch():
    app=QApplication(sys.argv);app.setStyle('Fusion');app.setStyleSheet(css())
    window=NativeLab();window.show();return app.exec()
