import cloudscraper
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# --- NEW STRATEGY: DIRECT DATA FEED (JSON) ---
# We use a global gold price feed instead of scraping news sites.
# This bypasses the "Anti-Bot" blocks on GoodReturns.
DATA_URL = "https://data-asg.goldprice.org/dbXRates/INR"

scraper = cloudscraper.create_scraper()

def get_live_rates():
    """
    Fetches live market data from goldprice.org JSON feed.
    Returns dictionary with base 24k Gold and Silver per gram in INR.
    """
    try:
        # Fake a browser visit
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.0.0 Safari/537.36",
            "Referer": "https://goldprice.org/"
        }
        
        response = scraper.get(DATA_URL, headers=headers)
        if response.status_code == 200:
            data = response.json()
            # The feed returns prices per OUNCE in INR
            # Structure: {"items": [{"xauPrice": 200000.50, "xagPrice": 2500.50, ...}]}
            if "items" in data and len(data["items"]) > 0:
                item = data["items"][0]
                price_gold_ounce = item.get("xauPrice", 0)
                price_silver_ounce = item.get("xagPrice", 0)
                
                # Convert Ounce to Gram (1 Ounce = 31.1035 Grams)
                gold_24k_gram = price_gold_ounce / 31.1035
                silver_gram = price_silver_ounce / 31.1035
                
                return gold_24k_gram, silver_gram
    except Exception as e:
        print(f"Feed Error: {e}")
    
    return 0.0, 0.0

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/get_initial_rates', methods=['POST'])
def get_initial_rates():
    # 1. Get Live Base Rates (24K Gold & Silver)
    base_gold_24k, base_silver = get_live_rates()
    
    # 2. Process inputs
    data = request.json
    user_carat = str(data.get('carat', '22'))
    
    # 3. Calculate Carat Price
    # If feed failed (0), these will remain 0
    gold_rate_user = 0
    if base_gold_24k > 0:
        if user_carat == "24":
            gold_rate_user = base_gold_24k
        elif user_carat == "22":
            gold_rate_user = base_gold_24k * (22/24)
        elif user_carat == "18":
            gold_rate_user = base_gold_24k * (18/24)
            
    # Add a small premium (Import duty/GST approx 10-15% is usually added in local market rates)
    # Global spot rates are raw. Indian market rates are higher.
    # We add ~12% to match GoodReturns typical market rate.
    if gold_rate_user > 0: gold_rate_user *= 1.12
    if base_gold_24k > 0: base_gold_24k *= 1.12
    if base_silver > 0: base_silver *= 1.12
    
    return jsonify({
        "gold_rate_user": round(gold_rate_user, 2),
        "gold_rate_24k": round(base_gold_24k, 2),
        "silver_rate": round(base_silver, 2)
    })

@app.route('/calculate', methods=['POST'])
def calculate():
    data = request.json
    
    # Safe float conversion
    def safe_float(v):
        try: return float(v) if v else 0.0
        except: return 0.0

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

    # Nisab Logic
    nisab_threshold = 595 * rate_silver
    is_eligible = False
    zakat_payable = 0
    
    if nisab_threshold > 0:
        if net_worth >= nisab_threshold:
            is_eligible = True
            zakat_payable = net_worth * 0.025
    elif net_worth > 0:
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
