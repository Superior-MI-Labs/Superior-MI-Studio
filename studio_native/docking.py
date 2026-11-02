"""Native QMainWindow dock-region visibility policy.

Placement, splitters, floating, and pane ownership remain with Qt. This module
adds only a region-level visibility policy and an accessible persistent grip.
It never owns or replaces the editor, inspector, or library widgets.
"""
from __future__ import annotations

from PyQt6.QtCore import QObject, QTimer, Qt
from PyQt6.QtGui import QCursor
from PyQt6.QtWidgets import QWidget, QLabel, QHBoxLayout, QMenu, QSizePolicy

MODES=('pinned','collapsed','auto-hide')


class DockGrip(QWidget):
    """Visible native-dock title bar, even while its content is collapsed."""
    def __init__(self, region, dock):
        super().__init__(dock)
        self._initial_region=region
        self.dock=dock
        self.setObjectName('DockGrip_'+dock.objectName())
        self.setFixedHeight(25)
        self.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Fixed)
        self.setToolTip('Double-click to pin/collapse · Right-click for dock behavior · Drag to reposition')
        line=QHBoxLayout(self)
        line.setContentsMargins(7,0,6,0)
        line.setSpacing(8)
        grip=QLabel('⋮⋮',self)
        grip.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        grip.setStyleSheet('color:#b8ddec;font-weight:700;')
        self.label=QLabel(dock.windowTitle(),self)
        self.label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.label.setStyleSheet('color:#9acee4;font-weight:700;')
        line.addWidget(grip)
        line.addWidget(self.label,1)
        self.setStyleSheet('DockGrip { background:#0f2a41;border-bottom:1px solid #244b62; }')

    @property
    def region(self):
        # Resolve actual Qt placement at interaction time. A pane dragged to
        # the other side should obey its NEW dock region's state, not its type.
        area=self._initial_region.window.dockWidgetArea(self.dock)
        return next((region for region in self._initial_region.window._dock_regions.values()
                     if region.area==area),self._initial_region)

    def mouseDoubleClickEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton:
            self.region.set_mode('collapsed' if self.region.mode=='pinned' else 'pinned')
            event.accept()
        else:event.ignore()

    def mousePressEvent(self,event):
        # Preserve QDockWidget's established drag/floating behavior.
        event.ignore()

    def mouseMoveEvent(self,event):event.ignore()

    def mouseReleaseEvent(self,event):event.ignore()

    def contextMenuEvent(self,event):
        menu=QMenu(self)
        for mode,label in (('pinned','Show · pinned'),('collapsed','Hide · collapsed'),
                           ('auto-hide','Auto-hide · reveal on hover')):
            entry=menu.addAction(label)
            entry.setCheckable(True)
            entry.setChecked(self.region.mode==mode)
            entry.triggered.connect(lambda checked=False,m=mode:self.region.set_mode(m))
        menu.addSeparator()
        panes=menu.addMenu('Windows in this region')
        for dock in self.region.docks:
            panes.addAction(dock.toggleViewAction())
        menu.addAction('Dock window' if self.dock.isFloating() else 'Float window',
                       lambda:self.dock.setFloating(not self.dock.isFloating()))
        menu.exec(event.globalPos())
        event.accept()

    def enterEvent(self,event):
        self.region.on_grip_enter()
        super().enterEvent(event)


class DockRegionController(QObject):
    """One visibility state for all Qt dock widgets in an actual side region.

    Only displayed dock contents participate in region collapse. Hidden docks
    remain hidden; selecting a different inspector/editor is not implicitly
    converted into a visibility or source-edit operation.
    """
    def __init__(self, window, name, area):
        super().__init__(window)
        self.window=window
        self.name=name
        self.area=area
        self.mode='pinned'
        self._preview=False
        self._saved_extent=360
        self._hover_timer=QTimer(self)
        self._hover_timer.setInterval(280)
        self._hover_timer.timeout.connect(self._check_hover)

    @property
    def docks(self):
        # Qt's current layout, not a parallel registry, owns area membership.
        return [dock for dock in getattr(self.window,'_managed_docks',())
                if not dock.isFloating() and self.window.dockWidgetArea(dock)==self.area]

    def register(self,dock):
        managed=self.window._managed_docks
        if dock in managed:raise ValueError('Duplicate dock region registration')
        if self.window.dockWidgetArea(dock)!=self.area:
            raise ValueError('Dock registered in the wrong native Qt area')
        managed.append(dock)
        dock.setTitleBarWidget(DockGrip(self,dock))
        # Never force a minimum width on QDockWidget: Qt explicitly places
        # size constraints on its content and changes frames when floating.
        dock.setMinimumSize(0,0)
        dock.topLevelChanged.connect(lambda floating,d=dock:self._on_floating(d,floating))

    def _on_floating(self,dock,floating):
        # An auto-hidden floating window could become inaccessible. Pin it.
        if floating and self.mode!='pinned':self.set_mode('pinned')

    def _current_extent(self):
        for dock in self.docks:
            if dock.isVisible() and not dock.isFloating():
                return dock.width() if self.area in (Qt.DockWidgetArea.LeftDockWidgetArea,
                                                     Qt.DockWidgetArea.RightDockWidgetArea) else dock.height()
        return 0

    def _resize(self,extent):
        targets=[dock for dock in self.docks if dock.isVisible() and not dock.isFloating()]
        if targets:
            orientation=(Qt.Orientation.Horizontal if self.area in (
                Qt.DockWidgetArea.LeftDockWidgetArea,Qt.DockWidgetArea.RightDockWidgetArea)
                else Qt.Orientation.Vertical)
            self.window.resizeDocks(targets,[extent]*len(targets),orientation)

    def _set_content(self,visible):
        for dock in self.docks:
            content=dock.widget()
            if content is not None:
                content.setVisible(bool(visible))

    def _collapse(self):
        self._preview=False
        self._hover_timer.stop()
        if self._current_extent()>75:
            self._saved_extent=self._current_extent()
        self._set_content(False)
        self._resize(28)

    def _expand(self,*,temporary=False):
        self._preview=temporary
        self._set_content(True)
        self._resize(max(220,self._saved_extent))
        if temporary:self._hover_timer.start()
        else:self._hover_timer.stop()

    def set_mode(self,mode,*,save=True):
        if mode not in MODES:raise ValueError('Unknown dock region mode')
        if mode=='auto-hide' and any(dock.isFloating() for dock in self.docks):
            mode='pinned'   # Floating auto-hide is deliberately unsupported.
        self.mode=mode
        if mode=='pinned':self._expand()
        else:self._collapse()
        if save:
            self.window._dock_modes[self.name]=mode
            self.window._queue_presentation_save()
        for dock in self.docks:
            grip=dock.titleBarWidget()
            if grip is not None:
                grip.setToolTip('Dock region: '+mode+' · Double-click to pin/collapse · Right-click for options')

    def on_grip_enter(self):
        if self.mode=='auto-hide' and not self._preview:
            self._expand(temporary=True)

    def _check_hover(self):
        if self.mode!='auto-hide' or not self._preview:
            self._hover_timer.stop()
            return
        cursor=QCursor.pos()
        if any(dock.isVisible() and dock.rect().contains(dock.mapFromGlobal(cursor))
               for dock in self.docks):
            return
        self._collapse()
