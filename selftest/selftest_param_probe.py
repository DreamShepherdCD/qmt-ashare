# -*- coding: utf-8 -*-
"""param_panel_probe_v1 的本地自测（不依赖 QMT）

验证三件事：
  1) 未注入面板值时，探针读到的是代码默认值
  2) 「面板注入」= 改写模块全局变量，探针能识别出「与默认不同」
  3) handlebar 多次调用之间值稳定（不会中途变）

用法：python3 selftest/selftest_param_probe.py
"""
import io
import os
import sys
import types
import contextlib

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(os.path.dirname(HERE), 'probes', 'param_panel_probe_v1.py')


class Ctx(object):
    """模拟 QMT 的 ContextInfo"""

    def __init__(self, **kw):
        self.do_back_test = True
        self.barpos = 0
        self.timetag = 1794533400000
        self.start = '2026-11-13 09:30:00'
        self.end = '2026-11-13 15:00:00'
        self.capital = 1000000
        self.period = '1m'
        for k, v in kw.items():
            setattr(self, k, v)


def load_module(log_dir=''):
    """把探针源码装进独立模块对象（globals 与真实运行一致）"""
    mod = types.ModuleType('probe_under_test')
    src = open(SRC, encoding='utf-8').read()
    src = src.replace("LOG_DIR = r'D:\\qmt_export'", "LOG_DIR = r'%s'" % log_dir)
    exec(compile(src, SRC, 'exec'), mod.__dict__)
    return mod


def run(mod, ctx, bars=10):
    """跑 init + N 根 handlebar，返回全部输出行"""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        mod.init(ctx)
        for _ in range(bars):
            ctx.barpos += 1
            mod.handlebar(ctx)
    return buf.getvalue()


def check(name, cond, detail=''):
    status = 'PASS' if cond else 'FAIL'
    print('[%s] %s%s' % (status, name, ('  ' + detail) if detail and not cond else ''))
    return cond


def main():
    ok = 0
    total = 0

    # --- 1) 无注入：全部等于默认 ---
    mod = load_module()
    out = run(mod, Ctx())
    total += 1
    ok += check('无注入时读到代码默认值',
                'P_INT=1(int)' in out and 'P_FLOAT=0.5(float)' in out
                and "P_STR='abc'(str)" in out and 'P_NEG=-3(int)' in out)

    total += 1
    ok += check('无注入时不出现「与默认不同」', '与默认不同' not in out)

    # --- 2) 模拟面板注入：改写模块全局变量 ---
    mod = load_module()
    ctx = Ctx()
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        mod.init(ctx)                     # 注入前先跑 init（模拟「注入晚于 init」）
        mod.P_INT = 7                     # <- 模拟面板写入
        mod.P_FLOAT = 0.25
        mod.P_STR = 'xyz'
        mod.P_NEG = -9
        mod.p_lower = 5
        for _ in range(10):
            ctx.barpos += 1
            mod.handlebar(ctx)
    out = buf.getvalue()
    total += 1
    ok += check('init 阶段仍是默认值（注入晚于 init 的情形）',
                'P_INT=1(int)' in out)

    total += 1
    ok += check('handlebar 阶段识别到注入（int）', 'P_INT=7(int)' in out)
    total += 1
    ok += check('handlebar 阶段识别到注入（float）', 'P_FLOAT=0.25(float)' in out)
    total += 1
    ok += check('handlebar 阶段识别到注入（str）', "P_STR='xyz'(str)" in out)
    total += 1
    ok += check('handlebar 阶段识别到注入（负数）', 'P_NEG=-9(int)' in out)
    total += 1
    ok += check('handlebar 阶段识别到注入（小写名）', 'p_lower=5(int)' in out)

    # --- 3) 多根 bar 之间稳定 ---
    total += 1
    ok += check('多次 handlebar 之间值稳定', '与首根相比变化的变量：无' in out)

    # --- 4) 字符串型注入（面板可能注入 str 而非 int）---
    mod = load_module()
    ctx = Ctx()
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        mod.init(ctx)
        mod.P_INT = '7'                   # 面板可能给字符串
        mod.handlebar(ctx)
    out = buf.getvalue()
    total += 1
    ok += check('字符串型注入能被识别并暴露类型', "P_INT='7'(str)" in out)

    # --- 5) do_back_test / 区间原样输出 ---
    total += 1
    ok += check('打印 do_back_test 与回测区间',
                'do_back_test=True' in out and 'start=' in out)

    print('\n结果：%d/%d passed' % (ok, total))
    return 0 if ok == total else 1


if __name__ == '__main__':
    sys.exit(main())
