# main.py
# Version 21.0: Removed Global Sentiment + Cleaned Layout

import os
import json
import requests
import textwrap
import csv
import io
import tweepy
import yfinance as yf
from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont
from bs4 import BeautifulSoup

# --- CONFIGURATION ---
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "global_market_update.png")
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

# --- GRAPHICS HELPERS ---
def get_font(size, bold=False):
    script_dir = os.path.dirname(__file__)
    font_name = "arialbd.ttf" if bold else "arial.ttf"
    font_path = os.path.join(script_dir, font_name)
    try:
        return ImageFont.truetype(font_path, size)
    except Exception as e:
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
        'User-Agent': 'Mozilla/5.0',
        'Referer': 'https://www.nseindia.com/',
        'Accept': '*/*'
    })
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
                return ban_list
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
        "Nikkei 225": "^N225",
        "Dow Futures": "YM=F",
        "S&P 500": "^GSPC",
        "Nasdaq": "^IXIC",
        "Hang Seng": "^HSI",
        "Gold Futures": "GC=F",
        "Bitcoin": "BTC-USD"
    }
    
    for name, ticker in indices.items():
        print(f"   Fetching {name}...")
        try:
            t = yf.Ticker(ticker)
            hist = t.history(period="5d")
            close_data = hist["Close"].dropna()
            
            if len(close_data) < 2:
                print(f"      ⚠️ Not enough data for {name}")
                data[name] = ("N/A", "0.00%")
                continue

            curr = close_data.iloc[-1]
            prev = close_data.iloc[-2]
            
            chg = ((curr - prev) / prev) * 100
            data[name] = (f"{curr:,.2f}", f"{chg:+.2f}%")
            
        except Exception as e:
            print(f"   Error fetching {name}: {e}")
            data[name] = ("N/A", "0.00%")
            
    return data

def create_image(data, ban_list, high_low_data):
    print("3. Generating Image (V21 - No Sentiment)...")
    img = Image.new("RGB", (WIDTH, HEIGHT), COLOR_BG)
    d = ImageDraw.Draw(img)

    draw_text(d, (WIDTH / 2, 70), "Global Market Update", get_font(72, bold=True), HEADER_TEXT_COLOR)
    draw_text(d, (WIDTH / 2, 135), datetime.now().strftime("%d %b, %Y"), get_font(42), HEADER_DATE_COLOR)
    
    # REMOVED: Global Sentiment
    # MOVED: "Market Data" to the Left side to serve as the section header
    draw_text(d, (60, 185), "MARKET DATA", get_font(22, bold=True), COLOR_ACCENT, anchor="lm")
    
    d.line([(50, 210), (WIDTH - 50, 210)], fill=COLOR_CARD, width=2)

    start_y = 230
    col_1_x = 50
    col_2_x = 550
    card_w = 480
    card_h = 100
    gap_y = 20
    
    order = ["GIFTNIFTY", "Nikkei 225", "Dow Futures", "S&P 500", "Nasdaq", "Hang Seng", "Gold Futures", "Bitcoin"]
    
    last_y = 0
    for i, key in enumerate(order):
        val, chg = data.get(key, ("N/A", "0.00%"))
        row = i // 2
        col = i % 2
        x = col_1_x if col == 0 else col_2_x
        y = start_y + (row * (card_h + gap_y))
        
        draw_card_compact(d, x, y, card_w, card_h, key.upper(), val, chg)
        last_y = y + card_h

    # Bottom Section
    bottom_y = last_y + 45
    col1_x, col2_x, col3_x = 60, 420, 760
    
    # 1. Ban List
    draw_text(d, (col1_x, bottom_y), "F&O BAN LIST", get_font(24, bold=True), COLOR_BAN, anchor="lt")
    ban_curr_y = bottom_y + 40
    if not ban_list:
        draw_text(d, (col1_x, ban_curr_y), "None", get_font(24), COLOR_TEXT_MAIN, anchor="lt")
    else:
        for item in ban_list[:5]:
            draw_text(d, (col1_x, ban_curr_y), f"• {item}", get_font(24), COLOR_TEXT_MAIN, anchor="lt")
            ban_curr_y += 35
        if len(ban_list) > 5:
             draw_text(d, (col1_x, ban_curr_y), f"+{len(ban_list)-5} others", get_font(22), COLOR_TEXT_SUB, anchor="lt")

    # 2. Highs
    highs = high_low_data.get('highs', [])
    draw_text(d, (col2_x, bottom_y), f"52-Week HIGHS ({len(highs)})", get_font(24, bold=True), COLOR_HIGH, anchor="lt")
    high_curr_y = bottom_y + 40
    if not highs:
        draw_text(d, (col2_x, high_curr_y), "None", get_font(24), COLOR_TEXT_MAIN, anchor="lt")
    else:
        for item in highs[:5]:
            draw_text(d, (col2_x, high_curr_y), f"▲ {item}", get_font(24), COLOR_TEXT_MAIN, anchor="lt")
            high_curr_y += 35
        if len(highs) > 5:
             draw_text(d, (col2_x, high_curr_y), f"+{len(highs)-5} others", get_font(22), COLOR_TEXT_SUB, anchor="lt")

    # 3. Lows
    lows = high_low_data.get('lows', [])
    draw_text(d, (col3_x, bottom_y), f"52-Week LOWS ({len(lows)})", get_font(24, bold=True), COLOR_NEUTRAL, anchor="lt")
    low_curr_y = bottom_y + 40
    if not lows:
        draw_text(d, (col3_x, low_curr_y), "None", get_font(24), COLOR_TEXT_MAIN, anchor="lt")
    else:
        for item in lows[:5]:
            draw_text(d, (col3_x, low_curr_y), f"▼ {item}", get_font(24), COLOR_TEXT_MAIN, anchor="lt")
            low_curr_y += 35
        if len(lows) > 5:
             draw_text(d, (col3_x, low_curr_y), f"+{len(lows)-5} others", get_font(22), COLOR_TEXT_SUB, anchor="lt")

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
    
    api_key = os.environ.get("TWITTER_API_KEY")
    api_secret = os.environ.get("TWITTER_API_SECRET")
    access_token = os.environ.get("TWITTER_ACCESS_TOKEN")
    access_secret = os.environ.get("TWITTER_ACCESS_TOKEN_SECRET")

    if not all([api_key, api_secret, access_token, access_secret]):
        print("❌ Error: Twitter Keys not found in environment!")
        return

    try:
        auth = tweepy.OAuth1UserHandler(api_key, api_secret, access_token, access_secret)
        api = tweepy.API(auth)
        media = api.media_upload(image_path)

        client = tweepy.Client(
            consumer_key=api_key, consumer_secret=api_secret,
            access_token=access_token, access_token_secret=access_secret
        )
        
        # --- TWEET TEXT ---
        date_str = datetime.now().strftime('%d %b, %Y')
        tweet_text = f"Global Market Update – {date_str}\n\n"
        
        display_map = {
            "GIFTNIFTY": "GIFTNIFTY",
            "Nikkei 225": "Nikkei 225",
            "Dow Futures": "Dow Futures",
            "S&P 500": "S&P 500",
            "Nasdaq": "Nasdaq",
            "Hang Seng": "Hang Seng"
        }
        
        key_order = ["GIFTNIFTY", "Nikkei 225", "Dow Futures", "S&P 500", "Nasdaq", "Hang Seng"]
        
        for key in key_order:
            if key in data:
                val, chg = data[key]
                name = display_map.get(key, key)
                tweet_text += f"{name}: {val} ({chg})\n"
                
        tweet_text += "\n#GIFTNIFTY #Nifty #DowJones #Nasdaq $bitcoin"

        client.create_tweet(text=tweet_text, media_ids=[media.media_id_string])
        print("🚀 Tweet Posted Successfully!")
    except Exception as e:
        print(f"❌ Twitter Error: {e}")

# --- MAIN EXECUTION ---
if __name__ == "__main__":
    print("--- STARTING CLOUD AUTOMATION (V21) ---")
    m_data = fetch_market_data()
    fno_list = fetch_fo_ban_list()
    hl_data = fetch_52wk_data()
    
    img_path = create_image(m_data, fno_list, hl_data)
    
    if os.environ.get("TWITTER_API_KEY"):
        post_to_twitter(img_path, m_data)
    else:
        print("⚠️ No Twitter keys found (Local Mode). Image saved but not posted.")
    
    print("--- DONE ---")
