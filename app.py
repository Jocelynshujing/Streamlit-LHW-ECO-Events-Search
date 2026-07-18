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
    ["All Impacts", "Fish Kills / Mortalities", "Algal Blooms / Cyanobacteria", "Oxygen Depletion / Hypoxia"]
)

# Build the Boolean Query dynamically based on user selections
base_water_terms = '(lake OR reservoir OR lagoon OR "freshwater ecosystem")'
base_heat_terms = '(heatwave OR "extreme heat" OR "record temperature" OR "thermal stress")'

if eco_impact == "Fish Kills / Mortalities":
    impact_terms = '("fish kill" OR "mass mortality" OR "dead fish")'
elif eco_impact == "Algal Blooms / Cyanobacteria":
    impact_terms = '("algae bloom" OR cyanobacteria OR "toxic algae" OR microcystis)'
elif eco_impact == "Oxygen Depletion / Hypoxia":
    impact_terms = '(hypoxia OR anoxia OR "oxygen depletion" OR stratification)'
else:
    # "All Impacts" combines them using OR logic
    impact_terms = '("fish kill" OR "algae bloom" OR cyanobacteria OR hypoxia OR "oxygen depletion")'

# Final combined query string
final_query = f"{base_water_terms} AND {base_heat_terms} AND {impact_terms}"

# Show the query to the user so they see the tool's inner logic
with st.expander("Show Active Boolean Search Query Logic"):
    st.code(final_query, language="text")

# Fetch button
if st.sidebar.button("Search Media Database", type="primary"):
    if not api_key:
        st.error("Please enter a valid NewsAPI key in the sidebar to run the search.")
    else:
        with st.spinner("Searching global news archives..."):
            # NewsAPI 'everything' endpoint allows for deep keyword queries
            url = "https://newsapi.org/v2/everything"
            
            # Request parameters
            params = {
                "q": final_query,
                "sortBy": "relevancy",  # Prioritizes most relevant keyword matches
                "language": "en",       # Keeps articles in English for this tool
                "pageSize": 25,         # Number of articles to return
                "apiKey": api_key
            }
            
            try:
                response = requests.get(url, params=params)
                data = response.json()
                
                if data.get("status") == "error":
                    st.error(f"API Error: {data.get('message')}")
                elif data.get("totalResults") == 0:
                    st.warning("No articles found matching this exact combination of environmental keywords.")
                else:
                    articles = data.get("articles", [])
                    st.success(f"Found {data.get('totalResults')} matching global news articles!")
                    
                    # Display results in clean UI elements
                    for idx, article in enumerate(articles):
                        st.markdown(f"### {idx+1}. [{article['title']}]({article['url']})")
                        
                        # Metadata tags
                        col1, col2, col3 = st.columns([2, 2, 4])
                        with col1:
                            st.caption(f"📰 **Source:** {article['source']['name']}")
                        with col2:
                            # Formatting the ISO timestamp
                            date_str = article['publishedAt'][:10]
                            st.caption(f"📅 **Published:** {date_str}")
                        
                        # Article description/snippet
                        st.write(article['description'] if article['description'] else "*No description snippet available.*")
                        st.markdown("---")
                        
            except Exception as e:
                st.error(f"An unexpected connection error occurred: {e}")