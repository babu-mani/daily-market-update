# 📈 Daily Market Update Bot

An automated Python script that generates a daily financial dashboard covering Global Indices, F&O Ban List, and 52-Week High/Low stocks, and posts it to Twitter (X) automatically using GitHub Actions.

FEATURES
1. Fetches global market data including GIFT Nifty, Dow Futures, Nasdaq, S&P 500, Nikkei 225, Hang Seng, Gold, and Bitcoin using yfinance
2. Scrapes NSE data for the F&O Ban List and 52-Week High and Low stocks
3. Generates a high-quality 1080p dashboard image using Pillow
4. Automatically posts the image and summary text to Twitter (X) every day at 8:45 AM IST using GitHub Actions
5. Handles market holidays, empty datasets, and cloud execution paths safely

PROJECT STRUCTURE
daily-market-update/
api/
main.py            Core script
arial.ttf          Required font
arialbd.ttf        Required bold font
requirements.txt   Python dependencies
.github/workflows/
daily_post.yml     GitHub Actions cron workflow

SETUP AND USAGE

PREREQUISITES
1. GitHub account
2. Twitter (X) developer account with API access

SECRETS AND ENVIRONMENT VARIABLES
Add the following secrets in GitHub under Settings > Secrets and variables > Actions

TWITTER_API_KEY
TWITTER_API_SECRET
TWITTER_ACCESS_TOKEN
TWITTER_ACCESS_TOKEN_SECRET

MANUAL RUN FOR TESTING
1. Open the repository on GitHub
2. Go to the Actions tab
3. Select Daily Market Update workflow
4. Click Run workflow

SAMPLE OUTPUT
The generated dashboard image contains
1. Top section showing global indices and crypto
2. Bottom left section showing the current F&O Ban list
3. Bottom center section showing new 52-Week High stocks
4. Bottom right section showing new 52-Week Low stocks

DISCLAIMER
This project is for educational and informational purposes only.
It does not constitute financial advice.
Market data is sourced from public providers such as Yahoo Finance and NSE and may be delayed.

Created by @ChartWizMani
