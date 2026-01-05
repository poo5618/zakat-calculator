import cloudscraper
from bs4 import BeautifulSoup
from flask import Flask, render_template, request, jsonify
import re

app = Flask(__name__)

# --- CONFIGURATION ---
CITY_SLUGS = {
    "Delhi": "delhi",
    "Mumbai": "mumbai",
    "Chennai": "chennai",
    "Kolkata": "kolkata",
    "Bangalore": "bangalore",
    "Hyderabad": "hyderabad",
    "Pune": "pune",
    "Jaipur": "jaipur",
    "Lucknow": "lucknow",
    "Ahmedabad": "ahmedabad",
    "Patna": "patna",
    "Kerala": "kerala",
    "Nashik": "nashik"
}

# Browser emulator to bypass blocks
scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True})

def clean_price(text):
    """Converts '₹ 247' or '247.50' to float"""
    try:
        clean = re.sub(r'[^\d.]', '', text)
        return float(clean)
    except:
        return 0.0

def safe_float(value):
    """Prevents crashes from empty inputs"""
    try:
        if not value: return 0.0
        return float(value)
    except ValueError:
        return 0.0

def fetch_gold_rate(city, carat):
    """Fetches Gold using IDs: 24K-price, 22K-price, etc."""
    try:
        slug = CITY_SLUGS.get(city, 'delhi')
        url = f"https://www.goodreturns.in/gold-rates/{slug}.html"
        
        response = scraper.get(url)
        if response.status_code != 200: return 0.0

        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 1. Look for exact ID (e.g. 24K-price)
        target_id = f"{carat}K-price"
        element = soup.find(id=target_id)

        if element:
            return clean_price(element.text)
        
        # 2. Fallback: Find 24K ID and calculate
        el_24 = soup.find(id="24K-price")
        if el_24:
            price_24 = clean_price(el_24.text)
            if str(carat) == "22": return price_24 * (22/24)
            elif str(carat) == "18": return price_24 * (18/24)
            return price_24
            
        return 0.0
    except Exception as e:
        print(f"Gold Scrape Error: {e}")
        return 0.0

def fetch_silver_rate(city):
    """Fetches Silver using the ID found in your screenshot: silver-1g-price"""
    try:
        slug = CITY_SLUGS.get(city, 'delhi')
        url = f"https://www.goodreturns.in/silver-rates/{slug}.html"
        
        print(f"Fetching Silver URL: {url}")
        response = scraper.get(url)
        
        if response.status_code != 200: 
            print("Silver Request Blocked")
            return 0.0

        soup = BeautifulSoup(response.text, 'html.parser')
        
        # --- NEW STRATEGY: EXACT ID FROM YOUR SCREENSHOT ---
        # Your screenshot shows: <span id="silver-1g-price">₹247</span>
        element = soup.find(id="silver-1g-price")
        
        if element:
            price = clean_price(element.text)
            print(f"Silver ID Found: {price}")
            return price

        print("Silver: ID 'silver-1g-price' not found.")
        return 0.0
    except Exception as e:
        print(f"Silver Scrape Error: {e}")
        return 0.0

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/get_initial_rates', methods=['POST'])
def get_initial_rates():
    data = request.json
    city = data.get('state', 'Delhi')
    user_carat = data.get('carat', '22')
    
    # Fetch rates strictly
    gold_rate_user = fetch_gold_rate(city, user_carat)
    silver_rate = fetch_silver_rate(city)
    gold_rate_24k = fetch_gold_rate(city, '24') 
    
    return jsonify({
        "gold_rate_user": gold_rate_user,
        "gold_rate_24k": gold_rate_24k,
        "silver_rate": silver_rate
    })

@app.route('/calculate', methods=['POST'])
def calculate():
    data = request.json
    
    # 1. Safe Inputs
    gold_weight = safe_float(data.get('gold_weight'))
    silver_weight = safe_float(data.get('silver_weight'))
    silver_val_input = safe_float(data.get('silver_value'))
    
    cash = safe_float(data.get('cash'))
    investments = safe_float(data.get('investments'))
    business = safe_float(data.get('business'))
    liabilities = safe_float(data.get('liabilities'))
    
    rate_gold_user = safe_float(data.get('rate_gold_user'))
    rate_silver = safe_float(data.get('rate_silver'))
    rate_gold_24k = safe_float(data.get('rate_gold_24k'))

    # 2. Calculate Asset Values
    total_gold_val = gold_weight * rate_gold_user
    
    total_silver_val = silver_val_input
    if total_silver_val == 0 and silver_weight > 0:
        total_silver_val = silver_weight * rate_silver

    gross_assets = total_gold_val + total_silver_val + cash + investments + business
    net_worth = gross_assets - liabilities

    # 3. Zakat Logic (Nisab)
    # Rule: If Net Worth >= Value of 595 grams of Silver, Zakat is due.
    
    nisab_threshold = 595 * rate_silver
    
    is_eligible = False
    zakat_payable = 0
    
    if nisab_threshold > 0:
        if net_worth >= nisab_threshold:
            is_eligible = True
            zakat_payable = net_worth * 0.025
    else:
        # Fallback if silver rate fails: check if net worth is positive
        if net_worth > 0:
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