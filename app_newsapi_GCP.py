import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import re
from google.cloud import bigquery
from google.oauth2 import service_account

# Page configurations
st.set_page_config(page_title="Lake Eco-Crisis Explorer", page_icon="🌊", layout="wide")

st.title("🌊 Lake Eco-Crisis Media Explorer")
st.markdown("This tool combines real-time NewsAPI scanning with a 30-year GDELT BigQuery historical trend index to track global lake degradation events.")

# --- INITIALIZE BIGQUERY CLIENT ---
@st.cache_resource
def get_bq_client():
    try:
        credentials = service_account.Credentials.from_service_account_info(
            st.secrets["gcp_service_account"]
        )
        return bigquery.Client(credentials=credentials, project=credentials.project_id)
    except Exception as e:
        st.sidebar.error(f"GCP Authentication Failed: Make sure .streamlit/secrets.toml is set up.")
        return None

bq_client = get_bq_client()

# --- SIDEBAR CONFIGURATION ---
st.sidebar.header("Configuration")
api_key = st.sidebar.text_input("Enter NewsAPI Key", type="password", help="Get a free key from newsapi.org")

st.sidebar.header("Universal Filter Criteria")
eco_impact = st.sidebar.selectbox(
    "Primary Ecological Focus",
    ["All Impacts", "Fish Kills / Mortalities", "Algal Blooms / Cyanobacteria", "Ecosystem Degradation", "Water Supply / Scarcity"]
)

media_tier = st.sidebar.selectbox(
    "NewsAPI Media Outlets Tier",
    ["All Media", "Elite Media Only", "Non-Elite Media Only"],
    help="Select source priority configuration for the NewsAPI Real-Time view."
)

continent = st.sidebar.selectbox(
    "Continent / Region",
    ["Global (All)", "North America", "Asia", "Europe", "Africa", "South America", "Oceania"]
)

# --- QUERY BUILDERS & VALIDATION LISTS ---
base_water_terms = '("lake" OR "reservoir" OR "freshwater")'
base_heat_terms = '("heatwave" OR "heat" OR "record temperature" OR "hot" OR "rising temperature" OR "thermal stress")'

# Extracting raw strings for local keyword validation filters
water_terms_list = ["lake", "reservoir", "freshwater"]

# Determine specific impact strings for logic matching
if eco_impact == "Fish Kills / Mortalities":
    impact_terms = '("fish kill" OR "mass mortality" OR "fish die-off" OR "mass casualty event")'
    gdelt_keyword = "FISH_KILL" # Simplified theme fallback for GDELT
elif eco_impact == "Algal Blooms / Cyanobacteria":
    impact_terms = '("algal bloom" OR "cyanobacteria" OR "blue-green algae" OR "harmful algal bloom" OR "microcystis")'
    gdelt_keyword = "ALGAL_BLOOM"
elif eco_impact == "Ecosystem Degradation":
    impact_terms = '("ecosystem collapse" OR "ecological degradation" OR "habitat loss" OR "biodiversity loss")'
    gdelt_keyword = "ENV_CLIMATECHANGE"
elif eco_impact == "Water Supply / Scarcity":
    impact_terms = '("water scarcity" OR "water shortage" OR "reduced water supply" OR "drought stress" OR "potable water risk" OR "water restriction")'
    gdelt_keyword = "ENV_WATER_SCARCITY"
else:
    impact_terms = '("fish kill" OR "mass mortality" OR "algal bloom" OR "cyanobacteria" OR "harmful algal bloom" OR "habitat loss" OR "biodiversity loss" OR "water scarcity" OR "water shortage")'
    gdelt_keyword = "ENV_WATER_SCARCITY"

# Map Continents to Boolean Geo-Terms
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

# Build final Boolean string for NewsAPI
if geo_terms:
    final_query = f"{base_water_terms} AND {base_heat_terms} AND {impact_terms} AND {geo_terms}"
else:
    final_query = f"{base_water_terms} AND {base_heat_terms} AND {impact_terms}"

# --- DATA RETRIEVAL LOGIC ---

# 1. NewsAPI Live Ingestion
@st.cache_data(show_spinner=False, ttl=1800)
def fetch_filtered_news(query, tier_choice, api_token, limit):
    url = "https://newsapi.org/v2/everything"
    elite_sources = "bbc-news,cnn,reuters,the-wall-street-journal,the-washington-post,associated-press,bloomberg,the-globe-and-mail,time,newsweek"
    elite_domains_to_exclude = "bbc.co.uk,cnn.com,reuters.com,wsj.com,washingtonpost.com,apnews.com,bloomberg.com,theglobeandmail.com,time.com,newsweek.com"
    
    params = {
        "q": query,
        "pageSize": limit,
        "sortBy": "relevancy",
        "language": "en",
        "apiKey": api_token
    }
    if tier_choice == "Elite Media Only":
        params["sources"] = elite_sources
    elif tier_choice == "Non-Elite Media Only":
        params["excludeDomains"] = elite_domains_to_exclude
        
    response = requests.get(url, params=params, timeout=12)
    response.raise_for_status()
    return response.json()

# 2. GDELT BigQuery 30-Year Ingestion
@st.cache_data(show_spinner=False, ttl=86400)
def fetch_gdelt_historical(theme_keyword, start_yr, end_yr):
    if bq_client is None:
        return pd.DataFrame()
        
    start_date_int = int(f"{start_yr}0101000000")
    end_date_int = int(f"{end_yr}1231235959")
    
    # Efficiently querying indexed partition boundaries for the 30-year sweep
    query = f"""
        SELECT 
            SUBSTR(CAST(DATE AS STRING), 1, 4) AS Year, 
            COUNT(*) as MentionCount
        FROM `gdelt-bq.gdeltv2.gkg` 
        WHERE DATE >= {start_date_int} AND DATE <= {end_date_int}
          AND (V2Themes LIKE '%ENV_WATER_SCARCITY%' OR V2Themes LIKE '%ENV_CLIMATECHANGE%')
          AND (LOWER(V2Themes) LIKE '%lake%' OR LOWER(V2Themes) LIKE '%reservoir%')
        GROUP BY Year
        ORDER BY Year ASC
    """
    query_job = bq_client.query(query)
    results = query_job.result()
    return results.to_dataframe()

def validate_title_relevance(title, water_terms):
    if not title: return False
    title_lower = title.lower()
    return any(term.lower() in title_lower for term in water_terms)

# --- INTERFACE TABS CONTROLLER ---
tab1, tab2 = st.tabs(["⏰ Real-Time Media Tracker (NewsAPI)", "📈 30-Year Historical Trends (GDELT BigQuery)"])

with tab1:
    st.header("Breaking & Recent Crisis Context")
    max_records = st.slider("Maximum Articles to Retrieve", min_value=10, max_value=100, value=20, step=10, key="newsapi_limit")
    
    with st.expander("Show Active Search & Media Filter Logic"):
        st.markdown(f"**Selected Media Mode:** `{media_tier}`")
        st.code(final_query, language="text")

    if st.button("Search Live Media Database", type="primary", key="live_btn"):
        if not api_key:
            st.error("Please enter a valid NewsAPI key in the sidebar configuration.")
        else:
            try:
                with st.spinner("Harvesting data from targeted publication matrix..."):
                    data = fetch_filtered_news(final_query, media_tier, api_key, max_records)
                    
                if data.get("status") == "error":
                    st.error(f"API Error: {data.get('message')}")
                elif data.get("totalResults") == 0 or not data.get("articles"):
                    st.warning("No articles found matching this exact sequence within the selected criteria.")
                else:
                    articles = data.get("articles", [])
                    filtered_articles = [a for a in articles if validate_title_relevance(a.get("title", ""), water_terms_list)]
                                
                    st.metric("Articles Matching Title Sensitivity", len(filtered_articles))
                    
                    m_col1, m_col2 = st.columns(2)
                    m_col1.metric("Articles Harvested", len(filtered_articles))
                    m_col2.metric("Current Stream Target", media_tier)
                    st.markdown("---")
                    
                    if len(filtered_articles) == 0:
                        st.warning("No articles matched the title keyword constraints.")
                    else:
                        for idx, article in enumerate(filtered_articles):
                            has_img = article.get("urlToImage")
                            text_col, img_col = st.columns([3, 1]) if has_img else (st.container(), None)
                                
                            with text_col:
                                st.markdown(f"### {idx+1}. [{article['title']}]({article['url']})")
                                col1, col2 = st.columns(2)
                                col1.caption(f"📢 **Source:** {article['source']['name']}")
                                date_str = article['publishedAt'][:10] if article.get('publishedAt') else "Unknown"
                                col2.caption(f"📅 **Published:** {date_str}")
                                st.write(article['description'] if article['description'] else "*No description snippet available.*")
                            
                            if img_col and has_img:
                                with img_col:
                                    try: st.image(article["urlToImage"], use_container_width=True)
                                    except: pass
                                        
                            st.markdown("---")
                            
                        # CSV Export Setup
                        flat_data = [{"Title": a.get("title"), "URL": a.get("url"), "Published Date": a.get("publishedAt")[:10], "Source Channel": a.get("source", {}).get("name"), "Description Summary": a.get("description")} for a in filtered_articles]
                        df = pd.DataFrame(flat_data)
                        csv_data = df.to_csv(index=False).encode('utf-8')
                        st.download_button(
                            label="📥 Export Filtered Media Data as CSV",
                            data=csv_data,
                            file_name=f"live_eco_reports_{datetime.now().strftime('%Y%m%d')}.csv",
                            mime="text/csv"
                        )
            except requests.exceptions.HTTPError as err:
                st.error(f"API Connection Failure: {err}")
            except Exception as e:
                st.error(f"An unexpected tracking error occurred: {e}")

with tab2:
    st.header("Longitudinal Macro-Analysis (1996 - Present)")
    st.markdown("Queries the planet-scale GDELT Knowledge Graph database hosted on Google BigQuery to track long-term global media trends.")
    
    if bq_client is None:
        st.warning("To unlock historical tracking features, please populate your GCP Service Account keys inside `.streamlit/secrets.toml`.")
    else:
        year_range = st.slider("Timeline Window Lookup", 1996, 2026, (1996, 2026), key="gdelt_slider")
        
        if st.button("Generate 30-Year Trend Analysis", type="primary", key="hist_btn"):
            with st.spinner("Scanning decades of global media metadata partitions via BigQuery..."):
                try:
                    hist_df = fetch_gdelt_historical(gdelt_keyword, year_range[0], year_range[1])
                    
                    if not hist_df.empty:
                        st.subheader(f"Historical Media Coverage Frequency Map ({year_range[0]} - {year_range[1]})")
                        
                        # Data prep for charting
                        hist_df['Year'] = hist_df['Year'].astype(str)
                        chart_data = hist_df.set_index('Year')
                        
                        # Present structured Line Plot
                        st.line_chart(chart_data)
                        
                        with st.expander("Inspect Raw Aggregated Chronological Metrics"):
                            st.dataframe(hist_df)
                            
                        csv_hist = hist_df.to_csv(index=False).encode('utf-8')
                        st.download_button(
                            label="📥 Export Historical Metrics Trend CSV",
                            data=csv_hist,
                            file_name=f"gdelt_historical_trends_{year_range[0]}_{year_range[1]}.csv",
                            mime="text/csv"
                        )
                    else:
                        st.warning("No records matched within GDELT's global partitions under the selected keyword rules.")
                except Exception as bq_err:
                    st.error(f"BigQuery Parsing Failure: {bq_err}")
