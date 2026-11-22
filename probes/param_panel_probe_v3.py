# -*- coding: gbk -*-
"""QMT 参数机制探针 v3（只读，无 passorder）——一次跑完定两件事

v1 结论：面板值没进来（5 个变量全程 = 代码默认）。
用户实测：右侧「参数设置」面板**看不到**代码里的顶层变量 => 「顶层变量自动生成面板项」不成立。

v3 只验剩下的两条路：
  A. 手动在「参数设置」面板加行（名称/值），是否被下发？
     - 下发到 globals（模块执行前预置）=> BOOT 行会列出该变量
     - 下发到 ContextInfo 属性        => CI 行会显示值
     - 都没有                          => 面板这条路彻底不通
  B. 策略能不能【读】已存在的文件（决定「参数放外部文件」是否可行）
     - 同时打印 os.getcwd()，即策略运行目录（放参数文件的位置）

请在跑之前：到右侧「参数设置」面板试试手工新增两行
    名称 P_INT      值 7
    名称 MAX_TOTAL  值 3
（若面板根本没有新增/编辑入口，直接跑，A 也可判死）
"""

# ===== 必须在任何赋值之前执行 =====
try:
    _BOOT_KEYS = sorted(list(globals().keys()))
except BaseException:
    _BOOT_KEYS = ['<err>']

_WATCH = ('P_INT', 'P_FLOAT', 'P_STR', 'MAX_TOTAL')
try:
    _BOOT = {}
    for _k in _WATCH:
        if _k in globals():
            _BOOT[_k] = globals()[_k]
except BaseException:
    _BOOT = {'<err>': True}
del _k

BUILD = '20261122-1950'
STRAT_TAG = 'QPROBE3'
LOG_DIR = r'D:\qmt_export'

P_INT = 1
P_FLOAT = 0.5
P_STR = 'abc'
MAX_TOTAL = 6

_DEFAULTS = {'P_INT': 1, 'P_FLOAT': 0.5, 'P_STR': 'abc', 'MAX_TOTAL': 6}
_ORDER = _WATCH

_LOGF = None


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
            name = 'qmt_probe3_%s_%s%s.log' % (BUILD.replace('-', ''), stamp,
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
        parts.append('%s=%r%s' % (k, v, '' if same else '  <== 非默认'))
    _say('VAL', '%s | %s' % (where, ' | '.join(parts)))


def _read_test():
    """B 路：能否读取已存在的文件（决定外部参数文件是否可行）"""
    import os
    out = []
    try:
        cwd = os.getcwd()
    except BaseException:
        cwd = '<err>'
    out.append('cwd=%s' % cwd)
    cands = []
    for d in (LOG_DIR, cwd, os.path.join(cwd, 'python')):
        try:
            n = 0
            for fn in os.listdir(d):
                n += 1
                if n > 300:
                    break
                low = fn.lower()
                if low.endswith('.log') or low.endswith('.json') or low.endswith('.csv'):
                    cands.append(os.path.join(d, fn))
        except BaseException:
            pass
    if not cands:
        out.append('读取测试: 没找到可试的旧文件（未判定）')
    for p in cands[:3]:
        try:
            f = open(p, 'r', encoding='utf-8-sig')
            head = f.readline()[:40]
            f.close()
            out.append('读取成功: %s -> %r' % (os.path.basename(p), head))
        except BaseException as e:
            out.append('读取失败: %s -> %s: %s' % (os.path.basename(p),
                                                 type(e).__name__, str(e)[:60]))
    # 新建文件能否回读（同进程内）
    try:
        import time
        tp = os.path.join(LOG_DIR or cwd, 'qmt_probe3_self_%s.txt' % time.strftime('%H%M%S'))
        f = open(tp, 'w')
        f.write('hello\n')
        f.close()
        f = open(tp, 'r')
        back = f.readline().strip()
        f.close()
        out.append('自建回读: OK(%r)' % back)
    except BaseException as e:
        out.append('自建回读: %s: %s' % (type(e).__name__, str(e)[:60]))
    _say('FILE', ' | '.join(out))


def init(C):
    _open_log()
    _say('INIT', 'v_probe3 | build=%s | do_back_test=%r | capital=%r period=%r start=%r end=%r'
         % (BUILD, _gv(C, 'do_back_test', '<无>'), _gv(C, 'capital', None),
            _gv(C, 'period', None), _gv(C, 'start', None), _gv(C, 'end', None)))

    hit = [k for k in _WATCH if k in _BOOT_KEYS]
    _say('BOOT', '入口 globals 键数=%d | 命中目标变量=%s | 预置值=%r'
         % (len(_BOOT_KEYS), hit if hit else '无', _BOOT if _BOOT else '无'))

    ci = []
    for k in _WATCH:
        ci.append('%s=%r' % (k, getattr(C, k, '<无该属性>')))
    for cand in ('param', 'params', 'strategyParam', 'strategy_param', 'inputs'):
        try:
            if hasattr(C, cand):
                ci.append('%s=%r' % (cand, getattr(C, cand, None)))
        except BaseException:
            pass
    _say('CI', ' | '.join(ci))

    _read_test()
    _snapshot('init()')


def handlebar(C):
    global _HB_N
    try:
        _HB_N += 1
    except BaseException:
        _HB_N = 1
    n = _HB_N
    if n == 1:
        _say('BAR1', 'barpos=%r start=%r end=%r' % (_gv(C, 'barpos', '?'),
                                                   _gv(C, 'start', None), _gv(C, 'end', None)))
        _snapshot('handlebar#1')
        _say('SUM', '判读：BOOT 命中 / CI 有值 => 面板可下发；两者皆无 => 面板路线不通（改用代码常量或文件）')
    elif n == 200:
        _say('ALIVE', 'handlebar #200 barpos=%r' % (_gv(C, 'barpos', '?'),))
