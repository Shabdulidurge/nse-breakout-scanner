import os
import pandas as pd
import requests
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json

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

data = [
    ["Stock", "Price", "Volume"],
    ["RELIANCE", 2500, 100000]
]

worksheet.clear()
worksheet.update("A1", data)

print("Updated Successfully")
