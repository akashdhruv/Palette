from abc import ABC, abstractmethod


class BaseScreen(ABC):
    def __init__(self, manager):
        self.manager = manager
        self.state   = manager.state
        self.stdscr  = manager.stdscr
        self.rows, self.cols = self.stdscr.getmaxyx()

    def on_enter(self):  pass
    def on_exit(self):   pass
    def on_resume(self): pass

    @abstractmethod
    def draw(self): ...

    @abstractmethod
    def handle_key(self, key): ...
