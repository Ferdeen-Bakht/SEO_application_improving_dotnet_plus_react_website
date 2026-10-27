"""Crawl our site and competitor sites, export CSVs, compare side by side, and turn the gaps into recommendations."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from urllib.parse import urlparse

import pandas as pd

from seo_lab.config import DATA_DIR
from seo_lab.crawler import crawl_site
from seo_lab.page_metrics import STOP, score_metrics, tokens

EXPORT_DIR = DATA_DIR / "exports"
BENCHMARK_FILE = DATA_DIR / "benchmark.json"
HISTORY_FILE = DATA_DIR / "benchmark_history.json"

DEFAULT_COMPETITORS = [
    "https://www.lonelyplanet.com/destinations/france/paris",
    "https://www.roughguides.com/france/things-to-do-paris/",
    "https://www.nomadicmatt.com/travel-guides/france-travel-tips/",
    "https://www.japan.travel/en/",
]

COLUMNS = [
    ("url", "URL"), ("score", "SEO score"), ("title", "Title"), ("title_len", "Title length"),
    ("description", "Meta description"), ("desc_len", "Description length"), ("h1", "H1"), ("h2_count", "H2 count"),
    ("word_count", "Word count"), ("image_count", "Images"), ("alt_coverage", "Alt text %"),
    ("internal_links", "Internal links"), ("external_links", "External links"), ("canonical", "Canonical"),
    ("has_jsonld", "Structured data"), ("url_depth", "URL depth"), ("url_slug_len", "Slug length"),
]
NUMERIC = ["score", "title_len", "desc_len", "h2_count", "word_count", "image_count", "alt_coverage",
           "internal_links", "external_links", "url_depth"]


def site_label(url: str) -> str:
    host = urlparse(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def pages_to_frame(site: str, pages: list[dict]) -> pd.DataFrame:
    rows = []
    for p in pages:
        m = p.get("metrics")
        if not m or p.get("status_code") != 200:
            continue
        rows.append({"site": site, "score": score_metrics(m)["total"], **{k: m.get(k, "") for k, _ in COLUMNS if k not in {"score"}},
                     "h2_list": " | ".join(m.get("h2_list", []))})
    return pd.DataFrame(rows)


def friendly(df: pd.DataFrame) -> pd.DataFrame:
    """Column names suitable for a spreadsheet."""
    out = df[["site"] + [k for k, _ in COLUMNS if k in df.columns] + (["h2_list"] if "h2_list" in df.columns else [])].copy()
    out = out.rename(columns={"site": "Site", "h2_list": "H2 headings", **dict(COLUMNS)})
    return out


def crawl_many(urls: list[str], max_pages_each: int = 3) -> dict[str, list[dict]]:
    """Crawl each site on its own thread. Every crawl respects robots.txt, stays on its host and is capped."""
    def one(url):
        try:
            return site_label(url), crawl_site(url, max_pages=max_pages_each, delay_seconds=0.25), None
        except Exception as exc:  # report per site, keep the others
            return site_label(url), [], str(exc)
    with ThreadPoolExecutor(max_workers=min(4, len(urls) or 1)) as pool:
        return {label: {"pages": pages, "error": err} for label, pages, err in pool.map(one, urls)}


def save_csv(df: pd.DataFrame, name: str) -> str:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = EXPORT_DIR / name
    friendly(df).to_csv(path, index=False, encoding="utf-8-sig")
    return str(path)


def to_csv_bytes(df: pd.DataFrame) -> bytes:
    return friendly(df).to_csv(index=False).encode("utf-8-sig")


def summarize(df: pd.DataFrame) -> pd.DataFrame:
    """One row per site with averages; has_jsonld becomes a percentage of pages."""
    if df.empty:
        return pd.DataFrame()
    work = df.copy()
    work["has_jsonld"] = work["has_jsonld"].astype(float) * 100
    work["has_canonical"] = (work["canonical"].astype(str) != "").astype(float) * 100
    cols = NUMERIC + ["has_jsonld", "has_canonical"]
    summary = work.groupby("site")[cols].mean().round(1)
    summary.insert(0, "pages", work.groupby("site").size())
    return summary


# Navigation / boilerplate words that say nothing about the topic.
GENERIC = {"get", "see", "free", "official", "national", "organization", "home", "page", "search", "menu", "login", "sign", "join",
           "newsletter", "subscribe", "contact", "about", "privacy", "terms", "cookies", "experts", "expert", "tips"}


def _terms(text: str) -> set[str]:
    return {t for t in tokens(text) if t not in STOP and len(t) > 2}


def keyword_gaps(local_df: pd.DataFrame, comp_df: pd.DataFrame, limit: int = 12) -> list[dict]:
    """Words that appear in several competitor titles/H1/H2s but nowhere in ours."""
    ours = set()
    for _, r in local_df.iterrows():
        ours |= _terms(f"{r['title']} {r['h1']} {r.get('h2_list', '')}")
    brand_text = " ".join(comp_df["site"].unique()).replace(".", "").lower()  # e.g. "lonelyplanetcom roughguidescom"

    def useful(term: str) -> bool:
        return not term.isdigit() and term not in GENERIC and term not in brand_text

    sites_using: dict[str, set[str]] = {}
    for _, r in comp_df.iterrows():
        for t in filter(useful, _terms(f"{r['title']} {r['h1']} {r.get('h2_list', '')}")):
            sites_using.setdefault(t, set()).add(r["site"])
    # A term only counts when at least two different competitors use it, which filters out one site's own vocabulary.
    ranked = sorted(((t, len(s)) for t, s in sites_using.items() if len(s) >= 2 and t not in ours), key=lambda x: (-x[1], x[0]))
    return [{"term": t, "competitor_sites": c} for t, c in ranked[:limit]]


def make_insights(local_sum: pd.Series, comp_sum: pd.Series) -> list[dict]:
    """Compare our site averages with the competitor average and phrase each gap as a recommendation."""
    out = []

    def add(area, key, rec, priority, fmt="{:.0f}"):
        out.append({"area": area, "local": fmt.format(local_sum[key]), "competitors": fmt.format(comp_sum[key]),
                    "recommendation": rec, "priority": priority})

    if local_sum["word_count"] < 0.6 * comp_sum["word_count"]:
        add("Content depth (words)", "word_count",
            "Competitor pages are much longer. Add verifiable detail (practical tips, what to check, how to plan) in the page's own words; do not pad.", "high")
    if local_sum["h2_count"] < comp_sum["h2_count"] - 1:
        add("Subheadings (H2)", "h2_count", "Competitors break topics into more sections. Add descriptive subheadings.", "medium", "{:.1f}")
    if local_sum["has_jsonld"] < comp_sum["has_jsonld"]:
        add("Structured data (% pages)", "has_jsonld", "Competitors publish JSON-LD. Add schema.org markup to the site template (developer task).", "medium")
    if local_sum["alt_coverage"] < 100:
        add("Image alt text (%)", "alt_coverage", "Add descriptive alt text to every image.", "high")
    if local_sum["image_count"] < comp_sum["image_count"] * 0.5:
        add("Images per page", "image_count", "Competitors use more imagery. Add relevant images with alt text.", "low", "{:.1f}")
    if local_sum["internal_links"] < comp_sum["internal_links"] * 0.5:
        add("Internal links", "internal_links", "Link related guides together so visitors and crawlers can navigate between topics.", "low")
    if not 30 <= local_sum["title_len"] <= 65:
        add("Title length", "title_len", "Aim for roughly 30-65 characters with the main topic first.", "medium")
    if not 70 <= local_sum["desc_len"] <= 165:
        add("Meta description length", "desc_len", "Write page-specific descriptions of roughly 70-160 characters.", "medium")
    if local_sum["score"] < comp_sum["score"]:
        add("Overall SEO score", "score", "Work through the high-priority items above; re-run the benchmark afterwards to see the score change.", "info")
    return out


def build_benchmark(local_df: pd.DataFrame, comp_df: pd.DataFrame) -> dict:
    summary = summarize(pd.concat([local_df, comp_df], ignore_index=True))
    local_label = local_df["site"].iloc[0]
    comp_sum = summary.drop(index=local_label).mean(numeric_only=True)
    local_sum = summary.loc[local_label]
    return {
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "local_site": local_label,
        "competitors": sorted(comp_df["site"].unique().tolist()),
        "local_summary": local_sum.to_dict(),
        "competitor_average": comp_sum.to_dict(),
        "insights": make_insights(local_sum, comp_sum),
        "keyword_gaps": keyword_gaps(local_df, comp_df),
    }


def save_benchmark(bench: dict) -> None:
    BENCHMARK_FILE.write_text(json.dumps(bench, indent=2, ensure_ascii=False), encoding="utf-8")


def load_benchmark() -> dict | None:
    try:
        return json.loads(BENCHMARK_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def record_snapshot(local_df: pd.DataFrame, comp_avg_score: float | None) -> None:
    """Remember our average score over time so the dashboard can show how much it improved."""
    history = load_history()
    history.append({
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "local_score": round(float(local_df["score"].mean()), 1),
        "local_words": round(float(local_df["word_count"].mean()), 1),
        "competitor_score": None if comp_avg_score is None else round(float(comp_avg_score), 1),
    })
    HISTORY_FILE.write_text(json.dumps(history[-50:], indent=2), encoding="utf-8")


def load_history() -> list[dict]:
    try:
        return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
