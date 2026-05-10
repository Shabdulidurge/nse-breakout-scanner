import os
import json
import pandas as pd
import yfinance as yf
import gspread

from oauth2client.service_account import ServiceAccountCredentials

# ---------------- GOOGLE SHEETS AUTH ---------------- #

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

# ---------------- OPEN GOOGLE SHEET ---------------- #

sheet = client.open("Stock Analysis NSE Python")

worksheet = sheet.worksheet("Final List")

# ---------------- NIFTY 50 STOCKS ---------------- #

stocks = [
    "ADANIENT.NS",
    "ADANIPORTS.NS",
    "APOLLOHOSP.NS",
    "ASIANPAINT.NS",
    "AXISBANK.NS",
    "BAJAJ-AUTO.NS",
    "BAJFINANCE.NS",
    "BAJAJFINSV.NS",
    "BEL.NS",
    "BHARTIARTL.NS",
    "BPCL.NS",
    "BRITANNIA.NS",
    "CIPLA.NS",
    "COALINDIA.NS",
    "DRREDDY.NS",
    "EICHERMOT.NS",
    "ETERNAL.NS",
    "GRASIM.NS",
    "HCLTECH.NS",
    "HDFCBANK.NS",
    "HDFCLIFE.NS",
    "HEROMOTOCO.NS",
    "HINDALCO.NS",
    "HINDUNILVR.NS",
    "ICICIBANK.NS",
    "INDUSINDBK.NS",
    "INFY.NS",
    "ITC.NS",
    "JIOFIN.NS",
    "JSWSTEEL.NS",
    "KOTAKBANK.NS",
    "LT.NS",
    "M&M.NS",
    "MARUTI.NS",
    "NESTLEIND.NS",
    "NTPC.NS",
    "ONGC.NS",
    "POWERGRID.NS",
    "RELIANCE.NS",
    "SBILIFE.NS",
    "SBIN.NS",
    "SHRIRAMFIN.NS",
    "SUNPHARMA.NS",
    "TATACONSUM.NS",
    "TATAMOTORS.NS",
    "TATASTEEL.NS",
    "TCS.NS",
    "TECHM.NS",
    "TITAN.NS",
    "ULTRACEMCO.NS",
    "WIPRO.NS"
]

# ---------------- FETCH LIVE DATA ---------------- #

data_list = []

for stock in stocks:

    try:

        ticker = yf.Ticker(stock)

        hist = ticker.history(period="1d")

        if not hist.empty:

            latest = hist.iloc[-1]

            data_list.append([
                stock.replace(".NS", ""),
                round(latest['Open'], 2),
                round(latest['High'], 2),
                round(latest['Low'], 2),
                round(latest['Close'], 2),
                int(latest['Volume'])
            ])

            print(f"Fetched: {stock}")

    except Exception as e:

        print(f"Error in {stock}: {e}")

# ---------------- CREATE DATAFRAME ---------------- #

df = pd.DataFrame(data_list, columns=[
    'SYMBOL',
    'OPEN_PRICE',
    'HIGH_PRICE',
    'LOW_PRICE',
    'CLOSE_PRICE',
    'TOTTRDQTY'
])

# ---------------- SORT BY VOLUME ---------------- #

top_stocks = df.sort_values(
    by='TOTTRDQTY',
    ascending=False
).head(50)

# ---------------- PREPARE GOOGLE SHEETS DATA ---------------- #

sheet_data = [top_stocks.columns.tolist()] + top_stocks.values.tolist()

# ---------------- UPDATE GOOGLE SHEET ---------------- #

worksheet.clear()

worksheet.update("A1", sheet_data)

print("Top 50 NSE Stocks Updated Successfully")
