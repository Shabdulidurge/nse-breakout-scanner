import os
import json
import pandas as pd
import requests
import gspread

from oauth2client.service_account import ServiceAccountCredentials

# Read credentials from GitHub Secrets
google_credentials_json = os.environ['GOOGLE_CREDENTIALS']

# Google Sheets Authentication
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

creds_dict = json.loads(google_credentials_json)

creds = ServiceAccountCredentials.from_json_keyfile_dict(
    creds_dict,
    scope
)

client = gspread.authorize(creds)

# Open Google Sheet
sheet = client.open("Stock Analysis NSE Python")

worksheet = sheet.worksheet("Final List")

# NSE Session
session = requests.Session()

headers = {
    "User-Agent": "Mozilla/5.0",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/"
}

# Open NSE homepage first
session.get("https://www.nseindia.com", headers=headers)

# Fetch NSE stock data
url = "https://www.nseindia.com/api/equity-stockIndices?index=NIFTY%20250"

response = session.get(url, headers=headers)

print(response.status_code)

data_json = response.json()

print(data_json.keys())

# Convert data to dataframe
df = pd.DataFrame(data_json['data'])

# Select required columns
df = df[[
    'symbol',
    'open',
    'dayHigh',
    'dayLow',
    'lastPrice',
    'totalTradedVolume'
]]

# Rename columns
df.columns = [
    'SYMBOL',
    'OPEN_PRICE',
    'HIGH_PRICE',
    'LOW_PRICE',
    'CLOSE_PRICE',
    'TOTTRDQTY'
]

# Sort by traded volume
top_stocks = df.sort_values(
    by='TOTTRDQTY',
    ascending=False
).head(50)

# Prepare for Sheets
sheet_data = [top_stocks.columns.tolist()] + top_stocks.values.tolist()

# Update Google Sheet
worksheet.clear()
worksheet.update("A1", sheet_data)

print("NSE Data Updated Successfully")
