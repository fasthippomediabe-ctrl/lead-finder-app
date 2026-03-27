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
from urllib.parse import urljoin
from apify_client import ApifyClient

# ---------------- CONFIG ----------------

GOOGLE_ACTOR_ID = "compass/crawler-google-places"

# Verify the exact actor IDs you want to use in your Apify account
ANGI_ACTOR_ID = "igolaizola/angi-scraper"
HOMEADVISOR_ACTOR_ID = "alizarin_refrigerator-owner/homeadvisor-scraper"

STOP_WORDS = [
    "company",
    "service",
    "services",
    "store",
    "shop",
    "inc",
    "llc",
    "co",
    "dealer",
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

# ---------------- PAGE ----------------

st.set_page_config(page_title="Global Lead Finder", page_icon="🌍", layout="wide")
st.title("🌍 Global Business Lead Finder")

industries = st.text_area("Industries (one per line)", "plumber")
locations = st.text_area("Cities / Locations (one per line)", "Austin Texas\nDallas Texas\nHouston Texas")
country = st.text_input("Country (optional)", "United States")
max_results = st.number_input("Max results per search", 1, 200, 25)

st.subheader("Sources")
use_google = st.checkbox("Google Maps", True)
use_angi = st.checkbox("Angi", True)
use_homeadvisor = st.checkbox("HomeAdvisor", True)

find_emails = st.checkbox("Find emails from websites", True)
email_scan_limit = st.number_input("Max websites to scan", 1, 500, 50)

run_clicked = st.button("Run Global Scraper")

# ---------------- HELPERS ----------------

def expand_industry(industry):
    industry = industry.lower()

    variations = [
        industry,
        f"{industry} company",
        f"{industry} service",
        f"{industry} contractor",
        f"local {industry}",
        f"emergency {industry}",
        f"residential {industry}",
        f"commercial {industry}",
    ]
    return list(set(variations))

def normalize_website(url):
    if not url:
        return ""
    if not str(url).startswith("http"):
        return "https://" + str(url)
    return str(url)

def fetch_page(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=8)
        if r.status_code == 200:
            return r.text
    except Exception:
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

def safe_int(value, default=0):
    try:
        if pd.isna(value):
            return default
        return int(float(value))
    except Exception:
        return default

def build_keywords(industry_list):
    keywords = []
    for industry in industry_list:
        words = industry.lower().split()
        words = [w for w in words if w not in STOP_WORDS]
        keywords.extend(words)
    return list(set(keywords))

def is_relevant_business(row, keywords):
    name = str(row.get("Business Name", "")).lower()
    category = str(row.get("Category", "")).lower()

    for word in keywords:
        if word in name or word in category:
            return True
    return False

def remove_chain_business(row):
    name = str(row.get("Business Name", "")).lower()
    for bad in EXCLUDED_BUSINESSES:
        if bad in name:
            return False
    return True

# ---------------- NORMALIZERS ----------------

def normalize_google_item(item):
    return {
        "Source": "Google Maps",
        "Business Name": item.get("title", ""),
        "Category": item.get("categoryName", ""),
        "Address": item.get("address", ""),
        "Phone": item.get("phone", ""),
        "Website": item.get("website", ""),
        "Rating": item.get("totalScore", ""),
        "Reviews": item.get("reviewsCount", ""),
        "Listing URL": item.get("url", ""),
        "Email": "",
    }

def normalize_angi_item(item):
    # Adjust these keys once you inspect the actual Angi dataset output
    return {
        "Source": "Angi",
        "Business Name": item.get("title") or item.get("name") or item.get("businessName", ""),
        "Category": item.get("category") or item.get("service") or item.get("categoryName", ""),
        "Address": item.get("address") or item.get("location", ""),
        "Phone": item.get("phone") or item.get("phoneNumber", ""),
        "Website": item.get("website") or item.get("websiteUrl", ""),
        "Rating": item.get("rating") or item.get("stars") or item.get("totalScore", ""),
        "Reviews": item.get("reviewsCount") or item.get("reviewCount") or item.get("reviews", ""),
        "Listing URL": item.get("url") or item.get("listingUrl", ""),
        "Email": "",
    }

def normalize_homeadvisor_item(item):
    # Adjust these keys once you inspect the actual HomeAdvisor dataset output
    return {
        "Source": "HomeAdvisor",
        "Business Name": item.get("title") or item.get("name") or item.get("businessName", ""),
        "Category": item.get("category") or item.get("service") or item.get("categoryName", ""),
        "Address": item.get("address") or item.get("location", ""),
        "Phone": item.get("phone") or item.get("phoneNumber", ""),
        "Website": item.get("website") or item.get("websiteUrl", ""),
        "Rating": item.get("rating") or item.get("stars") or item.get("totalScore", ""),
        "Reviews": item.get("reviewsCount") or item.get("reviewCount") or item.get("reviews", ""),
        "Listing URL": item.get("url") or item.get("listingUrl", ""),
        "Email": "",
    }

# ---------------- APIFY SCRAPERS ----------------

def scrape_google_maps(client, query, max_results):
    run = client.actor(GOOGLE_ACTOR_ID).call(
        run_input={
            "searchStringsArray": [query],
            "maxCrawledPlacesPerSearch": int(max_results)
        }
    )
    dataset_id = run["defaultDatasetId"]
    items = list(client.dataset(dataset_id).iterate_items())
    return [normalize_google_item(item) for item in items]

def scrape_angi(client, industry, location, country, max_results):
    # This input may need adjustment depending on the Angi actor you choose
    search_query = f"{industry} {location} {country}".strip()

    run = client.actor(ANGI_ACTOR_ID).call(
        run_input={
            "search": search_query,
            "maxItems": int(max_results)
        }
    )
    dataset_id = run["defaultDatasetId"]
    items = list(client.dataset(dataset_id).iterate_items())
    return [normalize_angi_item(item) for item in items]

def scrape_homeadvisor(client, industry, location, country, max_results):
    # This input may need adjustment depending on the HomeAdvisor actor you choose
    search_query = f"{industry} {location} {country}".strip()

    run = client.actor(HOMEADVISOR_ACTOR_ID).call(
        run_input={
            "search": search_query,
            "maxItems": int(max_results)
        }
    )
    dataset_id = run["defaultDatasetId"]
    items = list(client.dataset(dataset_id).iterate_items())
    return [normalize_homeadvisor_item(item) for item in items]

# ---------------- MAIN ----------------

if run_clicked:
    token = os.getenv("APIFY_API_TOKEN")

    if not token:
        st.error("Missing APIFY_API_TOKEN")
        st.stop()

    if not any([use_google, use_angi, use_homeadvisor]):
        st.error("Please select at least one source.")
        st.stop()

    client = ApifyClient(token)

    industry_list = [i.strip() for i in industries.split("\n") if i.strip()]
    location_list = [c.strip() for c in locations.split("\n") if c.strip()]

    expanded_industries = []
    for industry in industry_list:
        expanded_industries.extend(expand_industry(industry))
    expanded_industries = list(set(expanded_industries))

    all_results = []

    enabled_sources = []
    if use_google:
        enabled_sources.append("Google Maps")
    if use_angi:
        enabled_sources.append("Angi")
    if use_homeadvisor:
        enabled_sources.append("HomeAdvisor")

    total_jobs = len(expanded_industries) * len(location_list) * len(enabled_sources)
    progress = st.progress(0)
    job = 0

    for industry in expanded_industries:
        for location in location_list:
            query = f"{industry} {location} {country}".strip()

            if use_google:
                st.write("Searching Google Maps:", query)
                try:
                    items = scrape_google_maps(client, query, max_results)
                    all_results.extend(items)
                except Exception as e:
                    st.warning(f"Google Maps error: {e}")
                job += 1
                progress.progress(job / total_jobs)

            if use_angi:
                st.write("Searching Angi:", query)
                try:
                    items = scrape_angi(client, industry, location, country, max_results)
                    all_results.extend(items)
                except Exception as e:
                    st.warning(f"Angi error: {e}")
                job += 1
                progress.progress(job / total_jobs)

            if use_homeadvisor:
                st.write("Searching HomeAdvisor:", query)
                try:
                    items = scrape_homeadvisor(client, industry, location, country, max_results)
                    all_results.extend(items)
                except Exception as e:
                    st.warning(f"HomeAdvisor error: {e}")
                job += 1
                progress.progress(job / total_jobs)

    if not all_results:
        st.warning("No results found.")
        st.stop()

    df = pd.DataFrame(all_results)

    expected_columns = [
        "Source",
        "Business Name",
        "Category",
        "Address",
        "Phone",
        "Website",
        "Rating",
        "Reviews",
        "Listing URL",
        "Email",
    ]

    for col in expected_columns:
        if col not in df.columns:
            df[col] = ""

    df = df[expected_columns]

    # ---------------- INDUSTRY FILTER ----------------

    keywords = build_keywords(industry_list)
    df = df[df.apply(lambda row: is_relevant_business(row, keywords), axis=1)]

    # ---------------- REMOVE CHAINS ----------------

    df = df[df.apply(remove_chain_business, axis=1)]

    # ---------------- DEDUPE ----------------

    df["dedupe_key"] = (
        df["Business Name"].fillna("").astype(str).str.lower().str.strip() + "|" +
        df["Phone"].fillna("").astype(str).str.lower().str.strip() + "|" +
        df["Address"].fillna("").astype(str).str.lower().str.strip()
    )

    df = df.drop_duplicates(subset=["dedupe_key"])
    df = df.drop(columns=["dedupe_key"])

    # ---------------- EMAIL FINDER ----------------

    if find_emails:
        df["Email"] = df["Email"].fillna("")
        sites = df[df["Website"].notna() & (df["Website"].astype(str).str.strip() != "")].head(email_scan_limit)

        if len(sites) > 0:
            email_progress = st.progress(0)

            for i, idx in enumerate(sites.index):
                website = df.loc[idx, "Website"]
                email = extract_email_from_website(website)
                df.loc[idx, "Email"] = email
                email_progress.progress((i + 1) / len(sites))
                time.sleep(0.05)

    # ---------------- OPPORTUNITY SCORE ----------------

    def score(row):
        website = str(row.get("Website", "")).strip()
        reviews = safe_int(row.get("Reviews", 0))

        if not website:
            return "HIGH"
        if reviews < 30:
            return "MEDIUM"
        return "LOW"

    df["Opportunity"] = df.apply(score, axis=1)

    # Optional sort
    opportunity_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    df["sort_order"] = df["Opportunity"].map(opportunity_order)
    df = df.sort_values(by=["sort_order", "Reviews"], ascending=[True, True])
    df = df.drop(columns=["sort_order"])

    st.success(f"{len(df)} businesses found")
    st.dataframe(df, use_container_width=True)

    csv = df.to_csv(index=False).encode("utf-8")

    st.download_button(
        "Download Leads",
        csv,
        "lead_generation_multisource.csv",
        "text/csv"
    )
