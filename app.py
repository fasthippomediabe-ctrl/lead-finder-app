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
import streamlit as st
from apify_client import ApifyClient

ACTOR_ID = "compass/crawler-google-places"

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
            "Edmonton, Alberta",
        ],
    },
    "United Kingdom": {
        "currency": "GBP",
        "language": "en",
        "cities": [
            "London, England",
            "Manchester, England",
            "Birmingham, England",
            "Liverpool, England",
            "Leeds, England",
            "Glasgow, Scotland",
        ],
    },
    "Australia": {
        "currency": "AUD",
        "language": "en",
        "cities": [
            "Sydney, New South Wales",
            "Melbourne, Victoria",
            "Brisbane, Queensland",
            "Perth, Western Australia",
            "Adelaide, South Australia",
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
            "Pasig",
        ],
    },
    "Germany": {
        "currency": "EUR",
        "language": "de",
        "cities": [
            "Berlin",
            "Munich",
            "Hamburg",
            "Frankfurt",
            "Cologne",
            "Stuttgart",
        ],
    },
    "France": {
        "currency": "EUR",
        "language": "fr",
        "cities": [
            "Paris",
            "Lyon",
            "Marseille",
            "Toulouse",
            "Nice",
            "Bordeaux",
        ],
    },
    "Spain": {
        "currency": "EUR",
        "language": "es",
        "cities": [
            "Madrid",
            "Barcelona",
            "Valencia",
            "Seville",
            "Malaga",
            "Bilbao",
        ],
    },
    "India": {
        "currency": "INR",
        "language": "en",
        "cities": [
            "Mumbai",
            "Delhi",
            "Bangalore",
            "Hyderabad",
            "Chennai",
            "Pune",
        ],
    },
    "Singapore": {
        "currency": "SGD",
        "language": "en",
        "cities": [
            "Singapore",
        ],
    },
}

IMPORTANT_COLUMNS = [
    "Title",
    "CategoryName",
    "Address",
    "City",
    "State",
    "CountryCode",
    "Phone",
    "Website",
    "TotalScore",
    "ReviewsCount",
    "URL",
]

st.set_page_config(page_title="Global Business Lead Finder", page_icon="🌍", layout="wide")

st.title("🌍 Global Business Lead Finder")
st.write("Choose a country, select cities, enter industries, and generate a clean lead list.")

country = st.selectbox("Country", list(COUNTRY_DATA.keys()))
country_info = COUNTRY_DATA[country]

st.info(
    f"Language: {country_info['language'].upper()} | "
    f"Currency: {country_info['currency']}"
)

industries = st.text_area(
    "Industries (one per line)",
    "dentist\nplumber\ngym"
)

selected_cities = st.multiselect(
    "Cities",
    country_info["cities"],
    default=country_info["cities"][:2],
)

custom_city = st.text_input("Optional custom city/location", "")

max_results = st.number_input("Max results per search", min_value=1, max_value=200, value=10)

min_rating = st.number_input(
    "Minimum Rating",
    min_value=0.0,
    max_value=5.0,
    value=0.0,
    step=0.1,
)

max_rating = st.number_input(
    "Maximum Rating",
    min_value=0.0,
    max_value=5.0,
    value=5.0,
    step=0.1,
)

min_reviews = st.number_input(
    "Minimum Number of Reviews",
    min_value=0,
    max_value=100000,
    value=0,
    step=1,
)

max_reviews = st.number_input(
    "Maximum Number of Reviews",
    min_value=0,
    max_value=100000,
    value=100000,
    step=1,
)

run_clicked = st.button("Run Global Scraper")

if run_clicked:
    token = os.getenv("APIFY_API_TOKEN")

    if not token:
        st.error("Please set your APIFY_API_TOKEN in the terminal first.")
        st.stop()

    industry_list = [i.strip() for i in industries.split("\n") if i.strip()]
    city_list = list(selected_cities)

    if custom_city.strip():
        city_list.append(custom_city.strip())

    # remove duplicates while preserving order
    city_list = list(dict.fromkeys(city_list))

    if not industry_list:
        st.error("Please enter at least one industry.")
        st.stop()

    if not city_list:
        st.error("Please select or enter at least one city/location.")
        st.stop()

    client = ApifyClient(token)
    all_results = []

    total_jobs = len(industry_list) * len(city_list)
    job_count = 0
    progress = st.progress(0.0)
    status_box = st.empty()

    for industry in industry_list:
        for city in city_list:
            query = f"{industry} in {city}, {country}"
            status_box.write(f"Running: {query}")

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
                st.warning(f"Skipped query '{query}' because of an error: {e}")

            job_count += 1
            progress.progress(job_count / total_jobs)

    if not all_results:
        st.warning("No results were found.")
        st.stop()

    df = pd.DataFrame(all_results)

    available_columns = [c for c in IMPORTANT_COLUMNS if c in df.columns]
    df = df[available_columns].copy()

    # normalize numeric columns
    if "totalScore" in df.columns:
        df["totalScore"] = pd.to_numeric(df["totalScore"], errors="coerce")

    if "reviewsCount" in df.columns:
        df["reviewsCount"] = pd.to_numeric(df["reviewsCount"], errors="coerce").fillna(0).astype(int)

    # add app-level metadata
    df["selectedCountry"] = country
    df["currency"] = country_info["currency"]
    df["language"] = country_info["language"]

    # filters
    if "totalScore" in df.columns:
        df = df[
            (df["totalScore"] >= min_rating) &
            (df["totalScore"] <= max_rating)
        ]

    if "reviewsCount" in df.columns:
        df = df[
            (df["reviewsCount"] >= min_reviews) &
            (df["reviewsCount"] <= max_reviews)
        ]

    # remove duplicates if possible
    if "url" in df.columns:
        df = df.drop_duplicates(subset=["url"])
    elif "title" in df.columns and "address" in df.columns:
        df = df.drop_duplicates(subset=["title", "address"])
    else:
        df = df.drop_duplicates()

    # opportunity scoring
    def score_lead(row):
        rating = row.get("totalScore", None)
        reviews = row.get("reviewsCount", None)
        website = row.get("website", "")

        if pd.isna(rating):
            rating = 0.0
        if pd.isna(reviews):
            reviews = 0

        no_website = not str(website).strip()

        if no_website or (reviews < 30 and rating <= 4.6):
            return "HIGH"
        if reviews < 80 and rating <= 4.8:
            return "MEDIUM"
        return "LOW"

    df["Opportunity"] = df.apply(score_lead, axis=1)

    # reorder columns
    preferred_order = [
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
        "Opportunity",
        "selectedCountry",
        "currency",
        "language",
        "url",
    ]
    final_columns = [c for c in preferred_order if c in df.columns]
    df = df[final_columns]

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
        "global_lead_generation_list.csv",
        "text/csv",

    )
