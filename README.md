# qmt-ashare —— A 股 ETF 期权卖方策略（券商 QMT 内置 Python）

**独立代码库。** 这份代码只在券商 QMT（君弘君智投研端）的内置 Python 里跑，不从任何容器/空间加载，
也不属于 `nanobot-quant` 的运行时——与云端 A 股分析脚本（`nanobot_quant/ashare/` 那类）**没有共享代码、
没有共同的运行环境、没有可比性**，所以单独成仓。

策略：ETF 现货算 TD 低9 → 卖虚值 put → 权利金回落止盈买平 → 到期 ITM 走自然行权接实股。

## 运行环境约束（决定了这里的一切写法）

| 约束 | 值 |
|---|---|
| Python | **3.6.8**（无 f-string 之外的现代语法，无第三方库） |
| 编码 | 策略文件必须 **GBK**；UTF-8 版只作阅读/编辑 |
| 行尾 | **CRLF** |
| 网络 | 无；且 `socket` 被模块白名单拦 |
| 文件 I/O | **只允许新建**：目标路径已存在 ⇒ `PermissionError: Forbidden FileIO`（读/覆盖/追加一律被拦，`os.remove`/`rename`/`listdir` 可用） |
| 界面 | 无 GUI/页面 API，只能 `print` 到日志 |
| 依赖 | 只有 xtquant 内置模块（`ContextInfo`、`get_market_data_ex`、`get_option_list`、`passorder` …） |

## 目录

```
ashare_put_v5_6.py          当前版本（UTF-8，可编辑/review/diff）
deliver/ashare_put_v5_6.py  交付版本（GBK + CRLF）——整份粘进 QMT 的就是它
build_deliver.py            一键从当前版本生成交付版本（并校验可 compile）
archive/                    历史版本 v1 … v5_5 + 旧交付件 + 两个一次性补丁脚本（只读，供与旧日志对照）
probes/                     QMT 侧只读探针（环境探测、期权链、1m 取数、回测盘口）
selftest/                   逐版本本地自测（不依赖 QMT，断言式 OK/FAIL）
CHANGELOG.md                逐版变更
```

## 交付流程

```bash
python3 build_deliver.py ashare_put_v5_6     # 生成 deliver（GBK+CRLF，校验可 compile）
python3 selftest/selftest_v5_6.py            # 本地自测，必须全绿
```

`build_deliver.py` 打印 `bytes / crlf / build`；selftest 断言 `crlf == 行数`、`bare_lf == 0`、GBK 可 `compile`。
**只粘 `deliver/` 那份**——UTF-8 版粘进 QMT 会中文乱码甚至 SyntaxError。

QMT 交易机通常不能上外网，所以 **GitHub 只作审计与追溯，不是交付通道**：交付永远是「生成 GBK 文件 →
粘进 QMT 策略编辑器」。

## 与容器/空间的关系（三条边界）

1. 本仓代码**不进镜像、不进任何 pip 包**，容器与 HF Space 完全不加载它
2. 改本仓**不需要空间重建、不碰任何 Dockerfile 的 pin/bust**（pin/bust 只跟容器内代码绑定）
3. 验收 = `selftest` 全绿 + **QMT 内实跑回测对比**（改前/改后：净盈亏、开平笔数、闸门拦截统计）

## 变更纪律（两档）

| 改动类型 | 流程 |
|---|---|
| 探针、日志、展示层、文档、自测 | 可直接进 `main` |
| **策略行为改动**（入场 / 出场 / 闸门 / 仓位 / 记账口径） | 走 `feat/*` 分支 → PR → 用户合并；PR 内必须贴一版 QMT 同参数回测对比 |

## 版本标识

- 文件名带版本：`ashare_put_v5_6.py`（改脚本**不覆盖**旧版，新版另存新文件，旧版移入 `archive/`）
- 文件内 `BUILD = '20261122-1935'` / `VERSION_LABEL = 'v5_6'`，INIT 行会打印，日志能直接对上版本
- git tag `qmt-v5_4` 指向该版本入库的 commit（v5_5 / v5_6 待 QMT 同参回测对比通过后再补打）

## 数据说明

期权/ETF 1m 历史（期权约 361M、ETF 约 24M）**不入仓**。数据由 `probes/` 里的导出脚本从 QMT 导出成 CSV，
每次导出的区间/行数/异常日统计见该 run 目录下的 `EXPORT_REPORT.txt`；分析在本地离线做。

## 已知口径（详见各版本文件头注释）

- 回测撮合：成交价 = bar close；滑点参数对期权 `passorder` 无效；保证金按平台比例严重低估
- 平台余额含义务仓市值重估，**不能当盈亏依据**；净 = 自建账本「已实现 + 浮盈亏」
- 价差在报告层用 `_spread_cost()` 并入逐笔成本（虚值/浅价 1 元/张；实值 px×10000×1.25%，上限 60 元/张）
- 手续费按张：卖开 1.20 / 买平 1.70
- TD 计数：**按交易日切分**（隔夜/非交易日重置、午休不切），与云端 td-table 同口径（v5_5 起；`SESSION_SPLIT=0` 可回到旧口径）
- 技术性失败（无价/无候选/无报价/在途委托）可在同浪内重试，上限 3 次；资金与张数门拒绝不重试（v5_5 起）
- 止盈**判定与成交同源取 ask**（卖方买回实际支付价）；ask 缺失回退 bid（v5_5 起）
- **预设块 `PRESET`（v5_6 起）**：`P1` = 仅 DTE 上限（权利金门关）、`P2`（默认）= 净权利金 ≥ 3× 往返成本、`P3` = 4×；未知名 fail-closed（只禁开新仓，持仓照管）
- **到期窗口 4~35 天（v5_6 起，默认 min 被抬到 4）**：`MAX_DTE=35` 剔除远月；`MIN_ENTRY_DTE` 会自动抬到 `FORCE_CLOSE_DTE_N + 1`（否则开出来就满足强平条件）
- **DTE 强平取价必成（v5_6 起）**：ask → bid → last → 回测内在价值 → 最近 K 线 ×1.02；买平失败按 `1+5%*n` 提价重试（上限 1.5 倍），未成交进 `[RISK]` 到期未平风险，日切与收尾各报一行
- **周期不符只禁开新仓（v5_6 起）**：面板 `period` 明确读到且 ≠ `SIGNAL_PERIOD` 时停开仓，止盈/强平/持仓照管照常；读不到视为未知、不拦
- **开仓拦截统计（v5_6 起）**：`[STAT]` 按原因累计（cycle/wave/limit/day/fund/prem/tech），日切与收尾各一行
- 实盘双锁：界面选实盘 **且** `LIVE_CONFIRM = 1` 才发单
