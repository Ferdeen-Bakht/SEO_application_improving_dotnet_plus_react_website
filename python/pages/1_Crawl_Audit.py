import json
import pandas as pd
import streamlit as st
from seo_lab.crawler import crawl_site
from seo_lab.config import DATA_DIR, DOTNET_BASE_URL

st.title("1. Crawl & audit")
st.write("A crawler is like a visitor that follows links from page to page and writes down what it finds. This crawl stays on the starting website's host and respects robots.txt.")
with st.form("crawl_form"):
    start_url = st.text_input("Starting URL", value=f"{DOTNET_BASE_URL}/")
    max_pages = st.slider("Maximum pages to visit", 1, 30, 10)
    submitted = st.form_submit_button("Start crawl", type="primary")

if submitted:
    try:
        with st.spinner("Fetching pages and checking SEO fields..."):
            pages = crawl_site(start_url, max_pages=max_pages)
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        (DATA_DIR / "last_crawl.json").write_text(json.dumps(pages, indent=2, ensure_ascii=False), encoding="utf-8")
        st.session_state["last_crawl_pages"] = pages
        st.success(f"Crawl finished. Visited {len(pages)} URL(s). Results also saved to data/last_crawl.json.")
    except Exception as exc:
        st.error(str(exc))

pages = st.session_state.get("last_crawl_pages", [])
if pages:
    flat = []
    for p in pages:
        findings = p.get("findings", [])
        flat.append({
            "URL": p.get("url", ""),
            "HTTP": p.get("status_code", 0),
            "Title": p.get("title", ""),
            "Title length": len(p.get("title", "")),
            "Meta description": p.get("description", ""),
            "H1": p.get("h1", ""),
            "Finding count": len(findings),
            "Main finding": findings[0]["issue"] if findings else "No basic checks flagged an issue",
        })
    st.subheader("Page inventory")
    st.dataframe(pd.DataFrame(flat), use_container_width=True, hide_index=True)
    st.download_button("Download crawl results (JSON)", json.dumps(pages, indent=2, ensure_ascii=False), "crawl_results.json", "application/json")
    st.subheader("Inspect one page")
    selected_url = st.selectbox("Choose a URL", [p["url"] for p in pages])
    page = next(p for p in pages if p["url"] == selected_url)
    a, b = st.columns(2)
    with a:
        st.write("**Title**", page.get("title") or "(missing)")
        st.write("**Meta description**", page.get("description") or "(missing)")
        st.write("**H1**", page.get("h1") or "(missing)")
        st.write("**Canonical**", page.get("canonical") or "(not declared)")
        st.write("**Robots directive**", page.get("robots") or "(no meta robots directive found)")
    with b:
        findings = page.get("findings", [])
        if not findings:
            st.success("No issue was flagged by this small set of checks. This does not mean the page is fully SEO-optimized.")
        for f in findings:
            with st.expander(f"{f.get('severity', 'info').upper()}: {f['issue']}"):
                st.write("**Why it matters:**", f.get("why", ""))
                st.write("**Possible next step:**", f.get("suggestion", ""))
    with st.expander("Show extracted text preview"):
        st.write(page.get("text", "")[:5000])
else:
    st.caption("Run your first crawl to see a page inventory and findings here.")

st.warning("This checker looks at basic HTML signals only. It does not prove Google has indexed a page, measure rankings, evaluate links across the whole web, or guarantee an SEO score.")
