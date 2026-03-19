# BinanceAlert OpenClaw Skill 🔔

币安智能预警系统 — OpenClaw 技能

## 功能

| 功能 | 描述 |
|------|------|
| 📈 价格预警 | 代币达到目标价时 Telegram 通知 |
| 📊 涨跌幅预警 | 24h 涨跌超阈值时提醒 |
| 🚀 新币上线监控 | 币安新交易对自动推送 |
| 🎯 Alpha空投监控 | 高潜力空投代币发现 |
| 📢 HODLer空投公告 | 币安官方公告实时推送 |

## 安装

```bash
cp -r binance-alert-skill /root/.openclaw/workspace/skills/binance-alert
```

## 使用

```
→ "帮我设置 BTC 突破 10 万的价格预警"
→ "ETH 涨跌超 10% 提醒我"
→ "查一下现在有没有 Alpha 空投机会"
→ "看看币安最新公告"
→ "查看当前有哪些预警"
```

## 依赖

- Python 3（纯标准库，无需额外安装）
- 复用 `/data/freqtrade/user_data/.secrets.env` 中的 `TG_BOT_TOKEN` / `TG_CHAT_ID`

## License

MIT
