import pandas as pd
import streamlit as st

from seo_lab import benchmark as bm
from seo_lab.config import DOTNET_BASE_URL
from seo_lab.crawler import crawl_site

LOCAL_CSV, COMP_CSV = "local_site.csv", "competitors.csv"


def load_frame(name: str) -> pd.DataFrame:
    """Reload an exported CSV back into the internal column names (so results survive a page refresh)."""
    path = bm.EXPORT_DIR / name
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path, encoding="utf-8-sig").fillna("")
    reverse = {v: k for k, v in bm.COLUMNS}
    df = df.rename(columns={"Site": "site", "H2 headings": "h2_list", **reverse})
    df["has_jsonld"] = df["has_jsonld"].astype(str).str.lower().isin({"true", "1"})
    for col in bm.NUMERIC:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df


st.title("5. Competitor benchmark")
st.write(
    "Compare our local travel site with public travel sites, side by side. The results feed the **Content optimizer** agent, "
    "which uses the gaps (page depth, headings, keywords, structured data) to recommend changes."
)

# ------------------------------------------------------------------ Step 1
st.header("Step 1 · Export local data")
st.write("Crawl the local site and save meta descriptions, word counts, URL structure and more to a CSV spreadsheet.")
if st.button("Crawl local site and export CSV", type="primary"):
    try:
        with st.spinner("Crawling the local site..."):
            pages = crawl_site(f"{DOTNET_BASE_URL}/", max_pages=30, delay_seconds=0.02)
            local = bm.pages_to_frame(bm.site_label(DOTNET_BASE_URL), pages)
        if local.empty:
            st.error("No HTML pages were crawled. Is the .NET site running?")
        else:
            path = bm.save_csv(local, LOCAL_CSV)
            st.success(f"Exported {len(local)} pages to {path}")
    except Exception as exc:
        st.error(str(exc))
local_df = load_frame(LOCAL_CSV)
if not local_df.empty:
    st.dataframe(bm.friendly(local_df), hide_index=True, width="stretch")
    st.download_button("Download local CSV", bm.to_csv_bytes(local_df), LOCAL_CSV, "text/csv")

# ------------------------------------------------------------------ Step 2
st.header("Step 2 · Crawl competitor sites")
st.write("Enter public travel sites, one URL per line, and run a separate crawl. The crawler respects each site's robots.txt, stays on that site, "
         "waits between requests and is capped to a few pages per site, so it is quick and gentle.")
urls_text = st.text_area("Competitor URLs (one per line)", value="\n".join(bm.DEFAULT_COMPETITORS), height=130)
max_pages = st.slider("Pages per competitor", 1, 6, 3)
if st.button("Crawl competitors and export CSV", type="primary"):
    urls = [u.strip() for u in urls_text.splitlines() if u.strip()][:8]
    if not urls:
        st.error("Enter at least one URL.")
    else:
        with st.spinner(f"Crawling {len(urls)} site(s)..."):
            results = bm.crawl_many(urls, max_pages)
        frames = []
        for label, r in results.items():
            frame = bm.pages_to_frame(label, r["pages"])
            if r["error"]:
                st.warning(f"{label}: {r['error']}")
            elif frame.empty:
                st.warning(f"{label}: no readable HTML pages (blocked by robots.txt or the site refused the request).")
            else:
                st.write(f"✅ {label}: {len(frame)} page(s)")
                frames.append(frame)
        if frames:
            comp = pd.concat(frames, ignore_index=True)
            path = bm.save_csv(comp, COMP_CSV)
            st.success(f"Exported {len(comp)} competitor pages to {path}")
            if not local_df.empty:
                bench = bm.build_benchmark(local_df, comp)
                bm.save_benchmark(bench)
                bm.record_snapshot(local_df, bench["competitor_average"]["score"])
                st.success("Benchmark saved. The Content optimizer will use it automatically.")
comp_df = load_frame(COMP_CSV)
if not comp_df.empty:
    st.dataframe(bm.friendly(comp_df), hide_index=True, width="stretch")
    st.download_button("Download competitor CSV", bm.to_csv_bytes(comp_df), COMP_CSV, "text/csv")

# ------------------------------------------------------------------ Step 3
st.header("Step 3 · Compare side by side")
if local_df.empty or comp_df.empty:
    st.info("Complete steps 1 and 2 to see the comparison.")
    st.stop()

bench = bm.build_benchmark(local_df, comp_df)
summary = bm.summarize(pd.concat([local_df, comp_df], ignore_index=True))
local_label = bench["local_site"]

st.subheader("Where do we stand?")
c1, c2, c3 = st.columns(3)
c1.metric("Our average SEO score", f"{bench['local_summary']['score']:.0f}/100", border=True)
c2.metric("Competitor average", f"{bench['competitor_average']['score']:.0f}/100",
          delta=f"{bench['local_summary']['score'] - bench['competitor_average']['score']:+.0f} for us", border=True)
c3.metric("Words per page: ours vs competitors", f"{bench['local_summary']['word_count']:.0f} vs {bench['competitor_average']['word_count']:.0f}", border=True)

history = bm.load_history()
if len(history) >= 2:
    first, last = history[0], history[-1]
    delta = last["local_score"] - first["local_score"]
    st.subheader("Improvement over time")
    st.metric(f"Our average score since the first snapshot ({first['ts'][:10]})", f"{last['local_score']:.0f}/100", delta=f"{delta:+.1f} points", border=True)
    st.line_chart(pd.DataFrame(history).set_index("ts")[["local_score", "competitor_score"]].rename(columns={"local_score": "Ours", "competitor_score": "Competitors"}))
    st.caption("A snapshot is saved every time you re-crawl competitors. Publish approved changes, re-run steps 1 and 2, and the line shows how much the site improved.")
else:
    st.caption("Improvement tracking starts with this snapshot. After you publish approved changes, re-run steps 1 and 2 to see how much the score improved.")

st.subheader("Site averages")
names = {"pages": "Pages", "score": "SEO score", "word_count": "Words", "title_len": "Title length", "desc_len": "Description length",
         "h2_count": "H2 count", "image_count": "Images", "alt_coverage": "Alt text %", "internal_links": "Internal links",
         "external_links": "External links", "has_jsonld": "Structured data %", "has_canonical": "Canonical %", "url_depth": "URL depth"}
table = summary[list(names)].rename(columns=names)
ordered = pd.concat([table.loc[[local_label]].rename(index=lambda s: f"{s} (ours)"), table.drop(index=local_label)])
st.dataframe(ordered, width="stretch")
st.download_button("Download comparison CSV", ordered.to_csv().encode("utf-8-sig"), "comparison.csv", "text/csv")
st.bar_chart(table[["SEO score", "Words"]].assign(Words=table["Words"] / 20).rename(columns={"Words": "Words ÷ 20"}))

st.subheader("What the agent will recommend")
st.dataframe(pd.DataFrame(bench["insights"]).rename(columns={"area": "Area", "local": "Ours", "competitors": "Competitors", "recommendation": "Recommendation", "priority": "Priority"}),
             hide_index=True, width="stretch")
if bench["keyword_gaps"]:
    st.write("**Keyword gaps** (used in titles/headings by 2+ competitors, absent from ours; number = competitors): " + ", ".join(f"{g['term']} ({g['competitor_sites']})" for g in bench["keyword_gaps"]))
else:
    st.caption("No keyword gaps found: no topic word is shared by two or more competitors that our site lacks.")
st.page_link("pages/2_Content_Optimizer.py", label="Open the Content optimizer to apply these →")

st.subheader("Compare two pages")
a_col, b_col = st.columns(2)
ours_pick = a_col.selectbox("Our page", local_df["url"].tolist())
theirs_pick = b_col.selectbox("Competitor page", comp_df["url"].tolist())
ours, theirs = local_df[local_df["url"] == ours_pick].iloc[0], comp_df[comp_df["url"] == theirs_pick].iloc[0]
rows = []
for key, label in [("title", "Title"), ("description", "Meta description"), ("h1", "H1"), ("h2_list", "H2 headings"), ("score", "SEO score"), ("word_count", "Words"),
                   ("title_len", "Title length"), ("desc_len", "Description length"), ("h2_count", "H2 count"), ("image_count", "Images"),
                   ("alt_coverage", "Alt text %"), ("internal_links", "Internal links"), ("has_jsonld", "Structured data"), ("url_depth", "URL depth")]:
    rows.append({"": label, "Ours": str(ours[key]), "Competitor": str(theirs[key])})
st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
st.caption("Competitor data is collected from public pages for comparison only. A higher number is not automatically better; check that changes stay accurate and useful.")
