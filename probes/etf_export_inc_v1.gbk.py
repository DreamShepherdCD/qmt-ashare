#encoding:gbk
# QMT 交付件 = 同内容 GBK 编码 + CRLF + 首行 #encoding:gbk（etf_export_inc_v1.gbk.py）
r"""
A股 ETF 现货 1m 增量导出（只读，全程无任何下单调用）

用途
----
把 QMT 本地 1m 数据补齐到既有基线之后（基线 run_20261120 覆盖 2026-09-01 ~ 2026-11-19）。

口径（与基线严格一致，勿改）
--------------------------
每日 241 根：09:30-11:30（含 09:30，121 根）+ 13:01-15:00（不含 13:00，120 根）
QMT 1m bar 时间戳 = bar 结束时刻；剔除 11:31-13:00 午休与盘前盘后。
输出 utf-8-sig（Excel 中文不乱码）。

输出
----
D:\qmt_export\run_YYYYmmdd_HHMMSS\<code>_1m.csv   每标的一份
D:\qmt_export\run_YYYYmmdd_HHMMSS\EXPORT_REPORT.txt
D:\qmt_export\run_YYYYmmdd_HHMMSS\_run.log

运行方式
--------
策略类型选「模型研究」→ 回测模式 → 点「回测」。
after_init 在回测时间轴之外执行，可读本地全区间（含当天最新 1m），且与回测/模拟模式无关，秒级完成。
返回后把 EXPORT_REPORT.txt 的内容回贴即可。

注意
----
1) 本脚本只读，不订阅行情、不下单、不改客户端数据。
2) 若某标的 rows=0 或末日仍停在 20261119，说明本地 datadir 还没有 11-20 之后的数据：
   先在 QMT 客户端「数据管理 / 补充数据」下载对应标的的 1m，再重跑本脚本。
3) 小概率落到 simulation 模式（无回测时钟）：先副图编译跑一次回测，再回主图跑回测。
"""
import os
import time
import traceback

CODES = ["510050.SH", "510300.SH", "510500.SH", "588000.SH", "588080.SH"]
START = "20261120"                      # 增量起点 = 基线末日(20261119)的次一交易日
END   = time.strftime("%Y%m%d")         # 取到本地最新为止，不会造数据

RUN_DIR = time.strftime("run_%Y%m%d_%H%M%S")
OUT_DIR = os.path.join(r"D:\qmt_export", RUN_DIR)
LOG     = os.path.join(OUT_DIR, "_run.log")
REPORT  = os.path.join(OUT_DIR, "EXPORT_REPORT.txt")

_done = {"v": False}


def _log(msg):
    try:
        os.makedirs(OUT_DIR, exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + str(msg) + "\n")
    except Exception:
        pass


def _ts14(x):
    """把索引/时间值统一成 14 位 YYYYMMDDHHMMSS 字符串。"""
    try:
        s = str(x)
    except Exception:
        return ""
    if len(s) >= 14 and s[:14].isdigit():
        return s[:14]
    # Timestamp / datetime
    try:
        return x.strftime("%Y%m%d%H%M%S")
    except Exception:
        pass
    digits = "".join(ch for ch in s if ch.isdigit())
    return digits[:14]


def _keep_hm(hm):
    """与基线一致：09:30-11:30 与 13:01-15:00。hm 为 4 位 HHMM。"""
    return ("0930" <= hm <= "1130") or ("1301" <= hm <= "1500")


def _export(ContextInfo):
    _log("FETCH %s -> %s | codes=%s" % (START, END, ",".join(CODES)))
    try:
        data = ContextInfo.get_market_data_ex(
            [],
            CODES,
            period="1m",
            start_time=START,
            end_time=END,
            count=-1,
            dividend_type="none",
            fill_data=False,
        )
    except Exception:
        _log("ERR get_market_data_ex: " + traceback.format_exc())
        return

    if not data:
        _log("ERR empty payload (no codes returned)")
        return

    report = []
    report.append("EXPORT REPORT  run=%s" % RUN_DIR)
    report.append("range requested: %s -> %s" % (START, END))
    report.append("mode note: after_init (outside backtest timeline)")
    report.append("")
    report.append("code,rows,days,per_day_mode,first,last")
    total = 0
    err_n = 0

    for code in CODES:
        try:
            df = data.get(code)
            if df is None or len(df) == 0:
                _log("EMPTY %s" % code)
                report.append("%s,0,0,-,-,-" % code)
                continue

            df = df.loc[:, ~df.columns.duplicated()].copy()
            # QMT 返回的 df 常已自带 stime 列（索引名同名，故基线 CSV 有两列同名 stime）
            if "stime" in list(df.columns):
                stimes = [_ts14(x) for x in df["stime"].tolist()]
            else:
                stimes = [_ts14(x) for x in df.index]
            df["stime"] = stimes
            # stime 固定放第一列
            df = df[["stime"] + [c for c in df.columns if c != "stime"]]

            keep = [_keep_hm(s[8:12]) for s in stimes]
            df = df.loc[keep]

            if len(df) == 0:
                _log("EMPTY_AFTER_FILTER %s (raw=%d)" % (code, len(idx)))
                report.append("%s,0,0,-,-,-" % code)
                continue

            path = os.path.join(OUT_DIR, "%s_1m.csv" % code.replace(".", "_"))
            df.to_csv(path, encoding="utf-8-sig", index=False)

            days = {}
            for s in df["stime"].tolist():
                d = s[:8]
                days[d] = days.get(d, 0) + 1
            cnt = {}
            for v in days.values():
                cnt[v] = cnt.get(v, 0) + 1
            mode_n = max(cnt.items(), key=lambda kv: kv[1])[0]
            bad = sum(1 for v in days.values() if v != 241)

            first = df["stime"].iloc[0]
            last = df["stime"].iloc[-1]
            total += len(df)
            _log("SAVED %s rows=%d days=%d per_day_mode=%d bad_days=%d %s->%s"
                 % (code, len(df), len(days), mode_n, bad, first, last))
            report.append("%s,%d,%d,%d,%s,%s%s"
                          % (code, len(df), len(days), mode_n, first, last,
                             "" if mode_n == 241 else "  [CHECK: per-day != 241]"))
        except Exception as e:
            err_n = err_n + 1
            _log("ERR %s: %s" % (code, traceback.format_exc()))
            report.append("%s,ERR,%s,-,-,-" % (code, type(e).__name__))

    report.append("")
    report.append("total_rows=%d  errors=%d" % (total, err_n))
    report.append("output_dir=%s" % OUT_DIR)
    if total == 0:
        report.append("")
        if err_n:
            report.append("!! 有 %d 个标的报错：看 _run.log 的 traceback 回贴" % err_n)
        else:
            report.append("!! 全部为空：先在 QMT 客户端「数据管理」下载 11-20 之后的 1m 再重跑")

    try:
        os.makedirs(OUT_DIR, exist_ok=True)
        with open(REPORT, "w", encoding="utf-8-sig") as f:
            f.write("\n".join(report) + "\n")
    except Exception:
        _log("ERR write report: " + traceback.format_exc())

    _log("DONE total_rows=%d dir=%s" % (total, OUT_DIR))


def init(ContextInfo):
    _log("INIT HIT")


def after_init(ContextInfo):
    # 回测时间轴之外执行：读本地全区间，秒级完成，与运行模式无关
    if _done["v"]:
        return
    _done["v"] = True
    _export(ContextInfo)


def handlebar(ContextInfo):
    # 必须存在；after_init 已导出，这里不再逐根推进
    pass
