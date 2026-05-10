import os
import json
import pandas as pd
import yfinance as yf
import gspread

from oauth2client.service_account import ServiceAccountCredentials

# Google Credentials
google_credentials_json = os.environ['GOOGLE_CREDENTIALS']

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

# Open Sheet
sheet = client.open("Stock Analysis NSE Python")

worksheet = sheet.worksheet("Final List")

# NSE Stock List
stocks = [
    "RELIANCE.NS",
    "TCS.NS",
    "INFY.NS",
    "HDFCBANK.NS",
    "ICICIBANK.NS",
    "SBIN.NS",
    "ITC.NS",
    "LT.NS",
    "BHARTIARTL.NS",
    "KOTAKBANK.NS"
]

data_list = []

for stock in stocks:

    ticker = yf.Ticker(stock)

    hist = ticker.history(period="5d")

    if not hist.empty:

        latest = hist.iloc[-1]

        data_list.append([
            stock.replace(".NS", ""),
            latest['Open'],
            latest['High'],
            latest['Low'],
            latest['Close'],
            latest['Volume']
        ])

# Create DataFrame
df = pd.DataFrame(data_list, columns=[
    'SYMBOL',
    'OPEN_PRICE',
    'HIGH_PRICE',
    'LOW_PRICE',
    'CLOSE_PRICE',
    'TOTTRDQTY'
])

# Sort by Volume
top_stocks = df.sort_values(
    by='TOTTRDQTY',
    ascending=False
)

# Prepare Google Sheets Data
sheet_data = [top_stocks.columns.tolist()] + top_stocks.values.tolist()

# Update Sheet
worksheet.clear()

worksheet.update("A1", sheet_data)

print("Yahoo Finance NSE Data Updated Successfully")
