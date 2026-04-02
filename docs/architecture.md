# Pengullet 项目技术文档

## 一、Polymarket 与套利原理

### 1.1 Polymarket 是什么

Polymarket 是一个建立在 Polygon（以太坊 L2）链上的去中心化预测市场。用户可以对真实世界事件的结果下注交易，比如"2026年美联储是否会降息？"、"某国选举谁会赢？"等等。

每个市场（Market）由一个问题和若干互斥结果组成。最简单的情况是二元市场，只有 Yes 和 No 两个结果。每个结果对应一个可交易的 Token，价格在 $0 到 $1 之间浮动。当市场最终结算时，正确结果的 Token 持有者获得 $1，错误结果的 Token 归零。

### 1.2 订单簿（CLOB）模型

Polymarket 使用的交易模型叫 CLOB（Central Limit Order Book，中央限价订单簿），和传统股票交易所一样：

- **Ask（卖单/要价）**：持有 Token 的人挂出的卖价，价格从低到高排列。最低的 Ask 叫 best ask（最优卖价）。
- **Bid（买单/出价）**：想买 Token 的人挂出的买价，价格从高到低排列。最高的 Bid 叫 best bid（最优买价）。
- **Spread（价差）**：best ask - best bid，即买卖之间的差距。

每个结果 Token 都有自己独立的订单簿。

### 1.3 套利机会的数学原理

理论上，一个二元市场的两个结果价格之和应该恰好等于 $1.00：

```
Price(Yes) + Price(No) = $1.00
```

因为不论哪个结果发生，持有全部结果 Token 的人一定能拿回 $1.00。

但在实际市场中，由于以下原因，这个等式经常被打破：

- 流动性碎片化：不同做市商独立报价，缺乏统一协调
- 信息延迟：新信息到达后，各结果价格调整速度不一致
- 做市商策略差异：不同做市商的定价模型和风险偏好不同
- 低流动性市场：参与者少，价格发现效率低

**当所有结果的最低 Ask 价格之和低于 $1.00 时，就出现了无风险套利机会。**

举个具体例子：

```
市场问题："明天会下雨吗？"
  Yes Token 的 best ask = $0.45（有人愿意以 $0.45 卖出 Yes Token）
  No  Token 的 best ask = $0.52（有人愿意以 $0.52 卖出 No Token）

总买入成本 = $0.45 + $0.52 = $0.97
无论明天下不下雨，你都会拿回 $1.00
利润 = $1.00 - $0.97 = $0.03（3.09% 回报率）
```

### 1.4 多结果市场套利

有些市场有多于两个互斥结果，比如"谁会赢得选举？"有 A、B、C 三个候选人。原理相同：

```
Price(A) + Price(B) + Price(C) = $1.00（理论上）
如果 Ask(A) + Ask(B) + Ask(C) < $1.00 → 套利机会
```

### 1.5 利润公式

```
毛利润 = $1.00 - Sum(所有结果的 best ask 价格)
净利润 = 毛利润 - 交易手续费 - Gas 费 - 滑点损失

只有当净利润 > 0 时，才值得执行
```

### 1.6 现实约束

- **交易手续费**：Polymarket 对获胜份额收取约 2% 的费用
- **Gas 费**：Polygon L2 的 Gas 极低，通常 < $0.01，但仍需考虑
- **滑点**：如果你想买的数量超过了 best ask 挂单的数量，就需要吃更高价位的单，实际成本会增加
- **流动性**：有些市场的订单簿很薄，可操作的量很小
- **时效性**：套利窗口可能只持续几秒，需要快速发现和执行

---

## 二、项目工程架构

### 2.1 目录结构

```
Pengullet/
├── pyproject.toml                  # 项目配置 + 依赖声明
├── uv.lock                         # 依赖版本锁定（uv 自动生成）
├── .venv/                          # 虚拟环境（uv 自动创建）
├── .env.example                    # 环境变量模板
├── .gitignore                      # Git 忽略规则
├── README.md                       # 快速上手说明
├── docs/
│   └── architecture.md             # 本文档
│
├── src/pengullet/                  # 核心代码（Python 包）
│   ├── __init__.py                 # 包入口，定义版本号
│   ├── config/                     # 配置管理
│   │   └── settings.py             # 读取 .env，类型校验
│   ├── market/                     # 市场数据层
│   │   ├── models.py               # 所有数据模型定义
│   │   ├── client.py               # Polymarket API 底层客户端
│   │   └── fetcher.py              # 高层数据抓取（含缓存）
│   ├── strategy/                   # 策略引擎
│   │   ├── scanner.py              # 套利机会扫描器
│   │   ├── evaluator.py            # 利润评估器
│   │   └── filters.py              # 机会过滤器
│   ├── execution/                  # 交易执行层
│   │   ├── executor.py             # 订单执行引擎
│   │   ├── risk.py                 # 风险管理
│   │   └── wallet.py               # 钱包签名管理
│   ├── monitoring/                 # 监控通知层
│   │   ├── logger.py               # 结构化日志配置
│   │   ├── notifier.py             # Telegram/Discord 推送
│   │   └── dashboard.py            # 运行状态面板
│   └── utils/                      # 通用工具
│       └── helpers.py              # 价格转换、异步重试等
│
├── scripts/                        # 可执行脚本
│   ├── scan.py                     # 一次性扫描（只看不做）
│   └── run_bot.py                  # 持续运行的交易机器人
│
└── tests/                          # 单元测试
    ├── test_scanner.py             # 扫描器测试（7 个用例）
    └── test_evaluator.py           # 评估器和过滤器测试（5 个用例）
```

### 2.2 包管理（uv）

本项目使用 uv 管理 Python 依赖，uv 是一个用 Rust 编写的极速包管理器。它的工作方式：

- **`pyproject.toml`**：声明项目需要哪些依赖，类似于 Node.js 的 `package.json`
- **`uv.lock`**：锁定每个依赖的精确版本，确保所有人安装的完全一致，类似于 `package-lock.json`
- **`.venv/`**：uv 自动创建的虚拟环境，所有包安装在这里

常用命令：

| 命令 | 作用 |
|---|---|
| `uv sync` | 安装所有依赖 |
| `uv sync --all-extras` | 安装包括开发依赖在内的所有依赖 |
| `uv add httpx` | 添加新依赖 |
| `uv remove httpx` | 移除依赖 |
| `uv run python scripts/scan.py` | 在 uv 环境中运行脚本 |
| `uv run pytest` | 运行测试 |

### 2.3 技术栈

| 组件 | 选型 | 作用 |
|---|---|---|
| 包管理 | uv | Python 依赖管理和虚拟环境 |
| HTTP 客户端 | httpx（异步） | 调用 Polymarket API，高性能并发请求 |
| 数据模型 | Pydantic v2 | 定义所有数据结构，自动做类型校验和序列化 |
| 配置管理 | pydantic-settings | 从 .env 文件读取配置，自动转成 Python 类型 |
| 交易 SDK | py-clob-client | Polymarket 官方提供的交易 SDK，处理订单签名和提交 |
| 区块链 | web3.py | 与 Polygon 链交互（查余额等） |
| 日志 | structlog | 结构化日志，每条日志带有键值对，便于过滤和分析 |
| 测试 | pytest + pytest-asyncio | Python 标准测试框架，支持异步测试 |
| 代码质量 | ruff | 极快的 linter 和代码格式化工具 |

### 2.4 配置管理（`config/settings.py`）

所有配置通过环境变量注入，使用 `pydantic-settings` 自动从 `.env` 文件加载。`Settings` 类定义了全部可配置项：

**API 凭证：**
- `POLYMARKET_API_URL`：CLOB API 地址（默认 `https://clob.polymarket.com`）
- `POLYMARKET_PRIVATE_KEY`：以太坊私钥，用于签名交易
- `POLYMARKET_API_KEY` / `API_SECRET` / `API_PASSPHRASE`：API 认证三件套

**交易参数：**
- `MIN_PROFIT_THRESHOLD`：最小净利润门槛，低于此值不执行（默认 $0.005）
- `MAX_POSITION_SIZE`：单笔最大仓位（默认 $50）
- `MAX_TOTAL_EXPOSURE`：所有持仓总敞口上限（默认 $500）
- `SCAN_INTERVAL_SECONDS`：扫描间隔（默认 10 秒）

**通知：**
- `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID`：Telegram 推送配置
- `DISCORD_WEBHOOK_URL`：Discord Webhook 推送配置

---

## 三、市场数据层详解（`market/`）

### 3.1 数据模型（`models.py`）

所有数据结构用 Pydantic BaseModel 定义，提供类型安全和自动校验：

**`OrderBookEntry`** — 订单簿中的一档报价：
- `price: Decimal` — 价格（如 0.45 表示 $0.45）
- `size: Decimal` — 该价位的可交易数量

**`OrderBook`** — 一个 Token 的完整订单簿：
- `asks` — 所有卖单列表
- `bids` — 所有买单列表
- `best_ask` 属性 — 返回价格最低的卖单
- `best_bid` 属性 — 返回价格最高的买单
- `spread` 属性 — best ask 和 best bid 之间的价差
- `ask_depth(levels)` — 前 N 档卖单的总可交易量
- `bid_depth(levels)` — 前 N 档买单的总可交易量

**`Token`** — 一个结果代币：
- `token_id` — 链上唯一标识
- `outcome` — 结果名称（如 "Yes" 或 "No"）
- `price` — 当前中间价
- `order_book` — 关联的订单簿

**`Market`** — 一个预测市场：
- `condition_id` — 市场唯一 ID
- `question` — 市场问题文本
- `tokens` — 该市场的所有结果 Token
- `is_tradeable` 属性 — 是否活跃且未关闭

**`ArbitrageCandidate`** — 一个被检测到的套利候选：
- `market` — 所在市场
- `best_asks` — 每个结果的最佳卖价
- `total_cost` — 总买入成本
- `profit_per_share` — 每份利润
- `max_shares` — 最大可操作数量（取决于最薄的那一腿）
- `gross_profit` — 毛利润总额
- `profit_pct` 属性 — 利润百分比

**`ScoredOpportunity`** — 经过评估后的套利机会：
- 包含 `ArbitrageCandidate` 加上费用明细
- `trading_fee` — 交易手续费
- `gas_fee` — Gas 费
- `slippage_estimate` — 滑点估计
- `net_profit` — 净利润
- `recommended_size` — 建议操作数量

### 3.2 API 客户端（`client.py`）

`PolymarketClient` 是对 Polymarket CLOB REST API 的异步封装。使用 httpx 做 HTTP 请求：

**初始化：**
- 接收 Settings 配置
- 懒加载 httpx.AsyncClient（首次请求时创建）
- 自动附加 API 认证 headers

**主要方法：**

| 方法 | 对应 API | 作用 |
|---|---|---|
| `get_markets()` | `GET /markets` | 获取一页市场数据 |
| `get_all_markets()` | 分页遍历 `/markets` | 获取全部市场（自动翻页） |
| `get_order_book(token_id)` | `GET /book` | 获取某个 Token 的订单簿 |
| `get_prices(token_ids)` | `GET /prices` | 批量获取多个 Token 的价格 |

翻页逻辑：API 返回 `next_cursor` 字段，当 cursor 为空或等于 `"LTE="` 时表示已到最后一页。

### 3.3 数据抓取器（`fetcher.py`）

`MarketFetcher` 是对 `PolymarketClient` 的高层封装，增加了缓存和并发控制：

**市场列表缓存：** 市场列表每 60 秒才重新拉取一次（TTL 缓存），避免每次扫描都调用 API。订单簿数据则每次都重新拉取，因为它变化很快。

**并发控制：** 使用 `asyncio.Semaphore(20)` 限制最多同时发起 20 个订单簿请求。Polymarket 有上千个市场，每个市场 2 个 Token，不限并发的话会触发 API 限流。

**异常容错：** 使用 `asyncio.gather(*tasks, return_exceptions=True)` 并行抓取所有订单簿，单个失败不影响其他，失败的会记录警告日志。

---

## 四、策略引擎详解（`strategy/`）

### 4.1 套利扫描器（`scanner.py`）

`ArbitrageScanner` 是核心算法组件，逻辑如下：

```
对每个市场 market：
    1. 检查是否有至少 2 个结果 Token
    2. 检查每个 Token 是否有订单簿数据
    3. 获取每个 Token 的 best ask（最低卖价）
    4. 计算 total_cost = sum(所有 best ask 价格)
    5. 如果 total_cost < $1.00：
       - profit_per_share = $1.00 - total_cost
       - max_shares = min(各 best ask 的挂单量)  ← 取最小值，因为要同时买入所有结果
       - gross_profit = profit_per_share × max_shares
       - 记录为套利候选
    6. 所有候选按 gross_profit 从大到小排序
```

**关键设计决策：** `max_shares` 取所有结果中挂单量的最小值，因为套利需要同时买入每个结果的相同数量。如果 Yes 有 100 份但 No 只有 10 份，那最多只能操作 10 份。

### 4.2 利润评估器（`evaluator.py`）

`Evaluator` 对每个套利候选进行详细的利润计算：

**费用模型：**
- 交易手续费 = 2% × 建议数量（Polymarket 对获胜份额收取约 2%）
- Gas 费 = 固定 $0.005（Polygon L2 Gas 极低）
- 滑点 = 基于订单深度的估算

**建议交易量计算：**
```
recommended_size = min(max_shares, MAX_POSITION_SIZE / total_cost)
```
即不超过订单簿深度，也不超过单笔最大仓位。

**滑点估算算法：** 如果建议交易量超过了 best ask 的挂单量，说明需要吃到更高价位的单。滑点按超出比例的 0.5% 线性估算。这是保守估计。

**净利润计算：**
```
net_profit = gross_profit - trading_fee - gas_fee - slippage
```

只有 `net_profit > 0` 的机会才会被保留。

### 4.3 机会过滤器（`filters.py`）

`OpportunityFilter` 在评估后再做一轮过滤，排除低质量机会：

| 过滤条件 | 阈值 | 原因 |
|---|---|---|
| 最小净利润 | $0.005（可配置） | 利润太低不值得操作 |
| 最小流动性 | 5 份 | 太少的挂单量意味着执行风险高 |
| 最小利润率 | 0.1% | 利润率太薄，稍有变动就会亏损 |

---

## 五、交易执行层详解（`execution/`）

### 5.1 订单执行器（`executor.py`）

`OrderExecutor` 负责将评估通过的机会变成实际交易：

**双模式运行：**
- **dry-run 模式**（默认）：不下真实订单，只记录日志显示"会怎么做"
- **live 模式**：通过 py-clob-client SDK 签名并提交真实订单

**执行流程：**
```
1. 风险检查（RiskManager.check）
2. 如果是 dry-run → 模拟执行，记录日志
3. 如果是 live：
   a. 确保钱包已初始化
   b. 对每个结果 Token 下 BUY 限价单
      - 价格 = 该结果的 best ask 价格
      - 数量 = recommended_size
   c. 如果所有订单都成功 → 记录交易
   d. 如果有订单失败 → 记录损失（触发风控计数）
```

**订单签名流程：** 使用 py-clob-client SDK，通过以太坊私钥做 EIP-712 签名（一种结构化数据签名标准），然后提交给 Polymarket CLOB 服务器。

### 5.2 风险管理器（`risk.py`）

`RiskManager` 在每笔交易前做风控检查：

| 检查项 | 规则 | 说明 |
|---|---|---|
| 熔断检查 | `is_halted == False` | 熔断触发后拒绝一切交易 |
| 单笔仓位 | `trade_cost <= MAX_POSITION_SIZE` | 单笔不超过 $50 |
| 总敞口 | `current_exposure + trade_cost <= MAX_TOTAL_EXPOSURE` | 所有持仓不超过 $500 |
| 冷却期 | 同一市场距上次交易 > 120 秒 | 避免在同一市场重复操作 |
| 熔断器 | 连续 5 次交易失败 → 自动暂停 | 防止系统异常时持续亏损 |

**状态追踪：**
- `_current_exposure`：当前总敞口金额
- `_market_last_trade`：每个市场上次交易的时间戳
- `_consecutive_losses`：连续失败计数
- `_halted`：是否已熔断

当头寸结算后，通过 `record_settlement()` 释放敞口。

### 5.3 钱包管理器（`wallet.py`）

`WalletManager` 封装了与链上交互的能力：

- 懒加载 `py-clob-client` 的 `ClobClient` 实例
- 使用私钥 + API 凭证初始化
- 提供 USDC 余额查询
- `clob_client` 属性供 `OrderExecutor` 使用来签名订单

---

## 六、监控通知层详解（`monitoring/`）

### 6.1 结构化日志（`logger.py`）

使用 structlog 配置日志系统。每条日志是结构化的键值对格式：

```
2026-04-02T12:30:00Z [info] arbitrage.found  question="Will it rain?" total_cost=0.97 profit_pct=3.09
```

相比传统的字符串日志，结构化日志更容易被程序解析、过滤和聚合分析。

### 6.2 通知推送（`notifier.py`）

`Notifier` 在发现可操作的套利机会时，推送告警到 Telegram 和/或 Discord：

**Telegram：** 调用 Bot API 的 `sendMessage` 接口，使用 Markdown 格式化消息。

**Discord：** 调用 Webhook URL 发送消息。

**消息格式示例：**
```
🐧 Pengullet Arbitrage Alert

Market: Will it rain tomorrow?
Total Cost: $0.9700
Profit/Share: $0.0300 (3.09%)
Net Profit: $0.0245
Recommended Size: 50.0 shares

Ask Prices:
  Yes: $0.4500 (size: 100.0)
  No:  $0.5200 (size: 80.0)
```

### 6.3 状态面板（`dashboard.py`）

`Dashboard` 在内存中追踪运行统计：

- 总扫描次数
- 发现的候选机会数
- 可操作（盈利）机会数
- 已执行交易数
- 累计利润
- 累计交易量
- 最近 20 条机会记录

Bot 停止时会打印一个文本面板，展示全部统计数据。运行中每个周期通过日志输出当前状态。

---

## 七、入口脚本

### 7.1 一次性扫描（`scripts/scan.py`）

运行方式：`uv run python scripts/scan.py`

流程：
1. 加载配置
2. 抓取所有活跃市场
3. 拉取订单簿数据
4. 扫描套利机会
5. 评估和过滤
6. 打印结果到终端

这是一个只读操作，不会下单，适合用来验证系统是否能正确发现机会。

### 7.2 持续运行 Bot（`scripts/run_bot.py`）

运行方式：
- `uv run python scripts/run_bot.py` — dry-run 模式（默认，不真实下单）
- `uv run python scripts/run_bot.py --live` — live 模式（真实下单）

流程：
```
无限循环：
    1. 抓取市场 + 订单簿
    2. 扫描套利
    3. 评估 + 过滤
    4. 记录扫描统计
    5. 对每个可操作机会：
       a. 发送通知（如已配置）
       b. 执行交易（dry-run 或 live）
       c. 记录执行统计
    6. 输出状态日志
    7. 等待 N 秒后重复
```

Ctrl+C 退出时会打印完整的运行统计面板。

---

## 八、测试

共 12 个测试用例，全部通过。

### 8.1 扫描器测试（`test_scanner.py`，7 个用例）

| 测试 | 验证内容 |
|---|---|
| `test_detects_arbitrage_when_total_ask_below_one` | Yes=$0.45 + No=$0.52 = $0.97 < $1.00 → 检测到套利 |
| `test_no_arbitrage_when_total_ask_equals_one` | Yes=$0.50 + No=$0.50 = $1.00 → 无套利 |
| `test_no_arbitrage_when_total_ask_above_one` | Yes=$0.55 + No=$0.50 = $1.05 → 无套利 |
| `test_max_shares_uses_smallest_ask_size` | Yes 有 200 份但 No 只有 50 份 → max_shares=50 |
| `test_skips_market_without_order_book` | 无订单簿的市场被跳过 |
| `test_skips_market_with_empty_asks` | 某个结果没有卖单时跳过 |
| `test_sorts_by_gross_profit_descending` | 多个机会按毛利润从大到小排序 |

### 8.2 评估器测试（`test_evaluator.py`，5 个用例）

| 测试 | 验证内容 |
|---|---|
| `test_profitable_candidate_is_scored` | 8% 利润的候选 → 评估后仍盈利 |
| `test_tiny_profit_is_excluded` | 0.1% 利润的候选 → 扣除费用后亏损，被排除 |
| `test_recommended_size_respects_max_position` | 建议数量不超过 MAX_POSITION_SIZE 限制 |
| `test_passes_good_opportunity` | 高利润高流动性的机会通过过滤 |
| `test_rejects_low_liquidity` | 仅 2 份挂单 → 流动性不足被拒 |

---

## 九、完整数据流图

```
                ┌─────────────────────┐
                │   Polymarket CLOB   │
                │       REST API      │
                └──────────┬──────────┘
                           │
                    GET /markets (分页)
                    GET /book (每个Token)
                           │
                ┌──────────▼──────────┐
                │   PolymarketClient  │ ← 底层 HTTP 客户端
                │   (client.py)       │   httpx 异步请求
                └──────────┬──────────┘
                           │
                ┌──────────▼──────────┐
                │   MarketFetcher     │ ← 高层封装
                │   (fetcher.py)      │   60s 缓存 + 并发20限制
                └──────────┬──────────┘
                           │
              List[Market with OrderBook]
                           │
                ┌──────────▼──────────┐
                │  ArbitrageScanner   │ ← 核心扫描
                │  (scanner.py)       │   sum(asks) < 1.0 ?
                └──────────┬──────────┘
                           │
              List[ArbitrageCandidate]
                           │
                ┌──────────▼──────────┐
                │     Evaluator       │ ← 利润计算
                │  (evaluator.py)     │   扣除费用和滑点
                └──────────┬──────────┘
                           │
              List[ScoredOpportunity]
                           │
                ┌──────────▼──────────┐
                │  OpportunityFilter  │ ← 质量过滤
                │  (filters.py)       │   最小利润/流动性/利润率
                └──────────┬──────────┘
                           │
              List[ScoredOpportunity]（已过滤）
                           │
                ┌──────────▼──────────┐
                │    RiskManager      │ ← 风控检查
                │    (risk.py)        │   仓位/敞口/冷却/熔断
                └──────────┬──────────┘
                           │
                ┌──────────▼──────────┐
                │   OrderExecutor     │ ← 下单执行
                │   (executor.py)     │   dry-run 或 live
                └──────────┬──────────┘
                           │
                ┌──────────▼──────────┐
                │   WalletManager     │ ← EIP-712 签名
                │   (wallet.py)       │   py-clob-client SDK
                └──────────┬──────────┘
                           │
                    POST /order → CLOB API
```

每次循环结束后，同时向 Logger → Notifier（Telegram/Discord）和 Dashboard 输出状态。

---

## 十、核心金融概念

### 10.1 做市商（Market Maker）

做市商是同时在订单簿两边挂买单和卖单的交易者，给市场提供流动性，靠买卖之间的价差（Spread）赚钱。

用生活中的例子理解：

```
想象你在景区门口开了一个外币兑换摊位：

  你挂的牌子：
    "我以 ¥6.9 收购美元"  ← 这是你的 Bid（买价）
    "我以 ¥7.1 出售美元"  ← 这是你的 Ask（卖价）

  游客 A 想卖美元 → 你 ¥6.9 买入
  游客 B 想买美元 → 你 ¥7.1 卖出

  你赚了 ¥0.2 的差价（Spread）
```

做市商在 Polymarket 上做的事情一模一样：

```
市场："明天会下雨吗？"

  你挂 Bid $0.48 买 Yes Token（等别人卖给你）
  你挂 Ask $0.52 卖 Yes Token（等别人来买）

  有人急着卖 → 你 $0.48 收了
  有人急着买 → 你 $0.52 卖了

  赚 $0.04 价差
```

做市商的风险：如果你买了一堆 Yes Token（$0.48 买的），结果突然坏消息来了，所有人都不看好 Yes，价格跌到 $0.30，你手里的库存就亏了。所以做市商需要不断调整报价来管理库存。

做市商 vs 普通交易者的区别：

| | 普通交易者 | 做市商 |
|---|---|---|
| 怎么赚钱 | 判断方向：觉得涨就买，跌就卖 | 不判断方向，靠买卖价差赚钱 |
| 挂单方式 | 只挂一边（要么买要么卖） | 两边同时挂（既买又卖） |
| 核心能力 | 预测未来走势 | 管理库存 + 控制风险 |

### 10.2 二元期权（Binary Option）

二元期权是结果只有两种的赌注——要么全拿，要么全没。

```
普通期权：
  你花 $5 买一个期权，到期时赚多少取决于股价涨了多少
  股价涨 $10 → 你赚 $5
  股价涨 $20 → 你赚 $15
  股价跌了  → 你亏 $5（期权费）

  赚多少是"连续"的，可以赚 $1、$2.5、$13.7... 任意值

二元期权：
  你花 $0.45 买一个二元期权
  到期时只有两种结果：
    赢了 → 固定拿回 $1.00（赚 $0.55）
    输了 → 什么都没有（亏 $0.45）

  没有中间值，要么 $1 要么 $0
```

Polymarket 的 Token 本质上就是二元期权：

```
市场："明天会下雨吗？"

  你花 $0.45 买了一个 Yes Token

  明天下雨了 → Yes Token 值 $1.00 → 你赚 $0.55
  明天没下雨 → Yes Token 值 $0.00 → 你亏 $0.45

  只有两种结果，没有"下了一半的雨赚一半钱"这种事
```

Token 价格 = 市场认为事件发生的概率。Yes Token 卖 $0.70 意味着市场认为有 70% 概率会发生。

### 10.3 Black-Scholes 模型

Black-Scholes（布莱克-肖尔斯）是一个期权定价模型，用数学公式计算一个期权"应该"值多少钱。

核心输入：

| 参数 | 含义 | 在 Polymarket 的对应 |
|---|---|---|
| S | 标的资产当前价格 | 用市场中间价或外部信息估算的概率 |
| K | 行权价格 | 对于二元期权，固定为 $0.50 |
| T | 到期时间 | 市场的截止日期距现在多久 |
| r | 无风险利率 | USDC 借贷利率或直接设 0 |
| σ | 波动率 | 从 Token 历史价格波动计算 |

在 Polymarket 的应用：Binary Option 的 Black-Scholes 定价公式可以算出一个 Token 的"理论合理价格"。如果市场价偏离了理论价，就有定价优势。

### 10.4 Avellaneda-Stoikov 模型

Avellaneda-Stoikov 是一个做市商策略模型（2008 年提出），解决的问题是：做市商应该怎么挂买单和卖单，才能既赚到价差，又控制住库存风险。

核心思想——根据库存动态调整报价：

| 状态 | 做市商应该怎么做 |
|---|---|
| 库存太多（买太多了） | 降低报价（Bid 和 Ask 都往下调，赶紧卖掉） |
| 库存太少（卖太多了） | 提高报价（Bid 和 Ask 都往上调，赶紧买回来） |
| 库存平衡 | 在中间价两侧对称报价 |

核心公式：

```
预留价格 = 中间价 - 库存 × 风险厌恶系数 × 波动率² × 剩余时间
报价价差 = 波动率² × 剩余时间 + (2/风险厌恶系数) × ln(1 + 风险厌恶系数/订单到达率)

Bid = 预留价格 - 价差/2
Ask = 预留价格 + 价差/2
```

简单说：库存多了就把报价整体往下偏移，库存少了就往上偏移，波动越大价差越宽。

### 10.5 两个模型在 Polymarket 上的组合应用

把 Black-Scholes 和 Avellaneda-Stoikov 组合起来，可以构建一个完整的做市系统：

```
Black-Scholes  →  给 Token 算出一个"理论合理价格"（定价锚点）
         ↓
Avellaneda-Stoikov  →  围绕这个价格，动态挂买单和卖单赚价差
```

具体流程：

```
1. Black-Scholes 算出 Yes Token 理论价 = $0.50

2. Avellaneda-Stoikov 决定报价：
   当前库存为 0 → 对称挂单
   Bid = $0.48（愿意以 $0.48 买入 Yes）
   Ask = $0.52（愿意以 $0.52 卖出 Yes）

3. 交易发生 → 库存变化 → 模型自动调整报价
   有人来买 → 你 $0.52 卖掉 → 库存减少 → 自动调高 Bid
   有人来卖 → 你 $0.48 买入 → 库存增加 → 自动调低 Ask
```

套利 vs 做市的对比：

| | 套利（Pengullet 目前的策略） | 做市（Black-Scholes + A-S） |
|---|---|---|
| 赚什么钱 | 找到 Sum(Ask)<$1 的定价错误 | 在买卖两边挂单赚价差 |
| 机会频率 | 很少，套利窗口稍纵即逝 | 持续有，只要有人交易就赚 |
| 风险 | 几乎无风险 | 有库存风险（但模型会控制） |
| 资金效率 | 低，等机会出现才能用 | 高，资金一直在工作 |
| 技术门槛 | 低，比较大小即可 | 高，需要定价模型+动态调参 |
| 额外收入 | 无 | Polymarket 有做市商奖励（Liquidity Rewards） |

---

## 十一、学习资源推荐

### 11.1 入门课程（推荐先看这些）

**金融基础 + 期权定价：**

- MIT OpenCourseWare: Finance Theory I (15.401) — 免费，Andrew Lo 教授主讲
  - 网址: https://ocw.mit.edu/courses/15-401-finance-theory-i-fall-2008/
  - 重点看 Options I/II/III 三节课，从零讲到 Black-Scholes 的推导
  - 有视频、课件、习题和答案，全部免费

- Khan Academy: Options, Futures and Other Derivatives — 免费
  - 网址: https://www.khanacademy.org/economics-finance-domain/core-finance/derivative-securities
  - 最友好的入门级别，用动画讲期权基本概念

**做市与微观结构：**

- Stanford CME 241: Reinforcement Learning for Finance
  - 课件: https://web.stanford.edu/class/cme241/lecture_slides/Tour-OrderBook.pdf
  - 免费 PDF，专门讲订单簿、做市策略和 Avellaneda-Stoikov 推导

- OBOE 平台: Avellaneda-Stoikov Framework 教程
  - 网址: https://oboe.com/learn/optimal-order-book-market-making-bg909t/
  - 交互式教程，一步步讲模型的每个组件

**预测市场专项：**

- Polymarket Trading Course
  - 网址: https://polymarketcourse.com/
  - 8 个模块，从预测市场基础到实战策略
  - 涵盖概率思维、寻找定价优势、仓位管理、风控

### 11.2 核心论文

**必读（按优先级排序）：**

1. Avellaneda & Stoikov (2008). "High-frequency trading in a limit order book"
   - 原文 PDF: https://math.nyu.edu/~avellane/HighFrequencyTrading.pdf
   - 做市策略的奠基论文，只有 8 页，数学推导清晰
   - 建议先看完 Stanford 的课件再读

2. Guéant, Lehalle & Fernandez-Tapia (2013). "Dealing with the Inventory Risk: A Solution to the Market Making Problem"
   - 对 Avellaneda-Stoikov 的扩展，加入了更现实的约束条件
   - ArXiv: https://arxiv.org/abs/1105.3115

3. Black & Scholes (1973). "The Pricing of Options and Corporate Liabilities"
   - 经典中的经典，不过原文数学偏难，建议通过课程理解后再看

### 11.3 实战教程

- "[WITH CODE] Market Making: Avellaneda–Stoikov model"
  - 网址: https://www.quantbeckman.com/p/can-you-manage-inventoryor-is-it
  - 带 Python 代码实现的 A-S 模型教程

- "Polymarket API Python Tutorial"
  - 网址: https://robottraders.io/blog/polymarket-api-python-tutorial
  - 用 Python 调用 Polymarket API 的实战教程

- GitHub: ragoragino/avellaneda-stoikov
  - 网址: https://github.com/ragoragino/avellaneda-stoikov
  - A-S 模型的开源 Python 实现，可以直接参考代码

### 11.4 建议学习路线

```
第一周: 理解基础概念
  ├── Khan Academy 期权入门（2-3小时）
  └── Polymarket Trading Course 前 3 个模块

第二周: Black-Scholes 定价
  ├── MIT OCW Finance Theory I — Options 三节课（3小时）
  └── OBOE 平台 Binary Option Pricing 教程

第三周: 做市与 Avellaneda-Stoikov
  ├── Stanford CME 241 订单簿课件
  ├── OBOE 平台 A-S Framework 教程
  └── 阅读 A-S 原始论文（8页）

第四周: 实战
  ├── 跑 Pengullet 的 demo_explore.py 熟悉真实数据
  ├── 参考 GitHub 开源实现写自己的做市策略
  └── 先用 dry-run 模式测试，不要实际交易
```
