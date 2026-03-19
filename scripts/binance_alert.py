#!/usr/bin/env python3
"""
BinanceAlert — openclaw 技能脚本
复用 /data/freqtrade/user_data/.secrets.env 中的 TG_BOT_TOKEN / TG_CHAT_ID
状态持久化到 /data/freqtrade/user_data/binance_alert_state.json

用法:
  python3 binance_alert.py price BTCUSDT 100000 above     # 价格预警
  python3 binance_alert.py change ETHUSDT 5               # 涨跌幅预警（%）
  python3 binance_alert.py listing                        # 检查新币上线
  python3 binance_alert.py alpha                          # Alpha空投机会
  python3 binance_alert.py announcement                   # 币安公告/HODLer空投
  python3 binance_alert.py run                            # 一次性跑全部检查（供定时任务用）
  python3 binance_alert.py status                         # 查看当前预警状态
"""

import sys
import os
import json
import time
import urllib.request
import urllib.parse
import gzip
import re
from pathlib import Path
from datetime import datetime

# ── 配置 ──────────────────────────────────────────────────────────────────────
ENV_FILE = Path("/data/freqtrade/user_data/.secrets.env")
STATE_FILE = Path("/data/freqtrade/user_data/binance_alert_state.json")
BINANCE_API = "https://api.binance.com"
BINANCE_WEB3 = "https://web3.binance.com"
BINANCE_CMS = "https://www.binance.com"


def load_env():
    if not ENV_FILE.exists():
        return
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


load_env()
TG_TOKEN = os.getenv("TG_BOT_TOKEN", "")
TG_CHAT = os.getenv("TG_CHAT_ID", "")


# ── 工具函数 ──────────────────────────────────────────────────────────────────
def http_get(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {
        "User-Agent": "Mozilla/5.0",
        "Accept-Encoding": "gzip"
    })
    with urllib.request.urlopen(req, timeout=15) as r:
        raw = r.read()
        if r.info().get("Content-Encoding") == "gzip":
            raw = gzip.decompress(raw)
        return json.loads(raw)


def http_post(url, data, headers=None):
    body = json.dumps(data).encode()
    h = {"Content-Type": "application/json", "Accept-Encoding": "identity"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, data=body, headers=h)
    with urllib.request.urlopen(req, timeout=15) as r:
        raw = r.read()
        if r.info().get("Content-Encoding") == "gzip":
            raw = gzip.decompress(raw)
        return json.loads(raw)


def tg_send(text):
    if not TG_TOKEN or not TG_CHAT:
        print(f"[TG未配置] {text}")
        return
    try:
        http_post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            {"chat_id": TG_CHAT, "text": text, "parse_mode": "Markdown"}
        )
    except Exception as e:
        print(f"TG发送失败: {e}")


def load_state():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {
        "price_alerts": [],
        "change_alerts": [],
        "known_symbols": [],
        "seen_announcements": [],
        "last_check": {}
    }


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2))


def out(data):
    print(json.dumps(data, ensure_ascii=False, indent=2))


# ── 1. 价格预警 ───────────────────────────────────────────────────────────────
def add_price_alert(symbol, target_price, condition="above", note=""):
    """condition: above / below"""
    state = load_state()
    symbol = symbol.upper()
    alert = {
        "id": f"price_{symbol}_{int(time.time())}",
        "symbol": symbol,
        "target_price": float(target_price),
        "condition": condition,
        "note": note,
        "created_at": datetime.now().isoformat(),
        "triggered": False
    }
    state["price_alerts"].append(alert)
    save_state(state)
    out({"action": "price_alert_added", "alert": alert})


def check_price_alerts(state):
    if not state["price_alerts"]:
        return
    triggered_ids = []
    for alert in state["price_alerts"]:
        if alert.get("triggered"):
            continue
        try:
            data = http_get(f"{BINANCE_API}/api/v3/ticker/price?symbol={alert['symbol']}")
            price = float(data["price"])
            hit = (alert["condition"] == "above" and price >= alert["target_price"]) or \
                  (alert["condition"] == "below" and price <= alert["target_price"])
            if hit:
                msg = (f"📈 *价格预警触发*\n\n"
                       f"交易对: *{alert['symbol']}*\n"
                       f"当前价格: `{price}`\n"
                       f"目标价格: `{alert['target_price']}` ({alert['condition']})\n"
                       f"备注: {alert.get('note', '')}\n"
                       f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                tg_send(msg)
                alert["triggered"] = True
                triggered_ids.append(alert["id"])
                print(f"[价格预警] {alert['symbol']} 触发: {price}")
        except Exception as e:
            print(f"[价格预警] {alert['symbol']} 检查失败: {e}")
    return triggered_ids


# ── 2. 涨跌幅预警 ─────────────────────────────────────────────────────────────
def add_change_alert(symbol, threshold_pct, note=""):
    state = load_state()
    symbol = symbol.upper()
    alert = {
        "id": f"change_{symbol}_{int(time.time())}",
        "symbol": symbol,
        "threshold_pct": float(threshold_pct),
        "note": note,
        "created_at": datetime.now().isoformat(),
        "triggered": False
    }
    state["change_alerts"].append(alert)
    save_state(state)
    out({"action": "change_alert_added", "alert": alert})


def check_change_alerts(state):
    if not state["change_alerts"]:
        return
    for alert in state["change_alerts"]:
        if alert.get("triggered"):
            continue
        try:
            data = http_get(f"{BINANCE_API}/api/v3/ticker/24hr?symbol={alert['symbol']}")
            change = float(data["priceChangePercent"])
            if abs(change) >= alert["threshold_pct"]:
                direction = "📈" if change > 0 else "📉"
                msg = (f"{direction} *涨跌幅预警触发*\n\n"
                       f"交易对: *{alert['symbol']}*\n"
                       f"24h涨跌: `{change:+.2f}%`\n"
                       f"阈值: `±{alert['threshold_pct']}%`\n"
                       f"当前价: `{data['lastPrice']}`\n"
                       f"备注: {alert.get('note', '')}\n"
                       f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                tg_send(msg)
                alert["triggered"] = True
                print(f"[涨跌幅预警] {alert['symbol']} 触发: {change:+.2f}%")
        except Exception as e:
            print(f"[涨跌幅预警] {alert['symbol']} 检查失败: {e}")


# ── 3. 新币上线监控 ───────────────────────────────────────────────────────────
def check_new_listings(state):
    try:
        data = http_get(f"{BINANCE_API}/api/v3/exchangeInfo")
        current = {s["symbol"] for s in data["symbols"] if s["status"] == "TRADING"}
        known = set(state.get("known_symbols", []))

        if not known:
            # 首次运行，只记录不报警
            state["known_symbols"] = list(current)
            save_state(state)
            print(f"[新币监控] 初始化完成，记录 {len(current)} 个交易对")
            return

        new_ones = current - known
        if new_ones:
            usdt_new = [s for s in new_ones if s.endswith("USDT")]
            if usdt_new:
                msg = (f"🚀 *新币上线提醒*\n\n"
                       f"发现 *{len(usdt_new)}* 个新 USDT 交易对:\n"
                       + "\n".join(f"• `{s}`" for s in sorted(usdt_new)) +
                       f"\n\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                       f"⚠️ 新币高波动，注意风险")
                tg_send(msg)
                print(f"[新币监控] 发现新币: {usdt_new}")
            state["known_symbols"] = list(current)
            save_state(state)
        else:
            print(f"[新币监控] 无新币，共 {len(current)} 个交易对")
    except Exception as e:
        print(f"[新币监控] 检查失败: {e}")


# ── 4. Alpha 空投监控 ─────────────────────────────────────────────────────────
def check_alpha_airdrop(state, min_score=50, min_kyc=500):
    try:
        data = http_post(
            f"{BINANCE_WEB3}/bapi/defi/v1/public/wallet-direct/buw/wallet/market/token/pulse/unified/rank/list",
            {"rankType": 20, "period": 50, "sortBy": 80, "orderAsc": False, "page": 1, "size": 50}
        )
        if data.get("code") != "000000":
            print(f"[Alpha] API返回异常: {data.get('message')}")
            return

        tokens = data.get("data", {}).get("tokens", [])
        opportunities = []

        for t in tokens:
            kyc = int(t.get("kycHolders") or 0)
            vol = float(t.get("volume24h") or 0)
            change = float(t.get("percentChange24h") or 0)
            mcap = float(t.get("marketCap") or 0)
            risk = t.get("auditInfo", {}).get("riskLevel", 99)

            # 提取 alpha points
            alpha_pts = 0
            for cat in (t.get("tokenTag") or {}).values():
                for tag in cat:
                    name = tag.get("tagName", "")
                    if "Alpha Points" in name or "alpha-points" in tag.get("languageKey", ""):
                        m = re.search(r"(\d+)x", name)
                        alpha_pts = int(m.group(1)) if m else 1

            score = 0
            reasons = []
            if kyc / max(int(t.get("holders") or 1), 1) > 0.3:
                score += 20; reasons.append("KYC比例高")
            if vol > 1_000_000:
                score += 15; reasons.append("交易量活跃")
            if -5 < change < 50:
                score += 10; reasons.append("价格走势健康")
            if 1_000_000 < mcap < 100_000_000:
                score += 15; reasons.append("市值适中")
            if risk == 1:
                score += 10; reasons.append("合约低风险")
            if alpha_pts > 0:
                score += 30; reasons.append(f"Alpha积分{alpha_pts}x")

            if score >= min_score and kyc >= min_kyc:
                opportunities.append({
                    "symbol": t.get("symbol"),
                    "score": score,
                    "kyc_holders": kyc,
                    "alpha_pts": alpha_pts,
                    "change_24h": change,
                    "reasons": reasons
                })

        if opportunities:
            opportunities.sort(key=lambda x: -x["score"])
            lines = []
            for o in opportunities[:5]:
                lines.append(
                    f"• *${o['symbol']}* ⭐{o['score']}分\n"
                    f"  KYC持有者: {o['kyc_holders']:,} | Alpha积分: {o['alpha_pts']}x\n"
                    f"  亮点: {', '.join(o['reasons'][:2])}"
                )
            msg = (f"🎯 *Alpha空投机会*\n\n"
                   f"发现 *{len(opportunities)}* 个高潜力代币:\n\n"
                   + "\n\n".join(lines) +
                   f"\n\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                   f"⚠️ 仅供参考，不构成投资建议")
            tg_send(msg)
            print(f"[Alpha] 发现 {len(opportunities)} 个机会")
        else:
            print(f"[Alpha] 无符合条件的机会（共扫描 {len(tokens)} 个代币）")
    except Exception as e:
        print(f"[Alpha] 检查失败: {e}")


# ── 5. 币安公告/HODLer空投监控 ───────────────────────────────────────────────
def check_announcements(state):
    seen = set(state.get("seen_announcements", []))
    new_seen = []
    found = []

    for catalog_id in [48, 161]:  # 新币上线 + 空投
        try:
            data = http_get(
                f"{BINANCE_CMS}/bapi/composite/v1/public/cms/article/catalog/list/query"
                f"?catalogId={catalog_id}&pageNo=1&pageSize=10",
                headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
            )
            articles = (data.get("data") or {}).get("articles") or []
            for a in articles:
                aid = str(a.get("id", ""))
                if aid in seen:
                    continue
                title = a.get("title", "")
                # 只关注 Alpha / HODLer / 空投 / 新币
                keywords = ["Alpha", "HODLer", "空投", "Airdrop", "Will List", "上线"]
                if any(kw.lower() in title.lower() for kw in keywords):
                    found.append({"id": aid, "title": title, "catalog": catalog_id})
                new_seen.append(aid)
        except Exception as e:
            print(f"[公告] catalog={catalog_id} 获取失败: {e}")

    if found:
        lines = "\n".join(f"• {f['title']}" for f in found)
        msg = (f"📢 *币安公告提醒*\n\n"
               f"发现 *{len(found)}* 条新公告:\n\n{lines}\n\n"
               f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
               f"🔗 请前往币安查看详情")
        tg_send(msg)
        print(f"[公告] 发现 {len(found)} 条新公告")
    else:
        print(f"[公告] 无新公告")

    # 更新 seen，只保留最近 500 条
    all_seen = list(seen) + new_seen
    state["seen_announcements"] = all_seen[-500:]
    save_state(state)


# ── 查看状态 ──────────────────────────────────────────────────────────────────
def show_status():
    state = load_state()
    active_price = [a for a in state.get("price_alerts", []) if not a.get("triggered")]
    active_change = [a for a in state.get("change_alerts", []) if not a.get("triggered")]
    out({
        "active_price_alerts": active_price,
        "active_change_alerts": active_change,
        "known_symbols_count": len(state.get("known_symbols", [])),
        "seen_announcements_count": len(state.get("seen_announcements", [])),
        "last_check": state.get("last_check", {})
    })


# ── 全量检查（定时任务入口）──────────────────────────────────────────────────
def run_all():
    state = load_state()
    print(f"[BinanceAlert] 开始全量检查 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    check_price_alerts(state)
    check_change_alerts(state)
    check_new_listings(state)
    check_alpha_airdrop(state)
    check_announcements(state)
    state["last_check"]["run_all"] = datetime.now().isoformat()
    save_state(state)
    print("[BinanceAlert] 全量检查完成")


# ── 入口 ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(0)

    action = args[0]

    if action == "price":
        if len(args) < 3:
            print("用法: price <SYMBOL> <目标价> [above|below]")
        else:
            add_price_alert(args[1], args[2], args[3] if len(args) > 3 else "above",
                            " ".join(args[4:]))
    elif action == "change":
        if len(args) < 3:
            print("用法: change <SYMBOL> <涨跌幅%>")
        else:
            add_change_alert(args[1], args[2], " ".join(args[3:]))
    elif action == "listing":
        state = load_state()
        check_new_listings(state)
    elif action == "alpha":
        state = load_state()
        check_alpha_airdrop(state)
    elif action == "announcement":
        state = load_state()
        check_announcements(state)
    elif action == "run":
        run_all()
    elif action == "status":
        show_status()
    else:
        print(f"未知操作: {action}")
        sys.exit(1)
