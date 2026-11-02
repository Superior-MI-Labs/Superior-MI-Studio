"""Shared graph-surface geometry; no Qt or programming-language dependencies.

A source document's root and each expanded composite own the same GraphSurfaceState.
Viewport dimensions, camera transforms, and extent belong to presentation only.
They never create a source node, binding, port, or execution edge.
"""
from __future__ import annotations
from dataclasses import dataclass
from math import isfinite

MIN_ZOOM = .01
MAX_ZOOM = 2.5


@dataclass
class GraphSurfaceState:
    viewport_width: float
    viewport_height: float
    content_width: float
    content_height: float
    offset_x: float = 0.0
    offset_y: float = 0.0
    zoom: float = 1.0

    def __post_init__(self):
        if not all(isfinite(x) and x > 0 for x in (self.viewport_width,self.viewport_height,
                                                   self.content_width,self.content_height)):
            raise ValueError('Graph dimensions must be finite and positive')
        if not isfinite(self.zoom) or not MIN_ZOOM <= self.zoom <= MAX_ZOOM:
            raise ValueError('Invalid graph zoom')
        self._clamp()

    def _clamp(self):
        # Free camera: there is intentionally NO content-dependent pan clamp.
        # Users must be able to navigate beyond nodes into empty graph space,
        # including after all content fits. Fit is an explicit separate action.
        if not all(isfinite(n) for n in (self.offset_x,self.offset_y)):
            raise ValueError('Nonfinite camera position')

    def pan(self, dx: float, dy: float):
        if not all(isfinite(n) for n in (dx,dy)):raise ValueError('Nonfinite pan')
        self.offset_x+=dx;self.offset_y+=dy;self._clamp()

    def zoom_at(self, factor: float, x: float, y: float):
        if not all(isfinite(n) for n in (factor,x,y)) or factor<=0:
            raise ValueError('Invalid zoom factor or anchor')
        old=self.zoom
        self.zoom=max(MIN_ZOOM,min(MAX_ZOOM,self.zoom*factor))
        # Keep the logical graph coordinate below the pointer stationary.
        self.offset_x=x-(x-self.offset_x)*self.zoom/old
        self.offset_y=y-(y-self.offset_y)*self.zoom/old
        self._clamp()

    def resize_viewport(self, width: float, height: float):
        if not all(isfinite(n) and n>0 for n in (width,height)):
            raise ValueError('Invalid viewport dimensions')
        self.viewport_width=float(width)
        self.viewport_height=float(height)
        self._clamp()

    def fit_contents(self, padding: float = 8.0, *, min_readable_zoom: float | None = None):
        """Fit contents, or prioritize readability for dense embedded graphs.

        Without a readability floor this remains a true full-content fit.
        With a floor, the top-left of oversized content stays visible and the
        user pans to the rest; this must never silently scale to 1% size.
        """
        if not isfinite(padding) or padding<0:
            raise ValueError('Invalid viewport padding')
        if min_readable_zoom is not None and (
                not isfinite(min_readable_zoom) or not MIN_ZOOM <= min_readable_zoom <= MAX_ZOOM):
            raise ValueError('Invalid readable zoom floor')
        available_w=max(1.0,self.viewport_width-2*padding)
        available_h=max(1.0,self.viewport_height-2*padding)
        desired=max(MIN_ZOOM,min(1.0,available_w/self.content_width,
                                     available_h/self.content_height))
        if min_readable_zoom is not None and desired < min_readable_zoom:
            self.zoom=min_readable_zoom
            self.offset_x=padding
            self.offset_y=padding
        else:
            self.zoom=desired
            self.offset_x=(self.viewport_width-self.content_width*self.zoom)/2
            self.offset_y=(self.viewport_height-self.content_height*self.zoom)/2
        self._clamp()

    def ensure_extent(self, right: float, bottom: float):
        if not all(isfinite(n) for n in (right,bottom)):
            raise ValueError('Nonfinite graph extent')
        self.content_width=max(self.content_width,right)
        self.content_height=max(self.content_height,bottom)
        self._clamp()

    def map_to_content(self,x:float,y:float):
        return ((x-self.offset_x)/self.zoom,(y-self.offset_y)/self.zoom)

    def view_position(self,x:float,y:float):
        return (self.offset_x+x*self.zoom,self.offset_y+y*self.zoom)

# Shared view metrics, not programming semantics. All graph producers and the
# renderer must agree on compact resource geometry.
RESOURCE_COMPACT_WIDTH = 186.0
RESOURCE_COMPACT_HEIGHT = 36.0


def marquee_selection(selected: set, hits: set, mode: str = 'replace') -> set:
    """Blueprint selection rules, independent of Qt and graph semantics.

    The renderer determines visible hits within one graph surface. Selection
    of presentation items is never an authorization to edit Python source.
    """
    if mode == 'replace':return set(hits)
    if mode == 'add':return set(selected) | set(hits)
    if mode == 'toggle':return set(selected) ^ set(hits)
    raise ValueError('Unknown marquee selection mode')


def resize_handle(x: float, y: float, width: float, height: float,
                  *, edge: float=7.0, corner: float=16.0) -> str | None:
    """Identify all eight resize handles in node-local coordinates.

    Pure geometry used by the shared canvas and by standalone graph items.
    Corners take precedence. Header controls and semantic pins are dispatched
    separately before calling this function.
    """
    if not all(isfinite(v) for v in (x,y,width,height)) or width<=0 or height<=0:
        raise ValueError('Invalid resize bounds')
    if x<0 or y<0 or x>width or y>height:return None
    near_left=x<=corner;near_right=x>=width-corner
    near_top=y<=corner;near_bottom=y>=height-corner
    if (near_left or near_right) and (near_top or near_bottom):
        return ('n' if near_top else 's')+('w' if near_left else 'e')
    if x<=edge:return 'w'
    if x>=width-edge:return 'e'
    if y<=edge:return 'n'
    if y>=height-edge:return 's'
    return None


def resize_rectangle(handle: str, width: float, height: float, dx: float, dy: float,
                     *, min_width=180.0, max_width=4000.0,
                     min_height=90.0, max_height=3000.0) -> tuple[float,float,float,float]:
    """Return new viewport dimensions and origin shift for any edge/corner.

    Origin shifts are measured against the PRE-drag parent-local rectangle;
    west/north drags hold the opposite boundary stationary even at limits.
    """
    if handle not in ('n','s','e','w','nw','ne','sw','se'):
        raise ValueError('Unknown resize handle')
    if not all(isfinite(v) for v in (width,height,dx,dy)) or width<=0 or height<=0:
        raise ValueError('Invalid resize values')
    actual_width=max(min_width,min(max_width,width+(-dx if 'w' in handle else dx if 'e' in handle else 0)))
    actual_height=max(min_height,min(max_height,height+(-dy if 'n' in handle else dy if 's' in handle else 0)))
    return (actual_width,actual_height,
            width-actual_width if 'w' in handle else 0.0,
            height-actual_height if 'n' in handle else 0.0)


def frame_visible_bounds(rectangles, viewport_width: float, viewport_height: float,
                         *, padding: float = 42.0, min_zoom: float = .3,
                         max_zoom: float = 1.3):
    """Frame *visible top-level node* bounds; never fit a scene background/viewport.

    Return (center_x, center_y, zoom, fully_fits) or None for no visible nodes.
    A huge graph retains a usable zoom floor and may need panning/focusing.
    The semantic graph and nested cameras are entirely unaffected.
    """
    if not all(isfinite(x) and x > 0 for x in (viewport_width, viewport_height,
                                                min_zoom, max_zoom)) or min_zoom > max_zoom:
        raise ValueError('Invalid frame viewport or zoom limits')
    if not isfinite(padding) or padding < 0:
        raise ValueError('Invalid frame padding')
    rects=list(rectangles)
    if not rects:
        return None
    for rect in rects:
        if len(rect) != 4 or not all(isfinite(x) for x in rect) or rect[2] <= 0 or rect[3] <= 0:
            raise ValueError('Invalid visible node rectangle')
    x1=min(r[0] for r in rects)
    y1=min(r[1] for r in rects)
    x2=max(r[0]+r[2] for r in rects)
    y2=max(r[1]+r[3] for r in rects)
    available_w=max(1.0,viewport_width-2*padding)
    available_h=max(1.0,viewport_height-2*padding)
    desired=min(max_zoom,available_w/(x2-x1),available_h/(y2-y1))
    return ((x1+x2)/2,(y1+y2)/2,max(min_zoom,desired),desired>=min_zoom)


def selected_pan_surface(hovered, parent_of, selected):
    """Choose the deepest selected graph, falling back to its ancestor/root.

    Selection is existing view state, not a second active-graph registry.
    The root is always available even if no nested owner is selected.
    Pure policy: Qt supplies containment and the selected-node predicate.
    """
    current = hovered
    while current is not None:
        parent = parent_of(current)
        if parent is None or selected(current):
            return current
        current = parent
    raise ValueError('Pan target has no graph root')


@dataclass(frozen=True)
class OverviewMap:
    """Stable scene-to-overview projection. Camera changes never move the map.

    Only visible top-level nodes define its extent; nested/hidden objects and
    the enormous scene background are not inputs. No Qt or language semantics.
    """
    scene_left: float
    scene_top: float
    scale: float
    map_left: float
    map_top: float

    def to_map(self, x: float, y: float) -> tuple[float, float]:
        return (self.map_left + (x - self.scene_left) * self.scale,
                self.map_top + (y - self.scene_top) * self.scale)

    def to_scene(self, x: float, y: float) -> tuple[float, float]:
        return (self.scene_left + (x - self.map_left) / self.scale,
                self.scene_top + (y - self.map_top) / self.scale)

    def project_rect(self, rect) -> tuple[float, float, float, float]:
        x, y = self.to_map(rect[0], rect[1])
        return x, y, rect[2] * self.scale, rect[3] * self.scale



def overview_viewport_size(width: float, height: float, *,
                           preferred_width: int = 228,
                           preferred_height: int = 154,
                           margin: int = 12,
                           min_width: int = 96,
                           min_height: int = 72) -> tuple[int,int] | None:
    """Pure sizing policy for the Qt-managed minimap layout.

    Qt positions the overlay. This helper only determines whether it fits and
    its maximum width/height; it must never emit a coordinate or rectangle.
    """
    values=(width,height,preferred_width,preferred_height,margin,min_width,min_height)
    if any(not isfinite(value) for value in values):
        raise ValueError('Nonfinite overview size values')
    if width < 0 or height < 0 or preferred_width<=0 or preferred_height<=0 or margin<0 or min_width<=0 or min_height<=0:
        raise ValueError('Invalid overview viewport dimensions')
    available_width=int(width)-2*margin
    available_height=int(height)-2*margin
    if available_width<min_width or available_height<min_height:
        return None
    return min(preferred_width,available_width),min(preferred_height,available_height)


def overview_map(rectangles, width: float, height: float, *, padding=12.0,
                 scene_margin=70.0) -> OverviewMap | None:
    """Map visible node bounds to a fixed-size overview without camera drift.

    Unlike frame-to-content, this intentionally does not constrain the zoom
    or position of the main graph. There is no second camera/source authority.
    """
    vals=(width,height,padding,scene_margin)
    if not all(isfinite(v) for v in vals) or width<=0 or height<=0 or padding<0 or scene_margin<0:
        raise ValueError('Invalid overview dimensions')
    if width<=2*padding or height<=2*padding:
        raise ValueError('Overview padding leaves no drawing space')
    rects=list(rectangles)
    if not rects:return None
    if any(len(r)!=4 or not all(isfinite(v) for v in r) or r[2]<=0 or r[3]<=0 for r in rects):
        raise ValueError('Invalid visible node rectangle')
    x1=min(r[0] for r in rects)-scene_margin
    y1=min(r[1] for r in rects)-scene_margin
    x2=max(r[0]+r[2] for r in rects)+scene_margin
    y2=max(r[1]+r[3] for r in rects)+scene_margin
    scale=min((width-2*padding)/(x2-x1),(height-2*padding)/(y2-y1))
    offset_x=(width-(x2-x1)*scale)/2
    offset_y=(height-(y2-y1)*scale)/2
    return OverviewMap(x1,y1,scale,offset_x,offset_y)


def overview_drag_offset(model: OverviewMap, viewport, pointer) -> tuple[float, float]:
    """Keep the grabbed point beneath the cursor while dragging a viewport box.

    A click outside the box deliberately jumps the camera to the pointer.
    This changes neither the semantic graph nor the overview projection.
    """
    if not isinstance(model, OverviewMap):
        raise TypeError('Overview drag requires a valid overview projection')
    if len(viewport)!=4 or len(pointer)!=2 or not all(isfinite(v) for v in (*viewport,*pointer)):
        raise ValueError('Invalid viewport or pointer')
    vx,vy,vw,vh=viewport
    if vw<=0 or vh<=0:raise ValueError('Invalid viewport size')
    px,py=pointer
    bx,by,bw,bh=model.project_rect(viewport)
    if bx<=px<=bx+bw and by<=py<=by+bh:
        sx,sy=model.to_scene(px,py)
        return (vx+vw/2-sx,vy+vh/2-sy)
    return (0.0,0.0)
