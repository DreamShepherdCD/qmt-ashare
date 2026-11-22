# -*- coding: gbk -*-
"""QMT 参数面板注入机制验证探针 v1（只读，不含任何下单调用）

验证目标：代码里定义顶层变量 -> 策略编辑器「参数设置」面板出现同名参数项 ->
面板填值在「运行 / 回测」两种形态下都被策略读到。

判读方法（关键）：
  每个变量都有一份「代码默认值」写死在 _DEFAULTS 里。
  日志里打印的读到值若与默认值不同 => 面板注入生效。
  - init() 阶段就不同  => 注入发生在 init 之前（最理想，参数可在 init 里读）
  - init() 是默认、handlebar 里变  => 注入晚于 init（读参数必须挪到 handlebar 之后）
  - 一直不变  => 面板没生效（或面板项未被识别）

附带验证：do_back_test / barpos / ContextInfo.start,end,capital,period 的原始值。
"""

BUILD = '20261122-1900'
STRAT_TAG = 'QPROBE'
LOG_DIR = r'D:\qmt_export'

# ==================== 待验证的面板参数（顶层变量） ====================
# 请在 QMT 策略编辑器的「参数设置」面板里找这 5 个名字，逐个改成下面的目标值：
P_INT = 1          # 目标改成 7
P_FLOAT = 0.5      # 目标改成 0.25
P_STR = 'abc'      # 目标改成 xyz
P_NEG = -3         # 目标改成 -9
p_lower = 3        # 目标改成 5（小写名，验证命名规则）

_DEFAULTS = {
    'P_INT': 1,
    'P_FLOAT': 0.5,
    'P_STR': 'abc',
    'P_NEG': -3,
    'p_lower': 3,
}
_ORDER = ('P_INT', 'P_FLOAT', 'P_STR', 'P_NEG', 'p_lower')

_LOGF = None
_HB = {'n': 0, 'first': {}}


def _gv(o, name, default=None):
    """读 ContextInfo 属性（不存在则给默认）"""
    try:
        v = getattr(o, name)
    except BaseException:
        return default
    return default if v is None else v


def _g(name, default=None):
    """读全局变量（面板注入即写在这里）"""
    v = globals().get(name)
    return default if v is None else v


def _open_log():
    """新建唯一名日志文件；写不了就只输出窗口（客户端只放行新建）"""
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
            name = 'qmt_probe_%s_%s%s.log' % (BUILD.replace('-', ''), stamp,
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
    _say('LOG', '所有候选目录都写不了 -> 仅输出窗口（直接复制窗口内容即可）')


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
    _say('INIT', 'v_probe start | build=%s | do_back_test=%r | barpos=%r'
         % (BUILD, _gv(C, 'do_back_test', '<无该属性>'), _gv(C, 'barpos', '?')))
    _say('INIT', 'ContextInfo：start=%r end=%r capital=%r period=%r'
         % (_gv(C, 'start', None), _gv(C, 'end', None),
            _gv(C, 'capital', None), _gv(C, 'period', None)))
    _snapshot('init()')
    _say('INIT', '判读：上面 5 个值若与代码默认不同 => 面板注入生效；'
                 'init 阶段就不同 => 注入早于 init（参数可在 init 里读）')


def handlebar(C):
    _HB['n'] += 1
    n = _HB['n']
    if n == 1:
        _HB['first'] = dict((k, _g(k, _DEFAULTS[k])) for k in _ORDER)
        _say('BAR1', '首根 bar | barpos=%r timetag=%r'
             % (_gv(C, 'barpos', '?'), _gv(C, 'timetag', '?')))
        _snapshot('handlebar#1')
    elif n == 3:
        _snapshot('handlebar#3')
    elif n == 10:
        _snapshot('handlebar#10（与首根比对，看中途是否变化）')
        changed = [k for k in _ORDER if _g(k, _DEFAULTS[k]) != _HB['first'].get(k)]
        _say('STABLE', '与首根相比变化的变量：%s' % (changed if changed else '无'))
    elif n % 50 == 0:
        _say('ALIVE', 'handlebar #%d barpos=%r do_back_test=%r'
             % (n, _gv(C, 'barpos', '?'), _gv(C, 'do_back_test', '<无该属性>')))
