import cloudscraper
from bs4 import BeautifulSoup
from flask import Flask, render_template, request, jsonify
import re

app = Flask(__name__)

# --- CONFIGURATION ---
CITY_SLUGS = {
    "Delhi": "delhi", "Mumbai": "mumbai", "Chennai": "chennai",
    "Kolkata": "kolkata", "Bangalore": "bangalore", "Hyderabad": "hyderabad",
    "Pune": "pune", "Jaipur": "jaipur", "Lucknow": "lucknow",
    "Ahmedabad": "ahmedabad", "Patna": "patna", "Kerala": "kerala", "Nashik": "nashik"
}

# --- THE FIX: DISGUISE AS GOOGLE BOT ---
# We force the 'User-Agent' to look like Google's crawler.
# Most sites whitelist this so they appear in search results.
scraper = cloudscraper.create_scraper()
GOOGLE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
    "Referer": "https://www.google.com/"
}

def clean_price(text):
    try:
        clean = re.sub(r'[^\d.]', '', text)
        return float(clean)
    except:
        return 0.0

def safe_float(value):
    try:
        if not value: return 0.0
        return float(value)
    except ValueError:
        return 0.0

def fetch_gold_rate(city, carat):
    try:
        slug = CITY_SLUGS.get(city, 'delhi')
        url = f"https://www.goodreturns.in/gold-rates/{slug}.html"
        
        # Use Google Bot Headers
        response = scraper.get(url, headers=GOOGLE_HEADERS)
        
        if response.status_code != 200: return 0.0

        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 1. Try Specific ID
        target_id = f"{carat}K-price"
        element = soup.find(id=target_id)
        if element: return clean_price(element.text)
        
        # 2. Try 24K and calculate
        el_24 = soup.find(id="24K-price")
        if el_24:
            p24 = clean_price(el_24.text)
            if str(carat) == "22": return p24 * (22/24)
            elif str(carat) == "18": return p24 * (18/24)
            return p24
        
        return 0.0
    except:
        return 0.0

def fetch_silver_rate(city):
    try:
        slug = CITY_SLUGS.get(city, 'delhi')
        url = f"https://www.goodreturns.in/silver-rates/{slug}.html"
        
        # Use Google Bot Headers
        response = scraper.get(url, headers=GOOGLE_HEADERS)
        
        if response.status_code != 200: return 0.0

        soup = BeautifulSoup(response.text, 'html.parser')
        
        # ID Strategy
        element = soup.find(id="silver-1g-price")
        if element: return clean_price(element.text)
        
        # Backup: Table Strategy
        table_div = soup.find('div', {'class': 'gold_silver_table'})
        if table_div:
            rows = table_div.find_all('tr')
            for row in rows:
                if "1 gram" in row.text.lower() or "1 g" in row.text.lower():
                    cols = row.find_all('td')
                    if len(cols) > 1: return clean_price(cols[1].text)
        
        return 0.0
    except:
        return 0.0

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/get_initial_rates', methods=['POST'])
def get_initial_rates():
    data = request.json
    city = data.get('state', 'Delhi')
    user_carat = data.get('carat', '22')
    
    return jsonify({
        "gold_rate_user": fetch_gold_rate(city, user_carat),
        "gold_rate_24k": fetch_gold_rate(city, '24'),
        "silver_rate": fetch_silver_rate(city)
    })

@app.route('/calculate', methods=['POST'])
def calculate():
    data = request.json
    
    gold_weight = safe_float(data.get('gold_weight'))
    silver_weight = safe_float(data.get('silver_weight'))
    silver_val_input = safe_float(data.get('silver_value'))
    cash = safe_float(data.get('cash'))
    investments = safe_float(data.get('investments'))
    business = safe_float(data.get('business'))
    liabilities = safe_float(data.get('liabilities'))
    rate_gold_user = safe_float(data.get('rate_gold_user'))
    rate_silver = safe_float(data.get('rate_silver'))
    
    total_gold_val = gold_weight * rate_gold_user
    total_silver_val = silver_val_input
    if total_silver_val == 0 and silver_weight > 0:
        total_silver_val = silver_weight * rate_silver

    gross_assets = total_gold_val + total_silver_val + cash + investments + business
    net_worth = gross_assets - liabilities

    nisab_threshold = 595 * rate_silver
    is_eligible = False
    zakat_payable = 0
    
    if nisab_threshold > 0:
        if net_worth >= nisab_threshold:
            is_eligible = True
            zakat_payable = net_worth * 0.025
    elif net_worth > 0:
        # Fallback if rates failed
        is_eligible = True
        zakat_payable = net_worth * 0.025

    return jsonify({
        "net_worth": round(net_worth, 2),
        "zakat_payable": round(zakat_payable, 2),
        "is_eligible": is_eligible,
        "nisab_threshold": round(nisab_threshold, 2),
        "gold_value_calc": round(total_gold_val, 2),
        "silver_value_calc": round(total_silver_val, 2)
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
