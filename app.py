import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta

# Page configurations
st.set_page_config(page_title="Lake Eco-Crisis Explorer", page_icon="🌊", layout="wide")

st.title("🌊 Lake Eco-Crisis Media Explorer")
st.markdown("This tool uses live Boolean logic to query thousands of popular global media outlets for lake degradation events caused by extreme local temperatures.")

# Setup API Key (Input via Sidebar for security)
st.sidebar.header("Configuration")
api_key = st.sidebar.text_input("Enter NewsAPI Key", type="password", help="Get a free key from newsapi.org")

# Sidebar Filters
st.sidebar.header("Filter Criteria")
eco_impact = st.sidebar.selectbox(
    "Primary Ecological Focus",
    ["All Impacts", "Fish Kills / Mortalities", "Algal Blooms / Cyanobacteria", "Ecosystem Degradation", "Water Supply & Scarcity"]
)

# --- NEW: Media Tier Filter ---
media_tier = st.sidebar.selectbox(
    "Media Outlets Tier",
    ["All Media", "Elite Media Only", "Non-Elite Media Only"],
    help="Select whether to search elite tier-1 networks, exclude them entirely, or view all media records."
)

# --- NEW: Continent Filter ---
continent = st.sidebar.selectbox(
    "Continent / Region",
    ["Global (All)", "North America", "Asia", "Europe", "Africa", "South America", "Oceania"]
)

# --- NEW: Title Keyword Sensitivity ---
min_keywords = st.sidebar.slider(
    "Minimum Keywords Required in Title", 
    min_value=0, max_value=3, value=1,
    help="Filter results to only show articles where at least this many of your query keywords appear in the title."
)

# Sidebar Result Limit
max_records = st.sidebar.slider("Maximum Articles to Retrieve", min_value=10, max_value=100, value=20, step=10)

# Build the Boolean Query dynamically based on user selections
base_water_terms = '("lake" OR "reservoir" OR "freshwater")'
base_heat_terms = '("heatwave" OR "heat" OR "record temperature" OR "hot" OR "rising temperature" OR "thermal stress")'

if eco_impact == "Fish Kills / Mortalities":
    impact_terms = '("fish kill" OR "mass mortality" OR "fish die-off" OR "mass casualty event")'
elif eco_impact == "Algal Blooms / Cyanobacteria":
    impact_terms = '("algal bloom" OR "cyanobacteria" OR "blue-green algae" OR "harmful algal bloom" OR "microcystis")'
elif eco_impact == "Ecosystem Degradation":
    impact_terms = '("ecosystem collapse" OR "ecological degradation" OR "habitat loss" OR "biodiversity loss")'
elif eco_impact == "Water Supply & Scarcity":
    impact_terms = '("water scarcity" OR "water shortage" OR "reduced water supply" OR "drought stress" OR "potable water risk")'
else:
    # "All Impacts" combines them using OR logic
    impact_terms = '("fish kill" OR "mass mortality" OR "fish die-off" OR "mass casualty event" OR "algal bloom" OR "cyanobacteria" OR "blue-green algae" OR "harmful algal bloom" OR "microcystis" OR "ecosystem collapse" OR "ecological degradation" OR "habitat loss" OR "biodiversity loss" OR "water scarcity" OR "water shortage" OR "reduced water supply" OR "drought stress" OR "potable water risk")'

# --- NEW: Map Continents to Boolean Geo-Terms ---
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

# Final combined query string (Injecting geo_terms if selected)
if geo_terms:
    final_query = f"{base_water_terms} AND {base_heat_terms} AND {impact_terms} AND {geo_terms}"
else:
    final_query = f"{base_water_terms} AND {base_heat_terms} AND {impact_terms}"

# --- Hardcoded Media Tiers Configurations ---
# Target Elite Source IDs for tracking
elite_sources = "bbc-news,cnn,reuters,the-wall-street-journal,the-washington-post,associated-press,bloomberg,the-globe-and-mail,time,newsweek"
# Matching Domains used to safely exclude them when Non-Elite mode is triggered
elite_domains_to_exclude = "bbc.co.uk,cnn.com,reuters.com,wsj.com,washingtonpost.com,apnews.com,bloomberg.com,theglobeandmail.com,time.com,newsweek.com"

# Show active search filters in layout
with st.expander("Show Active Search & Media Filter Logic"):
    st.markdown(f"**Selected Media Mode:** `{media_tier}`")
    st.code(final_query, language="text")
    
# --- Performance Optimization: Cached Ingestion Function ---
@st.cache_data(show_spinner=False, ttl=1800)
def fetch_filtered_news(query, tier_choice, api_token, limit):
    url = "https://newsapi.org/v2/everything"
    params = {
        "q": query,
        "pageSize": limit,
        "sortBy": "publishedAt",
        "language": "en",
        "apiKey": api_token
    }
    
    # Inject routing logic based on user's Media Tier selection
    if tier_choice == "Elite Media Only":
        params["sources"] = elite_sources
    elif tier_choice == "Non-Elite Media Only":
        params["excludeDomains"] = elite_domains_to_exclude
        
    response = requests.get(url, params=params, timeout=12)
    response.raise_for_status()
    return response.json()

# --- Helper Function to check keyword presence in title ---
def count_keywords_in_title(title, query_terms):
    if not title: return 0
    title_lower = title.lower()
    # Extract words from your query terms, removing special characters/logic
    import re
    search_words = [word.lower() for word in re.findall(r'\b\w+\b', query_terms) 
                    if word.lower() not in ['and', 'or', 'not', 'the', 'in', 'of']]
    # Count how many unique keywords are present in the title
    count = sum(1 for word in set(search_words) if word in title_lower)
    return count
    
# Fetch button
if st.sidebar.button("Search Media Database", type="primary"):
    if not api_key:
        st.error("Please enter a valid NewsAPI key in the sidebar to run the search.")
    else:
        try:
            with st.spinner("Harvesting data from targeted publication matrix..."):
                data = fetch_filtered_news(final_query, media_tier, api_key, max_records)
                
            if data.get("status") == "error":
                st.error(f"API Error: {data.get('message')}")
            elif data.get("totalResults") == 0 or not data.get("articles"):
                st.warning("No articles found matching this exact combination of environmental keywords within selected media tier.")
            else:
                articles = data.get("articles", [])

                # --- APPLY TITLE FILTER ---
                if min_keywords > 0:
                    filtered_articles = [
                        a for a in articles 
                        if count_keywords_in_title(a.get("title", ""), final_query) >= min_keywords
                    ]
                else:
                    filtered_articles = articles
                
                # Update metrics and loop to use 'filtered_articles' instead of 'articles'
                st.metric("Articles Matching Title Sensitivity", len(filtered_articles))
                
                # Layout Metrics Grid
                m_col1, m_col2 = st.columns(2)
                m_col1.metric("Articles Harvested", len(filtered_articles))
                m_col2.metric("Current Stream Target", media_tier)
                st.markdown("---")
                
                if len(filtered_articles) == 0:
                    st.warning("No articles matched the required number of keywords in the title.")
                else:
                    for idx, article in enumerate(filtered_articles):
                        has_img = article.get("urlToImage")
                        
                        if has_img:
                            text_col, img_col = st.columns([3, 1])
                        else:
                            text_col = st.container()
                            img_col = None
                            
                        with text_col:
                            st.markdown(f"### {idx+1}. [{article['title']}]({article['url']})")
                            
                            col1, col2 = st.columns(2)
                            with col1:
                                st.caption(f"📰 **Source:** {article['source']['name']}")
                            with col2:
                                date_str = article['publishedAt'][:10] if article.get('publishedAt') else "Unknown"
                                st.caption(f"📅 **Published:** {date_str}")
                            
                            st.write(article['description'] if article['description'] else "*No description snippet available.*")
                        
                        if img_col and has_img:
                            with img_col:
                                try:
                                    st.image(article["urlToImage"], use_container_width=True)
                                except Exception:
                                    pass
                                    
                        st.markdown("---")
                        
                    # Setup structured list for pandas file export
                    flat_data = []
                    for a in articles:
                        flat_data.append({
                            "Title": a.get("title"),
                            "URL": a.get("url"),
                            "Published Date": a.get("publishedAt")[:10] if a.get("publishedAt") else None,
                            "Source Channel": a.get("source", {}).get("name"),
                            "Description Summary": a.get("description")
                        })
                    
                    df = pd.DataFrame(flat_data)
                    csv_data = df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📥 Export Filtered Media Data as CSV",
                        data=csv_data,
                        file_name=f"filtered_eco_reports_{datetime.now().strftime('%Y%m%d')}.csv",
                        mime="text/csv"
                    )
                        
        except requests.exceptions.HTTPError as err:
            st.error(f"API Connection Failure: {err}")
        except Exception as e:
            st.error(f"An unexpected tracking error occurred: {e}")
