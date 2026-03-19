---
name: binance-alert
description: 币安智能预警系统。监控价格/涨跌幅预警、新币上线、Alpha空投机会、HODLer空投公告，通过 Telegram 实时推送。无需 API Key。
homepage: https://github.com/jian28277-hash/BinanceAlert-skill
metadata: {"clawdbot":{"emoji":"🔔","requires":{"bins":["python3"]}}}
---

# 币安预警 (BinanceAlert)

监控币安市场动态，通过 Telegram 实时推送。复用系统已配置的 TG_BOT_TOKEN / TG_CHAT_ID。

## 设置价格预警

```bash
python3 {baseDir}/scripts/binance_alert.py price <SYMBOL> <目标价> [above|below]
```

示例：BTC 突破 10 万时提醒
```bash
python3 {baseDir}/scripts/binance_alert.py price BTCUSDT 100000 above
```

## 设置涨跌幅预警

```bash
python3 {baseDir}/scripts/binance_alert.py change <SYMBOL> <涨跌幅%>
```

示例：ETH 24h 涨跌超过 8% 时提醒
```bash
python3 {baseDir}/scripts/binance_alert.py change ETHUSDT 8
```

## 检查新币上线

```bash
python3 {baseDir}/scripts/binance_alert.py listing
```

## 检查 Alpha 空投机会

```bash
python3 {baseDir}/scripts/binance_alert.py alpha
```

扫描 Binance Web3 Alpha 代币，按 KYC 持有者、积分倍数、市值等维度评分，推送高潜力机会。

## 检查币安公告（HODLer 空投）

```bash
python3 {baseDir}/scripts/binance_alert.py announcement
```

监控新币上线公告、HODLer 空投、Alpha 空投等官方公告。

## 全量检查（定时任务）

```bash
python3 {baseDir}/scripts/binance_alert.py run
```

一次性执行所有检查，供 systemd timer 调用。

## 查看当前预警状态

```bash
python3 {baseDir}/scripts/binance_alert.py status
```

Notes:
- 状态持久化到 /data/freqtrade/user_data/binance_alert_state.json
- 价格/涨跌幅预警触发一次后自动标记为已触发，不重复推送
- 新币监控首次运行只建立基线，不推送
- 建议用 systemd timer 每 5 分钟跑一次 run 命令
