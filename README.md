# R6 Siege Ban Checker

A Flask-based web application to check Rainbow Six Siege account ban status without requiring login credentials.

## Features

- ✅ No login required
- 🔍 Scrapes stats.cc for account information
- 🎮 Shows player level and last seen status
- 🚀 Fast and lightweight
- 🌐 Clean, modern web interface

## Technology Stack

- **Backend:** Flask (Python)
- **Scraping:** BeautifulSoup4, curl-cffi
- **Hosting:** Render (with Gunicorn)
- **Frontend:** HTML/CSS/JavaScript

## Deployment on Render

### Prerequisites
- A GitHub repository with the code
- A Render account (free tier available)

### Setup Steps

1. **Fork/Clone this repository**
   ```bash
   git clone https://github.com/The1Realhellboy/r6-ban-checker.git
   ```

2. **Create a new Web Service on Render**
   - Go to [render.com](https://render.com)
   - Click "New +" → "Web Service"
   - Connect your GitHub repository
   - Select this repository

3. **Configure the Service**
   - **Name:** `r6-ban-checker` (or your preferred name)
   - **Environment:** Python 3
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn bancheck:app`
   - **Instance Type:** Free tier is fine for personal use

4. **Deploy**
   - Click "Deploy"
   - Wait for the build to complete (usually 2-3 minutes)
   - Your app will be live at: `https://<your-service-name>.onrender.com`

## Local Development

### Install Dependencies
```bash
pip install -r requirements.txt
```

### Run Locally
```bash
python bancheck.py
```

Visit `http://localhost:5000` in your browser.

## API Usage

### Check Account Status
**Endpoint:** `POST /api/check`

**Request:**
```json
{
  "username": "PlayerName",
  "profile_id": "abc123-def456-..."
}
```

**Response:**
```json
{
  "username": "PlayerName",
  "profile_id": "abc123-def456-...",
  "level": 150,
  "last_seen": "2 days ago",
  "stats_status": "OK",
  "account_status": "VALID",
  "status_reason": "Account is valid (level 150, last seen: 2 days ago)"
}
```

## How It Works

1. Takes a username and profile ID
2. Fetches account data from stats.cc
3. Extracts player level and last seen status
4. Analyzes the data to determine if account is:
   - **VALID:** Active account with level > 5
   - **BANNED:** Level 0, no last seen data, or level < 5

## Account Status Criteria

**Account is BANNED if:**
- Level is 0
- No last seen data available
- Level is less than 5

**Account is VALID if:**
- Level > 0 with valid last seen data
- Level > 5 (regardless of last seen status)

## Environment Variables

- `PORT`: The port to run the server on (default: 5000)
  - Render automatically sets this to their assigned port

## File Structure
```
r6-ban-checker/
├── bancheck.py          # Main Flask application
├── requirements.txt     # Python dependencies
├── Procfile            # Render deployment config
└── README.md           # This file
```

## Notes

- This tool uses public stats.cc API/website - no authentication needed
- Respects rate limits with reasonable timeouts
- Free tier on Render may have limitations on concurrent connections

## License

This project is open source and available under the MIT License.

## Support

If you encounter issues:
1. Check Render deployment logs
2. Ensure all files are in the repository
3. Verify Python version compatibility (3.8+)
4. Check the stats.cc website is accessible

---

**Made with ❤️ for Rainbow Six Siege players**
