import streamlit as st

# ---------------- LOGIN ----------------

def check_login():
    def login_form():
        with st.form("Login"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("Login")

            if submit:
                if username == "boss" and password == "leadfinder123":
                    st.session_state["logged_in"] = True
                else:
                    st.error("Invalid username or password")

    if "logged_in" not in st.session_state:
        st.session_state["logged_in"] = False

    if not st.session_state["logged_in"]:
        st.title("🔐 Lead Finder Login")
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
from urllib.parse import urljoin
from apify_client import ApifyClient

# ---------------- CONFIG ----------------

ACTORS = {
    "Google Business Profile": "compass/crawler-google-places",
    "Angi (Angie's List)": "babak/angi-angie-s-list-scraper",
    "HomeAdvisor": "alizarin_refrigerator-owner/homeadvisor-scraper",
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

# ---------------- PAGE ----------------

st.set_page_config(page_title="Lead Finder", page_icon="🌍", layout="wide")

st.title("🌍 All-in-One Lead Finder")

# ---------------- SOURCE SELECTOR ----------------

source = st.selectbox("Lead Source", list(ACTORS.keys()))

st.divider()

# ---------------- SHARED: EMAIL OPTIONS ----------------

find_emails = st.sidebar.checkbox("Find emails from websites", True)
email_scan_limit = st.sidebar.number_input("Max websites to scan for emails", 1, 500, 50)

# ---------------- SOURCE-SPECIFIC INPUTS ----------------

# --- Google Business Profile ---
if source == "Google Business Profile":

    country = st.selectbox("Country", list(COUNTRY_DATA.keys()))
    country_info = COUNTRY_DATA[country]

    st.info(f"Language: {country_info['language'].upper()} | Currency: {country_info['currency']}")

    industries = st.text_area("Industries (one per line)", "dentist\nplumber\ngym")

    selected_cities = st.multiselect(
        "Cities",
        country_info["cities"],
        default=country_info["cities"][:1],
    )

    custom_city = st.text_input("Optional custom city/location", "")

    max_results = st.number_input("Max results per search", 1, 200, 10)

    min_rating = st.number_input("Minimum Rating", 0.0, 5.0, 0.0, 0.1)
    max_rating = st.number_input("Maximum Rating", 0.0, 5.0, 5.0, 0.1)

    min_reviews = st.number_input("Minimum Reviews", 0, 100000, 0)
    max_reviews = st.number_input("Maximum Reviews", 0, 100000, 100000)

# --- Angi ---
elif source == "Angi (Angie's List)":

    angi_location = st.text_input("Location", "Austin, Texas")
    angi_category = st.text_input("Category / Service Type", "plumber")
    angi_max = st.number_input("Max listings", 1, 500, 25)
    angi_include_reviews = st.checkbox("Include reviews", True)
    angi_max_reviews = st.number_input("Max reviews per listing", 0, 50, 5)

# --- HomeAdvisor ---
elif source == "HomeAdvisor":

    ha_category = st.text_input("Category / Service Type", "General Contractor")
    ha_city = st.text_input("City", "Austin")

    ha_state = st.selectbox("State", [
        "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
        "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
        "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
        "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
        "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
    ], index=42)  # TX default

    ha_use_custom_url = st.checkbox("Use custom URL instead")

    if ha_use_custom_url:
        ha_custom_url = st.text_input(
            "Custom HomeAdvisor URL",
            "https://www.homeadvisor.com/c.General-Contractor.Austin.TX.-12003807.html",
        )
    else:
        # Auto-build URL from category + city + state
        cat_slug = ha_category.strip().replace(" ", "-")
        city_slug = ha_city.strip().replace(" ", "-")
        ha_auto_url = f"https://www.homeadvisor.com/c.{cat_slug}.{city_slug}.{ha_state}.html"
        st.code(ha_auto_url, language=None)

# ---------------- RUN BUTTON ----------------

run_clicked = st.button("🚀 Run Scraper")

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
        if custom_city.strip():
            city_list.append(custom_city.strip())
        city_list = list(dict.fromkeys(city_list))

        total_jobs = len(industry_list) * len(city_list)
        progress = st.progress(0)
        job_count = 0

        for industry in industry_list:
            for city in city_list:
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

        if not all_results:
            st.warning("No results found.")
            st.stop()

        df = pd.DataFrame(all_results)

        # Filter columns
        important = [
            "title", "categoryName", "address", "city", "state",
            "countryCode", "phone", "website", "totalScore",
            "reviewsCount", "url",
        ]
        available = [c for c in important if c in df.columns]
        if available:
            df = df[available]

        # Apply rating/review filters
        if "totalScore" in df.columns:
            df["totalScore"] = pd.to_numeric(df["totalScore"], errors="coerce")
            df = df[(df["totalScore"] >= min_rating) & (df["totalScore"] <= max_rating)]

        if "reviewsCount" in df.columns:
            df["reviewsCount"] = pd.to_numeric(df["reviewsCount"], errors="coerce").fillna(0)
            df = df[(df["reviewsCount"] >= min_reviews) & (df["reviewsCount"] <= max_reviews)]

    # ==================== ANGI ====================
    elif source == "Angi (Angie's List)":

        st.write(f"Searching Angi for **{angi_category}** in **{angi_location}**...")
        progress = st.progress(0)

        try:
            progress.progress(10)
            run = client.actor(ACTORS[source]).call(
                run_input={
                    "location": angi_location,
                    "category": angi_category,
                    "includeReviews": angi_include_reviews,
                    "maxListings": int(angi_max),
                    "maxReviews": int(angi_max_reviews),
                    "directLinks": [],
                    "categoryLinks": [],
                    "zipcodes": [],
                    "proxyConfiguration": {"useApifyProxy": True},
                    "maxConcurrency": 100,
                }
            )
            progress.progress(70)

            status = run.get("status", "UNKNOWN")
            if status != "SUCCEEDED":
                st.error(f"Actor run did not succeed (status={status}).")
                st.stop()

            dataset_id = run.get("defaultDatasetId", "")
            items_raw = list(client.dataset(dataset_id).iterate_items())
            all_results = [flatten_record(item) for item in items_raw]
            progress.progress(90)

        except Exception as e:
            st.error(f"Scraper error: {e}")
            st.stop()

        if not all_results:
            st.warning("No results found.")
            st.stop()

        df = pd.DataFrame(all_results)

    # ==================== HOMEADVISOR ====================
    elif source == "HomeAdvisor":

        if ha_use_custom_url:
            url_list = [ha_custom_url.strip()]
        else:
            url_list = [ha_auto_url]

        if not url_list or not url_list[0]:
            st.warning("Please enter a valid HomeAdvisor URL or fill in category/city/state.")
            st.stop()

        st.write(f"Scraping: **{url_list[0]}**")
        progress = st.progress(0)

        try:
            progress.progress(10)
            run = client.actor(ACTORS[source]).call(
                run_input={
                    "startUrls": [{"url": u} for u in url_list],
                }
            )
            progress.progress(70)

            status = run.get("status", "UNKNOWN")
            if status != "SUCCEEDED":
                st.error(f"Actor run did not succeed (status={status}).")
                st.stop()

            dataset_id = run.get("defaultDatasetId", "")
            items_raw = list(client.dataset(dataset_id).iterate_items())
            all_results = [flatten_record(item) for item in items_raw]
            progress.progress(90)

        except Exception as e:
            st.error(f"Scraper error: {e}")
            st.stop()

        if not all_results:
            st.warning("No results found.")
            st.stop()

        df = pd.DataFrame(all_results)

    # ==================== POST-PROCESSING (ALL SOURCES) ====================

    df = df.drop_duplicates()
    df = remove_chains(df)

    website_col = find_website_col(df)

    df = add_emails(df, website_col)
    df = add_opportunity_score(df, website_col)

    st.success(f"✅ {len(df)} businesses found from {source}")

    st.dataframe(df, use_container_width=True)

    csv = df.to_csv(index=False).encode("utf-8")

    filename = source.lower().replace(" ", "_").replace("(", "").replace(")", "") + "_leads.csv"

    st.download_button(
        "📥 Download Leads CSV",
        csv,
        filename,
        "text/csv",
    )
