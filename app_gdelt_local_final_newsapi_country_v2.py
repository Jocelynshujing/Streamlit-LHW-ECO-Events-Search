import streamlit as st
import pandas as pd
from datetime import datetime
from pathlib import Path
import re
import os
import requests

# ═══════════════════════════════════════════════════════════════
# CONTINENT MAPPING FROM V2LOCATIONS (GDELT) — pycountry-convert + Fallback
# ═══════════════════════════════════════════════════════════════

# Attempt to import pycountry-convert; if unavailable, rely on manual mapping.
try:
    import pycountry_convert as pc
    PYCOUNTRY_AVAILABLE = True
except ImportError:
    PYCOUNTRY_AVAILABLE = False

# Manual mapping for non-standard GDELT codes and as fallback
GDELT_COUNTRY_TO_CONTINENT = {
    # North America
    "US": "North America", "CA": "North America", "MX": "North America",
    "GT": "North America", "BZ": "North America", "SV": "North America",
    "HN": "North America", "NI": "North America", "CR": "North America",
    "PA": "North America", "CU": "North America", "JM": "North America",
    "HT": "North America", "DO": "North America", "PR": "North America",
    # South America
    "AR": "South America", "BO": "South America", "BR": "South America",
    "CL": "South America", "CO": "South America", "EC": "South America",
    "FK": "South America", "GF": "South America", "GY": "South America",
    "PE": "South America", "PY": "South America", "SR": "South America",
    "UY": "South America", "VE": "South America",
    # Europe
    "GB": "Europe", "UK": "Europe",  # GDELT uses UK instead of GB
    "AL": "Europe", "AD": "Europe", "AT": "Europe", "BY": "Europe",
    "BE": "Europe", "BA": "Europe", "BG": "Europe", "HR": "Europe",
    "CY": "Europe", "CZ": "Europe", "DK": "Europe", "EE": "Europe",
    "FO": "Europe", "FI": "Europe", "FR": "Europe", "DE": "Europe",
    "GI": "Europe", "GR": "Europe", "HU": "Europe", "IS": "Europe",
    "IE": "Europe", "IT": "Europe", "LV": "Europe", "LI": "Europe",
    "LT": "Europe", "LU": "Europe", "MT": "Europe", "MD": "Europe",
    "MC": "Europe", "NL": "Europe", "NO": "Europe", "PL": "Europe",
    "PT": "Europe", "RO": "Europe", "RU": "Europe", "SM": "Europe",
    "RS": "Europe", "SK": "Europe", "SI": "Europe", "ES": "Europe",
    "SE": "Europe", "CH": "Europe", "UA": "Europe", "VA": "Europe",
    "MK": "Europe", "ME": "Europe", "XK": "Europe",
    # Asia
    "AF": "Asia", "AM": "Asia", "AZ": "Asia", "BH": "Asia",
    "BD": "Asia", "BT": "Asia", "BN": "Asia", "KH": "Asia",
    "CN": "Asia", "CY": "Asia", "GE": "Asia", "IN": "Asia",
    "ID": "Asia", "IR": "Asia", "IQ": "Asia", "IL": "Asia",
    "JP": "Asia", "JO": "Asia", "KZ": "Asia", "KW": "Asia", "KU": "Asia",
    "KG": "Asia", "LA": "Asia", "LB": "Asia", "MY": "Asia",
    "MV": "Asia", "MN": "Asia", "MM": "Asia", "NP": "Asia",
    "OM": "Asia", "PK": "Asia", "PH": "Asia", "QA": "Asia",
    "SA": "Asia", "SG": "Asia", "KR": "Asia", "LK": "Asia",
    "SY": "Asia", "TW": "Asia", "TJ": "Asia", "TI": "Asia",
    "TH": "Asia", "TL": "Asia", "TR": "Asia", "TM": "Asia",
    "TX": "Asia", "AE": "Asia", "UZ": "Asia", "VN": "Asia", "YE": "Asia",
    "PS": "Asia",
    # Africa
    "DZ": "Africa", "AO": "Africa", "BJ": "Africa", "BW": "Africa",
    "BF": "Africa", "BI": "Africa", "CM": "Africa", "CV": "Africa",
    "CF": "Africa", "TD": "Africa", "KM": "Africa", "CG": "Africa",
    "CD": "Africa", "CI": "Africa", "DJ": "Africa", "EG": "Africa",
    "GQ": "Africa", "ER": "Africa", "SZ": "Africa", "ET": "Africa",
    "GA": "Africa", "GM": "Africa", "GH": "Africa", "GN": "Africa",
    "GW": "Africa", "KE": "Africa", "LS": "Africa", "LR": "Africa",
    "LY": "Africa", "MG": "Africa", "MW": "Africa", "ML": "Africa",
    "MR": "Africa", "MU": "Africa", "MA": "Africa", "MZ": "Africa",
    "NA": "Africa", "NE": "Africa", "NG": "Africa", "RW": "Africa",
    "ST": "Africa", "SN": "Africa", "SC": "Africa", "SL": "Africa",
    "SO": "Africa", "ZA": "Africa", "SS": "Africa", "SD": "Africa",
    "TZ": "Africa", "TG": "Africa", "TN": "Africa", "UG": "Africa",
    "EH": "Africa", "ZM": "Africa", "ZW": "Africa",
    # Oceania
    "AU": "Oceania", "NZ": "Oceania", "FJ": "Oceania", "NC": "Oceania",
    "PG": "Oceania", "SB": "Oceania", "VU": "Oceania", "GU": "Oceania",
    "KI": "Oceania", "MH": "Oceania", "FM": "Oceania", "NR": "Oceania",
    "PW": "Oceania", "WS": "Oceania", "TO": "Oceania", "TV": "Oceania",
    "AS": "Oceania", "CK": "Oceania", "NU": "Oceania", "PF": "Oceania",
    "PN": "Oceania", "TK": "Oceania", "WF": "Oceania",
}


def extract_country_codes_from_v2locations(v2locations_str):
    """Extract unique 2-letter country codes from GDELT V2Locations string."""
    if pd.isna(v2locations_str) or not v2locations_str:
        return set()
    country_codes = set()
    entries = str(v2locations_str).split(';')
    for entry in entries:
        if not entry.strip():
            continue
        parts = entry.split('#')
        if len(parts) >= 4:
            country_code = parts[3].strip().upper()
            if country_code and len(country_code) == 2 and country_code.isalpha():
                country_codes.add(country_code)
    return country_codes


def get_continent_from_country_code(country_code):
    """Map a 2-letter country code to continent name. Tries pycountry-convert first, falls back to manual mapping."""
    country_code = country_code.upper()
    # Try pycountry-convert first if available
    if PYCOUNTRY_AVAILABLE:
        try:
            continent_code = pc.country_alpha2_to_continent_code(country_code)
            return pc.convert_continent_code_to_continent_name(continent_code)
        except (KeyError, Exception):
            pass
    # Fallback to manual mapping
    return GDELT_COUNTRY_TO_CONTINENT.get(country_code, "Unknown")


def get_continents_from_v2locations(v2locations_str):
    """Get all unique continents mentioned in a V2Locations string."""
    country_codes = extract_country_codes_from_v2locations(v2locations_str)
    continents = set()
    for code in country_codes:
        continent = get_continent_from_country_code(code)
        if continent != "Unknown":
            continents.add(continent)
    return sorted(list(continents))


def add_continent_columns_to_df(df):
    """Add continent columns to a GDELT dataframe based on V2Locations."""
    if 'V2Locations' not in df.columns:
        return df
    df = df.copy()
    df['CountryCodes'] = df['V2Locations'].apply(
        lambda x: sorted(list(extract_country_codes_from_v2locations(x)))
    )
    df['Continents'] = df['V2Locations'].apply(get_continents_from_v2locations)
    df['PrimaryContinent'] = df['Continents'].apply(lambda x: x[0] if x else 'Unknown')
    df['Continents_Display'] = df['Continents'].apply(lambda x: ', '.join(x) if x else 'Unknown')
    return df


# ═══════════════════════════════════════════════════════════════
# NEWSAPI COUNTRY CODE MAPPING (Built-in country parameter)
# ═══════════════════════════════════════════════════════════════

NEWSAPI_COUNTRY_CODES = {
    "Global (All)": None,
    "North America": ["us", "ca", "mx"],
    "South America": ["ar", "br", "co", "ve"],
    "Europe": ["gb", "de", "fr", "it", "es", "nl", "be", "ch", "at", "se", "no", "dk", "fi", "pl", "cz", "hu", "ro", "bg", "gr", "pt", "ie"],
    "Asia": ["cn", "in", "jp", "kr", "id", "th", "vn", "ph", "my", "sg"],
    "Africa": ["za", "ng", "eg", "ke"],
    "Oceania": ["au", "nz"]
}

COUNTRY_NAMES = {
    "us": "United States", "ca": "Canada", "mx": "Mexico",
    "ar": "Argentina", "br": "Brazil", "co": "Colombia", "ve": "Venezuela",
    "gb": "United Kingdom", "de": "Germany", "fr": "France", "it": "Italy",
    "es": "Spain", "nl": "Netherlands", "be": "Belgium", "ch": "Switzerland",
    "at": "Austria", "se": "Sweden", "no": "Norway", "dk": "Denmark", "fi": "Finland",
    "pl": "Poland", "cz": "Czech Republic", "hu": "Hungary", "ro": "Romania",
    "bg": "Bulgaria", "gr": "Greece", "pt": "Portugal", "ie": "Ireland",
    "cn": "China", "in": "India", "jp": "Japan", "kr": "South Korea",
    "id": "Indonesia", "th": "Thailand", "vn": "Vietnam", "ph": "Philippines",
    "my": "Malaysia", "sg": "Singapore",
    "za": "South Africa", "ng": "Nigeria", "eg": "Egypt", "ke": "Kenya",
    "au": "Australia", "nz": "New Zealand"
}

ELITE_SOURCES = "bbc-news,cnn,reuters,the-wall-street-journal,the-washington-post,associated-press,bloomberg,the-globe-and-mail,time,newsweek"
ELITE_DOMAINS = "bbc.co.uk,cnn.com,reuters.com,wsj.com,washingtonpost.com,apnews.com,bloomberg.com,theglobeandmail.com,time.com,newsweek.com"

# ═══════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════

GDELT_DATA_DIR = "./gdelt_lake_data/yearly"

st.set_page_config(page_title="Lake-Heatwave-Eco-Crisis Explorer", page_icon="🤩", layout="wide")

st.title("Lake-Heatwave-Eco-Crisis Media Explorer")
st.markdown("""
This tool analyzes **locally-downloaded GDELT historical data** and **real-time NewsAPI**
to track global lake degradation events linked to temperature and ecological stress.
""")

# ═══════════════════════════════════════════════════════════════
# SIDEBAR CONFIGURATION
# ═══════════════════════════════════════════════════════════════
st.sidebar.header("Configuration")

api_key = st.sidebar.text_input("Enter NewsAPI Key (Optional)", type="password",
                                 help="Get a free key from newsapi.org for real-time news")

st.sidebar.header("Filter Criteria")

eco_impact = st.sidebar.selectbox(
    "Primary Ecological Focus",
    ["All Impacts", "Fish Kills / Mortalities", "Algal Blooms / Cyanobacteria",
     "Ecosystem Degradation", "Water Supply / Scarcity", "Oxygen Depletion"]
)

media_tier = st.sidebar.selectbox(
    "Media Outlets Tier (NewsAPI only)",
    ["All Media", "Elite Media Only", "Non-Elite Media Only"],
    help="Select source priority for the NewsAPI Real-Time view."
)

continent = st.sidebar.selectbox(
    "Continent / Region",
    ["Global (All)", "North America", "South America", "Europe", "Asia", "Africa", "Oceania"]
)

st.sidebar.header("Timeline (GDELT)")
year_range = st.sidebar.slider(
    "Year Range",
    2015, 2026, (2020, 2025),
    key="gdelt_year_slider"
)

# ═══════════════════════════════════════════════════════════════
# FILTER MAPPING
# ═══════════════════════════════════════════════════════════════

theme_filter_map = {
    "All Impacts": None,
    "Fish Kills / Mortalities": "FISH_KILL",
    "Algal Blooms / Cyanobacteria": "ALGAL_BLOOM",
    "Ecosystem Degradation": "ECOSYSTEM_DEGRADATION",
    "Water Supply / Scarcity": "WATER_SCARCITY",
    "Oxygen Depletion": "OXYGEN_DEPLETION"
}
selected_theme = theme_filter_map[eco_impact]

selected_countries = NEWSAPI_COUNTRY_CODES.get(continent)

# ═══════════════════════════════════════════════════════════════
# DATA LOADING FUNCTIONS (GDELT)
# ═══════════════════════════════════════════════════════════════

@st.cache_data(show_spinner=False, ttl=3600)
def load_gdelt_data(data_dir, start_year, end_year):
    """Load GDELT yearly CSV files for the selected year range."""
    data_path = Path(data_dir)
    if not data_path.exists():
        st.error(f"❌ Data directory not found: `{data_dir}`")
        return pd.DataFrame()
    csv_files = []
    for pattern in ["*_lake_title_only_*.csv", "*gdelt_lake_*.csv", "*_lake_warm_eco_*.csv"]:
        csv_files.extend(sorted(data_path.glob(pattern)))
    csv_files = list(dict.fromkeys(csv_files))
    if not csv_files:
        st.warning(f"⚠️ No GDELT data files found in `{data_dir}`")
        st.info("""
        **Expected files:** `*_lake_title_only_2025.csv` or `gdelt_lake_2025.csv`
        **To generate data:**
        ```bash
        python download_gdelt_lake_title_only.py --start 2015 --end 2025 --output ./gdelt_lake_data
        ```
        """)
        return pd.DataFrame()
    dfs = []
    for csv_file in csv_files:
        try:
            year_match = re.search(r'(\d{4})', csv_file.stem)
            if year_match:
                year = int(year_match.group(1))
                if start_year <= year <= end_year:
                    df = pd.read_csv(csv_file)
                    if not df.empty:
                        dfs.append(df)
        except Exception as e:
            st.warning(f"Error reading {csv_file.name}: {e}")
    if not dfs:
        st.warning(f"No data found for years {start_year}-{end_year}")
        return pd.DataFrame()
    return pd.concat(dfs, ignore_index=True)


@st.cache_data(show_spinner=False, ttl=3600)
def filter_gdelt_data(df, theme_category=None, selected_continent=None):
    """Apply filters to GDELT data with continent detection from V2Locations."""
    if df.empty:
        return df
    filtered = df.copy()
    # Add continent columns if not already present
    if 'PrimaryContinent' not in filtered.columns:
        filtered = add_continent_columns_to_df(filtered)
    # Filter 1: Theme Category
    if theme_category and 'ThemeCategory' in filtered.columns:
        before = len(filtered)
        filtered = filtered[filtered['ThemeCategory'] == theme_category]
        st.caption(f"🎯 Theme filter `{theme_category}`: {before} → {len(filtered)} records")
    # Filter 2: Continent (using detected continent from V2Locations)
    if selected_continent and selected_continent != "Global (All)":
        before = len(filtered)
        mask = filtered['Continents'].apply(
            lambda x: selected_continent in x if isinstance(x, list) else False
        )
        filtered = filtered[mask]
        st.caption(f"🌍 Continent filter `{selected_continent}`: {before} → {len(filtered)} records")
    return filtered


# ═══════════════════════════════════════════════════════════════
# NEWSAPI FUNCTIONS
# ═══════════════════════════════════════════════════════════════

def build_newsapi_query(eco_impact):
    """Build NewsAPI query string."""
    base_water_terms = '("lake" OR "reservoir" OR "freshwater")'
    base_heat_terms = '("heatwave" OR "heat" OR "record temperature" OR "hot" OR "rising temperature" OR "thermal stress")'
    if eco_impact == "Fish Kills / Mortalities":
        impact_terms = '("fish kill" OR "mass mortality" OR "fish die-off" OR "mass casualty event")'
    elif eco_impact == "Algal Blooms / Cyanobacteria":
        impact_terms = '("algal bloom" OR "cyanobacteria" OR "blue-green algae" OR "harmful algal bloom" OR "microcystis")'
    elif eco_impact == "Ecosystem Degradation":
        impact_terms = '("ecosystem collapse" OR "ecological degradation" OR "habitat loss" OR "biodiversity loss")'
    elif eco_impact == "Water Supply / Scarcity":
        impact_terms = '("water scarcity" OR "water shortage" OR "reduced water supply" OR "drought stress" OR "potable water risk" OR "water restriction")'
    elif eco_impact == "Oxygen Depletion":
        impact_terms = '("hypoxia" OR "anoxia" OR "oxygen depletion" OR "dead zone")'
    else:
        impact_terms = '("fish kill" OR "mass mortality" OR "algal bloom" OR "cyanobacteria" OR "harmful algal bloom" OR "habitat loss" OR "biodiversity loss" OR "water scarcity" OR "water shortage" OR "hypoxia" OR "oxygen depletion")'
    return f"{base_water_terms} AND {base_heat_terms} AND {impact_terms}"


def fetch_newsapi_top_headlines(query, country_code, api_token, limit=20):
    """Fetch news using /top-headlines endpoint with country parameter."""
    url = "https://newsapi.org/v2/top-headlines"
    params = {
        "q": query,
        "country": country_code,
        "pageSize": limit,
        "apiKey": api_token
    }
    try:
        response = requests.get(url, params=params, timeout=15)
        data = response.json()
        if data.get("status") == "error":
            return {"error": data.get("message"), "articles": []}
        return data
    except requests.exceptions.RequestException as e:
        return {"error": str(e), "articles": []}


def fetch_newsapi_everything(query, api_token, limit=20, sources=None, exclude_domains=None):
    """Fetch news using /everything endpoint."""
    url = "https://newsapi.org/v2/everything"
    params = {
        "q": query,
        "pageSize": limit,
        "sortBy": "relevancy",
        "language": "en",
        "apiKey": api_token
    }
    if sources:
        params["sources"] = sources
    if exclude_domains:
        params["excludeDomains"] = exclude_domains
    try:
        response = requests.get(url, params=params, timeout=15)
        data = response.json()
        if data.get("status") == "error":
            return {"error": data.get("message"), "articles": []}
        return data
    except requests.exceptions.RequestException as e:
        return {"error": str(e), "articles": []}


@st.cache_data(show_spinner=False, ttl=1800)
def fetch_filtered_news(query, continent, media_tier, api_token, limit):
    """Fetch news with continent filtering using NewsAPI built-in country parameter."""
    countries = NEWSAPI_COUNTRY_CODES.get(continent)
    all_articles = []
    errors = []
    if countries and continent != "Global (All)":
        st.info(f"🌍 Searching {len(countries)} countries in {continent}...")
        limit_per_country = max(5, limit // len(countries) + 2)
        for country_code in countries:
            data = fetch_newsapi_top_headlines(query, country_code, api_token, limit=limit_per_country)
            if "error" in data:
                errors.append(f"{COUNTRY_NAMES.get(country_code, country_code)} ({country_code}): {data['error']}")
            else:
                articles = data.get("articles", [])
                for article in articles:
                    article["_newsapi_country_code"] = country_code
                    article["_newsapi_country_name"] = COUNTRY_NAMES.get(country_code, country_code)
                    article["_newsapi_continent"] = continent
                all_articles.extend(articles)
    else:
        st.info("🌍 Searching global news sources...")
        sources = None
        exclude_domains = None
        if media_tier == "Elite Media Only":
            sources = ELITE_SOURCES
        elif media_tier == "Non-Elite Media Only":
            exclude_domains = ELITE_DOMAINS
        data = fetch_newsapi_everything(query, api_token, limit=limit, sources=sources, exclude_domains=exclude_domains)
        if "error" in data:
            errors.append(data["error"])
        else:
            articles = data.get("articles", [])
            for article in articles:
                article["_newsapi_country_code"] = "global"
                article["_newsapi_country_name"] = "Global"
                article["_newsapi_continent"] = "Global"
            all_articles.extend(articles)
    # Remove duplicates by URL
    seen_urls = set()
    unique_articles = []
    for article in all_articles:
        url = article.get("url")
        if url and url not in seen_urls:
            seen_urls.add(url)
            unique_articles.append(article)
    return {
        "articles": unique_articles,
        "totalResults": len(unique_articles),
        "errors": errors
    }


def validate_title_relevance(title, water_terms):
    """Check if title contains lake/reservoir/freshwater terms."""
    if not title:
        return False
    title_lower = title.lower()
    return any(term in title_lower for term in water_terms)


# ═══════════════════════════════════════════════════════════════
# TABS
# ═══════════════════════════════════════════════════════════════
tab1, tab2 = st.tabs(["📈 Historical GDELT Analysis", "⏰ Real-Time News Tracker (NewsAPI)"])

# ═══════════════════════════════════════════════════════════════
# TAB 1: HISTORICAL GDELT DATA
# ═══════════════════════════════════════════════════════════════
with tab1:
    st.header("Historical Lake Eco-Crisis Events (GDELT Data)")
    st.markdown(f"""
    **Active Filters:**
    - 🎯 **Ecological Focus:** `{eco_impact}` {'(All themes)' if selected_theme is None else f'→ `ThemeCategory = {selected_theme}`'}
    - 🌍 **Region:** `{continent}`
    - 📅 **Year Range:** `{year_range[0]} - {year_range[1]}`
    - 💾 **Data Source:** Pre-downloaded GDELT GKG 2.0 (title-filtered)
    """)

    with st.spinner("Loading GDELT historical data..."):
        raw_df = load_gdelt_data(GDELT_DATA_DIR, year_range[0], year_range[1])

    if raw_df.empty:
        st.error("""
        ❌ **No GDELT data found.**
        **To set up data:**
        1. Run the downloader script:
           ```bash
           python download_gdelt_lake_title_only.py --start 2015 --end 2025 --output ./gdelt_lake_data
           ```
        2. Update `GDELT_DATA_DIR` in this app to point to `./gdelt_lake_data/yearly`
        3. Or upload your CSV files to the data directory
        """)
    else:
        with st.spinner("Applying filters & detecting continents from V2Locations..."):
            filtered_df = filter_gdelt_data(raw_df, selected_theme, selected_continent=continent)

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Records (All Years)", f"{len(raw_df):,}")
        col2.metric("Filtered Records", f"{len(filtered_df):,}")
        col3.metric("Unique Articles", f"{filtered_df['DocumentIdentifier'].nunique():,}" if not filtered_df.empty else "0")
        col4.metric("Year Range", f"{year_range[0]}-{year_range[1]}")

        st.markdown("---")

        if filtered_df.empty:
            st.warning("⚠️ No records match the selected filters. Try broadening your criteria.")
            st.info("""
            **Suggestions:**
            - Select "All Impacts" for ecological focus
            - Select "Global (All)" for region
            - Widen the year range
            """)
        else:
            # --- CHARTS ---
            st.subheader("📊 Trend Analysis")
            if 'Year' in filtered_df.columns:
                yearly_counts = filtered_df.groupby('Year').agg(
                    Records=('DocumentIdentifier', 'count'),
                    UniqueArticles=('DocumentIdentifier', 'nunique')
                ).reset_index()
                col_chart1, col_chart2 = st.columns(2)
                with col_chart1:
                    st.line_chart(yearly_counts.set_index('Year')['Records'],
                                  use_container_width=True, height=300)
                    st.caption("Total Records per Year")
                with col_chart2:
                    st.bar_chart(yearly_counts.set_index('Year')['UniqueArticles'],
                                 use_container_width=True, height=300)
                    st.caption("Unique Articles per Year")

            # Theme distribution
            if 'ThemeCategory' in filtered_df.columns and selected_theme is None:
                st.subheader("🎯 Theme Distribution")
                theme_counts = filtered_df['ThemeCategory'].value_counts()
                st.bar_chart(theme_counts, use_container_width=True, height=250)

            # Continent distribution
            if 'PrimaryContinent' in filtered_df.columns:
                st.subheader("🌍 Continent Distribution (from V2Locations)")
                continent_counts = filtered_df['PrimaryContinent'].value_counts()
                st.bar_chart(continent_counts, use_container_width=True, height=250)

            st.markdown("---")

            # --- ARTICLE LIST ---
            st.subheader("📰 Articles (Lake/Reservoir in Title + Temperature + Ecosystem)")

            items_per_page = 10
            total_items = len(filtered_df)
            if total_items > items_per_page:
                page = st.number_input("Page", min_value=1,
                                       max_value=max(1, (total_items // items_per_page) + 1),
                                       value=1, key="page")
                start_idx = (page - 1) * items_per_page
                end_idx = min(start_idx + items_per_page, total_items)
                display_df = filtered_df.iloc[start_idx:end_idx]
                st.caption(f"Showing {start_idx+1}-{end_idx} of {total_items} records")
            else:
                display_df = filtered_df

            for idx, row in display_df.iterrows():
                with st.container():
                    col_text, col_meta = st.columns([3, 1])
                    with col_text:
                        title = row.get('ExtractedTitle', '')
                        if not title or pd.isna(title):
                            title = "Untitled Article"
                        title_display = title.title() if title else "Untitled"
                        url = row.get('DocumentIdentifier', '#')
                        st.markdown(f"### [{title_display}]({url})")
                        tags = []
                        if 'MatchedLakeTerms' in row and pd.notna(row['MatchedLakeTerms']):
                            tags.extend([f"🌊 {t.strip()}" for t in str(row['MatchedLakeTerms']).split(',') if t.strip()])
                        if 'MatchedTempTerms' in row and pd.notna(row['MatchedTempTerms']):
                            tags.extend([f"🌡️ {t.strip()}" for t in str(row['MatchedTempTerms']).split(',') if t.strip()])
                        if 'MatchedEcoTerms' in row and pd.notna(row['MatchedEcoTerms']):
                            tags.extend([f"⚠️ {t.strip()}" for t in str(row['MatchedEcoTerms']).split(',') if t.strip()])
                        if tags:
                            st.markdown(f"**Matched:** {' · '.join(tags[:8])}")

                    with col_meta:
                        year = row.get('Year', 'N/A')
                        month = row.get('Month', '')
                        st.caption(f"📅 **{year}-{month}**" if pd.notna(month) and str(month) != 'nan' else f"📅 **{year}**")

                        theme = row.get('ThemeCategory', 'OTHER')
                        theme_colors = {
                            'FISH_KILL': '🔴', 'ALGAL_BLOOM': '🟠', 'WATER_SCARCITY': '🔵',
                            'ECOSYSTEM_DEGRADATION': '🟣', 'OXYGEN_DEPLETION': '⚫',
                            'POLLUTION': '🟤', 'OTHER': '⚪'
                        }
                        badge = theme_colors.get(theme, '⚪')
                        st.caption(f"{badge} **{theme}**")

                        source = row.get('SourceCommonName', '')
                        if source and pd.notna(source):
                            st.caption(f"📢 {source}")

                        # NEW: Continent & Country info from V2Locations
                        continents = row.get('Continents_Display', '')
                        if continents and continents != 'Unknown':
                            st.caption(f"🌎 **{continents}**")

                        country_codes = row.get('CountryCodes', [])
                        if country_codes:
                            st.caption(f"🏳️ {', '.join(country_codes)}")

                        locations = row.get('V2Locations', '')
                        if locations and pd.notna(locations):
                            loc_match = re.search(r'\d+#([^#]+)', str(locations))
                            if loc_match:
                                st.caption(f"📍 {loc_match.group(1)[:40]}...")

                    st.markdown("---")

            # --- EXPORT ---
            st.subheader("📥 Export Data")
            col_exp1, col_exp2 = st.columns(2)
            with col_exp1:
                csv_filtered = filtered_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Export Filtered Data (CSV)",
                    data=csv_filtered,
                    file_name=f"gdelt_filtered_{eco_impact.replace(' ', '_').replace('/', '_')}_{continent.replace(' ', '_')}_{year_range[0]}_{year_range[1]}.csv",
                    mime="text/csv"
                )
            with col_exp2:
                csv_raw = raw_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Export All Raw Data (CSV)",
                    data=csv_raw,
                    file_name=f"gdelt_raw_{year_range[0]}_{year_range[1]}.csv",
                    mime="text/csv"
                )

            with st.expander("🔍 View Raw Data Table"):
                st.dataframe(filtered_df, use_container_width=True)


# ═══════════════════════════════════════════════════════════════
# TAB 2: REAL-TIME NEWSAPI
# ═══════════════════════════════════════════════════════════════
with tab2:
    st.header("⏰ Real-Time News Tracker (NewsAPI)")
    countries = NEWSAPI_COUNTRY_CODES.get(continent)
    if countries:
        country_names = [f"{COUNTRY_NAMES.get(c, c)} ({c})" for c in countries]
        st.info(f"🌍 **{continent}** → Searching: {', '.join(country_names)}")
        st.caption("Using NewsAPI built-in `country` parameter for accurate regional filtering")
    else:
        st.info("🌍 **Global** → Searching all available sources")
        st.caption("Using NewsAPI `/everything` endpoint for global search")

    st.markdown(f"""
    **Active Filters:**
    - 🎯 **Ecological Focus:** `{eco_impact}`
    - 🌍 **Region:** `{continent}`
    - 📰 **Media Tier:** `{media_tier}`
    """)

    query = build_newsapi_query(eco_impact)
    with st.expander("Show Search Query"):
        st.code(query, language="text")
        if countries:
            st.code(f"Country codes: {', '.join(countries)}", language="text")

    max_records = st.slider("Maximum Articles", 10, 100, 20, key="newsapi_limit")

    if st.button("🔍 Search Live News", type="primary", key="newsapi_btn"):
        if not api_key:
            st.error("Please enter a NewsAPI key in the sidebar.")
        else:
            with st.spinner(f"Searching {continent} news sources..."):
                data = fetch_filtered_news(query, continent, media_tier, api_key, max_records)

            if data.get("errors"):
                with st.expander("⚠️ API Errors (some countries may not be supported)"):
                    for error in data["errors"]:
                        st.warning(error)

            articles = data.get("articles", [])
            if not articles:
                st.warning("No articles found. Try:")
                st.info("""
                - Broadening your ecological focus (select "All Impacts")
                - Expanding to "Global (All)" region
                - Checking your NewsAPI key is valid
                - Note: NewsAPI free tier has limited country support
                """)
            else:
                st.success(f"✅ Found {len(articles)} unique articles from {continent}")
                water_terms = ["lake", "reservoir", "freshwater"]
                filtered_articles = [
                    a for a in articles
                    if validate_title_relevance(a.get("title", ""), water_terms)
                ]
                col_m1, col_m2 = st.columns(2)
                col_m1.metric("Total Articles", len(articles))
                col_m2.metric("With Lake/Reservoir in Title", len(filtered_articles))
                if not filtered_articles:
                    st.warning("No articles with lake/reservoir in title found. Showing all results...")
                    filtered_articles = articles
                st.markdown("---")
                for idx, article in enumerate(filtered_articles):
                    with st.container():
                        col_text, col_meta = st.columns([3, 1])
                        with col_text:
                            st.markdown(f"### {idx+1}. [{article['title']}]({article['url']})")
                            st.write(article.get('description', '*No description*'))
                        with col_meta:
                            st.caption(f"📢 **{article['source']['name']}**")
                            country_name = article.get('_newsapi_country_name', 'Unknown')
                            article_continent = article.get('_newsapi_continent', 'Unknown')
                            country_code = article.get('_newsapi_country_code', '')
                            if country_code and country_code != "global":
                                st.caption(f"🌍 {country_name} ({country_code})")
                                st.caption(f"📍 {article_continent}")
                            else:
                                st.caption(f"🌍 Global")
                            date_str = article.get('publishedAt', '')[:10] if article.get('publishedAt') else "Unknown"
                            st.caption(f"📅 {date_str}")
                        st.markdown("---")

                flat_data = [{
                    "Title": a.get("title"),
                    "URL": a.get("url"),
                    "Published": a.get("publishedAt", "")[:10],
                    "Source": a.get("source", {}).get("name"),
                    "Country": a.get("_newsapi_country_name", ""),
                    "CountryCode": a.get("_newsapi_country_code", ""),
                    "Continent": a.get("_newsapi_continent", ""),
                    "Description": a.get("description")
                } for a in filtered_articles]
                df_news = pd.DataFrame(flat_data)
                csv_news = df_news.to_csv(index=False).encode('utf-8')
                st.download_button(
                    "📥 Export News Data",
                    csv_news,
                    f"newsapi_{continent.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.csv",
                    "text/csv"
                )


# ═══════════════════════════════════════════════════════════════
# FOOTER
# ═══════════════════════════════════════════════════════════════
st.sidebar.markdown("---")
st.sidebar.caption("🌊 Lake Eco-Crisis Explorer v2.1")
st.sidebar.caption("Historical: GDELT GKG 2.0 | Real-Time: NewsAPI")
st.sidebar.caption("Continent detection via pycountry-convert + V2Locations")
