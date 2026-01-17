# main.py
# Automated Daily Market Update (V16 + Twitter)

import os
import json
import requests
import textwrap
import csv
import io
import tweepy  # Added for Twitter
from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont
from tvDatafeed import TvDatafeed, Interval
from bs4 import BeautifulSoup

# --- CONFIGURATION ---
OUTPUT_FILE = "global_market_update.png"
# Font: We will assume the font file is in the same folder
FONT_PATH = "arial.ttf"
WIDTH, HEIGHT = 1080, 1080

# --- COLORS ---
COLOR_BG = "#0F172A"
COLOR_CARD = "#1E293B"
COLOR_TEXT_MAIN = "#FFFFFF" 
COLOR_TEXT_SUB = "#94A3B8"
COLOR_ACCENT = "#38BDF8"
COLOR_GREEN = "#10B981"
COLOR_RED = "#EF4444"
COLOR_NEUTRAL = "#F59E0B"
COLOR_BAN = "#F43F5E"
COLOR_HIGH = "#34D399"

HEADER_TEXT_COLOR = (255, 255, 255)
HEADER_DATE_COLOR = (180, 180, 200)
WATERMARK_COLOR   = "#D1D5DB" 

print("1. Initializing...")
tv = TvDatafeed()

# --- GRAPHICS HELPERS ---
def get_font(size, bold=False):
    font_file = "arialbd.ttf" if bold else "arial.ttf"
    try:
        return ImageFont.truetype(font_file, size)
    except:
        # Fallback to default if font file is missing in cloud
        return ImageFont.load_default()

def draw_text(draw, pos, text, font, fill, anchor="mm"):
    draw.text(pos, text, font=font, fill=fill, anchor=anchor)

def draw_card_compact(draw, x, y, w, h, title, value, change_str):
    draw.rounded_rectangle((x, y, x + w, y + h), radius=12, fill=COLOR_CARD)
    if change_str.startswith("-"):
        accent = COLOR_RED
        arrow = "▼"
    elif change_str.startswith("+"):
        accent = COLOR_GREEN
        arrow = "▲"
    else:
        accent = COLOR_TEXT_MAIN
        arrow = ""

    draw.text((x + 15, y + 15), title, font=get_font(18, bold=True), fill=COLOR_TEXT_SUB, anchor="lt")
    draw.text((x + 15, y + 45), value, font=get_font(34, bold=True), fill=COLOR_TEXT_MAIN, anchor="lt")
    clean_change = change_str.replace('+', '').replace('-', '')
    full_text = f"{arrow} {clean_change}"
    draw.text((x + w - 15, y + 48), full_text, font=get_font(26, bold=True), fill=accent, anchor="rt")

# --- DATA FETCHERS ---
def get_robust_session():
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Referer': 'https://www.nseindia.com/',
        'Accept': '*/*'
    })
    try:
        session.get("https://www.nseindia.com/", timeout=5)
    except:
        pass
    return session

def fetch_fo_ban_list():
    print("   Fetching F&O Ban List...")
    session = get_robust_session()
    for i in range(5):
        dt = datetime.now() - timedelta(days=i)
        date_str = dt.strftime("%d%m%Y")
        url = f"https://nsearchives.nseindia.com/archives/fo/sec_ban/fo_secban_{date_str}.csv"
        try:
            r = session.get(url, timeout=5)
            if r.status_code == 200:
                lines = r.text.splitlines()
                ban_list = []
                for line in lines[1:]:
                    if line.strip():
                        parts = line.split(',')
                        if len(parts) >= 2: ban_list.append(parts[1].strip())
                if ban_list: return ban_list
        except:
            continue
    return []

def fetch_52wk_data():
    print("   Fetching 52W High/Low Data...")
    session = get_robust_session()
    for i in range(5):
        dt = datetime.now() - timedelta(days=i)
        date_str = dt.strftime("%d%m%Y")
        url = f"https://nsearchives.nseindia.com/content/CM_52_wk_High_low_{date_str}.csv"
        try:
            r = session.get(url, timeout=10)
            if r.status_code == 200:
                f = io.StringIO(r.text)
                reader = csv.reader(f)
                rows = list(reader)
                if len(rows) > 2:
                    header_idx = 0
                    for idx, row in enumerate(rows):
                        if row and "SYMBOL" in row[0]:
                            header_idx = idx
                            break
                    data_rows = rows[header_idx+1:]
                    parsed_data = []
                    for row in data_rows:
                        if len(row) < 6: continue
                        sym = row[0]
                        try:
                            h_dt = datetime.strptime(row[3].strip().upper(), "%d-%b-%Y")
                            l_dt = datetime.strptime(row[5].strip().upper(), "%d-%b-%Y")
                            parsed_data.append((sym, h_dt, l_dt))
                        except:
                            continue
                    if not parsed_data: continue
                    max_h_date = max(p[1] for p in parsed_data)
                    max_l_date = max(p[2] for p in parsed_data)
                    highs = [p[0] for p in parsed_data if p[1] == max_h_date]
                    lows = [p[0] for p in parsed_data if p[2] == max_l_date]
                    return {"highs": highs, "lows": lows, "date": max_h_date.strftime("%d-%b")}
        except:
            continue
    return {"highs": [], "lows": [], "date": "N/A"}

def fetch_gift_nifty_live():
    try:
        url = "https://groww.in/indices/global-indices/sgx-nifty"
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=10)
        data = json.loads(BeautifulSoup(r.text, "html.parser").find("script", {"id": "__NEXT_DATA__"}).string)
        p = data["props"]["pageProps"]["globalIndicesData"]["priceData"]
        return f"{p['value']:,.2f}", f"{p['dayChangePerc']:+.2f}%"
    except:
        return "N/A", "0.00%"

def fetch_market_data():
    data = {}
    data["GIFTNIFTY"] = fetch_gift_nifty_live()
    indices = {
        "Nikkei 225": ({"symbol": "NI225", "exchange": "TVC"}, "^N225"),
        "Dow Jones Fut": ({"symbol": "YM1!", "exchange": "CBOT"}, "YM=F"),
        "S&P 500": ({"symbol": "SPX", "exchange": "TVC"}, "^GSPC"),
        "Nasdaq": ({"symbol": "IXIC", "exchange": "TVC"}, "^IXIC"),
        "Hang Seng": ({"symbol": "HSI", "exchange": "TVC"}, "^HSI"),
        "Gold (Fut)": ({"symbol": "GC1!", "exchange": "COMEX"}, "GC=F"),
        "Bitcoin": ({"symbol": "BTCUSD", "exchange": "CRYPTO"}, "BTC-USD")
    }
    for name, (tv_conf, yf_sym) in indices.items():
        print(f"   Fetching {name}...")
        fetched = False
        try:
            hist = tv.get_hist(symbol=tv_conf['symbol'], exchange=tv_conf['exchange'], interval=Interval.in_daily, n_bars=5)
            if hist is not None and not hist.empty:
                curr = hist['close'].iloc[-1]
                prev = hist['close'].iloc[-2]
                chg = ((curr - prev) / prev) * 100
                data[name] = (f"{curr:,.2f}", f"{chg:+.2f}%")
                fetched = True
        except:
            pass
        if not fetched:
            try:
                t = yf.Ticker(yf_sym)
                hist = t.history(period="5d")
                curr = hist["Close"].iloc[-1]
                prev = hist["Close"].iloc[-2]
                chg = ((curr - prev) / prev) * 100
                data[name] = (f"{curr:,.2f}", f"{chg:+.2f}%")
            except:
                data[name] = ("N/A", "0.00%")
    return data

def calc_market_bias(data):
    green = 0
    total = 0
    for key, val in data.items():
        chg_str = val[1]
        if chg_str.startswith("+") and "0.00" not in chg_str:
            green += 1
        total += 1
    ratio = green / total if total > 0 else 0
    if ratio >= 0.6: return "BULLISH", COLOR_GREEN
    if ratio <= 0.4: return "BEARISH", COLOR_RED
    return "NEUTRAL", COLOR_NEUTRAL

def create_image(data, ban_list, high_low_data):
    print("3. Generating Image...")
    img = Image.new("RGB", (WIDTH, HEIGHT), COLOR_BG)
    d = ImageDraw.Draw(img)

    draw_text(d, (WIDTH / 2, 70), "Global Market Update", get_font(72, bold=True), HEADER_TEXT_COLOR)
    draw_text(d, (WIDTH / 2, 135), datetime.now().strftime("%d %b, %Y"), get_font(42), HEADER_DATE_COLOR)
    
    bias_text, bias_color = calc_market_bias(data)
    draw_text(d, (60, 185), f"MARKET BIAS: {bias_text}", get_font(28, bold=True), bias_color, anchor="lm")
    draw_text(d, (WIDTH - 60, 185), "Live Data | F&O Update", get_font(22), COLOR_ACCENT, anchor="rm")
    d.line([(50, 210), (WIDTH - 50, 210)], fill=COLOR_CARD, width=2)

    start_y = 230
    col_1_x = 50
    col_2_x = 550
    card_w = 480
    card_h = 100
    gap_y = 20
    order = ["GIFTNIFTY", "Nikkei 225", "Dow Jones Fut", "S&P 500", "Nasdaq", "Hang Seng", "Gold (Fut)", "Bitcoin"]
    
    last_y = 0
    for i, key in enumerate(order):
        val, chg = data.get(key, ("N/A", "0.00%"))
        row = i // 2
        col = i % 2
        x = col_1_x if col == 0 else col_2_x
        y = start_y + (row * (card_h + gap_y))
        draw_card_compact(d, x, y, card_w, card_h, key.upper(), val, chg)
        last_y = y + card_h

    bottom_y = last_y + 45
    col1_x, col2_x, col3_x = 60, 420, 760
    
    # F&O BAN
    draw_text(d, (col1_x, bottom_y), "F&O BAN LIST", get_font(24, bold=True), COLOR_BAN, anchor="lt")
    ban_curr_y = bottom_y + 40
    if not ban_list:
        draw_text(d, (col1_x, ban_curr_y), "None", get_font(24), COLOR_TEXT_MAIN, anchor="lt")
    else:
        for item in ban_list[:5]:
            draw_text(d, (col1_x, ban_curr_y), f"• {item}", get_font(24), COLOR_TEXT_MAIN, anchor="lt")
            ban_curr_y += 35
        if len(ban_list) > 5:
             draw_text(d, (col1_x, ban_curr_y), f"+ {len(ban_list)-5} more", get_font(22), COLOR_TEXT_SUB, anchor="lt")

    # HIGHS
    highs = high_low_data.get('highs', [])
    draw_text(d, (col2_x, bottom_y), f"52W HIGHS ({len(highs)})", get_font(24, bold=True), COLOR_HIGH, anchor="lt")
    high_curr_y = bottom_y + 40
    if not highs:
        draw_text(d, (col2_x, high_curr_y), "None", get_font(24), COLOR_TEXT_MAIN, anchor="lt")
    else:
        for item in highs[:5]:
            draw_text(d, (col2_x, high_curr_y), f"▲ {item}", get_font(24), COLOR_TEXT_MAIN, anchor="lt")
            high_curr_y += 35
        if len(highs) > 5:
             draw_text(d, (col2_x, high_curr_y), f"+ {len(highs)-5} more", get_font(22), COLOR_TEXT_SUB, anchor="lt")

    # LOWS
    lows = high_low_data.get('lows', [])
    draw_text(d, (col3_x, bottom_y), f"52W LOWS ({len(lows)})", get_font(24, bold=True), COLOR_NEUTRAL, anchor="lt")
    low_curr_y = bottom_y + 40
    if not lows:
        draw_text(d, (col3_x, low_curr_y), "None", get_font(24), COLOR_TEXT_MAIN, anchor="lt")
    else:
        for item in lows[:5]:
            draw_text(d, (col3_x, low_curr_y), f"▼ {item}", get_font(24), COLOR_TEXT_MAIN, anchor="lt")
            low_curr_y += 35
        if len(lows) > 5:
             draw_text(d, (col3_x, low_curr_y), f"+ {len(lows)-5} more", get_font(22), COLOR_TEXT_SUB, anchor="lt")

    # Footer
    date_str_watermark = datetime.now().strftime("%d-%b-%Y")
    footer_txt = f"@ChartWizMani | Data as of {date_str_watermark} | For Informational Use Only"
    draw_text(d, (WIDTH / 2, HEIGHT - 35), footer_txt, get_font(24), WATERMARK_COLOR)

    img.save(OUTPUT_FILE)
    print(f"✅ SUCCESS! Image saved: {OUTPUT_FILE}")
    return OUTPUT_FILE

# --- TWITTER POSTING ---
def post_to_twitter(image_path, data):
    print("4. Posting to Twitter...")
    
    # Retrieve Keys from Cloud Environment Variables (Secure)
    api_key = os.environ.get("TWITTER_API_KEY")
    api_secret = os.environ.get("TWITTER_API_SECRET")
    access_token = os.environ.get("TWITTER_ACCESS_TOKEN")
    access_secret = os.environ.get("TWITTER_ACCESS_TOKEN_SECRET")

    if not all([api_key, api_secret, access_token, access_secret]):
        print("❌ Error: Twitter Keys not found in environment!")
        return

    try:
        # V1.1 for Media Upload
        auth = tweepy.OAuth1UserHandler(api_key, api_secret, access_token, access_secret)
        api = tweepy.API(auth)
        media = api.media_upload(image_path)

        # V2 for Tweeting
        client = tweepy.Client(
            consumer_key=api_key, consumer_secret=api_secret,
            access_token=access_token, access_token_secret=access_secret
        )
        
        # Compose Tweet Text
        bias, _ = calc_market_bias(data)
        gift_val = data.get("GIFTNIFTY", ("N/A", "0%"))[0]
        tweet_text = f"Global Market Update – {datetime.now().strftime('%d %b')}\n\n"
        tweet_text += f"📊 Market Bias: {bias}\n"
        tweet_text += f"🌏 GIFT Nifty: {gift_val}\n\n"
        tweet_text += "#StockMarket #Nifty #Trading #ChartWizMani"

        client.create_tweet(text=tweet_text, media_ids=[media.media_id_string])
        print("🚀 Tweet Posted Successfully!")
    except Exception as e:
        print(f"❌ Twitter Error: {e}")

# --- MAIN EXECUTION ---
if __name__ == "__main__":
    print("--- STARTING CLOUD AUTOMATION ---")
    m_data = fetch_market_data()
    fno_list = fetch_fo_ban_list()
    hl_data = fetch_52wk_data()
    
    img_path = create_image(m_data, fno_list, hl_data)
    
    # Only try to tweet if keys exist (prevents local crash)
    if os.environ.get("TWITTER_API_KEY"):
        post_to_twitter(img_path, m_data)
    else:
        print("⚠️ No Twitter keys found (Local Mode). Image saved but not posted.")
    
    print("--- DONE ---")