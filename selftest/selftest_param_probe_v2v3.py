# -*- coding: utf-8 -*-
"""param_panel_probe_v2 / v3 的本地自测（不依赖 QMT）

覆盖：
  v2 —— 预置 globals 时能识别（BOOT 命中）、无预置时判为「未下发」、ContextInfo 容器打印
  v3 —— 无预置判定、读取已存在文件成功、自建文件回读成功、预置场景命中

用法：python3 selftest/selftest_param_probe_v2v3.py
"""
import contextlib
import io
import os
import sys
import tempfile
import types

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


class Ctx(object):
    def __init__(self):
        self.do_back_test = True
        self.barpos = 0
        self.start = '-1'
        self.end = '-1'
        self.capital = 1000000.0
        self.period = '1d'
        self.param = {'P_INT': 7}


def load(name, log_dir=''):
    """装载探针源码为独立模块；允许注入预置 globals 以模拟面板下发"""
    path = os.path.join(ROOT, 'probes', name)
    src = open(path, encoding='utf-8').read()
    src = src.replace("LOG_DIR = r'D:\\qmt_export'", "LOG_DIR = r'%s'" % log_dir)
    return src


def mk(src, preseed=None):
    mod = types.ModuleType('probe')
    if preseed:
        mod.__dict__.update(preseed)
    exec(compile(src, 'probe', 'exec'), mod.__dict__)
    return mod


def run(mod, bars=2):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        ctx = Ctx()
        mod.init(ctx)
        for _ in range(bars):
            ctx.barpos += 1
            mod.handlebar(ctx)
    return buf.getvalue()


def check(name, cond):
    print('[%s] %s' % ('PASS' if cond else 'FAIL', name))
    return 1 if cond else 0


def main():
    ok = total = 0
    tmp = tempfile.mkdtemp()
    old = os.path.join(tmp, 'qmt_probe_old_20261122.log')
    open(old, 'w').write('===== old head =====\n')

    # ---------- v2 ----------
    src2 = load('param_panel_probe_v2.py', tmp)
    out = run(mk(src2))
    total += 1
    ok += check('v2 无预置 -> 判为未下发', '入口不存在任何目标参数变量' in out)
    total += 1
    ok += check('v2 无预置 -> 值全为默认', ['P_INT=1(int)' in out][0])

    out = run(mk(src2, {'P_INT': 7, 'P_FLOAT': 0.25, 'P_STR': 'xyz',
                        'P_NEG': -9, 'p_lower': 5}))
    total += 1
    ok += check('v2 预置 -> BOOT 命中', '入口已存在的参数变量' in out)
    total += 1
    ok += check('v2 复现「预置被代码默认覆盖」', 'P_INT=1(int)' in out)

    # ---------- v3 ----------
    src3 = load('param_panel_probe_v3.py', tmp)
    out = run(mk(src3))
    total += 1
    ok += check('v3 无预置 -> 命中目标变量=无', '命中目标变量=无' in out)
    total += 1
    ok += check('v3 能读到已存在文件', '读取成功: qmt_probe_old_20261122.log' in out)
    total += 1
    ok += check('v3 自建文件可回读', '自建回读: OK' in out)
    total += 1
    ok += check('v3 打印 cwd 与 ContextInfo 关键值',
                'cwd=' in out and 'do_back_test=True' in out)

    out = run(mk(src3, {'P_INT': 7, 'MAX_TOTAL': 3}))
    total += 1
    ok += check('v3 预置 -> 命中两个变量',
                "命中目标变量=['P_INT', 'MAX_TOTAL']" in out)

    print('\n结果：%d/%d passed' % (ok, total))
    return 0 if ok == total else 1


if __name__ == '__main__':
    sys.exit(main())
