import streamlit as st

# ---- LOGIN SYSTEM ----

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

# IMPORTS
import os
import pandas as pd
from apify_client import ApifyClient

ACTOR_ID = "compass/crawler-google-places"

COUNTRY_DATA = {
    "United States": {"currency": "USD", "language": "en"},
    "Canada": {"currency": "CAD", "language": "en"},
    "United Kingdom": {"currency": "GBP", "language": "en"},
    "Australia": {"currency": "AUD", "language": "en"},
    "Philippines": {"currency": "PHP", "language": "en"},
    "Germany": {"currency": "EUR", "language": "de"},
    "France": {"currency": "EUR", "language": "fr"},
    "Spain": {"currency": "EUR", "language": "es"},
    "India": {"currency": "INR", "language": "en"},
    "Singapore": {"currency": "SGD", "language": "en"},
}

IMPORTANT_COLUMNS = [
    "title",
    "categoryName",
    "address",
    "city",
    "state",
    "countryCode",
    "phone",
    "website",
    "totalScore",
    "reviewsCount",
    "url",
]

st.set_page_config(page_title="Global Business Lead Finder", page_icon="🌍", layout="wide")

st.title("🌍 Global Business Lead Finder")
st.write("Enter a city or location anywhere in the world to generate business leads.")

country = st.selectbox("Country", list(COUNTRY_DATA.keys()))
country_info = COUNTRY_DATA[country]

st.info(
    f"Language: {country_info['language'].upper()} | Currency: {country_info['currency']}"
)

industries = st.text_area(
    "Industries (one per line)",
    "dentist\nplumber\ngym"
)

location = st.text_input(
    "City / Location (example: Austin Texas, London, Berlin, Tokyo)",
    ""
)

max_results = st.number_input("Max results per search", 1, 200, 10)

min_rating = st.number_input("Minimum Rating", 0.0, 5.0, 0.0, 0.1)
max_rating = st.number_input("Maximum Rating", 0.0, 5.0, 5.0, 0.1)

min_reviews = st.number_input("Minimum Reviews", 0, 100000, 0)
max_reviews = st.number_input("Maximum Reviews", 0, 100000, 100000)

run_clicked = st.button("Run Global Scraper")

if run_clicked:

    token = os.getenv("APIFY_API_TOKEN")

    if not token:
        st.error("Please set APIFY_API_TOKEN in Streamlit secrets.")
        st.stop()

    if not location.strip():
        st.error("Please enter a city or location.")
        st.stop()

    industry_list = [i.strip() for i in industries.split("\n") if i.strip()]

    client = ApifyClient(token)
    all_results = []

    progress = st.progress(0)
    total_jobs = len(industry_list)
    job_count = 0

    for industry in industry_list:

        query = f"{industry} {location}"
        st.write("Running:", query)

        try:
            run = client.actor(ACTOR_ID).call(
                run_input={
                    "searchStringsArray": [query],
                    "maxCrawledPlacesPerSearch": int(max_results),
                }
            )

            dataset_id = run["defaultDatasetId"]
            items = list(client.dataset(dataset_id).iterate_items())

            all_results.extend(items)

        except Exception as e:
            st.warning(f"Error running query '{query}': {e}")

        job_count += 1
        progress.progress(job_count / total_jobs)

    if not all_results:
        st.warning("No results found.")
        st.stop()

    df = pd.DataFrame(all_results)

    available_columns = [c for c in IMPORTANT_COLUMNS if c in df.columns]
    df = df[available_columns].copy()

    if "totalScore" in df.columns:
        df["totalScore"] = pd.to_numeric(df["totalScore"], errors="coerce")

    if "reviewsCount" in df.columns:
        df["reviewsCount"] = pd.to_numeric(df["reviewsCount"], errors="coerce").fillna(0)

    if "totalScore" in df.columns:
        df = df[(df["totalScore"] >= min_rating) & (df["totalScore"] <= max_rating)]

    if "reviewsCount" in df.columns:
        df = df[(df["reviewsCount"] >= min_reviews) & (df["reviewsCount"] <= max_reviews)]

    df = df.drop_duplicates()

    def score_lead(row):
        rating = row.get("totalScore", 0)
        reviews = row.get("reviewsCount", 0)
        website = row.get("website", "")

        if not website or (reviews < 30 and rating <= 4.6):
            return "HIGH"
        if reviews < 80:
            return "MEDIUM"
        return "LOW"

    df["Opportunity"] = df.apply(score_lead, axis=1)

    st.success(f"Scraping finished. {len(df)} businesses found.")

    col1, col2, col3 = st.columns(3)
    col1.metric("Country", country)
    col2.metric("Currency", country_info["currency"])
    col3.metric("Language", country_info["language"].upper())

    st.dataframe(df, use_container_width=True)

    csv = df.to_csv(index=False).encode("utf-8")

    st.download_button(
        "Download Lead List",
        csv,
        "global_leads.csv",
        "text/csv",
    )
