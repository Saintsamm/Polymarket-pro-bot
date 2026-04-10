# ================================================================
#   POLYMARKET PRO BOT — Claude AI + Live Data + Telegram Alerts
#   Full Professional Analysis with 15min price action monitoring
# ================================================================

import os, json, time, schedule, requests, anthropic
import pandas as pd
import numpy as np
from datetime import datetime
from telegram import Bot
from telegram.error import TelegramError

# ── YOUR KEYS ────────────────────────────────────────────────────
ANTHROPIC_KEY    = os.environ.get("ANTHROPIC_API_KEY")
POLY_PRIVATE_KEY = os.environ.get("POLY_PRIVATE_KEY")
POLY_API_KEY     = os.environ.get("POLY_API_KEY")
POLY_API_SECRET  = os.environ.get("POLY_API_SECRET")
POLY_API_PASS    = os.environ.get("POLY_API_PASSPHRASE")
COINGECKO_KEY    = os.environ.get("COINGECKO_API_KEY")
TELEGRAM_TOKEN   = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# ── CLIENTS ───────────────────────────────────────────────────────
claude   = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
telegram = Bot(token=TELEGRAM_TOKEN)

# ================================================================
#   ⚙️  YOUR TRADING SETTINGS
# ================================================================
BANKROLL         = 100.00
MAX_TRADE_SIZE   = 12.00
MIN_EDGE         = 0.12
MIN_CONFIDENCE   = 7
DAILY_LOSS_CAP   = 20.00
MIN_VOLUME       = 1000
MAX_DAILY_TRADES = 5
SCAN_INTERVAL    = 15   # minutes between each scan

# ── TRACKING ──────────────────────────────────────────────────────
daily_pnl      = 0.0
trades_today   = 0
open_positions = []
scan_count     = 0

# ── CRYPTO MAP ────────────────────────────────────────────────────
CRYPTO_MAP = {
    "bitcoin":"bitcoin","btc":"bitcoin",
    "ethereum":"ethereum","eth":"ethereum",
    "solana":"solana","sol":"solana",
    "bnb":"binancecoin","xrp":"ripple","ripple":"ripple",
    "dogecoin":"dogecoin","doge":"dogecoin",
    "cardano":"cardano","ada":"cardano",
    "avalanche":"avalanche-2","avax":"avalanche-2",
    "chainlink":"chainlink","link":"chainlink",
    "polygon":"matic-network","matic":"matic-network",
    "polkadot":"polkadot","dot":"polkadot",
    "litecoin":"litecoin","ltc":"litecoin",
    "shiba":"shiba-inu","shib":"shiba-inu",
    "pepe":"pepe","sui":"sui","aptos":"aptos","apt":"aptos",
}


# ================================================================
#   TELEGRAM NOTIFICATION SYSTEM
#   Sends all bot activity directly to your Telegram
# ================================================================
def send_telegram(message, parse_mode="HTML"):
    """Sends a message to your Telegram account."""
    try:
        telegram.send_message(
            chat_id    = TELEGRAM_CHAT_ID,
            text       = message,
            parse_mode = parse_mode
        )
        print(f"📱 Telegram sent: {message[:60]}...")
    except TelegramError as e:
        print(f"⚠️  Telegram error: {e}")
    except Exception as e:
        print(f"⚠️  Telegram error: {e}")


def telegram_startup():
    """Sends startup message to Telegram."""
    msg = f"""
🤖 <b>POLYMARKET PRO BOT STARTED</b>

━━━━━━━━━━━━━━━━━━━━━━
💰 Capital: <b>${BANKROLL:.2f}</b>
📊 Max per trade: <b>${MAX_TRADE_SIZE:.2f}</b>
🎯 Min edge: <b>{MIN_EDGE*100:.0f}%</b>
🛑 Daily loss cap: <b>${DAILY_LOSS_CAP:.2f}</b>
🔢 Max trades/day: <b>{MAX_DAILY_TRADES}</b>
🌐 Web search: <b>ENABLED ✅</b>
💰 Live prices: <b>ENABLED ✅</b>
📈 Indicators: <b>20+ ✅</b>
⏱ Scanning every: <b>{SCAN_INTERVAL} minutes</b>
━━━━━━━━━━━━━━━━━━━━━━
🕐 Started: {datetime.now().strftime('%d %b %Y %H:%M')}

Bot is now watching markets 24/7.
You will receive alerts for every scan and trade.
    """
    send_telegram(msg)


def telegram_scan_start(scan_num, markets_found):
    """Notifies Telegram when a new scan begins."""
    msg = f"""
🔍 <b>SCAN #{scan_num} STARTED</b>
🕐 {datetime.now().strftime('%d %b %Y %H:%M')}
📡 Markets found: <b>{markets_found}</b>
💼 Trades today: <b>{trades_today}/{MAX_DAILY_TRADES}</b>
📈 Today P&L: <b>${daily_pnl:+.2f}</b>

Analyzing markets with live data...
    """
    send_telegram(msg)


def telegram_market_analysis(market, analysis, data_report):
    """Sends detailed analysis of each market to Telegram."""
    action   = analysis.get("action","SKIP")
    edge     = float(analysis.get("edge", 0))
    conf     = analysis.get("confidence", 0)
    prob     = analysis.get("true_yes_probability", 0)
    reason   = analysis.get("reason","")
    bullish  = analysis.get("bullish_signals",[])
    bearish  = analysis.get("bearish_signals",[])
    ind      = data_report.get("indicators",{})

    icons = {"BUY_YES":"🟢","BUY_NO":"🔴","SKIP":"⚪"}
    icon  = icons.get(action,"⚪")

    # Only send to Telegram if action is BUY or if high confidence SKIP
    if action == "SKIP" and conf < 6:
        return  # Skip low-interest markets to avoid spam

    price_line = ""
    if data_report.get("has_crypto_data"):
        price_line = f"""
💰 Live price: <b>${data_report.get('current_price',0):,.2f}</b> ({data_report.get('change_24h',0):+.2f}% 24h)
📈 Trend: <b>{ind.get('TREND_BIAS','N/A')}</b> | RSI: <b>{ind.get('RSI','N/A')}</b>
🎯 Support: <b>${ind.get('SUPPORT_1','?')}</b> | Resistance: <b>${ind.get('RESISTANCE_1','?')}</b>"""

    bullish_str = "\n".join([f"  ✅ {s}" for s in bullish[:3]]) if bullish else "  None"
    bearish_str = "\n".join([f"  ❌ {s}" for s in bearish[:2]]) if bearish else "  None"

    msg = f"""
{icon} <b>MARKET ANALYSIS</b>

📋 <b>{market['question'][:80]}</b>
━━━━━━━━━━━━━━━━━━━━━━{price_line}
📊 Market price: YES={market['yes_price']} ({market['yes_price']*100:.0f}%)
🧠 Claude estimate: <b>{prob*100:.0f}%</b> chance YES
📈 Edge found: <b>{edge:+.1%}</b>
🎯 Confidence: <b>{conf}/10</b>

<b>Bullish signals:</b>
{bullish_str}

<b>Bearish signals:</b>
{bearish_str}

📋 Decision: <b>{action}</b>
💬 Reason: {reason[:100]}
━━━━━━━━━━━━━━━━━━━━━━
    """
    send_telegram(msg)


def telegram_trade_placed(market, analysis, result):
    """Sends trade confirmation to Telegram."""
    action = analysis.get("action","SKIP")
    stake  = analysis.get("stake", 0)
    price  = market["yes_price"] if action=="BUY_YES" else market["no_price"]
    shares = round(float(stake)/float(price), 2) if price > 0 else 0
    profit = round(shares - float(stake), 2)

    msg = f"""
💸 <b>TRADE PLACED!</b> 

━━━━━━━━━━━━━━━━━━━━━━
📋 Market: <b>{market['question'][:70]}</b>
━━━━━━━━━━━━━━━━━━━━━━
📊 Action: <b>{action}</b>
💰 Stake: <b>${stake:.2f}</b>
📈 Price: <b>${price}</b>
🔢 Shares: <b>{shares:.2f}</b>
💵 Potential profit: <b>${profit:.2f}</b>
🆔 Order ID: <b>{result}</b>

🕐 Time: {datetime.now().strftime('%d %b %Y %H:%M')}
📂 Total open positions: {len(open_positions)+1}
📈 Trades today: {trades_today+1}/{MAX_DAILY_TRADES}
━━━━━━━━━━━━━━━━━━━━━━
    """
    send_telegram(msg)


def telegram_trade_failed(market, analysis, reason):
    """Notifies Telegram when a trade fails — manual action needed."""
    action = analysis.get("action","SKIP")
    stake  = analysis.get("stake", 0)
    price  = market["yes_price"] if action=="BUY_YES" else market["no_price"]

    msg = f"""
⚠️ <b>MANUAL TRADE NEEDED!</b>

Auto-trade failed. Please place this manually:

━━━━━━━━━━━━━━━━━━━━━━
📋 Market: <b>{market['question'][:70]}</b>
📊 Action: <b>{action}</b>
💰 Amount: <b>${stake:.2f}</b>
📈 Price: <b>${price}</b>
━━━━━━━━━━━━━━━━━━━━━━
👉 Go to polymarket.com and place this trade now!

❌ Reason it failed: {reason[:80]}
    """
    send_telegram(msg)


def telegram_no_trades():
    """Notifies Telegram when no trades found this scan."""
    msg = f"""
⏭️ <b>SCAN COMPLETE — No trades this round</b>

No markets met our criteria this scan.
💼 Trades today: {trades_today}/{MAX_DAILY_TRADES}
📈 Today P&L: ${daily_pnl:+.2f}
⏱ Next scan in {SCAN_INTERVAL} minutes.
    """
    send_telegram(msg)


def telegram_daily_summary():
    """Sends end of day summary to Telegram."""
    positions_text = ""
    if open_positions:
        positions_text = "\n<b>Open trades:</b>"
        for p in open_positions:
            positions_text += f"\n  [{p['time']}] {p['action']} ${p['stake']:.2f} → {p['question'][:35]}..."

    msg = f"""
📊 <b>DAILY SUMMARY</b>
{datetime.now().strftime('%d %b %Y')}

━━━━━━━━━━━━━━━━━━━━━━
💰 Starting capital: <b>${BANKROLL:.2f}</b>
📈 Today's P&L: <b>${daily_pnl:+.2f}</b>
🔢 Trades placed: <b>{trades_today}/{MAX_DAILY_TRADES}</b>
📂 Open positions: <b>{len(open_positions)}</b>
🛡️ Loss cap remaining: <b>${DAILY_LOSS_CAP+daily_pnl:.2f}</b>
{positions_text}
━━━━━━━━━━━━━━━━━━━━━━
Bot continues running overnight.
    """
    send_telegram(msg)


def telegram_error(error_msg):
    """Sends error alerts to Telegram."""
    msg = f"""
🚨 <b>BOT ERROR ALERT</b>

❌ Error: {error_msg[:200]}

🕐 Time: {datetime.now().strftime('%d %b %Y %H:%M')}
Bot will retry on next scan.
    """
    send_telegram(msg)


def telegram_loss_cap_hit():
    """Notifies when daily loss cap is reached."""
    msg = f"""
🛑 <b>DAILY LOSS CAP REACHED</b>

The bot has hit the daily loss limit of <b>${DAILY_LOSS_CAP:.2f}</b>

📈 Today's P&L: <b>${daily_pnl:+.2f}</b>
🔢 Trades today: <b>{trades_today}</b>

Bot has STOPPED trading for today.
Will resume tomorrow automatically.
Your remaining capital is protected. 🛡️
    """
    send_telegram(msg)


# ================================================================
#   LIVE DATA FETCHING
# ================================================================
def detect_crypto(question):
    q = question.lower()
    for keyword, coin_id in CRYPTO_MAP.items():
        if keyword in q:
            return coin_id
    return None


def fetch_current_price(coin_id):
    try:
        url    = "https://api.coingecko.com/api/v3/simple/price"
        params = {
            "ids"                : coin_id,
            "vs_currencies"      : "usd",
            "include_24hr_vol"   : True,
            "include_24hr_change": True,
            "include_market_cap" : True,
            "x_cg_demo_api_key"  : COINGECKO_KEY
        }
        r    = requests.get(url, params=params, timeout=10)
        data = r.json().get(coin_id, {})
        return {
            "current_price": data.get("usd", 0),
            "market_cap"   : data.get("usd_market_cap", 0),
            "volume_24h"   : data.get("usd_24h_vol", 0),
            "change_24h"   : data.get("usd_24h_change", 0),
        }
    except Exception as e:
        return {}


def fetch_ohlcv(coin_id, days=90):
    try:
        url    = f"https://api.coingecko.com/api/v3/coins/{coin_id}/ohlc"
        params = {"vs_currency":"usd","days":days,"x_cg_demo_api_key":COINGECKO_KEY}
        r      = requests.get(url, params=params, timeout=15)
        data   = r.json()
        if not data or not isinstance(data, list):
            return None
        df = pd.DataFrame(data, columns=["timestamp","open","high","low","close"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        return df.sort_values("timestamp").reset_index(drop=True)
    except:
        return None


def fetch_volume_history(coin_id, days=30):
    try:
        url    = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
        params = {"vs_currency":"usd","days":days,"interval":"daily","x_cg_demo_api_key":COINGECKO_KEY}
        r      = requests.get(url, params=params, timeout=15)
        data   = r.json()
        return {
            "volumes": [v[1] for v in data.get("total_volumes",[])],
            "prices" : [p[1] for p in data.get("prices",[])]
        }
    except:
        return {}


# ================================================================
#   TECHNICAL INDICATORS
# ================================================================
def calculate_indicators(df):
    if df is None or len(df) < 20:
        return {}
    close = df["close"].values
    high  = df["high"].values
    low   = df["low"].values
    r     = {}

    try:
        # Moving Averages
        r["MA7"]   = float(np.mean(close[-7:]))
        r["MA20"]  = float(np.mean(close[-20:]))
        r["MA50"]  = float(np.mean(close[-50:])) if len(close)>=50 else None
        r["MA200"] = float(np.mean(close[-200:])) if len(close)>=200 else None

        # EMA
        def ema(data, p):
            k = 2/(p+1); v = data[0]
            for x in data[1:]: v = x*k + v*(1-k)
            return v
        r["EMA12"] = ema(close, 12)
        r["EMA26"] = ema(close, 26)

        # MACD
        macd = r["EMA12"] - r["EMA26"]
        r["MACD_line"]   = round(macd, 2)
        r["MACD_signal"] = "BULLISH" if macd > 0 else "BEARISH"

        # RSI
        def rsi(data, p=14):
            d = np.diff(data[-p-1:])
            g = np.where(d>0,d,0); l = np.where(d<0,-d,0)
            ag = np.mean(g) if g.any() else 0.001
            al = np.mean(l) if l.any() else 0.001
            return round(100-(100/(1+ag/al)),2)
        r["RSI"] = rsi(close)
        r["RSI_signal"] = (
            "OVERSOLD"   if r["RSI"] < 30 else
            "OVERBOUGHT" if r["RSI"] > 70 else "NEUTRAL"
        )

        # Bollinger Bands
        bm = np.mean(close[-20:]); bs = np.std(close[-20:])
        r["BB_upper"]  = round(bm + 2*bs, 2)
        r["BB_lower"]  = round(bm - 2*bs, 2)
        r["BB_middle"] = round(bm, 2)
        r["BB_signal"] = (
            "Near LOWER band — potential bounce"   if close[-1] <= (bm-2*bs)*1.02 else
            "Near UPPER band — potential pullback" if close[-1] >= (bm+2*bs)*0.98 else
            "Within normal range"
        )

        # Stochastic
        hh = np.max(high[-14:]); ll = np.min(low[-14:])
        sk = ((close[-1]-ll)/(hh-ll))*100 if hh!=ll else 50
        r["STOCH_K"]      = round(sk,2)
        r["STOCH_signal"] = "OVERSOLD" if sk<20 else "OVERBOUGHT" if sk>80 else "NEUTRAL"

        # ATR
        trs = [max(high[i]-low[i],abs(high[i]-close[i-1]),abs(low[i]-close[i-1]))
               for i in range(-14,0)]
        r["ATR"]        = round(np.mean(trs),2)
        r["ATR_pct"]    = round((r["ATR"]/close[-1])*100,2)
        r["VOLATILITY"] = "HIGH" if r["ATR_pct"]>5 else "MEDIUM" if r["ATR_pct"]>2 else "LOW"

        # Support and Resistance
        r["RESISTANCE_1"] = round(float(sorted(high[-30:],reverse=True)[0]),2)
        r["RESISTANCE_2"] = round(float(sorted(high[-30:],reverse=True)[2]),2)
        r["SUPPORT_1"]    = round(float(sorted(low[-30:])[0]),2)
        r["SUPPORT_2"]    = round(float(sorted(low[-30:])[2]),2)
        r["DISTANCE_TO_R1"] = round(((r["RESISTANCE_1"]-close[-1])/close[-1])*100,2)
        r["DISTANCE_TO_S1"] = round(((close[-1]-r["SUPPORT_1"])/close[-1])*100,2)

        # Pivot Points
        pv = (high[-1]+low[-1]+close[-1])/3
        r["PIVOT"]    = round(pv,2)
        r["PIVOT_R1"] = round(2*pv-low[-1],2)
        r["PIVOT_S1"] = round(2*pv-high[-1],2)

        # Trend
        ts = "UP" if close[-1]>r["MA7"]  else "DOWN"
        tm = "UP" if close[-1]>r["MA20"] else "DOWN"
        tl = "UP" if (r["MA50"]  and close[-1]>r["MA50"])  else "DOWN"
        r["TREND_SHORT"] = ts
        r["TREND_MID"]   = tm
        r["TREND_LONG"]  = tl
        r["TREND_BIAS"]  = "BULLISH" if [ts,tm,tl].count("UP")>=2 else "BEARISH"
        r["MA_CROSS"]    = "GOLDEN CROSS" if (r["MA50"] and r["MA200"] and r["MA50"]>r["MA200"]) else "DEATH CROSS" if (r["MA50"] and r["MA200"]) else "N/A"

        # Momentum
        r["MOMENTUM_7D"]  = round(((close[-1]-close[-7])/close[-7])*100,2)
        r["MOMENTUM_14D"] = round(((close[-1]-close[-14])/close[-14])*100,2)

        # 52 week
        r["HIGH_52W"] = round(float(np.max(high)),2)
        r["LOW_52W"]  = round(float(np.min(low)),2)
        pos = ((close[-1]-r["LOW_52W"])/(r["HIGH_52W"]-r["LOW_52W"]))*100
        r["PRICE_POSITION_52W"] = round(pos,2)

    except Exception as e:
        print(f"   ⚠️ Indicator error: {e}")

    return r


def analyze_liquidity(volume_data):
    if not volume_data or not volume_data.get("volumes"):
        return {}
    vols = volume_data["volumes"]
    prices = volume_data.get("prices",[])
    avg7  = np.mean(vols[-7:])
    avg30 = np.mean(vols[-30:]) if len(vols)>=30 else np.mean(vols)
    trend = "INCREASING" if avg7 > avg30 else "DECREASING"
    spike = vols[-1] > avg30*1.5 if vols else False
    price_chg = ((prices[-1]-prices[-7])/prices[-7])*100 if len(prices)>=7 else 0
    if price_chg>0 and trend=="INCREASING":   pv = "BULLISH — rising price + rising volume"
    elif price_chg>0 and trend=="DECREASING": pv = "WARNING — rising price + falling volume"
    elif price_chg<0 and trend=="INCREASING": pv = "BEARISH — falling price + rising volume"
    else:                                      pv = "BEARISH — falling price + falling volume"
    score = 5
    if avg30>1e9: score+=3
    elif avg30>1e8: score+=2
    elif avg30>1e7: score+=1
    if trend=="INCREASING": score+=1
    if spike: score+=1
    score = min(score,10)
    return {
        "avg_volume_7d"   : round(avg7,0),
        "avg_volume_30d"  : round(avg30,0),
        "volume_trend"    : trend,
        "volume_spike"    : "YES" if spike else "NO",
        "pv_signal"       : pv,
        "liquidity_score" : score,
        "liquidity_rating": "EXCELLENT" if score>=8 else "GOOD" if score>=6 else "FAIR" if score>=4 else "POOR"
    }


# ================================================================
#   BUILD FULL DATA REPORT
# ================================================================
def build_data_report(market):
    question = market["question"]
    report   = {"has_crypto_data": False}
    coin_id  = detect_crypto(question)

    if coin_id:
        print(f"   💰 Fetching live data for {coin_id}...")
        price_data = fetch_current_price(coin_id)
        if price_data:
            report.update(price_data)
            report["has_crypto_data"] = True
            print(f"   📊 Price: ${price_data.get('current_price',0):,.2f} ({price_data.get('change_24h',0):+.2f}% 24h)")

        df = fetch_ohlcv(coin_id, 90)
        if df is not None:
            report["indicators"] = calculate_indicators(df)

        vol_data = fetch_volume_history(coin_id, 30)
        if vol_data:
            report["liquidity"] = analyze_liquidity(vol_data)

        time.sleep(2)

    return report


# ================================================================
#   CLAUDE ANALYSIS WITH WEB SEARCH
# ================================================================
def claude_analyze(market, data_report):
    today    = datetime.now().strftime("%B %d %Y")
    question = market["question"]
    ind      = data_report.get("indicators", {})
    liq      = data_report.get("liquidity", {})

    tech = ""
    if data_report.get("has_crypto_data"):
        tech = f"""
LIVE DATA:
  Current price  : ${data_report.get('current_price',0):,.2f}
  24h change     : {data_report.get('change_24h',0):+.2f}%
  24h volume     : ${data_report.get('volume_24h',0):,.0f}
  Market cap     : ${data_report.get('market_cap',0):,.0f}

INDICATORS:
  RSI            : {ind.get('RSI','N/A')} → {ind.get('RSI_signal','N/A')}
  MACD           : {ind.get('MACD_signal','N/A')}
  Stochastic     : {ind.get('STOCH_K','N/A')} → {ind.get('STOCH_signal','N/A')}
  Trend bias     : {ind.get('TREND_BIAS','N/A')}
  MA Cross       : {ind.get('MA_CROSS','N/A')}
  Momentum 7d    : {ind.get('MOMENTUM_7D','N/A')}%
  Momentum 14d   : {ind.get('MOMENTUM_14D','N/A')}%
  Volatility     : {ind.get('VOLATILITY','N/A')} ({ind.get('ATR_pct','N/A')}%)

SUPPORT/RESISTANCE:
  Resistance 2   : ${ind.get('RESISTANCE_2','N/A')}
  Resistance 1   : ${ind.get('RESISTANCE_1','N/A')}
  ← PRICE HERE → ${data_report.get('current_price',0):,.2f}
  Support 1      : ${ind.get('SUPPORT_1','N/A')}
  Support 2      : ${ind.get('SUPPORT_2','N/A')}
  Pivot R1       : ${ind.get('PIVOT_R1','N/A')}
  Pivot          : ${ind.get('PIVOT','N/A')}
  Pivot S1       : ${ind.get('PIVOT_S1','N/A')}

BOLLINGER BANDS:
  Upper          : ${ind.get('BB_upper','N/A')}
  Middle
