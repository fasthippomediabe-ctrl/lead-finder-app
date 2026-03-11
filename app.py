import streamlit as st

# LOGIN
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

import os
import pandas as pd
from apify_client import ApifyClient

ACTOR_ID = "compass/crawler-google-places"

st.set_page_config(page_title="Global Lead Finder", page_icon="🌍", layout="wide")

st.title("🌍 Global Business Lead Finder")

st.write("Generate high-quality business leads anywhere in the world.")

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

max_results = st.number_input("Max results per search", 1, 200, 50)

min_rating = st.number_input("Minimum Rating", 0.0, 5.0, 0.0)
max_rating = st.number_input("Maximum Rating", 0.0, 5.0, 5.0)

run_clicked = st.button("Run Global Scraper")

if run_clicked:

    token = os.getenv("APIFY_API_TOKEN")

    if not token:
        st.error("Missing APIFY_API_TOKEN")
        st.stop()

    client = ApifyClient(token)

    industry_list = [i.strip() for i in industries.split("\n") if i.strip()]
    location_list = [c.strip() for c in locations.split("\n") if c.strip()]

    if not industry_list:
        st.error("Please add industries")
        st.stop()

    if not location_list:
        st.error("Please add locations")
        st.stop()

    all_results = []

    total_jobs = len(industry_list) * len(location_list)
    progress = st.progress(0)
    job_count = 0

    for industry in industry_list:
        for location in location_list:

            if country:
                query = f"{industry} {location} {country}"
            else:
                query = f"{industry} {location}"

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
                st.warning(f"Error: {e}")

            job_count += 1
            progress.progress(job_count / total_jobs)

    if not all_results:
        st.warning("No results found.")
        st.stop()

    df = pd.DataFrame(all_results)

    # CLEAN CRM OUTPUT
    columns_map = {
        "title": "Business Name",
        "categoryName": "Category",
        "address": "Address",
        "phone": "Phone",
        "website": "Website",
        "totalScore": "Rating",
        "reviewsCount": "Reviews",
        "url": "Google Maps"
    }

    df = df[list(columns_map.keys())]
    df.rename(columns=columns_map, inplace=True)

    df["Rating"] = pd.to_numeric(df["Rating"], errors="coerce")
    df["Reviews"] = pd.to_numeric(df["Reviews"], errors="coerce")

    # FILTER
    df = df[
        (df["Rating"] >= min_rating) &
        (df["Rating"] <= max_rating)
    ]

    df = df.drop_duplicates()

    # LEAD TYPE DETECTION
    def classify(row):

        if not row["Website"]:
            return "NO_WEBSITE"

        if row["Reviews"] < 30:
            return "LOW_REVIEWS"

        return "STRONG_BUSINESS"

    df["LeadType"] = df.apply(classify, axis=1)

    # OPPORTUNITY SCORE
    def score(row):

        if row["LeadType"] == "NO_WEBSITE":
            return "HIGH"

        if row["Reviews"] < 50:
            return "MEDIUM"

        return "LOW"

    df["Opportunity"] = df.apply(score, axis=1)

    st.success(f"{len(df)} businesses found")

    st.dataframe(df, use_container_width=True)

    csv = df.to_csv(index=False).encode("utf-8")

    st.download_button(
        "Download Lead List",
        csv,
        "lead_generation_list.csv",
        "text/csv"
    )
