import ccxt
import pandas as pd
import numpy as np
import requests
import yagmail
import time
import datetime
import os
import logging
from dotenv import load_dotenv
from flask import Flask

# 加载 .env 配置
load_dotenv()

# 配置日志
LOG_DIR = os.getenv("LOG_DIR", ".")
os.makedirs(LOG_DIR, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(f"{LOG_DIR}/coinmarket.log"),
        logging.StreamHandler(),
    ],
)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
WECHAT_WEBHOOK_URL = os.getenv("WECHAT_WEBHOOK_URL")
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")
EMAIL_TO = os.getenv("EMAIL_TO")
SYMBOLS = os.getenv("SYMBOLS", "BTC/USDT").split(",")
TIMEFRAME = os.getenv("TIMEFRAME", "1h")
INTERVAL_SECONDS = int(os.getenv("INTERVAL_SECONDS", 300))

app = Flask(__name__)


@app.route("/health")
def health():
    return "ok", 200


def fetch_klines(symbol="BTC/USDT", timeframe="1h", limit=100):
    exchange = ccxt.binance()
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(
        ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"]
    )
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    return df


def calculate_indicators(df):
    for span in [6, 13, 24, 52]:
        df[f"EMA{span}"] = df["close"].ewm(span=span, adjust=False).mean()
    df["vol_ma20"] = df["volume"].rolling(window=20).mean()
    return df


def check_signal(df):
    latest = df.iloc[-1]
    ema_values = [latest["EMA6"], latest["EMA13"], latest["EMA24"], latest["EMA52"]]
    max_diff = max(ema_values) - min(ema_values)
    close_price = latest["close"]

    ema_fit = max_diff / close_price < 0.01
    volume_spike = latest["volume"] > 1.5 * latest["vol_ma20"]

    return ema_fit and volume_spike


def send_telegram(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
        requests.post(url, data=data)
    except Exception as e:
        logging.error(f"Telegram 发送失败: {e}")


def send_wechat(message):
    try:
        headers = {"Content-Type": "application/json"}
        json_data = {"msgtype": "markdown", "markdown": {"content": message}}
        requests.post(WECHAT_WEBHOOK_URL, json=json_data, headers=headers)
    except Exception as e:
        logging.error(f"企业微信发送失败: {e}")


def send_email(subject, content):
    try:
        yag = yagmail.SMTP(user=EMAIL_USER, password=EMAIL_PASS, host="smtp.qq.com")
        yag.send(to=EMAIL_TO, subject=subject, contents=content)
    except Exception as e:
        logging.error(f"邮件发送失败: {e}")


def notify_all(message):
    logging.info(f"推送通知: {message}")
    send_telegram(message)
    send_wechat(message)
    send_email("【交易提醒】EMA拟合+放量", message)


def run_monitor():
    logging.info("启动监控服务...")
    while True:
        for sym in SYMBOLS:
            try:
                df = fetch_klines(sym, timeframe=TIMEFRAME)
                df = calculate_indicators(df)
                if check_signal(df):
                    msg = f"🚨 [{sym}] 检测到 EMA 拟合 + 放量！时间：{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                    notify_all(msg)
            except Exception as e:
                error_msg = f"❌ 错误监控到 [{sym}] ：{e}"
                logging.error(error_msg)
                send_telegram(error_msg)
        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    import threading

    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=8000)).start()
    run_monitor()
