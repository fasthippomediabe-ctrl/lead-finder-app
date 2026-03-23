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
        st.title("🔐 Angi Lead Finder Login")
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

ACTOR_ID = "babak/angi-angie-s-list-scraper"

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

st.set_page_config(page_title="Angi Lead Finder", page_icon="🔧", layout="wide")

st.title("🔧 Angi (Angie's List) Lead Finder")

location = st.text_input("Location", "Austin, Texas")

category = st.text_input("Category / Service Type", "plumber")

max_listings = st.number_input("Max listings", 1, 500, 25)

include_reviews = st.checkbox("Include reviews", True)
max_reviews = st.number_input("Max reviews per listing", 0, 50, 5)

find_emails = st.checkbox("Find emails from websites", True)
email_scan_limit = st.number_input("Max websites to scan for emails", 1, 500, 50)

run_clicked = st.button("Run Angi Scraper")

# ---------------- EMAIL HELPERS ----------------

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

# ---------------- FLATTEN HELPER ----------------

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

# ---------------- MAIN ----------------

if run_clicked:

    token = os.getenv("APIFY_API_TOKEN")

    if not token:
        st.error("Missing APIFY_API_TOKEN environment variable.")
        st.stop()

    client = ApifyClient(token)

    actor_input = {
        "location": location,
        "category": category,
        "includeReviews": include_reviews,
        "maxListings": int(max_listings),
        "maxReviews": int(max_reviews),
        "directLinks": [],
        "categoryLinks": [],
        "zipcodes": [],
        "proxyConfiguration": {"useApifyProxy": True},
        "maxConcurrency": 100,
    }

    st.write(f"Searching Angi for **{category}** in **{location}**...")

    progress = st.progress(0)

    try:
        progress.progress(10)

        run = client.actor(ACTOR_ID).call(run_input=actor_input)

        progress.progress(70)

        status = run.get("status", "UNKNOWN")
        dataset_id = run.get("defaultDatasetId", "")

        if status != "SUCCEEDED":
            st.error(f"Actor run did not succeed (status={status}). Check the Apify console.")
            st.stop()

        items_raw = list(client.dataset(dataset_id).iterate_items())
        items_flat = [flatten_record(item) for item in items_raw]

        progress.progress(90)

    except Exception as e:
        st.error(f"Scraper error: {e}")
        st.stop()

    if not items_flat:
        st.warning("No results found.")
        st.stop()

    df = pd.DataFrame(items_flat)

    # ---------------- REMOVE CHAINS ----------------

    def remove_chain(row):
        name = str(row.get("name", row.get("businessName", ""))).lower()
        for bad in EXCLUDED_BUSINESSES:
            if bad in name:
                return False
        return True

    df = df[df.apply(remove_chain, axis=1)]
    df.drop_duplicates(inplace=True)

    # ---------------- EMAIL FINDER ----------------

    # Find the website column (Angi actors may use different names)
    website_col = None
    for col_name in ["website", "websiteUrl", "url", "Website"]:
        if col_name in df.columns:
            website_col = col_name
            break

    df["Email"] = ""

    if find_emails and website_col:

        sites = df[df[website_col].notna() & (df[website_col] != "")].head(email_scan_limit)

        email_progress = st.progress(0)

        for i, idx in enumerate(sites.index):
            website = df.loc[idx, website_col]
            email = extract_email_from_website(website)
            df.loc[idx, "Email"] = email
            email_progress.progress((i + 1) / len(sites))
            time.sleep(0.05)

    # ---------------- OPPORTUNITY SCORE ----------------

    def score(row):
        rating = row.get("rating", row.get("overallRating", 0))
        reviews = row.get("reviewCount", row.get("numberOfReviews", 0))

        try:
            rating = float(rating) if rating else 0
        except (ValueError, TypeError):
            rating = 0

        try:
            reviews = int(reviews) if reviews else 0
        except (ValueError, TypeError):
            reviews = 0

        website = row.get(website_col, "") if website_col else ""

        if not website or (reviews < 10 and rating < 4.5):
            return "HIGH"
        if reviews < 30:
            return "MEDIUM"
        return "LOW"

    df["Opportunity"] = df.apply(score, axis=1)

    progress.progress(100)

    st.success(f"{len(df)} businesses found on Angi")

    st.dataframe(df, use_container_width=True)

    csv = df.to_csv(index=False).encode("utf-8")

    st.download_button(
        "Download Angi Leads",
        csv,
        "angi_leads.csv",
        "text/csv",
    )
