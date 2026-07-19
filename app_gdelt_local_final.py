import streamlit as st
import pandas as pd
from datetime import datetime
from pathlib import Path
import re
import os
import streamlit as st

#st.write("Current directory:", os.getcwd())
#st.write("Files in repo:", os.listdir("."))
#st.write("Files in gdelt_lake_data:", os.listdir("gdelt_lake_data") if os.path.exists("gdelt_lake_data") else "Folder not found!")
# ═══════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════

# Path to your downloaded GDELT data folder
# Update this to point to your actual data directory
GDELT_DATA_DIR = "gdelt_lake_data/yearly"  # ← UPDATE THIS PATH

# Page configurations
st.set_page_config(page_title="Lake Eco-Crisis Explorer", page_icon="🌊", layout="wide")

st.title("🌊 Lake Eco-Crisis Media Explorer")
st.markdown("""
This tool analyzes **locally-downloaded GDELT historical data** to track global lake degradation events 
linked to temperature and ecological stress. Data is pre-filtered: only articles whose **title contains 
"lake" or "reservoir"** AND mention **temperature/heat terms** AND **ecosystem events** are included.
""")

# ═══════════════════════════════════════════════════════════════
# SIDEBAR CONFIGURATION — Same filters as app.py
# ═══════════════════════════════════════════════════════════════
st.sidebar.header("Configuration")

# Optional: NewsAPI key for real-time tab
api_key = st.sidebar.text_input("Enter NewsAPI Key (Optional)", type="password", 
                                 help="Get a free key from newsapi.org for real-time news")

st.sidebar.header("Filter Criteria")

# Same eco impact filter as app.py
eco_impact = st.sidebar.selectbox(
    "Primary Ecological Focus",
    ["All Impacts", "Fish Kills / Mortalities", "Algal Blooms / Cyanobacteria", 
     "Ecosystem Degradation", "Water Supply / Scarcity", "Oxygen Depletion"]
)

# Media tier (for NewsAPI tab)
media_tier = st.sidebar.selectbox(
    "Media Outlets Tier (NewsAPI only)",
    ["All Media", "Elite Media Only", "Non-Elite Media Only"],
    help="Select source priority for the NewsAPI Real-Time view."
)

# Continent filter (applied to V2Locations)
continent = st.sidebar.selectbox(
    "Continent / Region",
    ["Global (All)", "North America", "Asia", "Europe", "Africa", 
     "South America", "Oceania"]
)

# Year range filter
st.sidebar.header("Timeline")
year_range = st.sidebar.slider(
    "Year Range", 
    2015, 2026, (2020, 2025), 
    key="gdelt_year_slider"
)

# ═══════════════════════════════════════════════════════════════
# FILTER MAPPING (Same logic as app.py)
# ═══════════════════════════════════════════════════════════════

# Map eco_impact to ThemeCategory
theme_filter_map = {
    "All Impacts": None,
    "Fish Kills / Mortalities": "FISH_KILL",
    "Algal Blooms / Cyanobacteria": "ALGAL_BLOOM",
    "Ecosystem Degradation": "ECOSYSTEM_DEGRADATION",
    "Water Supply / Scarcity": "WATER_SCARCITY",
    "Oxygen Depletion": "OXYGEN_DEPLETION"
}
selected_theme = theme_filter_map[eco_impact]

# Continent to location keywords
continent_keywords_map = {
    "Global (All)": None,
    "North America": ["united states", "usa", "canada", "mexico", "north america"],
    "Asia": ["china", "india", "japan", "vietnam", "thailand", "asia", "southeast asia"],
    "Europe": ["united kingdom", "uk", "france", "germany", "spain", "italy", "europe"],
    "Africa": ["kenya", "south africa", "nigeria", "egypt", "uganda", "africa"],
    "South America": ["brazil", "argentina", "colombia", "peru", "south america"],
    "Oceania": ["australia", "new zealand", "fiji", "oceania"]
}
selected_continent_keywords = continent_keywords_map.get(continent)

# ═══════════════════════════════════════════════════════════════
# DATA LOADING FUNCTIONS
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

    combined = pd.concat(dfs, ignore_index=True)
    return combined


@st.cache_data(show_spinner=False, ttl=3600)
def filter_gdelt_data(df, theme_category=None, continent_keywords=None):
    """
    Apply filters to GDELT data.

    Parameters:
        df: DataFrame with GDELT data
        theme_category: str or None — filter by ThemeCategory column
        continent_keywords: list or None — filter V2Locations by continent keywords
    """
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
# TAB 2: REAL-TIME NEWSAPI (Same as original app.py)
# ═══════════════════════════════════════════════════════════════
with tab2:
    st.header("⏰ Real-Time News Tracker (NewsAPI)")
    st.markdown("""
    Search live news articles using NewsAPI. This requires a valid API key.
    Filters are applied the same way as the historical GDELT tab.
    """)

    # Build query (same logic as app.py)
    base_water_terms = '("lake" OR "reservoir" OR "freshwater")'
    base_heat_terms = '("heatwave" OR "heat" OR "record temperature" OR "hot" OR "rising temperature" OR "thermal stress")'

    if eco_impact == "Fish Kills / Mortalities":
        impact_terms = '("fish_kill" OR "fish_mortality" OR "fish_die_off" OR "mass_mortality" OR "dead_fish" OR "fish_death")'
    elif eco_impact == "Algal Blooms / Cyanobacteria":
        impact_terms = '("algal_bloom" OR "cyanobacteria" OR "blue_green_algae" OR "harmful_algal" OR "microcystis" OR "eutrophication" OR "bloom" OR "toxic_algae")'
    elif eco_impact == "Ecosystem Degradation":
        impact_terms = '("ecosystem_collapse" OR "ecological_degradation" OR "habitat_loss" OR "biodiversity_loss" OR "wetland_loss" OR "environmental_degradation")'
    elif eco_impact == "Water Supply / Scarcity":
        impact_terms = '("water_scarcity" OR "water_shortage" OR "drought" OR "water_restriction" OR "low_water_level" OR "desiccation")'
    elif eco_impact == "Oxygen Depletion":
        impact_terms = '("hypoxia" OR "anoxia" OR "oxygen_depletion" OR "dead_zone")'
    else:
        impact_terms = '("fish kill" OR "mass mortality" OR "algal bloom" OR "cyanobacteria" OR "harmful algal bloom" OR "habitat loss" OR "biodiversity loss" OR "water scarcity" OR "water shortage" OR "hypoxia", "oxygen depletion")'

    # Geo terms
    if continent == "North America":
        geo_terms = '("North America" OR "United States" OR USA OR Canada OR Mexico)'
    elif continent == "Asia":
        geo_terms = '(Asia OR China OR India OR Japan OR "Southeast Asia" OR Vietnam OR Thailand)'
    elif continent == "Europe":
        geo_terms = '(Europe OR UK OR "United Kingdom" OR France OR Germany OR Spain OR Italy)'
    elif continent == "Africa":
        geo_terms = '(Africa OR Kenya OR "South Africa" OR Nigeria OR Egypt OR Uganda)'
    elif continent == "South America":
        geo_terms = '("South America" OR Brazil OR Argentina OR Colombia OR Peru)'
    elif continent == "Oceania":
        geo_terms = '(Oceania OR Australia OR "New Zealand" OR Fiji)'
    else:
        geo_terms = None

    # Build final query
    if geo_terms:
        final_query = f"{base_water_terms} AND {base_heat_terms} AND {impact_terms} AND {geo_terms}"
    else:
        final_query = f"{base_water_terms} AND {base_heat_terms} AND {impact_terms}"

    st.code(final_query, language="text")

    # NewsAPI search button
    max_records = st.slider("Maximum Articles", 10, 100, 20, key="newsapi_limit")

    if st.button("Search Live News", type="primary", key="newsapi_btn"):
        if not api_key:
            st.error("Please enter a NewsAPI key in the sidebar.")
        else:
            import requests

            try:
                with st.spinner("Fetching live news..."):
                    url = "https://newsapi.org/v2/everything"
                    params = {
                        "q": final_query,
                        "pageSize": max_records,
                        "sortBy": "relevancy",
                        "language": "en",
                        "apiKey": api_key
                    }

                    # Media tier filter
                    elite_sources = "bbc-news,cnn,reuters,the-wall-street-journal,the-washington-post,associated-press,bloomberg,the-globe-and-mail,time,newsweek"
                    elite_domains = "bbc.co.uk,cnn.com,reuters.com,wsj.com,washingtonpost.com,apnews.com,bloomberg.com,theglobeandmail.com,time.com,newsweek.com"

                    if media_tier == "Elite Media Only":
                        params["sources"] = elite_sources
                    elif media_tier == "Non-Elite Media Only":
                        params["excludeDomains"] = elite_domains

                    response = requests.get(url, params=params, timeout=12)
                    data = response.json()

                if data.get("status") == "error":
                    st.error(f"API Error: {data.get('message')}")
                elif not data.get("articles"):
                    st.warning("No articles found matching these criteria.")
                else:
                    articles = data["articles"]

                    # Title validation (same as app.py)
                    water_terms_list = ["lake", "reservoir", "freshwater"]
                    filtered_articles = [
                        a for a in articles 
                        if a.get("title") and any(t in a["title"].lower() for t in water_terms_list)
                    ]

                    st.metric("Articles with 'lake/reservoir/freshwater' in title", len(filtered_articles))

                    for idx, article in enumerate(filtered_articles):
                        st.markdown(f"### {idx+1}. [{article['title']}]({article['url']})")
                        col1, col2 = st.columns(2)
                        col1.caption(f"📢 **Source:** {article['source']['name']}")
                        col2.caption(f"📅 **Published:** {article['publishedAt'][:10] if article.get('publishedAt') else 'Unknown'}")
                        st.write(article.get('description', '*No description*'))
                        st.markdown("---")

                    # Export
                    flat_data = [{
                        "Title": a.get("title"),
                        "URL": a.get("url"),
                        "Published": a.get("publishedAt", "")[:10],
                        "Source": a.get("source", {}).get("name"),
                        "Description": a.get("description")
                    } for a in filtered_articles]

                    df_news = pd.DataFrame(flat_data)
                    csv_news = df_news.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        "📥 Export News Data",
                        csv_news,
                        f"newsapi_{datetime.now().strftime('%Y%m%d')}.csv",
                        "text/csv"
                    )

            except Exception as e:
                st.error(f"Error fetching news: {e}")


# ═══════════════════════════════════════════════════════════════
# FOOTER
# ═══════════════════════════════════════════════════════════════
st.sidebar.markdown("---")
st.sidebar.caption("🌊 Lake Eco-Crisis Explorer v2.0")
st.sidebar.caption("Historical: GDELT GKG 2.0 | Real-Time: NewsAPI")
