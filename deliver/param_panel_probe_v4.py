# -*- coding: gbk -*-
"""QMT 面板 vs 代码：内置参数优先级探针 v4（只读，无下单调用）

背景：自定义参数无法经面板下发（v1–v3 已证），所以参数只能写在代码里（PRESET 块）。
但界面上的 4 个「内置参数」与代码里的常量语义重叠，必须先搞清谁说了算：
    period（K 线周期）  <->  代码 SIGNAL_PERIOD
    start / end（回测区间）<-> 代码 BT_START / BT_END
    capital（初始资金）  <->  代码 CAPITAL / 自建账本口径

做法：init 里把 4 项都设成【一眼能区分】的代码值，看首几根 bar 实际用的是什么：
    代码值：start=2024-01-02  end=2024-01-10  period='1d'  capital=500000

判读（看 INIT 后的 SET 行 + 前 3 根 BAR 行）：
  * BAR 行 start/end = 2024-01-02~01-10 且 bar 间隔 86400s  => 代码赢
  * BAR 行 start/end = 面板区间        且 bar 间隔 60s      => 面板赢
  * 逐项混着 => 按项分别记录（这就是要的优先级矩阵）

请在跑之前把右侧回测参数面板设成便于区分的一组，例如：
    周期 1m、起始 2026-11-13、结束 2026-11-19、资金 1000000
"""

BUILD = '20261122-2010'
STRAT_TAG = 'QPROBE4'
LOG_DIR = r'D:\qmt_export'

# 代码侧「故意写得不等于面板」的值
CODE_START = '2024-01-02'
CODE_END = '2024-01-10'
CODE_PERIOD = '1d'
CODE_CAPITAL = 500000

_LOGF = None
_HB = {'n': 0, 'prev': None, 'deltas': []}


def _gv(o, name, default=None):
    try:
        v = getattr(o, name)
    except BaseException:
        return default
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
            name = 'qmt_probe4_%s_%s%s.log' % (BUILD.replace('-', ''), stamp,
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
    _say('LOG', '日志目录都写不了 -> 仅输出窗口')


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


def _dt(ms):
    try:
        import datetime
        return datetime.datetime.fromtimestamp(float(ms) / 1000.0).strftime('%Y-%m-%d %H:%M:%S')
    except BaseException:
        return '<conv err>'


def init(C):
    _open_log()
    _say('INIT', 'v_probe4 | do_back_test=%r' % (_gv(C, 'do_back_test', '<无>'),))
    _say('PANEL@INIT', 'start=%r end=%r period=%r periodName=%r capital=%r'
         % (_gv(C, 'start', None), _gv(C, 'end', None), _gv(C, 'period', None),
            _gv(C, 'periodName', None), _gv(C, 'capital', None)))
    for k, v in (('start', CODE_START), ('end', CODE_END),
                 ('period', CODE_PERIOD), ('capital', CODE_CAPITAL)):
        try:
            setattr(C, k, v)
            res = 'ok'
        except BaseException as e:
            res = '%s: %s' % (type(e).__name__, str(e)[:40])
        _say('SET', 'C.%s <- %r => %s | 读回=%r' % (k, v, res, getattr(C, k, '<无>')))
    _say('SET', '说明：SET 行只证明「赋值不报错」，真生效与否看下面 BAR 行的实际值')


def handlebar(C):
    _HB['n'] += 1
    n = _HB['n']
    tt = _gv(C, 'get_bar_timetag', None)
    try:
        tag = C.get_bar_timetag(C.barpos)
    except BaseException:
        tag = _gv(C, 'timetag', None)
    delta = None
    if tag is not None and _HB['prev'] is not None:
        try:
            delta = float(tag) - float(_HB['prev'])
            _HB['deltas'].append(delta)
        except BaseException:
            delta = None
    if tag is not None:
        _HB['prev'] = tag
    if n <= 3:
        _say('BAR', '#%d barpos=%r tag=%r dt=%s 间隔秒=%r | start=%r end=%r period=%r capital=%r'
             % (n, _gv(C, 'barpos', '?'), tag, _dt(tag) if tag else '?', delta,
                _gv(C, 'start', None), _gv(C, 'end', None),
                _gv(C, 'period', None), _gv(C, 'capital', None)))
    elif n == 10:
        ds = [d for d in _HB['deltas'] if d]
        ds.sort()
        med = ds[len(ds) // 2] if ds else None
        _say('SUM', '前 9 个间隔中位=%r 秒（86400≈日线 / 60≈1分钟 / 300≈5分钟；-1 或 0 = 休市跨夜）'
             % (med,))
        _say('SUM', '判读：BAR 行 start/end=2024-01-02~01-10 + 间隔 86400 => 代码赢；'
                    '= 面板区间 + 间隔 60 => 面板赢；逐项不同 => 按项记矩阵')
