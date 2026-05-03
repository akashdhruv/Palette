from __future__ import annotations
import re
import math
from typing import Union, Optional

import sympy as sp
import numpy as np

from graph.state import CalcState


# ---------------------------------------------------------------------------
# Expression preprocessing pipeline
# ---------------------------------------------------------------------------

def substitute_ans(expr: str, state: CalcState) -> str:
    return re.sub(r'\bANS\b', str(state.vars['ANS']), expr)


def substitute_vars(expr: str, state: CalcState) -> str:
    def replacer(m: re.Match) -> str:
        name = m.group(0)
        return str(state.vars.get(name, 0.0))
    return re.sub(r'\b[A-Z]\b', replacer, expr)


_IMPL_MUL: list[tuple[re.Pattern, str]] = [
    (re.compile(r'(\d)([A-Za-z(])'),  r'\1*\2'),  # 2x, 2(, 2sin
    (re.compile(r'(\))(\()'),          r'\1*\2'),  # )( → )*(
    (re.compile(r'\)(\d)'),            r')*\1'),   # )2 → )*2
]


def implicit_multiply(expr: str) -> str:
    for pattern, repl in _IMPL_MUL:
        expr = pattern.sub(repl, expr)
    return expr


def caret_to_pow(expr: str) -> str:
    return expr.replace('^', '**')


_TRIG_FUNCS = ('sin', 'cos', 'tan', 'asin', 'acos', 'atan',
               'sinh', 'cosh', 'tanh')


def _find_matching_paren(s: str, open_pos: int) -> int:
    depth = 0
    for i in range(open_pos, len(s)):
        if s[i] == '(':
            depth += 1
        elif s[i] == ')':
            depth -= 1
            if depth == 0:
                return i
    return len(s) - 1


def _wrap_trig_args(expr: str, fn_name: str) -> str:
    result = []
    i = 0
    pat = fn_name + '('
    while i < len(expr):
        idx = expr.find(pat, i)
        if idx == -1:
            result.append(expr[i:])
            break
        # Ensure it's a whole-word match (not e.g. 'arcsin')
        if idx > 0 and expr[idx - 1].isalpha():
            result.append(expr[i:idx + len(pat)])
            i = idx + len(pat)
            continue
        close = _find_matching_paren(expr, idx + len(fn_name))
        inner = expr[idx + len(fn_name) + 1: close]
        result.append(expr[i:idx + len(fn_name) + 1])  # fn_name + '('
        result.append(f'(3.141592653589793/180)*({inner})')
        result.append(')')
        i = close + 1
    return ''.join(result)


def degree_wrap(expr: str, state: CalcState) -> str:
    if state.angle_mode != 'DEG':
        return expr
    for fn in _TRIG_FUNCS:
        expr = _wrap_trig_args(expr, fn)
    return expr


def preprocess_expr(raw: str, state: CalcState) -> str:
    expr = raw.strip()
    expr = substitute_ans(expr, state)
    expr = implicit_multiply(expr)   # must run before substitute_vars so 2X→2*X first
    expr = substitute_vars(expr, state)
    expr = caret_to_pow(expr)
    expr = degree_wrap(expr, state)
    return expr


# ---------------------------------------------------------------------------
# SymPy evaluation namespace
# ---------------------------------------------------------------------------

_SYMPY_NS: dict = {
    'sin': sp.sin, 'cos': sp.cos, 'tan': sp.tan,
    'asin': sp.asin, 'acos': sp.acos, 'atan': sp.atan, 'atan2': sp.atan2,
    'sinh': sp.sinh, 'cosh': sp.cosh, 'tanh': sp.tanh,
    'asinh': sp.asinh, 'acosh': sp.acosh, 'atanh': sp.atanh,
    'sqrt': sp.sqrt, 'log': sp.log, 'ln': sp.log, 'exp': sp.exp,
    'abs': sp.Abs, 'pi': sp.pi, 'e': sp.E, 'E': sp.E,
    'factorial': sp.factorial,
    'floor': sp.floor, 'ceiling': sp.ceiling, 'ceil': sp.ceiling,
    'nCr': lambda n, r: sp.binomial(n, r),
    'nPr': lambda n, r: sp.factorial(n) // sp.factorial(n - r),
    'round': lambda x, d=0: sp.Float(round(float(x), int(d))),
    'iPart': lambda x: sp.Integer(int(float(x))),
    'fPart': lambda x: x - sp.Integer(int(float(x))),
    'rand': lambda: sp.Float(__import__('random').random()),
    'gcd': sp.gcd, 'lcm': sp.lcm,
    'det': lambda m: m.det(),
    'I': sp.I,
}


class EvalResult:
    __slots__ = ('value', 'display', 'error')

    def __init__(
        self,
        value: Union[float, complex, None],
        display: str,
        error: str = '',
    ) -> None:
        self.value   = value
        self.display = display
        self.error   = error


def format_number(val: float, state: CalcState) -> str:
    mode   = state.display_mode
    digits = state.float_digits
    if mode == 'SCI':
        return f'{val:.{max(1, digits - 1)}E}'
    elif mode == 'ENG':
        return _format_eng(val, digits)
    else:  # FLOAT
        if val == 0:
            return '0'
        if val == int(val) and abs(val) < 1e10:
            return str(int(val))
        return f'{val:.{digits}G}'


def _format_eng(val: float, digits: int) -> str:
    if val == 0:
        return '0'
    exp = int(math.floor(math.log10(abs(val))))
    eng_exp = (exp // 3) * 3
    mantissa = val / (10 ** eng_exp)
    return f'{mantissa:.{max(1, digits - 1)}f}E{eng_exp:+d}'


def evaluate(raw: str, state: CalcState) -> EvalResult:
    if not raw.strip():
        return EvalResult(None, '', '')
    try:
        processed = preprocess_expr(raw, state)
        sym_expr  = sp.parse_expr(processed, local_dict=_SYMPY_NS)
        numeric   = complex(sym_expr.evalf(15))
    except ZeroDivisionError:
        return EvalResult(None, 'ERR:DIV/0', 'Division by zero')
    except (sp.SympifyError, SyntaxError, TypeError, ValueError) as exc:
        return EvalResult(None, 'ERR:SYNTAX', str(exc))
    except Exception as exc:
        return EvalResult(None, f'ERR:{str(exc)[:20]}', str(exc))

    if abs(numeric.imag) < 1e-10:
        val     = numeric.real
        display = format_number(val, state)
        return EvalResult(val, display)
    else:
        re_s = format_number(numeric.real, state)
        im_s = format_number(abs(numeric.imag), state)
        sign = '+' if numeric.imag >= 0 else '-'
        display = f'{re_s}{sign}{im_s}i'
        return EvalResult(numeric, display)


# ---------------------------------------------------------------------------
# Fast numpy evaluator for graphing
# ---------------------------------------------------------------------------

_NP_NS: dict = {
    'np': np,
    'sin': np.sin, 'cos': np.cos, 'tan': np.tan,
    'asin': np.arcsin, 'acos': np.arccos, 'atan': np.arctan,
    'sinh': np.sinh, 'cosh': np.cosh, 'tanh': np.tanh,
    'sqrt': np.sqrt, 'log': np.log, 'ln': np.log, 'exp': np.exp,
    'abs': np.abs, 'pi': np.pi, 'e': np.e,
    'floor': np.floor, 'ceil': np.ceil, 'ceiling': np.ceil,
    'factorial': np.vectorize(math.factorial),
}


def make_numpy_func(expr_str: str, state: CalcState):
    if not expr_str.strip():
        return None
    try:
        processed = preprocess_expr(expr_str, state)
        # Replace sympy-only constructs with numpy equivalents
        processed = processed.replace('**', '**')  # already fine
        code = compile(f'_y = {processed}', '<graph>', 'exec')

        def evaluator(x: np.ndarray) -> np.ndarray:
            local_ns = {**_NP_NS, 'x': x}
            exec(code, local_ns)  # noqa: S102
            result = local_ns['_y']
            if np.isscalar(result):
                return np.full_like(x, float(result))
            return np.asarray(result, dtype=float)

        return evaluator
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    from graph.state import CalcState
    s = CalcState()
    tests = [
        ('sin(pi/2)', '1'),
        ('2^10', '1024'),
        ('sqrt(2)', '1.41421356'),
        ('2X', None),         # needs X set
        ('ANS+1', None),
        ('nCr(5,2)', '10'),
    ]
    s.vars['X'] = 3.0
    s.vars['ANS'] = 7.0
    for expr, expected in tests:
        r = evaluate(expr, s)
        status = 'OK' if not r.error else 'ERR'
        print(f'[{status}] {expr!r:20s} → {r.display!r}')
