import os
import pandas as pd
import requests
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
from datetime import datetime
from zipfile import ZipFile

# Read credentials from GitHub Secrets
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

sheet = client.open("Stock Analysis NSE Python")

worksheet = sheet.worksheet("Final List")

today = datetime.now().strftime("%d%m%Y")

url = f"https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_{today}_F_0000.csv.zip"

zip_file = "bhavcopy.zip"

response = requests.get(url)

with open(zip_file, "wb") as file:
    file.write(response.content)

with ZipFile(zip_file, 'r') as zip_ref:
    zip_ref.extractall()

csv_file = [f for f in os.listdir() if f.endswith(".csv")][0]

df = pd.read_csv(csv_file)

df = df[[
    'SYMBOL',
    'OPEN_PRICE',
    'HIGH_PRICE',
    'LOW_PRICE',
    'CLOSE_PRICE',
    'TOTTRDQTY'
]]

top_stocks = df.sort_values(
    by='TOTTRDQTY',
    ascending=False
).head(50)

data = [top_stocks.columns.tolist()] + top_stocks.values.tolist()

worksheet.clear()
worksheet.update("A1", data)

print("Bhav Copy Updated Successfully")
