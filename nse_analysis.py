import os
import json
import pandas as pd
import gspread

from oauth2client.service_account import ServiceAccountCredentials
from nsepython import *

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

# Fetch NSE Data
stocks = nsefetch(
    "https://www.nseindia.com/api/equity-stockIndices?index=NIFTY%20250"
)

print(stocks)

df = pd.DataFrame(stocks)

# Select Required Columns
df = df[[
    'symbol',
    'open',
    'dayHigh',
    'dayLow',
    'lastPrice',
    'totalTradedVolume'
]]

# Rename Columns
df.columns = [
    'SYMBOL',
    'OPEN_PRICE',
    'HIGH_PRICE',
    'LOW_PRICE',
    'CLOSE_PRICE',
    'TOTTRDQTY'
]

# Sort by Volume
top_stocks = df.sort_values(
    by='TOTTRDQTY',
    ascending=False
).head(50)

# Convert Data for Google Sheets
data = [top_stocks.columns.tolist()] + top_stocks.values.tolist()

# Update Google Sheet
worksheet.clear()
worksheet.update("A1", data)

print("NSE Data Updated Successfully")
