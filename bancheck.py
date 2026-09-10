import re
import os
from flask import Flask, render_template_string, request, jsonify
from bs4 import BeautifulSoup
import urllib3
import logging

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Try curl_cffi first, fallback to requests if it fails
try:
    from curl_cffi import requests as curl_requests
    USE_CURL_CFFI = True
    logger.info("[+] Using curl_cffi for requests")
except ImportError:
    logger.warning("[-] curl_cffi not available, using standard requests")
    import requests as curl_requests
    USE_CURL_CFFI = False

# ============================================================
# STATS.CC SCRAPER
# ============================================================

class StatsCCScraper:
    def __init__(self):
        if USE_CURL_CFFI:
            self.session = curl_requests.Session(impersonate="chrome")
        else:
            self.session = curl_requests.Session()
        
        self.session.headers.update({
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })

    def get_player_page(self, username, profile_id):
        url = f"https://stats.cc/siege/{username}/{profile_id}"
        print(f"[+] Stats URL: {url}")
        
        try:
            response = self.session.get(url, timeout=30, verify=False)
            print(f"[+] stats.cc HTTP: {response.status_code}")
            
            if response.status_code != 200:
                print(f"[-] HTTP Status: {response.status_code}")
                return None
            return response.text
        except Exception as exc:
            print(f"[-] stats.cc error: {exc}")
            logger.error(f"Scraper error: {exc}")
            return None

    @staticmethod
    def extract_level(soup):
        # Primary selector
        element = soup.select_one("span.bg-base-200.border-base-200.rounded-md")
        if element:
            value = element.get_text(strip=True)
            if value.isdigit():
                return int(value)
        
        # Fallback
        for element in soup.select("span.bg-base-200"):
            value = element.get_text(strip=True)
            if value.isdigit():
                number = int(value)
                if 1 <= number <= 9999:
                    return number
        return None

    @staticmethod
    def extract_last_played(soup):
        label = soup.find(id="Last Played")
        if not label:
            return None
        
        parent = label.parent
        if not parent:
            return None
        
        # Preferred structure
        value = parent.select_one("div.justify-end span")
        if value:
            text = value.get_text(" ", strip=True)
            if text:
                return text
        
        # Fallback
        spans = parent.find_all("span")
        for span in spans:
            text = span.get_text(" ", strip=True)
            if text:
                return text
        
        return None

    def get_stats(self, username, profile_id):
        html = self.get_player_page(username, profile_id)
        
        if not html:
            return {
                "level": None,
                "last_seen": None,
                "status": "REQUEST_FAILED"
            }
        
        soup = BeautifulSoup(html, "html.parser")
        level = self.extract_level(soup)
        last_seen = self.extract_last_played(soup)
        
        return {
            "level": level,
            "last_seen": last_seen,
            "status": "OK"
        }

# ============================================================
# R6 BAN CHECKER - NO LOGIN REQUIRED
# ============================================================

class R6BanChecker:
    def __init__(self, username, profile_id):
        self.username = username
        self.profile_id = profile_id
        self.stats = StatsCCScraper()

    @staticmethod
    def parse_days(last_seen):
        if not last_seen:
            return None
        
        text = last_seen.lower()
        match = re.search(r"(\d+)\s*(minute|hour|day|week|month|year)s?", text)
        
        if not match:
            return None
        
        number = int(match.group(1))
        unit = match.group(2)
        
        if unit == "minute":
            return 0
        if unit == "hour":
            return 0
        if unit == "day":
            return number
        if unit == "week":
            return number * 7
        if unit == "month":
            return number * 30
        if unit == "year":
            return number * 365
        
        return None

    @classmethod
    def check_status(cls, level, last_seen):
        level = level or 0
        days = cls.parse_days(last_seen)
        
        # BANNED CONDITIONS:
        # 1. Level is 0 (definitely banned)
        if level == 0:
            return "BANNED", "Account is banned (level 0)"
        
        # 2. Last seen is N/A or None (banned or hidden)
        if last_seen is None or last_seen == "N/A" or last_seen.strip() == "":
            return "BANNED", "Account is banned (no last seen data)"
        
        # 3. Level is very low (under 5) - likely banned or fresh account
        if level < 5:
            return "BANNED", f"Account is banned or suspicious (level {level})"
        
        # VALID CONDITIONS:
        # 1. Has level > 0 and has valid last seen data
        if level > 0 and last_seen:
            return "VALID", f"Account is valid (level {level}, last seen: {last_seen})"
        
        # 2. Has level > 0 (even if last seen parsing failed)
        if level > 0:
            return "VALID", f"Account is valid (level {level})"
        
        # Default: if we can't determine, assume banned
        return "BANNED", "Unable to verify account - likely banned"

    def analyze(self):
        print()
        print("=" * 65)
        print("       R6 ACCOUNT BAN CHECKER")
        print("=" * 65)
        print()
        
        print(f"[+] Checking account: {self.username}")
        print(f"[+] Profile ID: {self.profile_id}")
        print()
        
        # Check stats.cc
        stats = self.stats.get_stats(self.username, self.profile_id)
        level = stats.get("level")
        last_seen = stats.get("last_seen")
        stats_status = stats.get("status")
        
        # Determine status
        status, reason = self.check_status(level, last_seen)
        
        result = {
            "username": self.username,
            "profile_id": self.profile_id,
            "level": level if level is not None else "Unknown",
            "last_seen": last_seen if last_seen else "N/A",
            "stats_status": stats_status,
            "account_status": status,
            "status_reason": reason
        }
        
        return result

# ============================================================
# HTML TEMPLATE
# ============================================================

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>R6 Siege Ban Checker</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #0a0a1a 0%, #1a1a3e 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            color: #fff;
        }
        
        .container {
            background: rgba(20, 20, 40, 0.9);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            padding: 40px;
            max-width: 600px;
            width: 90%;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.8);
            border: 1px solid rgba(255, 255, 255, 0.05);
        }
        
        h1 {
            text-align: center;
            font-size: 2em;
            margin-bottom: 10px;
            background: linear-gradient(90deg, #ff6b35, #ff2e63, #ff6b35);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            text-shadow: 0 0 20px rgba(255, 46, 99, 0.3);
        }
        
        .subtitle {
            text-align: center;
            color: #8888aa;
            margin-bottom: 30px;
            font-size: 0.9em;
        }
        
        .input-group {
            margin-bottom: 15px;
        }
        
        label {
            display: block;
            color: #aaaacc;
            margin-bottom: 5px;
            font-size: 0.9em;
            font-weight: 600;
        }
        
        input {
            width: 100%;
            padding: 12px 16px;
            border-radius: 10px;
            border: 2px solid rgba(255, 255, 255, 0.05);
            background: rgba(255, 255, 255, 0.05);
            color: #fff;
            font-size: 1em;
            transition: all 0.3s ease;
        }
        
        input:focus {
            outline: none;
            border-color: #ff2e63;
            background: rgba(255, 46, 99, 0.05);
            box-shadow: 0 0 20px rgba(255, 46, 99, 0.1);
        }
        
        input::placeholder {
            color: #555577;
        }
        
        button {
            width: 100%;
            padding: 14px;
            border: none;
            border-radius: 10px;
            background: linear-gradient(90deg, #ff2e63, #ff6b35);
            color: #fff;
            font-size: 1.1em;
            font-weight: 700;
            cursor: pointer;
            transition: all 0.3s ease;
            margin-top: 10px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        
        button:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 30px rgba(255, 46, 99, 0.3);
        }
        
        button:disabled {
            opacity: 0.5;
            cursor: not-allowed;
            transform: none;
        }
        
        #result {
            margin-top: 25px;
            display: none;
            animation: slideUp 0.5s ease;
        }
        
        @keyframes slideUp {
            from {
                opacity: 0;
                transform: translateY(20px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        
        .result-card {
            background: rgba(255, 255, 255, 0.03);
            border-radius: 15px;
            padding: 20px;
            border: 1px solid rgba(255, 255, 255, 0.05);
        }
        
        .result-row {
            display: flex;
            justify-content: space-between;
            padding: 10px 0;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
        }
        
        .result-row:last-child {
            border-bottom: none;
        }
        
        .result-label {
            color: #8888aa;
            font-weight: 500;
        }
        
        .result-value {
            color: #fff;
            font-weight: 600;
            text-align: right;
        }
        
        .status-badge {
            display: inline-block;
            padding: 6px 16px;
            border-radius: 20px;
            font-size: 0.9em;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        .status-valid {
            background: rgba(0, 255, 0, 0.2);
            color: #66ff66;
            border: 1px solid rgba(0, 255, 0, 0.3);
            animation: glowGreen 2s infinite;
        }
        
        .status-banned {
            background: rgba(255, 0, 0, 0.3);
            color: #ff4444;
            border: 1px solid rgba(255, 0, 0, 0.4);
            animation: pulse 1.5s infinite;
        }
        
        @keyframes pulse {
            0% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.7; transform: scale(0.95); }
            100% { opacity: 1; transform: scale(1); }
        }
        
        @keyframes glowGreen {
            0% { box-shadow: 0 0 5px rgba(0, 255, 0, 0.2); }
            50% { box-shadow: 0 0 20px rgba(0, 255, 0, 0.4); }
            100% { box-shadow: 0 0 5px rgba(0, 255, 0, 0.2); }
        }
        
        .status-error {
            background: rgba(255, 255, 255, 0.1);
            color: #8888aa;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        .error-message {
            color: #ff4444;
            padding: 15px;
            background: rgba(255, 0, 0, 0.1);
            border-radius: 10px;
            text-align: center;
            border: 1px solid rgba(255, 0, 0, 0.2);
        }
        
        .loading {
            display: none;
            text-align: center;
            padding: 20px;
        }
        
        .spinner {
            display: inline-block;
            width: 40px;
            height: 40px;
            border: 3px solid rgba(255, 255, 255, 0.1);
            border-top-color: #ff2e63;
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
        }
        
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        
        .footer {
            text-align: center;
            color: #444466;
            font-size: 0.8em;
            margin-top: 20px;
        }
        
        .footer a {
            color: #6666aa;
            text-decoration: none;
        }
        
        .footer a:hover {
            color: #8888cc;
        }
        
        .example {
            background: rgba(255, 255, 255, 0.03);
            border-radius: 8px;
            padding: 10px;
            margin-top: 5px;
            font-size: 0.8em;
            color: #666688;
            border: 1px solid rgba(255, 255, 255, 0.05);
        }
        
        .example span {
            color: #8888aa;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎮 R6 Ban Checker</h1>
        <p class="subtitle">Check Rainbow Six Siege account status</p>
        
        <form id="checkForm">
            <div class="input-group">
                <label>👤 Username</label>
                <input type="text" id="username" placeholder="Enter R6 username" required>
            </div>
            <div class="input-group">
                <label>🆔 Profile ID</label>
                <input type="text" id="profile_id" placeholder="Enter profile ID" required>
            </div>
            <div class="example">
                <span>Example:</span> username: "PlayerName" • profile_id: "abc123-def456-..."
            </div>
            <button type="submit" id="checkBtn">Check Account</button>
        </form>
        
        <div class="loading" id="loading">
            <div class="spinner"></div>
            <p style="margin-top: 10px; color: #8888aa;">Checking account...</p>
        </div>
        
        <div id="result"></div>
        
        <div class="footer">
            <p>🔍 Results from stats.cc • No credentials required</p>
        </div>
    </div>
    
    <script>
        document.getElementById('checkForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const username = document.getElementById('username').value.trim();
            const profile_id = document.getElementById('profile_id').value.trim();
            const btn = document.getElementById('checkBtn');
            const loading = document.getElementById('loading');
            const resultDiv = document.getElementById('result');
            
            if (!username || !profile_id) {
                alert('Please enter both username and profile ID');
                return;
            }
            
            btn.disabled = true;
            loading.style.display = 'block';
            resultDiv.style.display = 'none';
            
            try {
                const response = await fetch('/api/check', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ username, profile_id })
                });
                
                const data = await response.json();
                displayResult(data);
            } catch (error) {
                displayError('Network error. Please try again.');
                console.error('Error:', error);
            } finally {
                btn.disabled = false;
                loading.style.display = 'none';
            }
        });
        
        function displayResult(data) {
            const resultDiv = document.getElementById('result');
            
            if (data.status === 'ERROR') {
                resultDiv.innerHTML = `
                    <div class="error-message">
                        <strong>❌ Error</strong><br>
                        ${data.message}
                    </div>
                `;
                resultDiv.style.display = 'block';
                return;
            }
            
            const statusMap = {
                'VALID': 'status-valid',
                'BANNED': 'status-banned'
            };
            
            const statusClass = statusMap[data.account_status] || 'status-error';
            
            resultDiv.innerHTML = `
                <div class="result-card">
                    <div class="result-row">
                        <span class="result-label">Username</span>
                        <span class="result-value">${data.username || 'Unknown'}</span>
                    </div>
                    <div class="result-row">
                        <span class="result-label">Profile ID</span>
                        <span class="result-value" style="font-size:0.8em; word-break:break-all;">${data.profile_id || 'Unknown'}</span>
                    </div>
                    <div class="result-row">
                        <span class="result-label">Level</span>
                        <span class="result-value">${data.level || 'Unknown'}</span>
                    </div>
                    <div class="result-row">
                        <span class="result-label">Last Seen</span>
                        <span class="result-value">${data.last_seen || 'N/A'}</span>
                    </div>
                    <div class="result-row" style="border-bottom: none;">
                        <span class="result-label">Account Status</span>
                        <span class="result-value">
                            <span class="status-badge ${statusClass}">${data.account_status || 'UNKNOWN'}</span>
                        </span>
                    </div>
                </div>
            `;
            resultDiv.style.display = 'block';
            
            console.log('Result:', data);
        }
        
        function displayError(message) {
            const resultDiv = document.getElementById('result');
            resultDiv.innerHTML = `
                <div class="error-message">
                    <strong>❌ Error</strong><br>
                    ${message}
                </div>
            `;
            resultDiv.style.display = 'block';
        }
    </script>
</body>
</html>
"""

# ============================================================
# FLASK ROUTES
# ============================================================

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/check', methods=['POST'])
def check_account():
    try:
        data = request.get_json()
        
        if not data or 'username' not in data or 'profile_id' not in data:
            return jsonify({
                "status": "ERROR",
                "message": "Username and profile_id are required"
            }), 400
        
        username = data['username'].strip()
        profile_id = data['profile_id'].strip()
        
        if not username or not profile_id:
            return jsonify({
                "status": "ERROR",
                "message": "Username and profile_id cannot be empty"
            }), 400
        
        # Run the check (no login required)
        checker = R6BanChecker(username, profile_id)
        result = checker.analyze()
        
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"Error in check_account: {str(e)}", exc_info=True)
        return jsonify({
            "status": "ERROR",
            "message": f"An error occurred: {str(e)}"
        }), 500

# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    
    print("=" * 65)
    print("       🎮 R6 Siege Ban Checker Web Server")
    print("=" * 65)
    print()
    print(f"Server running at: http://localhost:{port}")
    print(f"Using curl_cffi: {USE_CURL_CFFI}")
    print()
    print("API Endpoint: POST /api/check")
    print('  Body: {"username": "player_name", "profile_id": "profile_id_here"}')
    print()
    print("Status results: VALID or BANNED only")
    print("=" * 65)
    print()
    
    app.run(host='0.0.0.0', port=port, debug=False)
