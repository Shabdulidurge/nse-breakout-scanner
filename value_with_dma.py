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
# 1. GOOGLE CREDENTIALS
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
    print(
        f"CRITICAL ERROR: Google authentication failed: "
        f"{type(e).__name__}: {e}"
    )
    exit(1)


# ============================================================
# 2. GOOGLE SHEET
# ============================================================

spreadsheet_id = "1j1yjepGneUhHyhnMJGQ1s7YEfS4B78XT_IERrkYP1Oc"

try:

    worksheet = client.open_by_key(
        spreadsheet_id
    ).worksheet("Value_With_DMA")

except Exception as e:

    print(
        f"CRITICAL ERROR: Could not open Value_With_DMA: "
        f"{type(e).__name__}: {e}"
    )
    exit(1)


# ============================================================
# 3. NSE SESSION
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


# Establish NSE session/cookies
try:

    print("Connecting to NSE...")

    homepage = session.get(
        "https://www.nseindia.com/",
        headers=headers,
        timeout=30
    )

    print(
        f"NSE homepage status: {homepage.status_code}"
    )

except Exception as e:

    print(
        f"WARNING: NSE homepage connection failed: "
        f"{type(e).__name__}: {e}"
    )


# ============================================================
# 4. NSE BHAVCOPY FETCHER
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

        print(
            f"HTTP Status: {response.status_code}"
        )

        print(
            f"Response Size: "
            f"{len(response.content) / 1024:.2f} KB"
        )

        # ----------------------------------------------------
        # HTTP CHECK
        # ----------------------------------------------------

        if response.status_code != 200:

            print(
                f"FAILED: NSE returned HTTP "
                f"{response.status_code}"
            )

            try:
                print(
                    "NSE response:",
                    response.text[:300]
                )
            except Exception:
                pass

            return None

        # ----------------------------------------------------
        # ZIP CHECK
        # ----------------------------------------------------

        if not response.content.startswith(b"PK"):

            print(
                "FAILED: NSE response is not a ZIP file."
            )

            print(
                "First bytes:",
                response.content[:100]
            )

            return None

        # ----------------------------------------------------
        # OPEN ZIP
        # ----------------------------------------------------

        with zipfile.ZipFile(
            io.BytesIO(response.content)
        ) as z:

            files = z.namelist()

            print("Files inside ZIP:")

            for file in files:
                print(f"  - {file}")

            csv_files = [
                f for f in files
                if f.lower().endswith(".csv")
            ]

            if not csv_files:

                print(
                    "FAILED: No CSV file found inside ZIP."
                )

                return None

            csv_filename = csv_files[0]

            print(
                f"Reading CSV: {csv_filename}"
            )

            with z.open(csv_filename) as f:

                try:

                    df = pd.read_csv(
                        f,
                        low_memory=False
                    )

                except UnicodeDecodeError:

                    print(
                        "UTF-8 failed. Trying latin-1..."
                    )

                    f.seek(0)

                    df = pd.read_csv(
                        f,
                        encoding="latin-1",
                        low_memory=False
                    )

        # ----------------------------------------------------
        # CLEAN COLUMN NAMES
        # ----------------------------------------------------

        df.columns = [
            str(c).strip()
            for c in df.columns
        ]

        print("")
        print("NSE Columns:")
        print(df.columns.tolist())

        # ----------------------------------------------------
        # FIND SYMBOL
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

        # ----------------------------------------------------
        # FIND CLOSE
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # FIND SERIES
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # FIND VOLUME
        # ----------------------------------------------------

        vol_col = next(
            (
                c for c in [
                    "TtlTradgVol",
                    "TtlTrdQty",
                    "TotTrdQty",
                    "TOTTRDQTY"
                ]
                if c in df.columns
            ),
            None
        )

        print("")
        print("Detected columns:")
        print(f"Symbol : {sym_col}")
        print(f"Close  : {close_col}")
        print(f"Series : {series_col}")
        print(f"Volume : {vol_col}")

        # ----------------------------------------------------
        # VALIDATE COLUMNS
        # ----------------------------------------------------

        if not sym_col:

            print(
                "FAILED: Symbol column not found."
            )

            return None

        if not close_col:

            print(
                "FAILED: Close price column not found."
            )

            return None

        if not vol_col:

            print(
                "FAILED: Trading volume column not found."
            )

            return None

        # ----------------------------------------------------
        # KEEP EQ ONLY
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
                f"EQ filter: "
                f"{before} → {len(df)} rows"
            )

        # ----------------------------------------------------
        # REMOVE ETFs / UNWANTED
        # ----------------------------------------------------

        filter_keywords = (
            "BEES|ETF|GOLD|LIQUID|CASE|SILVER|LIQ"
        )

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
            f"ETF/unwanted filter: "
            f"{before} → {len(df)} rows"
        )

        # ----------------------------------------------------
        # NUMERIC CONVERSION
        # ----------------------------------------------------

        df[vol_col] = pd.to_numeric(
            df[vol_col],
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
                vol_col,
                close_col
            ]
        )

        print(
            f"Valid rows after cleaning: "
            f"{len(df)}"
        )

        # ----------------------------------------------------
        # TOP 250 BY TRADING VOLUME
        # ----------------------------------------------------

        df_top = (
            df.sort_values(
                by=vol_col,
                ascending=False
            )
            .head(250)
        )

        # ----------------------------------------------------
        # SAFETY CHECK
        # ----------------------------------------------------

        if len(df_top) < 200:

            print(
                f"FAILED: Only {len(df_top)} stocks "
                f"found. Expected approximately 250."
            )

            print(
                "Google Sheet will NOT be updated."
            )

            return None

        # ----------------------------------------------------
        # SHOW TOP 10
        # ----------------------------------------------------

        print("")
        print("TOP 10 BY TRADING VOLUME:")

        print(
            df_top[
                [
                    sym_col,
                    vol_col,
                    close_col
                ]
            ]
            .head(10)
            .to_string(index=False)
        )

        # ----------------------------------------------------
        # PREPARE DATA
        # ----------------------------------------------------

        result = df_top[
            [
                sym_col,
                vol_col,
                close_col
            ]
        ].values.tolist()

        print("")
        print(
            f"SUCCESS: {len(result)} stocks prepared."
        )

        return result

    # ========================================================
    # ERROR HANDLING
    # ========================================================

    except zipfile.BadZipFile as e:

        print(
            f"FAILED: Invalid ZIP file: {e}"
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
# 5. FIND LATEST AVAILABLE TRADING DAY
# ============================================================

today = datetime.now()

data_to_insert = None
fetched_date_str = ""

print("")
print("=" * 70)
print("SEARCHING FOR LATEST NSE DATA")
print("=" * 70)

# Search 30 calendar days
for i in range(30):

    test_date = today - timedelta(days=i)

    # Skip Saturday and Sunday
    if test_date.weekday() >= 5:
        continue

    result = fetch_bhavcopy_for_date(
        test_date
    )

    if result:

        data_to_insert = result

        fetched_date_str = test_date.strftime(
            "%d-%b-%Y"
        )

        print("")
        print(
            f"FOUND VALID DATA: "
            f"{fetched_date_str}"
        )

        break

    # Small pause between NSE requests
    time.sleep(1)


# ============================================================
# 6. UPDATE GOOGLE SHEET
# ============================================================

if data_to_insert:

    try:

        print("")
        print("=" * 70)
        print("UPDATING VALUE_WITH_DMA SHEET")
        print("=" * 70)

        # Clear previous Top 250
        worksheet.batch_clear(
            ["A2:C251"]
        )

        # Insert new Top 250
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
            "%d-%b %H:%M"
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
        print("=" * 70)
        print("SUCCESS: VALUE_WITH_DMA UPDATED")
        print("=" * 70)
        print(
            f"Data Date   : {fetched_date_str}"
        )
        print(
            f"Stocks      : {len(data_to_insert)}"
        )
        print(
            f"Last Update : {ist_now} IST"
        )
        print("=" * 70)

    except Exception as e:

        print("")
        print("=" * 70)
        print("GOOGLE SHEET UPDATE FAILED")
        print("=" * 70)
        print(
            f"{type(e).__name__}: {e}"
        )
        print("=" * 70)

else:

    print("")
    print("=" * 70)
    print("FAILED: NO VALID NSE DATA FOUND")
    print("=" * 70)
    print(
        "Checked the last 30 calendar days."
    )
    print(
        "Google Sheet was NOT changed."
    )
    print("=" * 70)
