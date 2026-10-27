import streamlit as st
from seo_lab.repository import init_db

st.set_page_config(page_title="AI SEO Learning Lab", page_icon="🔎", layout="wide")
init_db()

pages = [
    st.Page("pages/0_Home.py", title="Home & setup", icon="🏠", default=True),
    st.Page("pages/1_Crawl_Audit.py", title="1. Crawl & audit", icon="🕷️"),
    st.Page("pages/2_Content_Optimizer.py", title="2. Content optimizer", icon="✍️"),
    st.Page("pages/3_Approval_Queue.py", title="3. Approval & publishing", icon="✅"),
    st.Page("pages/4_SEO_Concepts.py", title="4. SEO concepts", icon="📚"),
    st.Page("pages/5_Competitor_Benchmark.py", title="5. Competitor benchmark", icon="📊"),
    st.Page("pages/6_Connections.py", title="6. Connections", icon="🔗"),
    st.Page("pages/7_SEO_Dashboard.py", title="7. SEO dashboard", icon="📈"),
]
selected = st.navigation(pages, position="sidebar")
with st.sidebar:
    st.caption("Local AI • Human approval • No automatic publishing")
selected.run()
