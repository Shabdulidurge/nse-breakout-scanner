import gspread
from oauth2client.service_account import ServiceAccountCredentials

import pandas as pd
import requests
import zipfile
import io
from datetime import datetime, timedelta
import os
import json
import time


# ============================================================
# 1. GOOGLE SHEETS CREDENTIALS
# ============================================================

creds_json = os.environ.get("GOOGLE_CREDENTIALS")

if not creds_json:
    print("CRITICAL ERROR: GOOGLE_CREDENTIALS secret is missing!")
    exit(1)

try:
    creds_dict = json.loads(creds_json)

    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]

    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        creds_dict,
        scope
    )

    client = gspread.authorize(creds)

except Exception as e:
    print(f"CRITICAL ERROR: Google authentication failed: {type(e).__name__}: {e}")
    exit(1)


spreadsheet_id = "1j1yjepGneUhHyhnMJGQ1s7YEfS4B78XT_IERrkYP1Oc"

try:
    worksheet = client.open_by_key(spreadsheet_id).worksheet("Final List")
except Exception as e:
    print(f"CRITICAL ERROR: Could not open Google Sheet: {type(e).__name__}: {e}")
    exit(1)


# ============================================================
# 2. NSE SESSION
# ============================================================

session = requests.Session()

headers = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/151.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/",
    "Connection": "keep-alive",
}


# First visit NSE homepage to establish cookies/session
try:
    print("Connecting to NSE...")
    homepage = session.get(
        "https://www.nseindia.com/",
        headers=headers,
        timeout=30
    )

    print(f"NSE homepage status: {homepage.status_code}")

except Exception as e:
    print(f"WARNING: NSE homepage connection failed: {type(e).__name__}: {e}")


# ============================================================
# 3. FETCH NSE BHAVCOPY
# ============================================================

def fetch_bhavcopy_for_date(date_obj):

    date_str = date_obj.strftime("%Y%m%d")

    url = (
        "https://nsearchives.nseindia.com/content/cm/"
        f"BhavCopy_NSE_CM_0_0_0_{date_str}_F_0000.csv.zip"
    )

    print("")
    print("=" * 70)
    print(f"Checking NSE Bhavcopy: {date_str}")
    print(f"URL: {url}")

    try:

        response = session.get(
            url,
            headers=headers,
            timeout=30
        )

        print(f"HTTP Status: {response.status_code}")
        print(f"File Size: {len(response.content) / 1024:.2f} KB")

        if response.status_code != 200:

            print(
                f"FAILED: NSE returned HTTP {response.status_code}"
            )

            # Print small portion of response for debugging
            try:
                print(
                    "NSE response:",
                    response.text[:300]
                )
            except:
                pass

            return None

        # ----------------------------------------------------
        # Check whether response is actually a ZIP
        # ----------------------------------------------------

        if not response.content.startswith(b"PK"):

            print("FAILED: Response is NOT a ZIP file.")
            print(
                "First 100 bytes:",
                response.content[:100]
            )

            return None

        # ----------------------------------------------------
        # Open ZIP
        # ----------------------------------------------------

        with zipfile.ZipFile(io.BytesIO(response.content)) as z:

            files = z.namelist()

            print("Files inside ZIP:")
            for file in files:
                print(f"  - {file}")

            csv_files = [
                f for f in files
                if f.lower().endswith(".csv")
            ]

            if not csv_files:

                print("FAILED: No CSV file found inside ZIP.")
                return None

            csv_filename = csv_files[0]

            print(f"Reading CSV: {csv_filename}")

            with z.open(csv_filename) as f:

                # Try UTF-8 first
                try:
                    df = pd.read_csv(f, low_memory=False)

                except UnicodeDecodeError:

                    print("UTF-8 failed. Trying latin-1...")

                    f.seek(0)

                    df = pd.read_csv(
                        f,
                        encoding="latin-1",
                        low_memory=False
                    )

        # ----------------------------------------------------
        # Clean column names
        # ----------------------------------------------------

        df.columns = [
            str(c).strip()
            for c in df.columns
        ]

        print("")
        print("Columns received from NSE:")
        print(df.columns.tolist())

        # ----------------------------------------------------
        # Identify columns
        # ----------------------------------------------------

        sym_col = next(
            (
                c for c in [
                    "TckrSymb",
                    "SYMBOL",
                    "Symbol"
                ]
                if c in df.columns
            ),
            None
        )

        close_col = next(
            (
                c for c in [
                    "ClsPric",
                    "CLOSE",
                    "Close",
                    "ClsPrice"
                ]
                if c in df.columns
            ),
            None
        )

        series_col = next(
            (
                c for c in [
                    "SctySrs",
                    "SERIES",
                    "Series"
                ]
                if c in df.columns
            ),
            None
        )

        turnover_col = next(
            (
                c for c in [
                    "TtlTrfVal",
                    "TtlTrdVal",
                    "TotalTradedValue",
                    "TURNOVER_LACS",
                    "TURNOVER"
                ]
                if c in df.columns
            ),
            None
        )

        print("")
        print("Detected columns:")
        print(f"Symbol   : {sym_col}")
        print(f"Close    : {close_col}")
        print(f"Series   : {series_col}")
        print(f"Turnover : {turnover_col}")

        # ----------------------------------------------------
        # Validate columns
        # ----------------------------------------------------

        if not sym_col:
            print("FAILED: Stock symbol column not found.")
            return None

        if not close_col:
            print("FAILED: Closing price column not found.")
            return None

        if not turnover_col:
            print("FAILED: Turnover column not found.")
            return None

        # ----------------------------------------------------
        # Keep EQ stocks
        # ----------------------------------------------------

        if series_col:

            before = len(df)

            df = df[
                df[series_col]
                .astype(str)
                .str.strip()
                .str.upper()
                == "EQ"
            ]

            print(
                f"EQ filter: {before} → {len(df)} rows"
            )

        # ----------------------------------------------------
        # Remove ETFs / unwanted instruments
        # ----------------------------------------------------

        filter_keywords = r"BEES|ETF|GOLD|LIQUID"

        before = len(df)

        df = df[
            ~df[sym_col]
            .astype(str)
            .str.contains(
                filter_keywords,
                case=False,
                na=False,
                regex=True
            )
        ]

        print(
            f"ETF/unwanted filter: {before} → {len(df)} rows"
        )

        # ----------------------------------------------------
        # Convert turnover and close to numbers
        # ----------------------------------------------------

        df[turnover_col] = pd.to_numeric(
            df[turnover_col],
            errors="coerce"
        )

        df[close_col] = pd.to_numeric(
            df[close_col],
            errors="coerce"
        )

        # Remove invalid rows

        df = df.dropna(
            subset=[
                sym_col,
                turnover_col,
                close_col
            ]
        )

        print(
            f"Valid rows after cleaning: {len(df)}"
        )

        # ----------------------------------------------------
        # TOP 250 BY TURNOVER
        # ----------------------------------------------------

        df_top = (
            df.sort_values(
                by=turnover_col,
                ascending=False
            )
            .head(250)
        )

        print("")
        print("TOP 10 BY TURNOVER:")
        print(
            df_top[
                [sym_col, turnover_col, close_col]
            ].head(10).to_string(index=False)
        )

        # ----------------------------------------------------
        # Prepare Google Sheet data
        # ----------------------------------------------------

        result = df_top[
            [sym_col, turnover_col, close_col]
        ].values.tolist()

        print("")
        print(
            f"SUCCESS: {len(result)} stocks prepared."
        )

        return result

    except zipfile.BadZipFile as e:

        print(
            f"FAILED: Bad ZIP file: {e}"
        )

        return None

    except pd.errors.ParserError as e:

        print(
            f"FAILED: CSV parsing error: {e}"
        )

        return None

    except Exception as e:

        print(
            f"FAILED: {type(e).__name__}: {e}"
        )

        return None


# ============================================================
# 4. FIND MOST RECENT AVAILABLE TRADING DAY
# ============================================================

today = datetime.now()

data_to_insert = None
fetched_date_str = ""
fetched_date_obj = None


# Search 30 calendar days instead of only 7
for i in range(30):

    test_date = today - timedelta(days=i)

    # Skip Saturday and Sunday
    if test_date.weekday() >= 5:
        continue

    result = fetch_bhavcopy_for_date(test_date)

    if result:

        data_to_insert = result

        fetched_date_obj = test_date

        fetched_date_str = test_date.strftime(
            "%d-%b-%Y"
        )

        print("")
        print(
            f"FOUND DATA: {fetched_date_str}"
        )

        break

    # Small pause so we don't hammer NSE
    time.sleep(1)


# ============================================================
# 5. UPDATE GOOGLE SHEET
# ============================================================

if data_to_insert:

    try:

        print("")
        print("=" * 70)
        print("UPDATING GOOGLE SHEET...")
        print("=" * 70)

        # Clear old data
        worksheet.batch_clear(
            ["A2:C251"]
        )

        # Insert new data
        worksheet.update(
            "A2",
            data_to_insert
        )

        # IST timestamp
        ist_now = (
            datetime.utcnow()
            + timedelta(
                hours=5,
                minutes=30
            )
        ).strftime(
            "%d-%b-%Y %H:%M"
        )

        status_msg = (
            f"Data Date: {fetched_date_str} | "
            f"Last Update: {ist_now} (IST)"
        )

        worksheet.update(
            "K2",
            [[status_msg]]
        )

        print("")
        print("==========================================")
        print("          SUCCESS 🎉")
        print("==========================================")
        print(
            f"Data Date   : {fetched_date_str}"
        )
        print(
            f"Stocks      : {len(data_to_insert)}"
        )
        print(
            f"Last Update : {ist_now} IST"
        )
        print("Google Sheet updated successfully!")
        print("==========================================")

    except Exception as e:

        print("")
        print("==========================================")
        print("GOOGLE SHEET UPDATE FAILED ❌")
        print("==========================================")
        print(
            f"{type(e).__name__}: {e}"
        )
        print("==========================================")


else:

    print("")
    print("==========================================")
    print("          COMPLETE FAILURE ❌")
    print("==========================================")
    print(
        "Could not find/process NSE Bhavcopy "
        "in the last 30 calendar days."
    )
    print("The Google Sheet was NOT changed.")
    print("==========================================")
