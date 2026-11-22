# -*- coding: utf-8 -*-
"""v5_6 自测：预设档 / G2 权利金门 / 强平取价与重试 / min_dte 互斥
（含 v5_5 M1/M2/M3、v5_4 C 浪门、v5_3 A/B 回归，不依赖 QMT）

运行：python3 qmt/selftest/selftest_v5_6.py
"""
import sys
import io

import os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # qmt/
for _p in (ROOT, os.path.join(ROOT, 'archive')):
    sys.path.insert(0, _p)


def _src(name):
    """取源码文本：当前版本在 qmt/、历史版本在 qmt/archive/"""
    for _base in (ROOT, os.path.join(ROOT, 'archive')):
        _p = os.path.join(_base, name)
        if os.path.exists(_p):
            return io.open(_p, encoding='utf-8').read()
    raise SystemExit('source not found: %s' % name)


import ashare_put_v5_6 as M  # noqa: E402

ORIG_UNREAL = M._bt_unreal
SRC = _src('ashare_put_v5_6.py')

lines = []
errors = []


def _log(tag, msg, key=None, force=False):
    lines.append((tag, msg, key))


def check(name, cond, detail=''):
    if cond:
        print('[OK] %s' % name)
    else:
        errors.append(name)
        print('[FAIL] %s %s' % (name, detail))


def reset(bar=1):
    lines[:] = []
    M._log = _log
    M._noise_flush = lambda tag='NOISE': None
    M._BT.update({'on': True, 'closed': 0, 'ymd': 20261113, 'hm': 930, 'eod_done': 0})
    M.S.in_bt = 1
    M.S.bt = M._new_bt()
    M.S.bt['bar'] = bar
    M._account = lambda C=None: {'avail': 1.0e6, 'balance': 1000797.90, 'margin': 0.0}
    M._positions = lambda C=None: []
    M._bt_unreal = lambda C=None: (0.0, [])


# ==================== M1：TD 计数按交易日切分 ====================
# 单调下跌 20 根：无切分时计数一路累加（out[19]=16）
closes = [10.0 - 0.01 * i for i in range(20)]
cnt_off = M.setup_counts(closes, 4)
check('M1-1 无 days 时保持旧口径（跨日累加）',
      cnt_off[4] == 1 and cnt_off[19] == 16, str(cnt_off[:8]) + '...' + str(cnt_off[19]))

days = ['20261113'] * 12 + ['20261116'] * 8
cnt_on = M.setup_counts(closes, 4, days)
check('M1-2 换日首 4 根无法形成段内比较窗口 → 0',
      cnt_on[12] == 0 and cnt_on[13] == 0 and cnt_on[14] == 0 and cnt_on[15] == 0,
      str(cnt_on[10:20]))
check('M1-3 换日后从段内第 5 根重新起数（不继承昨日）',
      cnt_on[16] == 1 and cnt_on[19] == 4, str(cnt_on[10:20]))
check('M1-4 同一交易日内不变（等价旧口径）',
      cnt_on[:12] == cnt_off[:12], str(cnt_on[:12]))

# 隔夜跳空场景：昨日已数到 8，今日开盘继续跌 —— 切分后必须重新起数
closes2 = [10.0 - 0.01 * i for i in range(12)] + [9.5 - 0.01 * i for i in range(8)]
days2 = ['20261113'] * 12 + ['20261116'] * 8
off2 = M.setup_counts(closes2, 4)
on2 = M.setup_counts(closes2, 4, days2)
check('M1-5 隔夜跳空：旧口径会把昨日计数带进今日',
      off2[12] >= 9 and on2[12] == 0, 'off=%d on=%d' % (off2[12], on2[12]))
check('M1-6 切分后同日不会因隔夜跳空提前触发 9',
      max(on2[12:]) < 9, str(on2[12:]))
check('M1-7 Sell 计数同口径（预留函数也接了 days）',
      M.sell_setup_counts(closes, 4, days)[19] == 0 and M.sell_setup_counts(closes, 4)[19] == 0)

check('M1-8 日内周期切分、日线以上不切',
      M.session_split_enabled('1m') and M.session_split_enabled('5m')
      and not M.session_split_enabled('1d') and not M.session_split_enabled('1D')
      and not M.session_split_enabled('1w'), '')

i_days = SRC.find("days = [str(b.get('t', ''))[:8] for b in bars]")
i_counts = SRC.find('counts = setup_counts(closes, cmp_len, days)')
check('M1-9 _try_entry 已接线（构造 days 并传入 setup_counts）',
      0 < i_days < i_counts, 'i_days=%d i_counts=%d' % (i_days, i_counts))
check('M1-10 切分可用 SESSION_SPLIT 关闭（对照旧口径）',
      M.SESSION_SPLIT == 1 and 'SESSION_SPLIT' in SRC)
check('M1-11 INIT 打生效值', '按交易日切分=' in SRC)

# ==================== M2：技术性失败同浪重试 ====================
cy = {'bought': False, 'prev': 0, 'reset': True, 'retry': 0, 'retry_n': 0}
M._tech_fail(cy, '510050', '取不到标的价')
check('M2-1 技术性失败置 retry 并计数', cy['retry'] == 1 and cy['retry_n'] == 1, str(cy))
M._tech_fail(cy, '510050', '无报价')
M._tech_fail(cy, '510050', '在途委托')
check('M2-2 重试次数累加', cy['retry'] == 1 and cy['retry_n'] == 3, str(cy))
M._tech_fail(cy, '510050', '无候选')
check('M2-3 超过上限后放弃本浪（retry 清零）',
      cy['retry'] == 0 and cy['retry_n'] == 4, str(cy))
M._clear_retry(cy)
check('M2-4 _clear_retry 清零', cy['retry'] == 0 and cy['retry_n'] == 0, str(cy))
check('M2-5 常量默认 3', M.MAX_TECH_RETRY == 3, str(M.MAX_TECH_RETRY))

# 结构断言：在途委托检查不能留在函数入口（旧写法整根 bar 跳评信号）
i_def = SRC.find('def _try_entry(C, undl, positions, cfg):')
i_sig = SRC.find('_first = is_first_cross(counts, th)')
i_pend = SRC.find("if len(S.pending) > 0:")
check('M2-6 在途委托检查已移到信号判定之后',
      i_def < i_sig < i_pend and i_pend > 0,
      'def=%d sig=%d pending=%d' % (i_def, i_sig, i_pend))
check('M2-7 在途委托算技术性失败（可重试）',
      "在途委托未回收" in SRC and "_tech_fail(cy, undl, '在途委托未回收" in SRC)
check('M2-8 资金门拒绝不重试（清额度）',
      SRC.find('if not ok:') > 0 and SRC.find('if not ok:\n        _clear_retry(cy)') > 0)
check('M2-9 委托未受理也算技术性失败、不再置 bought',
      "本周期不再重试" not in SRC and "_tech_fail(cy, undl, '下单失败 ref=" in SRC)
check('M2-10 信号判定允许累加期重试（cur >= th）',
      "_retry = bool(cy.get('retry')) and cur >= th" in SRC)
check('M2-11 计数回落清额度（本浪结束）',
      "if cur < th:\n        # 计数回落到阈值以下 = 本浪结束" in SRC)
check('M2-12 INIT 打生效值', '技术性重试：每浪最多' in SRC)

# ==================== M3：止盈基准改 ask ====================
cfg_tp = {'tp_pct': 50}
a, r, px = M.decide_exit({'open': 0.0100}, {'bid': 0.0049, 'ask': 0.0055}, cfg_tp)
check('M3-1 bid 已回落 51% 但 ask 只回落 45% → 不止盈', a == '', str((a, r, px)))
a, r, px = M.decide_exit({'open': 0.0100}, {'bid': 0.0060, 'ask': 0.0049}, cfg_tp)
check('M3-2 ask 回落 51% → 止盈，成交价取 ask',
      a == 'close' and abs(px - 0.0049) < 1e-12, str((a, r, px)))
a, r, px = M.decide_exit({'open': 0.0100}, {'bid': 0.0049, 'ask': 0.0}, cfg_tp)
check('M3-3 ask 缺失回退 bid（fail-safe 不退化成不止盈）',
      a == 'close' and abs(px - 0.0049) < 1e-12, str((a, r, px)))
a, r, px = M.decide_exit({'open': 0.0}, {'bid': 0.0049, 'ask': 0.0055}, cfg_tp)
check('M3-4 开仓价缺失不动作', a == '' and px == 0.0)
a, r, px = M.decide_exit({'open': 0.0100}, {'bid': 0.0122, 'ask': 0.0122}, cfg_tp)
check('M3-5 回测口径（bid=ask=close）不受影响', a == '' and px == 0.0)
check('M3-6 判定与成交同源', "ref = ask if ask > 0 else bid" in SRC
      and "return 'close', 'tp%.0f%%(fall%.1f%%)' % (cfg['tp_pct'], fall), ref" in SRC)
check('M3-7 不再用 bid 判回落', "fall = (open_px - bid) / open_px" not in SRC)

# ==================== v5_4 回归：C 浪门语义 ====================
wm1 = {'wave_max': 1}
check('C1 空仓不拦', M._wave_blocked(wm1, 0) == (False, ''))
b, why = M._wave_blocked(wm1, 1)
check('C2 已有 1 张 → 拦', b is True and '本浪已开 1 张' in why, why)
b, why = M._wave_blocked(wm1, 2)
check('C3 已有 2 张 → 拦且报真实张数', b is True and '本浪已开 2 张' in why, why)
check('C4 wave_max=0 关闭该门', M._wave_blocked({'wave_max': 0}, 5) == (False, ''))
check('C5 wave_max=2 时 1 张放行', M._wave_blocked({'wave_max': 2}, 1) == (False, ''))
check('C6 wave_max=2 时 2 张拦', M._wave_blocked({'wave_max': 2}, 2)[0] is True)
check('C7 cfg 缺 key 视为关闭', M._wave_blocked({}, 3) == (False, ''))
check('C8 cfg=None 不崩且放行', M._wave_blocked(None, 3) == (False, ''))
check('C9 per_undl 传字符串也能判', M._wave_blocked(wm1, '1')[0] is True)

cfg = M._cfg()
check('W7 _cfg() 含 wave_max=1', cfg.get('wave_max') == 1, str(cfg.get('wave_max')))
check('W8 _cfg() 其余闸门未变',
      (cfg.get('max_undl'), cfg.get('max_total'), cfg.get('max_day')) == (3, 6, 0),
      str((cfg.get('max_undl'), cfg.get('max_total'), cfg.get('max_day'))))
check('W9 新增闸门不进 _cfg()（只是执行期常量）',
      'retry' not in str(cfg.keys()) and 'split' not in str(cfg.keys()), str(sorted(cfg.keys())))

# ==================== 11-13 闸门重放（v5_4 行为不能变） ====================
seq = ['510500', '588000', '588000', '510300', '510500', '510300',
       '510050', '510500', '510300', '510500', '588000', '510050',
       '510500', '588000', '510300', '510050', '588000', '510500', '510050']


def replay(wave_max):
    pos = {}
    opened, blocked = [], {}
    for undl in seq:
        per = pos.get(undl, 0)
        total = sum(pos.values())
        wb, _ = M._wave_blocked({'wave_max': wave_max}, per)
        if wb:
            blocked['wave'] = blocked.get('wave', 0) + 1
            continue
        if per >= 3 or total >= 6:
            blocked['cap'] = blocked.get('cap', 0) + 1
            continue
        pos[undl] = per + 1
        opened.append(undl)
    return opened, blocked


op_v4, bl_v4 = replay(1)
check('S1 一浪一张：11-13 每标的至多 1 张',
      all(op_v4.count(u) <= 1 for u in set(op_v4)), str(op_v4))
check('S2 一浪一张：首日只开 4 张（4 个标的各 1）', len(op_v4) == 4, str(op_v4))
check('S3 510050 有机会（旧版被 total=6/6 挡死）', '510050' in op_v4, str(op_v4))
check('S4 浪门确实拦下重复信号', bl_v4.get('wave', 0) >= 10, str(bl_v4))
op_off, bl_off = replay(0)
check('S5 关浪门回到旧行为（首日 6 张、510050 进不去）',
      len(op_off) == 6 and '510050' not in op_off, str((len(op_off), op_off)))
check('S6 关浪门时拦截全来自张数上限', bl_off.get('wave', 0) == 0, str(bl_off))

# ==================== v5_6：预设档 / G2 门 / 强平取价 / min_dte 互斥 ====================
ok_p, name_p, ratio_p = M.resolve_preset('P2')
check('V1-1 PRESET=P2 → 3.0',
      ok_p == 1 and name_p == 'P2' and abs(ratio_p - 3.0) < 1e-9, str((ok_p, name_p, ratio_p)))
ok_p, name_p, ratio_p = M.resolve_preset(' p3 ')
check('V1-2 大小写/空白容错 P3 → 4.0',
      ok_p == 1 and name_p == 'P3' and abs(ratio_p - 4.0) < 1e-9, str((ok_p, name_p, ratio_p)))
ok_p, name_p, ratio_p = M.resolve_preset('PX')
check('V1-3 未知名 fail-closed（ok=0 → 只禁开仓）',
      ok_p == 0 and name_p == 'PX' and ratio_p == 0.0, str((ok_p, name_p, ratio_p)))
check('V1-4 表可注入（云端可单测不同档）',
      M.resolve_preset('X', {'X': {'min_prem_ratio': 1.5}})[2] == 1.5)

check('V2-1 min_dte=2 / 强平3 → 抬到 4', M.eff_min_dte(2, 1, 3) == (4, 1))
check('V2-2 min_dte=4 / 强平3 → 不动', M.eff_min_dte(4, 1, 3) == (4, 0))
check('V2-3 强平关 → 不动', M.eff_min_dte(2, 0, 3) == (2, 0))
check('V2-4 min_dte=1 / 强平0 → 无变化', M.eff_min_dte(1, 1, 0) == (1, 0))

ok_g, net_g, cost_g, ratio_g = M.prem_gate_ok(0.0005, 10000, 1.2, 1.7, 3.0)
check('V3-1 510050 薄档（5 元/张）被拦',
      ok_g is False and abs(cost_g - 4.9) < 1e-9 and ratio_g < 1, str((net_g, cost_g, ratio_g)))
ok_g, net_g, cost_g, ratio_g = M.prem_gate_ok(0.005, 10000, 1.2, 1.7, 3.0)
check('V3-2 厚档（50 元/张）放行', ok_g is True and ratio_g > 3, str((net_g, cost_g, ratio_g)))
check('V3-3 ratio=0 关闭门', M.prem_gate_ok(0.0001, 10000, 1.2, 1.7, 0)[0] is True)

ORIG_SETTLE = M._settle_px
ORIG_BARS = M._bars
M._bars = lambda C, code, period, n: [{'c': 0.05}]
px_f, src_f = M._force_close_px(None, 'X', {})
check('V4-1 无盘口回退最近 K 线+2%',
      abs(px_f - 0.051) < 1e-12 and src_f == 'K线+2%', str((px_f, src_f)))
px_f, src_f = M._force_close_px(None, 'X', {'bid': 0.02})
check('V4-2 ask 缺失用 bid', abs(px_f - 0.02) < 1e-12 and src_f == 'bid', str((px_f, src_f)))
px_f, src_f = M._force_close_px(None, 'X', {'bid': 0.02}, 2)
check('V4-3 失败 2 次 → 提价 10%', abs(px_f - 0.022) < 1e-12, str((px_f, src_f)))
px_f, src_f = M._force_close_px(None, 'X', {'bid': 0.02}, 20)
check('V4-4 提价封顶 1.5 倍', abs(px_f - 0.03) < 1e-12, str((px_f, src_f)))
M._bars = ORIG_BARS
M._settle_px = ORIG_SETTLE

M.S.gate_cnt = {'cycle': 2, 'prem': 5}
check('V5-1 [STAT] 汇总含 cycle/prem',
      'cycle=2' in M._gate_stats_text() and 'prem=5' in M._gate_stats_text(),
      M._gate_stats_text())
M.S.gate_cnt = {}
check('V5-2 无拦截时文案', M._gate_stats_text() == '无拦截')
M.S.risk_unclosed = {'10012598.SHO': 1}
check('V6-1 风险行带合约代码', '10012598.SHO' in M._risk_text(None))
M.S.risk_unclosed = {}
check('V6-2 无风险时为空', M._risk_text(None) == '')

check('V7-1 远月剔除已接线', 'if max_dte > 0 and dte > max_dte:' in SRC)
check('V7-2 强平失败可重试（不再一律 dry_skip）',
      'S.force_fail[code] = n' in SRC and 'S.dry_skip[code] = 1\n                continue\n            continue' not in SRC)
check('V7-3 周期不符只禁开仓', 'if not S.period_ok:' in SRC)
check('V7-4 权利金门在选档之前',
      SRC.find('ok0, _net0, _cost0, _r0') > 0
      and SRC.find('ok0, _net0, _cost0, _r0') < SRC.find('pick = pick_put('))
check('V7-5 强平取价走 _force_close_px',
      SRC.find('px, src = _force_close_px(') > 0)

# ==================== A/B 回归（v5_3 已验的不能被改坏） ====================
reset(bar=1204)
M._bt_terminal(None)
check('R1 终局 bar=1205', M.S.bt['bar'] == 1205 and 'bar=1205' in lines[1][1], lines[1][1][:60])
reset()
M._bt_unreal = ORIG_UNREAL
M.S.bt['pos'] = {'10012598.SHO': {'open': 0.0122, 'unit': 10000, 'qty': 1, 'fee': 2.2}}
M._bt_last_px = lambda C, code: 0.0237
tot, det = M._bt_unreal(object())
check('R2 卖方% 标签与数值', '卖方-94.3%' in det[0] and abs(tot + 117.2) < 1e-6, det[0])
reset()
M._bt_unreal = ORIG_UNREAL
M._bt_summary(eod=True)
check('R3 日终仍 1 行', len([1 for t, _, _ in lines if t == 'BTSUM']) == 1)
check('R4 BUILD / VERSION', M.BUILD == '20261122-1935' and M.VERSION_LABEL == 'v5_6',
      '%s / %s' % (M.BUILD, M.VERSION_LABEL))

print('')
if errors:
    print('FAILED: %s' % ', '.join(errors))
    sys.exit(1)
print('ALL PASSED')
print('')
print('--- 11-13 闸门重放（一浪一张，max_undl=3 / max_total=6）---')
print('开仓 %d 张: %s' % (len(op_v4), ' '.join(op_v4)))
print('拦截 %s' % bl_v4)
print('--- 同序列关浪门（旧行为）---')
print('开仓 %d 张: %s' % (len(op_off), ' '.join(op_off)))
print('拦截 %s' % bl_off)
