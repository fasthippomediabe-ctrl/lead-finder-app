import streamlit as st

# ---------------- USER ACCOUNTS ----------------

USERS = {
    "boss": {"password": "leadfinder123", "role": "admin"},
    "bryan": {"password": "bryan2024", "role": "admin"},
    "user1": {"password": "user1pass", "role": "user"},
    "user2": {"password": "user2pass", "role": "user"},
}

def check_login():
    def login_form():
        with st.form("Login"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("Login")

            if submit:
                if username in USERS and USERS[username]["password"] == password:
                    st.session_state["logged_in"] = True
                    st.session_state["username"] = username
                    st.session_state["role"] = USERS[username]["role"]
                    st.rerun()
                else:
                    st.error("Invalid username or password")

    if "logged_in" not in st.session_state:
        st.session_state["logged_in"] = False

    if not st.session_state["logged_in"]:
        st.title("Lead Finder Login")
        login_form()
        st.stop()

check_login()

# ---------------- IMPORTS ----------------

import os
import re
import time
import json
import pandas as pd
import requests
from datetime import datetime
from urllib.parse import urljoin
from apify_client import ApifyClient
import gspread

# ---------------- CONFIG ----------------

SPREADSHEET_ID = "1oksMAwVZNeuf1EIRYz9EXoli9C1pkUF4KYrunRoZQ7A"

ACTORS = {
    "Google Business Profile": "compass/crawler-google-places",
    "Angi (Angie's List)": "fatihtahta/angi-scraper-with-contacts",
}

COUNTRY_DATA = {
    "United States": {
        "currency": "USD",
        "language": "en",
        "cities": [
            "Austin, Texas",
            "Dallas, Texas",
            "Miami, Florida",
            "Houston, Texas",
            "Phoenix, Arizona",
            "Denver, Colorado",
            "Los Angeles, California",
            "Chicago, Illinois",
            "Seattle, Washington",
            "New York, New York",
        ],
    },
    "Canada": {
        "currency": "CAD",
        "language": "en",
        "cities": [
            "Toronto, Ontario",
            "Vancouver, British Columbia",
            "Calgary, Alberta",
            "Montreal, Quebec",
            "Ottawa, Ontario",
        ],
    },
    "United Kingdom": {
        "currency": "GBP",
        "language": "en",
        "cities": [
            "London",
            "Manchester",
            "Birmingham",
            "Liverpool",
            "Leeds",
        ],
    },
    "Philippines": {
        "currency": "PHP",
        "language": "en",
        "cities": [
            "Manila",
            "Quezon City",
            "Cebu City",
            "Davao City",
            "Makati",
        ],
    },
}

ANGI_CATEGORIES = [
    "air-duct-cleaning", "animal-removal", "tv-antenna", "appliance-repair",
    "architects", "asbestos-removal", "awnings", "remodeling-basements",
    "basement-waterproofing", "basketball-goals", "bathtub-refinishing",
    "biohazard-remediation", "blind-cleaning", "cabinet-makers",
    "cabinet-refinishing", "carpet-cleaning", "carpet", "ceiling-fans",
    "central-vacuum-cleaners", "childproofing", "chimney-caps",
    "chimney-repair", "chimney-sweep", "cleaning", "closets",
    "computer-repair", "concrete-driveways", "concrete-repair", "countertops",
    "deck-maintenance", "decks-and-porches", "dock-building-repair",
    "pet-fencing", "doors", "drain-cleaning", "drain-pipe-installation",
    "drapery-cleaning", "driveway-gates", "driveways", "dryer-vent-cleaning",
    "drywall", "dumpster-rental", "earthquake-retrofit", "egress",
    "electrical", "epoxy-flooring", "excavating", "fencing", "fireplaces",
    "firewood", "buffing-and-polishing", "floor-cleaning", "flooring",
    "foundation-repair", "fountains", "furniture-refinishing", "garage-builders",
    "garage-doors", "gas-logs", "gas-leak-repair", "contractor",
    "generator-installers", "glass-block", "glass-and-mirrors",
    "gas-grill-repair", "gutter-cleaning", "gutter-repair-replacement",
    "handyman-service", "landscaping-hardscaping-and-pavers",
    "hardwood-flooring", "hauling", "heating-oil-companies",
    "holiday-decorating", "home-automation", "home-builders",
    "energy-audit", "home-inspection", "kitchen-and-bath-remodeling",
    "home-security-systems", "home-staging", "home-theater-systems",
    "home-warranty-companies", "house-cleaning", "exterior-painting",
    "hurricane-shutters", "hvac", "insulation", "interior-design",
    "interior-painting", "wrought-iron", "lawn-irrigation", "appraisals",
    "land-surveying", "landscaping-lighting", "appliance-sales", "landscaping",
    "lawn-and-yard-work", "lawn-mower-repair", "lawn-fertilization-and-treatment",
    "lead-testing-and-removal", "leaf-removal", "leather-and-vinyl-repair",
    "lighting", "locksmiths", "mailbox-repair", "marble-and-granite",
    "masonry", "metal-fabrication-and-restoration",
    "remodeling-modular-and-mobile-home", "mold-testing-and-remediation",
    "moving", "concrete-leveling", "mulch-and-topsoil", "plant-nurseries",
    "oriental-rug-cleaning", "outdoor-kitchens", "sunroom-and-patio-remodeling",
    "patios", "pest-control", "home-phone-service", "phone-repair",
    "piano-moving", "plaster-plaster-repair", "playground-equipment",
    "plumbing", "pool-and-spa-service", "swimming-pools", "pressure-washing",
    "home-and-garage-organization", "radon-testing", "real-estate-agents",
    "property-appraiser", "roof-cleaning", "roof-ice-and-snow-removal",
    "roofing", "roto-tilling", "satellite-tv-service", "screen-repair",
    "septic-tank", "sewer-cleaning", "siding", "skylights",
    "small-appliance-repair", "snow-removal", "solar-panels",
    "concrete-stamped-decorative", "stone-and-gravel", "structural-engineering",
    "stucco", "ceramic-tile", "garbage-collection", "tree-service",
    "upholstering", "upholstery-cleaning", "wallpapering",
    "wallpaper-removal", "water-and-smoke-damage", "water-heaters",
    "water-softeners", "welding", "wells-and-pumps", "window-cleaning",
    "windows", "hurricane-film", "window-tinting", "window-treatments",
    "woodworking",
]

EXCLUDED_BUSINESSES = [
    "amazon",
    "walmart",
    "target",
    "costco",
    "best buy",
    "home depot",
    "lowes",
]

EMAIL_REGEX = re.compile(r'([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})')

HEADERS = {"User-Agent": "Mozilla/5.0"}

COMMON_CONTACT_PATHS = [
    "",
    "/contact",
    "/contact-us",
    "/about",
    "/about-us",
]

# ---------------- AUTO-UPDATE ANGI CATEGORIES ----------------

def fetch_angi_categories():
    """Scrape Angi companylist pages to discover all available category slugs."""
    from bs4 import BeautifulSoup
    categories = set(ANGI_CATEGORIES)  # start with existing

    # Scrape a few state/city pages to find category links
    sample_pages = [
        "https://www.angi.com/companylist/us/tx/austin/",
        "https://www.angi.com/companylist/us/ca/los-angeles/",
        "https://www.angi.com/companylist/us/ny/new-york/",
        "https://www.angi.com/companylist/us/fl/miami/",
        "https://www.angi.com/companylist/us/il/chicago/",
    ]

    for page_url in sample_pages:
        try:
            r = requests.get(page_url, headers=HEADERS, timeout=10)
            if r.status_code != 200:
                continue
            soup = BeautifulSoup(r.text, "html.parser")
            for link in soup.find_all("a", href=True):
                href = link["href"]
                # Category links look like: /companylist/us/tx/austin/plumbing.htm
                if "/companylist/us/" in href and href.endswith(".htm"):
                    parts = href.rstrip("/").split("/")
                    if len(parts) >= 2:
                        slug = parts[-1].replace(".htm", "")
                        if slug and slug not in ["index"]:
                            categories.add(slug)
        except:
            continue

    return sorted(categories)

# ---------------- PAGE ----------------

st.set_page_config(page_title="Lead Finder", page_icon="🌍", layout="wide")

st.title("🌍 All-in-One Lead Finder")

# ---------------- SIDEBAR: USER + TOOLS ----------------

st.sidebar.markdown(f"Logged in as: **{st.session_state.get('username', '')}** ({st.session_state.get('role', '')})")
if st.sidebar.button("Logout"):
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

st.sidebar.divider()

st.sidebar.markdown("[Check Apify Usage & Billing](https://console.apify.com/billing)")
st.sidebar.divider()

# Downloadable instructions
lead_finder_instructions = """ALL-IN-ONE LEAD FINDER - User Guide
=====================================

STEP 1: Select Lead Source
- Google Business Profile: Search businesses worldwide via Google Maps
- Angi (Angie's List): Search US-only service businesses

STEP 2: Configure Search (Google Business Profile)
- Select a country (US, Canada, UK, Philippines, or type any country)
- Enter industries (one per line, e.g. "dentist", "plumber", "gym")
- Select preset cities or type any city worldwide
- Set max results per search (up to 200)
- Set rating and review filters (min/max)

STEP 2: Configure Search (Angi)
- Select a category/service type from the list
- Enter city and state
- Set max results (up to 1000)
- Optionally paste a custom Angi company list URL

STEP 3: Email Options
- Enable/disable email scraping from business websites
- Set max websites to scan for emails (default: 50)

STEP 4: Run the Scraper
- Click "Run Scraper" to start
- Results show with Opportunity Score (HIGH/MEDIUM/LOW)
- Duplicate businesses from previous scrapes are flagged

STEP 5: Filter & Download Results
- Search results by name, address, or category
- Filter duplicates (New only / Duplicates only)
- Download as CSV or Excel
- Results auto-save to Google Sheets

FEATURES:
- Opportunity scoring based on rating, reviews, and website presence
- Chain/franchise filtering (excludes Amazon, Walmart, etc.)
- Email extraction from business websites
- Duplicate detection across previous scrapes
- Scrape history with re-download capability

TIPS:
- Use "Search all available listings" for comprehensive scrapes (uses more credits)
- Reduce email scan limit for faster results
- Check Apify billing to monitor credit usage
- Admin users can sync Angi categories to discover new service types
"""

with st.sidebar.expander("**How to use**", expanded=False):
    st.markdown(
        "1. Select lead source (Google or Angi)\n"
        "2. Enter industries, cities, and filters\n"
        "3. Enable email scraping (optional)\n"
        "4. Click **Run Scraper**\n"
        "5. Filter results and download CSV/Excel\n"
        "6. Auto-saved to Google Sheets"
    )
    st.download_button(
        "📄 Download Full Instructions",
        lead_finder_instructions.encode("utf-8"),
        "Lead_Finder_Instructions.txt",
        "text/plain",
        use_container_width=True,
    )

st.sidebar.divider()

# ---------------- SOURCE SELECTOR ----------------

source = st.selectbox("Lead Source", list(ACTORS.keys()))

st.divider()

# ---------------- SHARED: EMAIL OPTIONS ----------------

st.sidebar.markdown(f"[View Scrape History (Google Sheets)](https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/)")
st.sidebar.divider()

# Admin-only: Update Angi categories (bottom of sidebar, small text)
if st.session_state.get("role") == "admin":
    st.sidebar.divider()
    if st.sidebar.button("Sync categories", type="secondary", use_container_width=False):
        with st.sidebar:
            with st.spinner("Scanning..."):
                new_cats = fetch_angi_categories()
                added = set(new_cats) - set(ANGI_CATEGORIES)
                st.session_state["angi_categories_updated"] = new_cats
                if added:
                    st.caption(f"Added {len(added)} new: {', '.join(sorted(added))}")
                else:
                    st.caption(f"Up to date ({len(new_cats)} categories)")

# ---------------- SOURCE-SPECIFIC INPUTS ----------------

# --- Google Business Profile ---
if source == "Google Business Profile":

    # Country: dropdown with presets + option to type any country
    country_options = list(COUNTRY_DATA.keys()) + ["-- Other --"]
    country_selection = st.selectbox("Country", country_options)

    if country_selection == "-- Other --":
        country = st.text_input("Enter country name", "")
        language = st.text_input("Search language (e.g. en, es, fr, de, ja)", "en")
        country_info = {"language": language, "cities": []}
    else:
        country = country_selection
        country_info = COUNTRY_DATA[country]

    if country_info.get("language"):
        st.info(f"Language: {country_info['language'].upper()}")

    industries = st.text_area("Industries (one per line)", "dentist\nplumber\ngym")

    # Cities: show presets if available, plus free text for any city
    if country_info.get("cities"):
        selected_cities = st.multiselect(
            "Preset Cities (optional)",
            country_info["cities"],
            default=country_info["cities"][:1],
        )
    else:
        selected_cities = []

    custom_cities = st.text_area(
        "Cities (one per line — type any city worldwide)",
        "" if selected_cities else "Austin, Texas",
    )

    gbp_search_all = st.checkbox("Search all available listings", False)
    if gbp_search_all:
        max_results = 200
        st.caption("Will scrape up to 200 results per search (Apify max). This will use more credits.")
    else:
        max_results = st.number_input("Max results per search", 1, 200, 10)

    min_rating = st.number_input("Minimum Rating", 0.0, 5.0, 0.0, 0.1)
    max_rating = st.number_input("Maximum Rating", 0.0, 5.0, 5.0, 0.1)

    min_reviews = st.number_input("Minimum Reviews", 0, 100000, 0)
    max_reviews = st.number_input("Maximum Reviews", 0, 100000, 100000)

# --- Angi ---
elif source == "Angi (Angie's List)":

    st.caption("Angi is US-only. For international searches, use Google Business Profile.")

    # Use updated categories if admin fetched new ones
    active_categories = st.session_state.get("angi_categories_updated", ANGI_CATEGORIES)
    sorted_cats = sorted(active_categories)

    angi_category = st.selectbox(
        "Category / Service Type",
        ["-- Type my own --"] + sorted_cats,
        index=sorted_cats.index("plumbing") + 1 if "plumbing" in sorted_cats else 1,
    )
    if angi_category == "-- Type my own --":
        angi_category_custom = st.text_input(
            "Enter category slug (e.g. 'plumbing', 'garage-builders')",
            "",
        )
        angi_category = angi_category_custom.strip().lower().replace(" ", "-") if angi_category_custom.strip() else ""

    angi_city = st.text_input("City", "austin")

    angi_state = st.selectbox("State", [
        "al", "ak", "az", "ar", "ca", "co", "ct", "de", "fl", "ga",
        "hi", "id", "il", "in", "ia", "ks", "ky", "la", "me", "md",
        "ma", "mi", "mn", "ms", "mo", "mt", "ne", "nv", "nh", "nj",
        "nm", "ny", "nc", "nd", "oh", "ok", "or", "pa", "ri", "sc",
        "sd", "tn", "tx", "ut", "vt", "va", "wa", "wv", "wi", "wy",
    ], index=42)  # tx default

    angi_search_all = st.checkbox("Search all available listings", False)
    if angi_search_all:
        angi_max = 1000
        st.caption("Will scrape all available listings (up to 1000). This will use more credits.")
    else:
        angi_max = st.number_input("Max results", 1, 1000, 25)
    st.caption("Note: The Angi actor may scrape more results than requested. Cost is based on what the actor scrapes, not what is displayed.")

    cat_slug = angi_category
    city_slug = angi_city.strip().lower().replace(" ", "-")
    angi_auto_url = f"https://www.angi.com/companylist/us/{angi_state}/{city_slug}/{cat_slug}.htm"

    st.markdown("---")
    st.code(angi_auto_url, language=None)

    st.info(
        "**Note:** Angi scraping may not work for all cities/categories. "
        "The URL above is auto-generated — if it returns no results, try these steps:\n\n"
        f"1. Browse [angi.com/companylist/us/{angi_state}/](https://www.angi.com/companylist/us/{angi_state}/) to find your city and category\n"
        "2. Click on your city, then select a category (e.g. 'Plumbing Services')\n"
        "3. You should land on a page like `angi.com/companylist/us/ny/new-york/plumbing.htm`\n"
        "4. Copy that URL and paste it below"
    )

    angi_custom_url = st.text_input(
        "Paste Angi company list URL here (leave blank to use auto-generated URL)",
        "",
    )
    if angi_custom_url and "/companylist/" not in angi_custom_url:
        st.warning("This URL looks like a search page, not a company list page. The scraper needs a URL containing '/companylist/' (e.g. angi.com/companylist/us/tx/austin/plumber.htm)")

# ---------------- EMAIL OPTIONS ----------------

email_col1, email_col2 = st.columns(2)
with email_col1:
    find_emails = st.checkbox("Find emails from websites", True)
with email_col2:
    email_scan_limit = st.number_input("Max websites to scan for emails", 1, 500, 50)

# ---------------- RUN BUTTON ----------------

run_clicked = st.button("🚀 Run Scraper")

# ---------------- GOOGLE SHEETS ----------------

def get_gsheet_client():
    """Connect to Google Sheets using service account from Streamlit secrets or env."""
    try:
        creds_dict = dict(st.secrets["gcp_service_account"])
        gc = gspread.service_account_from_dict(creds_dict)
        return gc
    except Exception:
        pass
    # Fallback: try JSON file path from env
    creds_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    if creds_path and os.path.exists(creds_path):
        gc = gspread.service_account(filename=creds_path)
        return gc
    return None

def save_to_google_sheets(df, source, search_info=""):
    """Save scrape results to Google Sheets: adds a history log entry + a new data tab."""
    gc = get_gsheet_client()
    if not gc:
        st.warning("Google Sheets not configured — results not saved to cloud.")
        return

    try:
        sh = gc.open_by_key(SPREADSHEET_ID)
    except Exception as e:
        st.warning(f"Could not open Google Sheet: {e}")
        return

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    tab_name = f"{source[:3]} - {search_info[:20]} - {datetime.now().strftime('%m/%d %H:%M')}"
    # Sheet tab names max 100 chars
    tab_name = tab_name[:100]

    # --- Create data tab ---
    try:
        clean_df = df.copy()
        # Convert all values to strings to avoid serialization issues
        for col in clean_df.columns:
            clean_df[col] = clean_df[col].astype(str)

        ws = sh.add_worksheet(title=tab_name, rows=len(clean_df) + 1, cols=len(clean_df.columns))
        ws.update([clean_df.columns.tolist()] + clean_df.values.tolist())
    except Exception as e:
        st.warning(f"Could not create data tab: {e}")
        return

    # --- Update history log (first sheet) ---
    try:
        history_ws = sh.sheet1
        # Check if header exists
        existing = history_ws.get_all_values()
        if not existing:
            history_ws.update("A1:E1", [["Timestamp", "Source", "Search", "Results", "Tab Name"]])

        next_row = len(existing) + 1
        history_ws.update(f"A{next_row}:E{next_row}", [[timestamp, source, search_info, len(df), tab_name]])
    except Exception as e:
        st.warning(f"Could not update history log: {e}")

    st.success(f"Saved to Google Sheets tab: **{tab_name}**")

# ---------------- HELPERS ----------------

def normalize_website(url):
    if not url:
        return ""
    if not url.startswith("http"):
        return "https://" + url
    return url

def fetch_page(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=8)
        if r.status_code == 200:
            return r.text
    except:
        return ""
    return ""

def extract_email_from_website(site):
    site = normalize_website(site)
    if not site:
        return ""
    for path in COMMON_CONTACT_PATHS:
        url = site if path == "" else urljoin(site, path)
        html = fetch_page(url)
        if not html:
            continue
        emails = EMAIL_REGEX.findall(html)
        if emails:
            return emails[0]
    return ""

def flatten_record(item):
    flat = {}
    for key, value in item.items():
        if isinstance(value, list):
            flat[key] = " | ".join(
                json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else str(v)
                for v in value
            )
        elif isinstance(value, dict):
            flat[key] = json.dumps(value, ensure_ascii=False)
        elif value is None:
            flat[key] = ""
        else:
            flat[key] = value
    return flat

def find_website_col(df):
    for col_name in ["website", "websiteUrl", "Website", "url", "companyWebsite"]:
        if col_name in df.columns:
            return col_name
    return None

def remove_chains(df):
    def check(row):
        name = ""
        for col in ["Business Name", "name", "businessName", "title"]:
            if col in row.index and row[col]:
                name = str(row[col]).lower()
                break
        for bad in EXCLUDED_BUSINESSES:
            if bad in name:
                return False
        return True
    return df[df.apply(check, axis=1)]

def add_emails(df, website_col):
    df["Email"] = ""
    if not find_emails or not website_col:
        return df
    sites = df[df[website_col].notna() & (df[website_col] != "")].head(email_scan_limit)
    if sites.empty:
        return df
    email_progress = st.progress(0)
    for i, idx in enumerate(sites.index):
        website = df.loc[idx, website_col]
        email = extract_email_from_website(website)
        df.loc[idx, "Email"] = email
        email_progress.progress((i + 1) / len(sites))
        time.sleep(0.05)
    return df

def add_opportunity_score(df, website_col):
    def score(row):
        rating = 0
        reviews = 0
        website = ""

        for col in ["totalScore", "rating", "overallRating", "averageRating", "TotalScore"]:
            if col in row.index and row[col]:
                try:
                    rating = float(row[col])
                except (ValueError, TypeError):
                    pass
                break

        for col in ["reviewsCount", "reviewCount", "numberOfReviews", "numReviews", "ReviewsCount"]:
            if col in row.index and row[col]:
                try:
                    reviews = int(row[col])
                except (ValueError, TypeError):
                    pass
                break

        if website_col and website_col in row.index:
            website = row[website_col] or ""

        if not website or (reviews < 10 and rating < 4.5):
            return "HIGH"
        if reviews < 30:
            return "MEDIUM"
        return "LOW"

    df["Opportunity"] = df.apply(score, axis=1)
    return df

# ---------------- MAIN LOGIC ----------------

if run_clicked:

    token = os.getenv("APIFY_API_TOKEN")

    if not token:
        st.error("Missing APIFY_API_TOKEN environment variable.")
        st.stop()

    client = ApifyClient(token)

    all_results = []

    # ==================== GOOGLE BUSINESS PROFILE ====================
    if source == "Google Business Profile":

        industry_list = [i.strip() for i in industries.split("\n") if i.strip()]
        city_list = list(selected_cities)
        # Add custom typed cities
        for c in custom_cities.split("\n"):
            if c.strip():
                city_list.append(c.strip())
        city_list = list(dict.fromkeys(city_list))

        total_jobs = len(industry_list) * len(city_list)
        progress = st.progress(0)
        job_count = 0

        stop_placeholder = st.empty()
        stopped = False

        for industry in industry_list:
            for city in city_list:
                if stop_placeholder.button("Stop Scraping", key=f"stop_{job_count}"):
                    stopped = True
                    st.warning(f"Stopped after {job_count} of {total_jobs} searches.")
                    break

                query = f"{industry} {city}"
                st.write("Searching:", query)

                try:
                    run = client.actor(ACTORS[source]).call(
                        run_input={
                            "searchStringsArray": [query],
                            "maxCrawledPlacesPerSearch": int(max_results),
                            "language": country_info["language"],
                        }
                    )
                    dataset_id = run["defaultDatasetId"]
                    items = list(client.dataset(dataset_id).iterate_items())[:max_results]
                    all_results.extend(items)
                except Exception as e:
                    st.warning(f"Error: {e}")

                job_count += 1
                progress.progress(job_count / total_jobs)
            if stopped:
                break

        stop_placeholder.empty()

        if not all_results:
            st.warning("No results found.")
            st.stop()

        df = pd.DataFrame(all_results)

        # Filter and rename columns
        column_rename = {
            "title": "Business Name",
            "categoryName": "Category",
            "address": "Address",
            "city": "City",
            "state": "State",
            "countryCode": "Country",
            "phone": "Phone",
            "website": "Website",
            "totalScore": "Rating",
            "reviewsCount": "Reviews",
            "url": "Google Maps URL",
        }
        available = [c for c in column_rename.keys() if c in df.columns]
        if available:
            df = df[available]
            df.rename(columns=column_rename, inplace=True)

        # Apply rating/review filters
        if "Rating" in df.columns:
            df["Rating"] = pd.to_numeric(df["Rating"], errors="coerce")
            df = df[(df["Rating"] >= min_rating) & (df["Rating"] <= max_rating)]

        if "Reviews" in df.columns:
            df["Reviews"] = pd.to_numeric(df["Reviews"], errors="coerce").fillna(0)
            df = df[(df["Reviews"] >= min_reviews) & (df["Reviews"] <= max_reviews)]

    # ==================== ANGI ====================
    elif source == "Angi (Angie's List)":

        angi_url = angi_custom_url.strip() if angi_custom_url.strip() else angi_auto_url

        st.write(f"Scraping Angi: **{angi_url}**")
        progress = st.progress(0)

        try:
            progress.progress(10)
            # Scale timeout: ~30s base + 10s per result requested
            angi_timeout = min(30 + int(angi_max) * 10, 300)
            run = client.actor(ACTORS[source]).call(
                run_input={
                    "startUrls": [{"url": angi_url}],
                    "maxItems": int(angi_max),
                    "maxResults": int(angi_max),
                    "maxCrawledPages": int(angi_max),
                    "maxRequestsPerCrawl": int(angi_max) + 5,
                },
                timeout_secs=angi_timeout,
                memory_mbytes=256,
            )
            progress.progress(70)

            status = run.get("status", "UNKNOWN")
            dataset_id = run.get("defaultDatasetId", "")

            if status == "TIMED-OUT" and dataset_id:
                st.warning("Actor timed out — showing partial results collected so far.")
            elif status != "SUCCEEDED":
                st.error(f"Actor run did not succeed (status={status}).")
                st.stop()

            items_raw = list(client.dataset(dataset_id).iterate_items())[:int(angi_max)]
            all_results = [flatten_record(item) for item in items_raw]
            progress.progress(90)

        except Exception as e:
            st.error(f"Scraper error: {e}")
            st.stop()

        if not all_results:
            st.warning("No results found.")
            st.stop()

        # Parse nested Angi JSON into clean columns
        clean_rows = []
        for item in items_raw:
            row = {}

            # Business identity
            bi = item.get("business_identity", {})
            if isinstance(bi, str):
                try: bi = json.loads(bi)
                except: bi = {}
            row["Business Name"] = bi.get("business_name", "")
            row["Profile URL"] = bi.get("profile_url", "")

            # Contact details
            cd = item.get("contact_details", {})
            if isinstance(cd, str):
                try: cd = json.loads(cd)
                except: cd = {}
            row["Phone"] = cd.get("phone_primary", "")
            row["Address"] = cd.get("open_address", "")
            row["Website"] = cd.get("website", "")

            # Location
            loc = item.get("location_details", {})
            if isinstance(loc, str):
                try: loc = json.loads(loc)
                except: loc = {}
            row["Service Area"] = loc.get("service_area", "")

            # Company profile
            cp = item.get("company_profile", {})
            if isinstance(cp, str):
                try: cp = json.loads(cp)
                except: cp = {}
            overview = cp.get("business_overview", {})
            if isinstance(overview, str):
                try: overview = json.loads(overview)
                except: overview = {}
            row["Description"] = overview.get("description", "")[:200]
            profile_attrs = cp.get("profile_attributes", {})
            if isinstance(profile_attrs, str):
                try: profile_attrs = json.loads(profile_attrs)
                except: profile_attrs = {}
            row["In Business Since"] = profile_attrs.get("in_business_since", "")

            # Ratings
            cf = item.get("customer_feedback", {})
            if isinstance(cf, str):
                try: cf = json.loads(cf)
                except: cf = {}
            ratings = cf.get("ratings_summary", {})
            if isinstance(ratings, str):
                try: ratings = json.loads(ratings)
                except: ratings = {}
            row["Rating"] = ratings.get("overall_rating", "")
            if row["Rating"] and isinstance(row["Rating"], float):
                row["Rating"] = round(row["Rating"], 1)
            row["Reviews"] = ratings.get("review_count", 0)

            # Categories
            so = item.get("service_offerings", {})
            if isinstance(so, str):
                try: so = json.loads(so)
                except: so = {}
            cats = so.get("categories", [])
            if isinstance(cats, str):
                try: cats = json.loads(cats)
                except: cats = []
            if cats and isinstance(cats, list):
                row["Categories"] = ", ".join(c.get("name", "") for c in cats[:5] if isinstance(c, dict))
            else:
                row["Categories"] = ""

            # Licensing
            comp = item.get("compliance", {})
            if isinstance(comp, str):
                try: comp = json.loads(comp)
                except: comp = {}
            lic = comp.get("licensing", {})
            if isinstance(lic, str):
                try: lic = json.loads(lic)
                except: lic = {}
            row["Insured"] = lic.get("insured", False)

            clean_rows.append(row)

        df = pd.DataFrame(clean_rows)

    # ==================== POST-PROCESSING (ALL SOURCES) ====================

    df = df.drop_duplicates()
    df = remove_chains(df)

    website_col = find_website_col(df)

    df = add_emails(df, website_col)
    df = add_opportunity_score(df, website_col)

    # Save to session state so results persist across reruns
    st.session_state["last_results"] = df
    st.session_state["last_source"] = source

    # Build search info for history
    if source == "Google Business Profile":
        st.session_state["last_search_info"] = f"{industries.split(chr(10))[0]} in {city_list[0] if city_list else 'unknown'}"
    else:
        st.session_state["last_search_info"] = f"{angi_category} in {angi_city}"

# ---------------- DISPLAY RESULTS (persists across reruns) ----------------

if "last_results" in st.session_state:
    df = st.session_state["last_results"]
    source_display = st.session_state.get("last_source", "")
    search_info = st.session_state.get("last_search_info", "")

    # ---------------- DUPLICATE DETECTION ----------------

    def check_duplicates(df):
        """Check Google Sheets for businesses already scraped."""
        gc = get_gsheet_client()
        if not gc:
            return df
        try:
            sh = gc.open_by_key(SPREADSHEET_ID)
            existing_names = set()
            for ws in sh.worksheets()[1:]:  # skip history log tab
                try:
                    records = ws.get_all_values()
                    if records:
                        header = records[0]
                        name_idx = None
                        for i, h in enumerate(header):
                            if h.lower() in ["business name", "title", "name"]:
                                name_idx = i
                                break
                        if name_idx is not None:
                            for row in records[1:]:
                                if name_idx < len(row) and row[name_idx]:
                                    existing_names.add(row[name_idx].strip().lower())
                except:
                    continue

            if existing_names:
                name_col = None
                for col in ["Business Name", "title", "name"]:
                    if col in df.columns:
                        name_col = col
                        break
                if name_col:
                    df["Duplicate"] = df[name_col].apply(
                        lambda x: "Yes" if str(x).strip().lower() in existing_names else "No"
                    )
                    dup_count = (df["Duplicate"] == "Yes").sum()
                    if dup_count > 0:
                        st.warning(f"Found {dup_count} businesses already in previous scrapes (marked as 'Duplicate: Yes')")
        except Exception as e:
            st.caption(f"Could not check duplicates: {e}")
        return df

    df = check_duplicates(df)

    # ---------------- RESULTS DISPLAY ----------------

    st.success(f"✅ {len(df)} businesses found from {source_display}")

    # Filter results
    st.subheader("Filter Results")
    filter_col1, filter_col2 = st.columns(2)
    with filter_col1:
        search_filter = st.text_input("Search by name, address, or category", "", key="filter_search")
    with filter_col2:
        if "Duplicate" in df.columns:
            dup_filter = st.selectbox("Show duplicates", ["All", "New only", "Duplicates only"], key="filter_dup")
        else:
            dup_filter = "All"

    filtered_df = df.copy()
    if search_filter:
        mask = filtered_df.apply(lambda row: search_filter.lower() in str(row.values).lower(), axis=1)
        filtered_df = filtered_df[mask]
    if dup_filter == "New only" and "Duplicate" in filtered_df.columns:
        filtered_df = filtered_df[filtered_df["Duplicate"] == "No"]
    elif dup_filter == "Duplicates only" and "Duplicate" in filtered_df.columns:
        filtered_df = filtered_df[filtered_df["Duplicate"] == "Yes"]

    st.caption(f"Showing {len(filtered_df)} of {len(df)} results")
    st.dataframe(filtered_df, use_container_width=True)

    # ---------------- DOWNLOAD OPTIONS ----------------

    csv = filtered_df.to_csv(index=False).encode("utf-8")
    filename_base = source.lower().replace(" ", "_").replace("(", "").replace(")", "") + "_leads"

    dl_col1, dl_col2 = st.columns(2)
    with dl_col1:
        st.download_button(
            "📥 Download CSV",
            csv,
            f"{filename_base}.csv",
            "text/csv",
        )
    with dl_col2:
        # Excel export
        from io import BytesIO
        excel_buffer = BytesIO()
        filtered_df.to_excel(excel_buffer, index=False, engine="openpyxl")
        excel_buffer.seek(0)
        st.download_button(
            "📥 Download Excel",
            excel_buffer,
            f"{filename_base}.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    # Save to Google Sheets (only on fresh scrape, not on filter rerun)
    if "last_saved" not in st.session_state or st.session_state.get("last_saved") != id(df):
        save_to_google_sheets(df, source_display, search_info)
        st.session_state["last_saved"] = id(df)

        # Save to session history
        if "scrape_history" not in st.session_state:
            st.session_state["scrape_history"] = []

        st.session_state["scrape_history"].append({
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "source": source_display,
            "results": len(df),
            "csv": csv,
            "filename": f"{filename_base}.csv",
        })

# ---------------- SCRAPE HISTORY ----------------

if "scrape_history" in st.session_state and st.session_state["scrape_history"]:

    st.divider()
    st.subheader("Scrape History")

    for i, entry in enumerate(reversed(st.session_state["scrape_history"])):
        idx = len(st.session_state["scrape_history"]) - 1 - i
        col1, col2, col3, col4 = st.columns([2, 2, 1, 1])

        with col1:
            st.text(entry["timestamp"])
        with col2:
            st.text(entry["source"])
        with col3:
            st.text(f"{entry['results']} leads")
        with col4:
            st.download_button(
                "Download",
                entry["csv"],
                entry["filename"],
                "text/csv",
                key=f"history_{idx}",
            )
