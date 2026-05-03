from __future__ import annotations
import copy
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class WindowVars:
    xmin: float = -10.0
    xmax: float =  10.0
    xscl: float =   1.0
    ymin: float = -10.0
    ymax: float =  10.0
    yscl: float =   1.0
    xres: int   =   1


@dataclass
class CalcState:
    # Y= function slots (Y1–Y9)
    y_exprs:   list[str]  = field(default_factory=lambda: [''] * 9)
    y_enabled: list[bool] = field(default_factory=lambda: [True] * 9)

    # Graph window
    window: WindowVars = field(default_factory=WindowVars)

    # Data lists L1–L6
    lists: dict[str, list[float]] = field(
        default_factory=lambda: {f'L{i}': [] for i in range(1, 7)}
    )

    # Variable store A–Z + ANS + theta
    vars: dict[str, float] = field(
        default_factory=lambda: {
            **{chr(c): 0.0 for c in range(ord('A'), ord('Z') + 1)},
            'ANS': 0.0,
            'theta': 0.0,
        }
    )

    # Mode flags
    angle_mode:   str = 'RAD'    # 'RAD' | 'DEG'
    display_mode: str = 'FLOAT'  # 'FLOAT' | 'SCI' | 'ENG'
    func_type:    str = 'FUNC'   # 'FUNC' | 'POL' | 'PAR'
    float_digits: int = 9

    # Home screen history: list of (input_expr, result_str)
    history: list[tuple[str, str]] = field(default_factory=list)
    max_history: int = 50

    # Current input buffer and cursor
    input_buffer: str = ''
    cursor_pos:   int = 0

    # Trace state
    trace_fn_idx: int   = 0
    trace_x:      float = 0.0

    # Graph dirty flag
    graph_dirty: bool = True

    # Stat results
    last_reg_type: str               = ''
    reg_coeffs:    dict[str, float]  = field(default_factory=dict)
    stat1var:      dict[str, float]  = field(default_factory=dict)

    # Zoom history for ZoomPrev
    zoom_stack: list[WindowVars] = field(default_factory=list)

    def push_history(self, expr: str, result: str) -> None:
        self.history.append((expr, result))
        if len(self.history) > self.max_history:
            self.history.pop(0)
        try:
            self.vars['ANS'] = float(result)
        except (ValueError, TypeError):
            pass

    def invalidate_graph(self) -> None:
        self.graph_dirty = True

    def save_zoom(self) -> None:
        self.zoom_stack.append(copy.deepcopy(self.window))

    def restore_zoom(self) -> bool:
        if self.zoom_stack:
            self.window = self.zoom_stack.pop()
            self.invalidate_graph()
            return True
        return False
