from __future__ import annotations
import curses
from graph.screens import BaseScreen
from graph.display import Color, draw_status_bar, draw_softkey_bar, safe_addstr
from graph.renderer import GraphRenderer
from graph.keys import Key, BACK_KEYS

_SOFTKEYS = ['Y=', 'WINDOW', 'ZOOM', 'TRACE', '']


class GraphScreen(BaseScreen):

    def __init__(self, manager):
        super().__init__(manager)
        self._gr = GraphRenderer(self.state)

    def on_enter(self):
        curses.curs_set(0)
        self._gr.render_graph(force=self.state.graph_dirty)

    def on_resume(self):
        curses.curs_set(0)

    # ------------------------------------------------------------------

    def draw(self):
        draw_status_bar(self.stdscr, self.state)
        draw_softkey_bar(self.stdscr, _SOFTKEYS)
        self._gr.blit_to_window(self.stdscr, start_row=1, start_col=1)

        # Show intersection points below the graph
        intersections = getattr(self._gr, '_intersections', [])
        if intersections:
            rows, cols = self.stdscr.getmaxyx()
            info_row = min(1 + 20 + 1, rows - 2)  # below graph area
            for idx, (ix, iy) in enumerate(intersections[:3]):  # show up to 3
                text = f'X{idx+1}=({ix:.4g},{iy:.4g})'
                safe_addstr(self.stdscr, info_row, 1 + idx * 20, text,
                            curses.color_pair(Color.HIGHLIGHT))

    # ------------------------------------------------------------------

    def handle_key(self, key):
        if key in BACK_KEYS:
            self.manager.pop()
        elif key in Key.F1:
            self.manager.replace('yedit')
        elif key in Key.F2:
            self.manager.replace('window')
        elif key in Key.F3:
            self.manager.push('zoom')
        elif key in Key.F4:
            self.manager.push('trace')

    def get_renderer(self) -> GraphRenderer:
        return self._gr
