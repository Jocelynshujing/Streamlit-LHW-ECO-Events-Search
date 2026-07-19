import streamlit as st
import pandas as pd
from datetime import datetime
from pathlib import Path
import re
import os
import requests

# ═══════════════════════════════════════════════════════════════
# NEWSAPI COUNTRY CODE MAPPING (Built-in country parameter)
# ═══════════════════════════════════════════════════════════════

# NewsAPI supports ~50 countries via 2-letter ISO codes
# Map continent selection to available country codes
NEWSAPI_COUNTRY_CODES = {
    "Global (All)": None,  # No country filter - use /everything endpoint
    "North America": ["us", "ca", "mx"],  # US, Canada, Mexico
    "South America": ["ar", "br", "co", "ve"],  # Argentina, Brazil, Colombia, Venezuela
    "Europe": ["gb", "de", "fr", "it", "es", "nl", "be", "ch", "at", "se", "no", "dk", "fi", "pl", "cz", "hu", "ro", "bg", "gr", "pt", "ie"],
    "Asia": ["cn", "in", "jp", "kr", "id", "th", "vn", "ph", "my", "sg"],
    "Africa": ["za", "ng", "eg", "ke"],
    "Oceania": ["au", "nz"]
}

# Country code to full name for display
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

# Elite media sources (for media tier filter)
ELITE_SOURCES = "bbc-news,cnn,reuters,the-wall-street-journal,the-washington-post,associated-press,bloomberg,the-globe-and-mail,time,newsweek"
ELITE_DOMAINS = "bbc.co.uk,cnn.com,reuters.com,wsj.com,washingtonpost.com,apnews.com,bloomberg.com,theglobeandmail.com,time.com,newsweek.com"

# ═══════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════

# Path to your downloaded GDELT data folder
GDELT_DATA_DIR = "gdelt_lake_data/yearly"  # Relative path for Streamlit Cloud

# Page configurations
st.set_page_config(page_title="Lake Eco-Crisis Explorer", page_icon="🌊", layout="wide")

st.title("🌊 Lake Eco-Crisis Media Explorer")
st.markdown("""
This tool analyzes **locally-downloaded GDELT historical data** and **real-time NewsAPI** 
to track global lake degradation events linked to temperature and ecological stress.
""")

# ═══════════════════════════════════════════════════════════════
# SIDEBAR CONFIGURATION
# ═══════════════════════════════════════════════════════════════
st.sidebar.header("Configuration")

# NewsAPI key
api_key = st.sidebar.text_input("Enter NewsAPI Key (Optional)", type="password", 
                                 help="Get a free key from newsapi.org for real-time news")

st.sidebar.header("Filter Criteria")

# Eco impact filter (shared between GDELT and NewsAPI)
eco_impact = st.sidebar.selectbox(
    "Primary Ecological Focus",
    ["All Impacts", "Fish Kills / Mortalities", "Algal Blooms / Cyanobacteria", 
     "Ecosystem Degradation", "Water Supply / Scarcity", "Oxygen Depletion"]
)

# Media tier (NewsAPI only)
media_tier = st.sidebar.selectbox(
    "Media Outlets Tier (NewsAPI only)",
    ["All Media", "Elite Media Only", "Non-Elite Media Only"],
    help="Select source priority for the NewsAPI Real-Time view."
)

# Continent filter (shared)
continent = st.sidebar.selectbox(
    "Continent / Region",
    ["Global (All)", "North America", "South America", "Europe", "Asia", "Africa", "Oceania"]
)

# Year range (GDELT only)
st.sidebar.header("Timeline (GDELT)")
year_range = st.sidebar.slider(
    "Year Range", 
    2015, 2026, (2020, 2025), 
    key="gdelt_year_slider"
)

# ═══════════════════════════════════════════════════════════════
# FILTER MAPPING
# ═══════════════════════════════════════════════════════════════

# Map eco_impact to ThemeCategory for GDELT
theme_filter_map = {
    "All Impacts": None,
    "Fish Kills / Mortalities": "FISH_KILL",
    "Algal Blooms / Cyanobacteria": "ALGAL_BLOOM",
    "Ecosystem Degradation": "ECOSYSTEM_DEGRADATION",
    "Water Supply / Scarcity": "WATER_SCARCITY",
    "Oxygen Depletion": "OXYGEN_DEPLETION"
}
selected_theme = theme_filter_map[eco_impact]

# Get NewsAPI country codes for selected continent
selected_countries = NEWSAPI_COUNTRY_CODES.get(continent)

# Continent keywords for GDELT V2Locations filtering
continent_keywords_map = {
    "Global (All)": None,
    "North America": ["united states", "usa", "canada", "mexico", "north america"],
    "South America": ["brazil", "argentina", "colombia", "peru", "venezuela", "chile", "south america"],
    "Asia": ["china", "india", "japan", "vietnam", "thailand", "asia", "southeast asia", "south korea", "indonesia", "malaysia", "singapore"],
    "Europe": ["united kingdom", "uk", "france", "germany", "spain", "italy", "europe", "netherlands", "belgium", "switzerland", "austria", "sweden", "norway", "denmark", "finland", "poland", "czech republic", "hungary", "romania", "bulgaria", "greece", "portugal", "ireland"],
    "Africa": ["kenya", "south africa", "nigeria", "egypt", "uganda", "africa", "morocco", "algeria", "tunisia", "libya", "ethiopia", "ghana", "tanzania"],
    "Oceania": ["australia", "new zealand", "fiji", "oceania", "papua new guinea"]
}
selected_continent_keywords = continent_keywords_map.get(continent)

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

    # Find all yearly CSV files (supports multiple naming patterns)
    csv_files = []
    for pattern in ["*_lake_title_only_*.csv", "*gdelt_lake_*.csv", "*_lake_warm_eco_*.csv"]:
        csv_files.extend(sorted(data_path.glob(pattern)))

    # Remove duplicates
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
        # Extract year from filename using regex
        try:
            year_match = re.search(r'(\d{4})', csv_file.stem)
            if year_match:
                year = int(year_match.group(1))
                if start_year <= year <= end_year:
                    df = pd.read_csv(csv_file)
                    if not df.empty:
                        dfs.append(df)
                        print(f"Loaded {csv_file.name}: {len(df)} records")
        except Exception as e:
            st.warning(f"Error reading {csv_file.name}: {e}")

    if not dfs:
        st.warning(f"No data found for years {start_year}-{end_year}")
        return pd.DataFrame()

    return pd.concat(dfs, ignore_index=True)


@st.cache_data(show_spinner=False, ttl=3600)
def filter_gdelt_data(df, theme_category=None, continent_keywords=None):
    """Apply filters to GDELT data."""
    if df.empty:
        return df

    filtered = df.copy()

    # Filter 1: Theme Category (exact match)
    if theme_category and 'ThemeCategory' in filtered.columns:
        before = len(filtered)
        filtered = filtered[filtered['ThemeCategory'] == theme_category]
        st.caption(f"🎯 Theme filter `{theme_category}`: {before} → {len(filtered)} records")

    # Filter 2: Continent (regex match on V2Locations)
    if continent_keywords and 'V2Locations' in filtered.columns:
        before = len(filtered)
        # Build regex pattern from keywords (escape special chars)
        pattern = '|'.join([re.escape(kw) for kw in continent_keywords])
        mask = filtered['V2Locations'].str.lower().str.contains(pattern, na=False, regex=True)
        filtered = filtered[mask]
        st.caption(f"🌍 Continent filter `{continent}`: {before} → {len(filtered)} records")

    return filtered


# ═══════════════════════════════════════════════════════════════
# NEWSAPI FUNCTIONS (with Built-in Country Parameter)
# ═══════════════════════════════════════════════════════════════

def build_newsapi_query(eco_impact):
    """Build NewsAPI query string (ecological terms only, no geo terms)."""
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
    """Fetch news using /everything endpoint (global search, no country param)."""
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
    """
    Fetch news with continent filtering using NewsAPI built-in country parameter.

    Strategy:
    - If specific continent with country codes: Use /top-headlines with country param
    - If Global or no country codes: Use /everything with broader search
    """
    countries = NEWSAPI_COUNTRY_CODES.get(continent)

    all_articles = []
    errors = []

    if countries and continent != "Global (All)":
        # Strategy 1: Query each country using /top-headlines (accurate country filtering)
        st.info(f"🌍 Searching {len(countries)} countries in {continent}...")

        # Distribute limit across countries
        limit_per_country = max(5, limit // len(countries) + 2)

        for country_code in countries:
            data = fetch_newsapi_top_headlines(query, country_code, api_token, limit=limit_per_country)

            if "error" in data:
                errors.append(f"{COUNTRY_NAMES.get(country_code, country_code)} ({country_code}): {data['error']}")
            else:
                articles = data.get("articles", [])
                # Add country metadata
                for article in articles:
                    article["_newsapi_country_code"] = country_code
                    article["_newsapi_country_name"] = COUNTRY_NAMES.get(country_code, country_code)
                    article["_newsapi_continent"] = continent
                all_articles.extend(articles)
    else:
        # Strategy 2: Global search using /everything
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

    # Show active filters
    st.markdown(f"""
    **Active Filters:**
    - 🎯 **Ecological Focus:** `{eco_impact}` {'(All themes)' if selected_theme is None else f'→ `ThemeCategory = {selected_theme}`'}
    - 🌍 **Region:** `{continent}` {'(All regions)' if selected_continent_keywords is None else f'→ Keywords: {selected_continent_keywords[:3]}...'}
    - 📅 **Year Range:** `{year_range[0]} - {year_range[1]}`
    - 💾 **Data Source:** Pre-downloaded GDELT GKG 2.0 (title-filtered)
    """)

    # Load data
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
        # Apply filters
        with st.spinner("Applying filters..."):
            filtered_df = filter_gdelt_data(raw_df, selected_theme, selected_continent_keywords)

        # Metrics
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

            # Yearly aggregation
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

            # Theme distribution (only if "All Impacts" selected)
            if 'ThemeCategory' in filtered_df.columns and selected_theme is None:
                st.subheader("🎯 Theme Distribution")
                theme_counts = filtered_df['ThemeCategory'].value_counts()
                st.bar_chart(theme_counts, use_container_width=True, height=250)

            st.markdown("---")

            # --- ARTICLE LIST ---
            st.subheader("📰 Articles (Lake/Reservoir in Title + Temperature + Ecosystem)")

            # Pagination
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
                        # Title from ExtractedTitle
                        title = row.get('ExtractedTitle', '')
                        if not title or pd.isna(title):
                            title = "Untitled Article"

                        # Capitalize title nicely
                        title_display = title.title() if title else "Untitled"

                        url = row.get('DocumentIdentifier', '#')
                        st.markdown(f"### [{title_display}]({url})")

                        # Matched terms as tags
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
                        # Year/Month
                        year = row.get('Year', 'N/A')
                        month = row.get('Month', '')
                        st.caption(f"📅 **{year}-{month}**" if pd.notna(month) and str(month) != 'nan' else f"📅 **{year}**")

                        # Theme category badge
                        theme = row.get('ThemeCategory', 'OTHER')
                        theme_colors = {
                            'FISH_KILL': '🔴',
                            'ALGAL_BLOOM': '🟠', 
                            'WATER_SCARCITY': '🔵',
                            'ECOSYSTEM_DEGRADATION': '🟣',
                            'OXYGEN_DEPLETION': '⚫',
                            'POLLUTION': '🟤',
                            'OTHER': '⚪'
                        }
                        badge = theme_colors.get(theme, '⚪')
                        st.caption(f"{badge} **{theme}**")

                        # Source
                        source = row.get('SourceCommonName', '')
                        if source and pd.notna(source):
                            st.caption(f"📢 {source}")

                        # Location preview
                        locations = row.get('V2Locations', '')
                        if locations and pd.notna(locations):
                            # Extract first location name from V2Locations format
                            loc_match = re.search(r'\d+#([^#]+)', str(locations))
                            if loc_match:
                                st.caption(f"📍 {loc_match.group(1)[:40]}...")

                    st.markdown("---")

            # --- EXPORT ---
            st.subheader("📥 Export Data")

            col_exp1, col_exp2 = st.columns(2)

            with col_exp1:
                # Export filtered data
                csv_filtered = filtered_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Export Filtered Data (CSV)",
                    data=csv_filtered,
                    file_name=f"gdelt_filtered_{eco_impact.replace(' ', '_').replace('/', '_')}_{continent.replace(' ', '_')}_{year_range[0]}_{year_range[1]}.csv",
                    mime="text/csv"
                )

            with col_exp2:
                # Export raw data
                csv_raw = raw_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Export All Raw Data (CSV)",
                    data=csv_raw,
                    file_name=f"gdelt_raw_{year_range[0]}_{year_range[1]}.csv",
                    mime="text/csv"
                )

            # --- RAW DATA TABLE ---
            with st.expander("🔍 View Raw Data Table"):
                st.dataframe(filtered_df, use_container_width=True)


# ═══════════════════════════════════════════════════════════════
# TAB 2: REAL-TIME NEWSAPI (with Built-in Country Parameter)
# ═══════════════════════════════════════════════════════════════
with tab2:
    st.header("⏰ Real-Time News Tracker (NewsAPI)")

    # Show which countries will be searched
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

    # Build query (ecological terms only, no geo terms)
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

            # Show errors if any
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

                # Filter by title relevance (lake/reservoir check)
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

                            # Show country/region info from NewsAPI
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

                # Export
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
st.sidebar.caption("🌊 Lake Eco-Crisis Explorer v2.0")
st.sidebar.caption("Historical: GDELT GKG 2.0 | Real-Time: NewsAPI")
