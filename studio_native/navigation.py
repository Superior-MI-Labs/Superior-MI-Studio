"""Navigation identities and breadcrumbs, independent of Qt or language syntax.

Resource containment, lexical scope and control-region containment are distinct
relationships. A breadcrumb target is a VIEW route, not a graph edge or source edit.
The parser/provider remain authoritative for whether a destination exists.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json


@dataclass(frozen=True)
class Route:
    kind: str                         # resource | source | region
    path: str                         # canonical provider identity in this prototype
    scope: str = 'module'              # lexical source identity
    mode: str = 'whole'                # whole | focus (source routes)
    region: str = ''                    # view-only child region (future focus session)

    def __post_init__(self):
        if self.kind not in ('resource', 'source', 'region') or not self.path:
            raise ValueError('Unsupported or empty navigation route')
        if self.kind in ('source', 'region') and self.mode not in ('whole', 'focus'):
            raise ValueError('Invalid source view mode')
        if self.kind == 'region' and not self.region:
            raise ValueError('Region routes require a source-owned region identity')


@dataclass(frozen=True)
class Crumb:
    text: str
    route: Route


def resource_crumbs(path: str | Path) -> tuple[Crumb, ...]:
    """Filesystem ancestry only; no stat, traversal, symlink resolution or execution."""
    current = Path(path).expanduser().absolute()
    ancestors = list(reversed(current.parents)) + [current]
    return tuple(Crumb('/' if item == Path(item.anchor) else item.name,
                       Route('resource', str(item))) for item in ancestors)


def source_crumbs(document, scope: str = 'module', mode: str = 'whole') -> tuple[Crumb, ...]:
    """Source file is a resource; its lexical scopes are adapter-owned identities."""
    if mode not in ('whole', 'focus') or (mode == 'focus' and scope not in document.scopes):
        raise ValueError('Unknown Python navigation scope/mode')
    # Whole-file routes are canonical module views. A caller switching out of
    # focus must not turn a stale scope key into a navigation failure.
    if mode == 'whole':
        scope = 'module'
    path = str(document.path)
    crumbs = list(resource_crumbs(document.path.parent))
    crumbs.append(Crumb(document.path.name, Route('source', path)))
    if mode == 'focus' and scope != 'module':
        parents = []
        current = scope
        while current != 'module':
            info = document.scopes[current]
            parents.append(Crumb(info.title, Route('source', path, current, 'focus')))
            current = info.parent
            if current is None:
                raise ValueError('Unterminated source scope ancestry')
        crumbs.extend(reversed(parents))
    return tuple(crumbs)



def shorten_crumb(text: str, limit: int = 22) -> str:
    """Pure view label. Preserve endpoints and full identity on the Crumb itself.

    This must never be used as a Route/path/symbol identifier: separate names
    may truncate to the same label without becoming the same destination.
    """
    if limit < 5:
        raise ValueError('Breadcrumb labels require at least five characters')
    if len(text) <= limit:
        return text
    head=(limit-1)*2//3
    tail=limit-1-head
    return text[:head]+'…'+text[-tail:]


def visible_breadcrumbs(crumbs: tuple[Crumb, ...], limit: int = 4):
    """Retain root and immediate ancestry; leave hidden routes in a menu.

    This is a projection of source/provider routes, not a second history.
    Returns (display with one None overflow marker, hidden Crumbs).
    """
    if limit < 3:
        raise ValueError('At least root, overflow and current are necessary')
    if len(crumbs) <= limit:
        return tuple(crumbs), ()
    count=limit-2
    return (crumbs[0],None,*crumbs[-count:]), tuple(crumbs[1:-count])


def root_camera_slot(session_id: str, route: Route) -> tuple[str, str]:
    """One persisted camera key per graph view, route and tab identity.

    Cameras remain owned by the existing presentation store; this function
    only builds their stable identity. A source focus, its whole-file view,
    and a separate tab of the same file must not share one root camera.
    Never use a displayed breadcrumb title as source identity.
    """
    if not isinstance(session_id, str) or not session_id.strip():
        raise ValueError('Root camera requires a graph-view session identity')
    if not isinstance(route, Route):
        raise TypeError('Root camera requires a validated Route')
    # JSON-encoded tuple avoids ambiguous separators in IDs, region or scopes.
    return (route.path, '@root-view:'+json.dumps(
        [session_id, route.kind, route.scope, route.mode, route.region],
        ensure_ascii=True, separators=(',', ':')))


class NavigationHistory:
    """Presentation-only back/forward history; destinations are validated on visit.

    A caller must navigate successfully before calling move(), so invalid or
    missing resources never advance history or corrupt the current view.
    """
    def __init__(self, initial: Route, *, limit: int = 128):
        if limit < 2:
            raise ValueError('Navigation history requires at least two entries')
        self._entries = [initial]
        self._position = 0
        self.limit = limit

    @property
    def current(self) -> Route:
        return self._entries[self._position]

    def visit(self, route: Route) -> bool:
        if route == self.current:
            return False
        del self._entries[self._position + 1:]
        self._entries.append(route)
        if len(self._entries) > self.limit:
            del self._entries[:len(self._entries) - self.limit]
        self._position = len(self._entries) - 1
        return True

    def peek(self, direction: int) -> Route | None:
        if direction not in (-1, 1):
            raise ValueError('History navigation is one step in either direction')
        pos = self._position + direction
        return self._entries[pos] if 0 <= pos < len(self._entries) else None

    def move(self, direction: int) -> Route | None:
        route = self.peek(direction)
        if route is not None:
            self._position += direction
        return route

    def replace_current(self, route: Route) -> bool:
        """Activate a validated view without adding a Back entry.

        View refreshes must not leave the session/camera pointed at a previous
        route. A changed current view also invalidates any forward branch.
        A same-route refresh preserves the existing Back/Forward history.
        """
        if not isinstance(route, Route):
            raise TypeError('Active navigation destination must be a Route')
        if route == self.current:
            return False
        del self._entries[self._position + 1:]
        self._entries[self._position] = route
        return True


class GraphViewSession:
    """One tab's independent navigation authority, independent of Qt and source.

    NavigationHistory owns its current route. A session does not copy a Python
    AST, a resource graph, a compiler graph, or an editable source document.
    Additional graph tabs may each get their own instance and Qt canvas.
    """
    def __init__(self, session_id: str, initial: Route, *, history_limit: int = 128):
        if not isinstance(session_id, str) or not session_id.strip():
            raise ValueError('A graph view needs a stable session ID')
        self.session_id = session_id
        self.history = NavigationHistory(initial, limit=history_limit)

    @property
    def route(self) -> Route:
        return self.history.current

    def camera_slot(self) -> tuple[str, str]:
        """Qualified view-camera identity; presentation store still owns values."""
        return root_camera_slot(self.session_id,self.route)

    def visit(self, destination: Route) -> bool:
        """Called only after the resource/language adapter accepts the route."""
        if not isinstance(destination, Route):
            raise TypeError('Session destination must be a validated Route')
        return self.history.visit(destination)

    def activate(self, destination: Route, *, record_history: bool = True,
                 history_direction: int | None = None) -> bool:
        """Commit one successfully resolved graph view to the active session.

        History navigation moves the existing cursor; refreshing a different
        route replaces its current entry rather than leaving a stale camera key.
        This is presentation-only, never a source or resource write.
        """
        if not isinstance(destination, Route):
            raise TypeError('Session destination must be a validated Route')
        if history_direction is not None:
            if history_direction not in (-1, 1):
                raise ValueError('History navigation direction must be -1 or +1')
            if self.history.peek(history_direction) != destination:
                raise ValueError('Resolved history destination does not match pending step')
            self.history.move(history_direction)
            return True
        if record_history:
            return self.history.visit(destination)
        return self.history.replace_current(destination)

    def peek(self, direction: int) -> Route | None:
        return self.history.peek(direction)

    def commit_history_move(self, direction: int, successful_destination: Route) -> bool:
        """Compatibility entrypoint; activate() is the only commit authority."""
        if self.history.peek(direction) != successful_destination:
            return False
        return self.activate(successful_destination,history_direction=direction)


class GraphViewSessions:
    """Tab-session membership; no second graph/source registry or cloned data."""
    def __init__(self):
        self._sessions: dict[str, GraphViewSession] = {}

    def open(self, session_id: str, destination: Route) -> GraphViewSession:
        if session_id in self._sessions:
            raise ValueError('Graph tab identity already exists: ' + session_id)
        session = GraphViewSession(session_id, destination)
        self._sessions[session_id] = session
        return session

    def get(self, session_id: str) -> GraphViewSession | None:
        return self._sessions.get(session_id)

    def close(self, session_id: str) -> bool:
        return self._sessions.pop(session_id, None) is not None

    def replace(self, session_id: str, destination: Route) -> GraphViewSession:
        """Reuse the same tab for a newly opened resource, resetting old history."""
        if session_id not in self._sessions:
            raise ValueError('Unknown graph tab identity: ' + session_id)
        session = GraphViewSession(session_id, destination)
        self._sessions[session_id] = session
        return session

    def __len__(self) -> int:
        return len(self._sessions)
