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

EMAIL_REGEX = re.compile(r'([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})')

COMMON_CONTACT_PATHS = [
    "",
    "/contact",
    "/contact-us",
    "/contacts",
    "/about",
    "/about-us",
    "/team",
    "/get-in-touch",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
}

# ---------------- PAGE ----------------

st.set_page_config(page_title="Global Lead Finder", page_icon="🌍", layout="wide")

st.title("🌍 Global Business Lead Finder")
st.write("Generate business leads, classify opportunity, and try to extract contact emails from websites.")

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

max_results = st.number_input("Max results per search", min_value=1, max_value=200, value=25)

min_rating = st.number_input("Minimum Rating", min_value=0.0, max_value=5.0, value=0.0, step=0.1)
max_rating = st.number_input("Maximum Rating", min_value=0.0, max_value=5.0, value=5.0, step=0.1)

min_reviews = st.number_input("Minimum Reviews", min_value=0, max_value=100000, value=0, step=1)
max_reviews = st.number_input("Maximum Reviews", min_value=0, max_value=100000, value=100000, step=1)

find_emails = st.checkbox("Find emails from websites", value=True)
email_scan_limit = st.number_input("Max websites to scan for emails", min_value=1, max_value=500, value=50, step=1)

run_clicked = st.button("Run Global Scraper")

# ---------------- HELPERS ----------------

def normalize_website(url: str) -> str:
    if not url or pd.isna(url):
        return ""
    url = str(url).strip()
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url

def clean_email(email: str) -> str:
    email = email.strip().lower()
    email = email.replace("mailto:", "")
    return email

def is_valid_email(email: str) -> bool:
    if not email:
        return False
    bad_parts = ["example.com", ".png", ".jpg", ".jpeg", ".webp", ".svg", ".js", ".css"]
    return not any(part in email for part in bad_parts)

def extract_emails_from_text(text: str) -> list[str]:
    emails = [clean_email(e) for e in EMAIL_REGEX.findall(text or "")]
    emails = [e for e in emails if is_valid_email(e)]
    return sorted(set(emails))

def get_domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""

def fetch_page(url: str, timeout: int = 10) -> str:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        if resp.status_code == 200 and "text/html" in resp.headers.get("Content-Type", ""):
            return resp.text
    except Exception:
        return ""
    return ""

def extract_email_from_website(website: str) -> tuple[str, str]:
    """
    Returns: (email, source_url)
    """
    base_url = normalize_website(website)
    if not base_url:
        return "", ""

    checked = set()
    candidate_urls = []

    # homepage + common contact/about paths
    for path in COMMON_CONTACT_PATHS:
        candidate_urls.append(urljoin(base_url.rstrip("/") + "/", path.lstrip("/")) if path else base_url)

    # unique while preserving order
    unique_urls = []
    for u in candidate_urls:
        if u not in checked:
            unique_urls.append(u)
            checked.add(u)

    base_domain = get_domain(base_url)

    for url in unique_urls:
        html = fetch_page(url)
        if not html:
            continue

        # direct regex scan
        emails = extract_emails_from_text(html)
        if emails:
            return emails[0], url

        # parse mailto links and contact/about links
        try:
            soup = BeautifulSoup(html, "html.parser")

            for a in soup.find_all("a", href=True):
                href = a["href"].strip()

                if href.lower().startswith("mailto:"):
                    email = clean_email(href)
                    if is_valid_email(email):
                        return email, url

            # second-level discovery: follow a small set of likely contact links
            for a in soup.find_all("a", href=True):
                href = a["href"].strip()
                text = (a.get_text(" ", strip=True) or "").lower()

                if any(keyword in href.lower() for keyword in ["contact", "about", "team"]) or \
                   any(keyword in text for keyword in ["contact", "about", "team", "get in touch"]):

                    next_url = urljoin(url, href)
                    next_domain = get_domain(next_url)
                    if next_domain != base_domain:
                        continue
                    if next_url in checked:
                        continue

                    checked.add(next_url)
                    html2 = fetch_page(next_url)
                    if not html2:
                        continue

                    emails2 = extract_emails_from_text(html2)
                    if emails2:
                        return emails2[0], next_url

                    soup2 = BeautifulSoup(html2, "html.parser")
                    for a2 in soup2.find_all("a", href=True):
                        href2 = a2["href"].strip()
                        if href2.lower().startswith("mailto:"):
                            email = clean_email(href2)
                            if is_valid_email(email):
                                return email, next_url
        except Exception:
            continue

    return "", ""

def classify_lead(row) -> str:
    website = str(row.get("Website", "") or "").strip()
    reviews = row.get("Reviews", 0)
    if pd.isna(reviews):
        reviews = 0

    if not website:
        return "NO_WEBSITE"
    if reviews < 30:
        return "LOW_REVIEWS"
    return "STRONG_BUSINESS"

def score_lead(row) -> str:
    lead_type = row.get("LeadType", "")
    reviews = row.get("Reviews", 0)
    if pd.isna(reviews):
        reviews = 0

    if lead_type == "NO_WEBSITE":
        return "HIGH"
    if lead_type == "LOW_REVIEWS":
        return "MEDIUM"
    if reviews < 80:
        return "MEDIUM"
    return "LOW"

# ---------------- MAIN ----------------

if run_clicked:
    token = os.getenv("APIFY_API_TOKEN")

    if not token:
        st.error("Missing APIFY_API_TOKEN")
        st.stop()

    client = ApifyClient(token)

    industry_list = [i.strip() for i in industries.split("\n") if i.strip()]
    location_list = [c.strip() for c in locations.split("\n") if c.strip()]

    if not industry_list:
        st.error("Please add at least one industry.")
        st.stop()

    if not location_list:
        st.error("Please add at least one city/location.")
        st.stop()

    all_results = []

    total_jobs = len(industry_list) * len(location_list)
    progress = st.progress(0)
    job_count = 0
    status_box = st.empty()

    for industry in industry_list:
        for location in location_list:
            query = f"{industry} {location} {country}".strip() if country.strip() else f"{industry} {location}".strip()
            status_box.write(f"Running: {query}")

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
                st.warning(f"Error while running '{query}': {e}")

            job_count += 1
            progress.progress(job_count / total_jobs)

    if not all_results:
        st.warning("No results found.")
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
        "city": "City",
        "state": "State",
        "countryCode": "CountryCode",
    }

    available_source_columns = [col for col in columns_map.keys() if col in df.columns]
    df = df[available_source_columns].copy()
    df.rename(columns={k: v for k, v in columns_map.items() if k in df.columns}, inplace=True)

    # numeric cleanup
    if "Rating" in df.columns:
        df["Rating"] = pd.to_numeric(df["Rating"], errors="coerce")

    if "Reviews" in df.columns:
        df["Reviews"] = pd.to_numeric(df["Reviews"], errors="coerce").fillna(0).astype(int)

    # filters
    if "Rating" in df.columns:
        df = df[(df["Rating"] >= min_rating) & (df["Rating"] <= max_rating)]

    if "Reviews" in df.columns:
        df = df[(df["Reviews"] >= min_reviews) & (df["Reviews"] <= max_reviews)]

    # dedupe
    if "Google Maps" in df.columns:
        df = df.drop_duplicates(subset=["Google Maps"])
    elif "Business Name" in df.columns and "Address" in df.columns:
        df = df.drop_duplicates(subset=["Business Name", "Address"])
    else:
        df = df.drop_duplicates()

    # lead type + opportunity
    df["LeadType"] = df.apply(classify_lead, axis=1)
    df["Opportunity"] = df.apply(score_lead, axis=1)

    # email finder
    df["Email"] = ""
    df["Email Source"] = ""

    if find_emails and "Website" in df.columns:
        websites_to_scan = df[df["Website"].fillna("").astype(str).str.strip() != ""].copy()
        websites_to_scan = websites_to_scan.head(int(email_scan_limit))

        if not websites_to_scan.empty:
            st.subheader("Scanning websites for emails")
            email_progress = st.progress(0)
            email_status = st.empty()

            scan_indices = list(websites_to_scan.index)
            total_scans = len(scan_indices)

            for idx_num, idx in enumerate(scan_indices, start=1):
                website = websites_to_scan.at[idx, "Website"]
                email_status.write(f"Checking: {website}")

                email, source_url = extract_email_from_website(website)
                if email:
                    df.at[idx, "Email"] = email
                    df.at[idx, "Email Source"] = source_url

                email_progress.progress(idx_num / total_scans)
                time.sleep(0.05)

    # final column order
    preferred_order = [
        "Business Name",
        "Category",
        "Address",
        "City",
        "State",
        "CountryCode",
        "Phone",
        "Website",
        "Email",
        "Email Source",
        "Rating",
        "Reviews",
        "LeadType",
        "Opportunity",
        "Google Maps",
    ]
    final_columns = [c for c in preferred_order if c in df.columns]
    df = df[final_columns]

    st.success(f"{len(df)} businesses found")

    metric1, metric2, metric3 = st.columns(3)
    metric1.metric("Total Leads", len(df))
    metric2.metric("With Email", int((df["Email"].astype(str).str.strip() != "").sum()) if "Email" in df.columns else 0)
    metric3.metric("High Opportunity", int((df["Opportunity"] == "HIGH").sum()) if "Opportunity" in df.columns else 0)

    st.dataframe(df, use_container_width=True)

    csv = df.to_csv(index=False).encode("utf-8")

    st.download_button(
        "Download Lead List",
        csv,
        "lead_generation_with_emails.csv",
        "text/csv"
    )
