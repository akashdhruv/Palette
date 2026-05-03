import curses


class ScreenManager:
    def __init__(self, stdscr, state):
        self.stdscr = stdscr
        self.state  = state
        self._stack     = []
        self._registry  = {}

    def register(self, name, screen_cls):
        self._registry[name] = screen_cls

    def _make(self, name):
        return self._registry[name](self)

    def push(self, name):
        screen = self._make(name)
        self._stack.append(screen)
        screen.on_enter()

    def pop(self):
        if self._stack:
            self._stack[-1].on_exit()
            self._stack.pop()
            if self._stack:
                self._stack[-1].on_resume()

    def quit(self):
        while self._stack:
            self._stack[-1].on_exit()
            self._stack.pop()

    def replace(self, name):
        if self._stack:
            self._stack[-1].on_exit()
            self._stack.pop()
        self.push(name)

    def run(self):
        self.push('home')
        self.stdscr.nodelay(False)
        while self._stack:
            self.rows, self.cols = self.stdscr.getmaxyx()
            top = self._stack[-1]
            top.rows, top.cols = self.rows, self.cols
            self.stdscr.erase()
            try:
                top.draw()
            except Exception:
                pass
            try:
                self.stdscr.refresh()
            except Exception:
                pass
            key = self.stdscr.getch()
            if key == curses.KEY_RESIZE:
                for s in self._stack:
                    s.rows, s.cols = self.rows, self.cols
            elif key != -1:
                try:
                    top.handle_key(key)
                except Exception:
                    pass
