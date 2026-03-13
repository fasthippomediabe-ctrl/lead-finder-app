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
import pandas as pd
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from apify_client import ApifyClient

# ---------------- CONFIG ----------------

ACTOR_ID = "compass/crawler-google-places"

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

COMMON_CONTACT_PATHS = [
    "",
    "/contact",
    "/contact-us",
    "/contacts",
    "/about",
    "/about-us",
    "/team",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

# ---------------- PAGE ----------------

st.set_page_config(page_title="Global Lead Finder", page_icon="🌍", layout="wide")

st.title("🌍 Global Business Lead Finder")

industries = st.text_area(
    "Industries (one per line)",
    "dentist\nplumber\ngym"
)

locations = st.text_area(
    "Cities / Locations (one per line)",
    "Austin Texas\nDallas Texas\nHouston Texas"
)

country = st.text_input(
    "Country (optional)",
    "United States"
)

max_results = st.number_input("Max results per search", 1, 200, 25)

min_rating = st.number_input("Minimum Rating", 0.0, 5.0, 0.0)
max_rating = st.number_input("Maximum Rating", 0.0, 5.0, 5.0)

min_reviews = st.number_input("Minimum Reviews", 0, 100000, 0)
max_reviews = st.number_input("Maximum Reviews", 0, 100000, 100000)

find_emails = st.checkbox("Find emails from websites", value=True)
email_scan_limit = st.number_input("Max websites to scan for emails", 1, 500, 50)

run_clicked = st.button("Run Global Scraper")

# ---------------- EMAIL HELPERS ----------------

def normalize_website(url):
    if not url or pd.isna(url):
        return ""
    if not url.startswith("http"):
        return "https://" + url
    return url

def fetch_page(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code == 200:
            return r.text
    except:
        return ""
    return ""

def extract_email_from_website(website):

    website = normalize_website(website)

    if not website:
        return ""

    for path in COMMON_CONTACT_PATHS:

        if path == "":
            url = website
        else:
            url = urljoin(website, path)

        html = fetch_page(url)

        if not html:
            continue

        emails = EMAIL_REGEX.findall(html)

        if emails:
            return emails[0]

    return ""

# ---------------- MAIN ----------------

if run_clicked:

    token = os.getenv("APIFY_API_TOKEN")

    if not token:
        st.error("Missing APIFY_API_TOKEN")
        st.stop()

    client = ApifyClient(token)

    industry_list = [i.strip() for i in industries.split("\n") if i.strip()]
    location_list = [c.strip() for c in locations.split("\n") if c.strip()]

    all_results = []

    progress = st.progress(0)
    job_count = 0
    total_jobs = len(industry_list) * len(location_list)

    for industry in industry_list:
        for location in location_list:

            query = f"{industry} {location} {country}"

            st.write("Running:", query)

            try:

                run = client.actor(ACTOR_ID).call(
                    run_input={
                        "searchStringsArray": [query],
                        "maxCrawledPlacesPerSearch": int(max_results)
                    }
                )

                dataset_id = run["defaultDatasetId"]

                items = list(client.dataset(dataset_id).iterate_items())

                all_results.extend(items)

            except Exception as e:
                st.warning(e)

            job_count += 1
            progress.progress(job_count / total_jobs)

    if not all_results:
        st.warning("No results found")
        st.stop()

    df = pd.DataFrame(all_results)

    columns_map = {
        "title": "Business Name",
        "categoryName": "Category",
        "address": "Address",
        "phone": "Phone",
        "website": "Website",
        "totalScore": "Rating",
        "reviewsCount": "Reviews",
        "url": "Google Maps",
    }

    df = df[list(columns_map.keys())]
    df.rename(columns=columns_map, inplace=True)

    # ---------------- INDUSTRY FILTER ----------------

    industry_keywords = []

    for industry in industry_list:
        industry_keywords.extend(industry.lower().split())

    industry_keywords = list(set(industry_keywords))

    def is_relevant(row):

        name = str(row["Business Name"]).lower()
        category = str(row["Category"]).lower()

        for word in industry_keywords:
            if word in name or word in category:
                return True

        return False

    df = df[df.apply(is_relevant, axis=1)]

    # ---------------- EXCLUDED CHAINS FILTER ----------------

    def remove_chains(row):

        name = str(row["Business Name"]).lower()

        for bad in EXCLUDED_BUSINESSES:
            if bad in name:
                return False

        return True

    df = df[df.apply(remove_chains, axis=1)]

    # ---------------- CLEAN DATA ----------------

    df["Rating"] = pd.to_numeric(df["Rating"], errors="coerce")
    df["Reviews"] = pd.to_numeric(df["Reviews"], errors="coerce")

    df = df[
        (df["Rating"] >= min_rating) &
        (df["Rating"] <= max_rating)
    ]

    df = df[
        (df["Reviews"] >= min_reviews) &
        (df["Reviews"] <= max_reviews)
    ]

    df = df.drop_duplicates()

    # ---------------- EMAIL SCRAPER ----------------

    df["Email"] = ""

    if find_emails:

        websites = df[df["Website"].notna()].head(email_scan_limit)

        email_progress = st.progress(0)

        for i, idx in enumerate(websites.index):

            site = df.loc[idx, "Website"]

            email = extract_email_from_website(site)

            df.loc[idx, "Email"] = email

            email_progress.progress((i+1) / len(websites))

            time.sleep(0.05)

    # ---------------- OPPORTUNITY SCORE ----------------

    def score(row):

        if not row["Website"]:
            return "HIGH"

        if row["Reviews"] < 30:
            return "MEDIUM"

        return "LOW"

    df["Opportunity"] = df.apply(score, axis=1)

    st.success(f"{len(df)} businesses found")

    st.dataframe(df)

    csv = df.to_csv(index=False).encode("utf-8")

    st.download_button(
        "Download Lead List",
        csv,
        "lead_generation_with_emails.csv",
        "text/csv"
    )
