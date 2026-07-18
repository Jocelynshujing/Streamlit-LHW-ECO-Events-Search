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
    ["All Impacts", "Fish Kills / Mortalities", "Algal Blooms / Cyanobacteria",]
)

# --- NEW: Continent Filter ---
continent = st.sidebar.selectbox(
    "Continent / Region",
    ["Global (All)", "North America", "Asia", "Europe", "Africa", "South America", "Oceania"]
)

# Sidebar Result Limit
max_records = st.sidebar.slider("Maximum Articles to Retrieve", min_value=10, max_value=100, value=20, step=10)

# Build the Boolean Query dynamically based on user selections
base_water_terms = '("lake" OR "reservoir" OR "freshwater")'
base_heat_terms = '("heatwave" OR "heat" OR "record temperature" OR "hot")'

if eco_impact == "Fish Kills / Mortalities":
    impact_terms = '("fish")'
elif eco_impact == "Algal Blooms / Cyanobacteria":
    impact_terms = '("algae" OR "cyanobacteria" OR "toxic")'
else:
    # "All Impacts" combines them using OR logic
    impact_terms = '("fish" OR "algae" OR "cyanobacteria" OR "toxic")'

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

# --- NEW: Hardcoded Elite Global Outlets (NewsAPI Unique Source IDs) ---
# This ensures data is harvested exclusively from top-tier international publications
#elite_sources = "bbc-news,cnn,reuters,the-wall-street-journal,the-washington-post,associated-press,bloomberg,the-globe-and-mail,time,newsweek"

# Show the query to the user so they see the tool's inner logic
with st.expander("Show Active Search & Media Filters"):
    #st.markdown(f"**Target Elite Outlets:** `{elite_sources}`")
    st.code(final_query, language="text")

# --- Performance Optimization: Cached Ingestion Function ---
@st.cache_data(show_spinner=False, ttl=1800)  # Keeps data cached for 30 minutes to reduce layout API overhead
def fetch_elite_news(query, sources_str, api_token, limit):
    # Using 'everything' endpoint to safely support your deep Boolean structures
    url = "https://newsapi.org/v2/everything"
    params = {
        "q": query,
        "sources": sources_str,    # Dynamically forces only our pre-filtered elite sources
        "pageSize": limit,
        "sortBy": "publishedAt",   # Brings back breaking live news priority
        "apiKey": api_token
    }
    response = requests.get(url, params=params, timeout=12)
    response.raise_for_status()
    return response.json()

# Fetch button
if st.sidebar.button("Search Media Database", type="primary"):
    if not api_key:
        st.error("Please enter a valid NewsAPI key in the sidebar to run the search.")
    else:
        try:
            with st.spinner("Filtering tier-1 publication matrix..."):
                data = fetch_elite_news(final_query, elite_sources, api_key, max_records)
                
            if data.get("status") == "error":
                st.error(f"API Error: {data.get('message')}")
            elif data.get("totalResults") == 0 or not data.get("articles"):
                st.warning("No elite articles found matching this exact combination of environmental keywords.")
            else:
                articles = data.get("articles", [])
                
                # Layout Metrics Grid
                m_col1, m_col2 = st.columns(2)
                m_col1.metric("Elite Media Hits", len(articles))
                m_col2.metric("Target Network Pool", "10 Global Outlets")
                
                st.markdown("---")
                
                # Display results in clean UI elements
                for idx, article in enumerate(articles):
                    has_img = article.get("urlToImage")
                    
                    # Split view layout if post has thumbnail media
                    if has_img:
                        text_col, img_col = st.columns([3, 1])
                    else:
                        text_col = st.container()
                        img_col = None
                        
                    with text_col:
                        st.markdown(f"### {idx+1}. [{article['title']}]({article['url']})")
                        
                        # Metadata tags
                        col1, col2 = st.columns(2)
                        with col1:
                            st.caption(f"📰 **Source:** {article['source']['name']}")
                        with col2:
                            # Formatting the ISO timestamp
                            date_str = article['publishedAt'][:10] if article.get('publishedAt') else "Unknown"
                            st.caption(f"📅 **Published:** {date_str}")
                        
                        # Article description/snippet
                        st.write(article['description'] if article['description'] else "*No description snippet available.*")
                    
                    if img_col and has_img:
                        with img_col:
                            try:
                                st.image(article["urlToImage"], use_container_width=True)
                            except Exception:
                                pass # Suppress errors for broken external links
                                
                    st.markdown("---")
                    
                # Setup structured data list for pandas export file
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
                    label="📥 Export Elite Media Data as CSV",
                    data=csv_data,
                    file_name=f"elite_eco_reports_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
                    
        except requests.exceptions.HTTPError as err:
            st.error(f"API Connection Failure: Check your credential string. Detail: {err}")
        except Exception as e:
            st.error(f"An unexpected tracking error occurred: {e}")
