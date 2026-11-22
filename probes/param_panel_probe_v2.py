# -*- coding: gbk -*-
"""QMT 参数面板注入机制验证探针 v2（只读，不含任何下单调用）

v1 的结论：面板值没进来（5 个变量全程等于代码默认，且类型未变）。
v2 用来定因，重点区分两种机制：

  H1「面板预置 globals，被代码顶掉」
     面板在【模块执行之前】就把 P_INT 等写进 globals，
     而本文件紧接着的 `P_INT = 1` 又把它覆盖掉 => 永远读到默认值。
     判据：_BOOT_KEYS 里出现 P_INT 等名字（或 _BOOT 有非默认值）。

  H2「面板根本不下发自定义变量」
     判据：_BOOT_KEYS 只有 __name__/__doc__ 之类；ContextInfo 上也找不到参数容器。

另外顺带记录：ContextInfo 的全部属性名、可能的参数容器（param/params/...）、
start/end 在 init 与首根 bar 时的原始值。
"""

# ===== 必须在任何赋值之前执行：抓「面板预置」快照 =====
try:
    _BOOT_KEYS = sorted(list(globals().keys()))
except BaseException:
    _BOOT_KEYS = ['<snapshot failed>']

_WATCH = ('P_INT', 'P_FLOAT', 'P_STR', 'P_NEG', 'p_lower')
try:
    _BOOT = {}
    for _k in _WATCH:
        if _k in globals():
            _BOOT[_k] = globals()[_k]
except BaseException:
    _BOOT = {'<snapshot failed>': True}
del _k

BUILD = '20261122-1930'
STRAT_TAG = 'QPROBE2'
LOG_DIR = r'D:\qmt_export'

# ==================== 待验证的面板参数（顶层变量） ====================
P_INT = 1          # 目标改成 7
P_FLOAT = 0.5      # 目标改成 0.25
P_STR = 'abc'      # 目标改成 xyz
P_NEG = -3         # 目标改成 -9
p_lower = 3        # 目标改成 5

_DEFAULTS = {
    'P_INT': 1,
    'P_FLOAT': 0.5,
    'P_STR': 'abc',
    'P_NEG': -3,
    'p_lower': 3,
}
_ORDER = _WATCH

_LOGF = None
_HB = {'n': 0, 'first': {}}


def _gv(o, name, default=None):
    try:
        v = getattr(o, name)
    except BaseException:
        return default
    return default if v is None else v


def _g(name, default=None):
    v = globals().get(name)
    return default if v is None else v


def _open_log():
    global _LOGF
    import os
    import time
    if not LOG_DIR:
        return
    stamp = time.strftime('%Y%m%d_%H%M%S')
    bases = [LOG_DIR]
    for k in ('USERPROFILE', 'TEMP', 'TMP'):
        v = os.environ.get(k, '')
        if v:
            bases.append(os.path.join(v, 'qmt_probe'))
    bases.append('C:\\Windows\\Temp\\qmt_probe')
    for d in bases:
        try:
            os.makedirs(d, exist_ok=True)
        except BaseException:
            pass
        for i in range(1, 30):
            name = 'qmt_probe2_%s_%s%s.log' % (BUILD.replace('-', ''), stamp,
                                              '' if i == 1 else '_%d' % i)
            p = os.path.join(d, name)
            try:
                if os.path.exists(p):
                    continue
            except BaseException:
                pass
            for enc in ('utf-8-sig', 'gbk', None):
                try:
                    f = open(p, 'w', encoding=enc) if enc else open(p, 'w')
                    _LOGF = f
                    _say('LOG', '日志落盘 -> %s' % p)
                    return
                except BaseException:
                    _LOGF = None
    _say('LOG', '所有候选目录都写不了 -> 仅输出窗口')


def _say(tag, msg):
    line = '[%s][%s] %s' % (STRAT_TAG, tag, msg)
    try:
        print(line, flush=True)
    except BaseException:
        print(line)
    if _LOGF is not None:
        try:
            _LOGF.write(line + '\n')
            _LOGF.flush()
        except BaseException:
            pass


def _snapshot(where):
    parts = []
    for k in _ORDER:
        d = _DEFAULTS[k]
        v = _g(k, d)
        same = (v == d) and (type(v) == type(d))
        parts.append('%s=%r(%s)%s' % (k, v, type(v).__name__,
                                      '' if same else '  <== 与默认不同'))
    _say('VAL', '%s | %s' % (where, ' | '.join(parts)))


def init(C):
    _open_log()
    _say('INIT', 'v_probe2 start | build=%s | do_back_test=%r | barpos=%r | cls=%s'
         % (BUILD, _gv(C, 'do_back_test', '<无>'), _gv(C, 'barpos', '?'),
            type(C).__name__))

    # ---- 决定性证据 1：模块执行前 globals 里有没有面板预置的参数 ----
    _say('BOOT', '模块入口 globals 键(%d): %s' % (len(_BOOT_KEYS), ', '.join(_BOOT_KEYS)))
    if _BOOT:
        _say('BOOT', '入口已存在的参数变量（面板预置？）: %r' % (_BOOT,))
    else:
        _say('BOOT', '入口不存在任何目标参数变量 => 面板未在模块执行前预置')

    # ---- 决定性证据 2：ContextInfo 上有没有参数容器 ----
    for cand in ('param', 'params', 'strategyParam', 'strategy_param',
                 'inputs', 'variables', 'args', 'kwargs'):
        try:
            has = hasattr(C, cand)
        except BaseException:
            has = '<err>'
        _say('CI', '%s 存在=%r 值=%r' % (cand, has, getattr(C, cand, '<无>')))

    try:
        names = [n for n in dir(C) if not n.startswith('_')]
    except BaseException:
        names = []
    _say('DIR', 'ContextInfo 属性(%d): %s' % (len(names), ', '.join(names)))
    for k in _WATCH:
        _say('CI', 'ContextInfo.%s = %r' % (k, getattr(C, k, '<无该属性>')))

    _say('INIT', 'ContextInfo：start=%r end=%r capital=%r period=%r periodname=%r'
         % (_gv(C, 'start', None), _gv(C, 'end', None), _gv(C, 'capital', None),
            _gv(C, 'period', None), _gv(C, 'periodName', None)))
    _snapshot('init()')


def handlebar(C):
    _HB['n'] += 1
    n = _HB['n']
    if n == 1:
        _HB['first'] = dict((k, _g(k, _DEFAULTS[k])) for k in _ORDER)
        _say('BAR1', '首根 bar | barpos=%r | start=%r end=%r'
             % (_gv(C, 'barpos', '?'), _gv(C, 'start', None), _gv(C, 'end', None)))
        _snapshot('handlebar#1')
        _say('BAR1', '注意：本行之后的值若与 init 相同，说明整个生命周期都没有注入')
    elif n == 3:
        _snapshot('handlebar#3')
    elif n == 10:
        _snapshot('handlebar#10')
        changed = [k for k in _ORDER if _g(k, _DEFAULTS[k]) != _HB['first'].get(k)]
        _say('STABLE', '与首根相比变化的变量：%s' % (changed if changed else '无'))
        _say('SUM', '最终判定见 BOOT 行：有目标变量 = H1(预置被覆盖)，无 = H2(未下发)')
    elif n % 200 == 0:
        _say('ALIVE', 'handlebar #%d barpos=%r' % (n, _gv(C, 'barpos', '?')))
