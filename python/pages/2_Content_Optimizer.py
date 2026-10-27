import pandas as pd
import streamlit as st

from seo_lab import agent
from seo_lab.benchmark import load_benchmark
from seo_lab.config import DOTNET_BASE_URL
from seo_lab.dotnet_client import get_page, get_pages
from seo_lab.repository import create_proposal

ICON = {"pass": "✅", "warn": "⚠️", "fail": "❌"}
VERDICT_COLOR = {"Looks good": "green", "Review": "orange", "Check facts": "red", "Risky": "red"}

st.title("2. Content optimizer")
st.write(
    "The AI agent inspects the page, runs technical SEO checks, compares what it finds with competitor data, and proposes "
    "separate changes. **You do not write a prompt.** Accept or reject each change; nothing reaches the website until you "
    "approve it on the next page."
)

try:
    pages = get_pages()
except Exception as exc:
    st.error(f"Cannot read pages from the .NET demo site at {DOTNET_BASE_URL}. Start the .NET app first. Details: {exc}")
    st.stop()

labels = {f"{p['path']} — {p['title']}": p["slug"] for p in pages}
choice = st.selectbox("Choose a page to improve", list(labels.keys()))
slug = labels[choice]
try:
    page = get_page(slug)
except Exception as exc:
    st.error(f"Could not load selected page: {exc}")
    st.stop()

bench = load_benchmark()
if bench:
    st.caption(f"Using competitor benchmark from {bench['created_at'][:16].replace('T', ' ')} UTC ({', '.join(bench['competitors'])}).")
else:
    st.info("No competitor benchmark yet. The agent still works, but run **5. Competitor benchmark** first for better, data-backed suggestions.")

with st.expander("Advanced (optional): keyword and verified facts"):
    keyword_override = st.text_input("Target keyword (leave empty to let the agent detect it)", max_chars=200)
    extra_facts = st.text_area("Extra verified facts the agent may use", max_chars=2000,
                               placeholder="Only facts you can support. Leave empty to use just what is already on the page.")

if st.button("🔍 Analyze page and suggest changes", type="primary"):
    try:
        with st.spinner("Running technical checks, then asking the local model for suggestions (this can take a minute)..."):
            known = {p["path"].rstrip("/") for p in pages}
            analysis = agent.analyze(page, DOTNET_BASE_URL, known, bench, keyword_override, extra_facts.strip())
        st.session_state["agent_run"] = {
            "slug": slug, "version": page.get("version", 1), "analysis": analysis,
            "decisions": {c["id"]: "pending" for c in analysis["changes"]},
        }
    except Exception as exc:
        st.error(str(exc))

run = st.session_state.get("agent_run")
if not run or run["slug"] != slug:
    with st.expander("Current page content"):
        st.write("**Title:**", page["title"])
        st.write("**Meta description:**", page["metaDescription"])
        st.write("**H1:**", page["h1"])
        for para in page["paragraphs"]:
            st.write(para)
    st.stop()

analysis, decisions = run["analysis"], run["decisions"]


def decide(change_id: str, value: str):
    st.session_state["agent_run"]["decisions"][change_id] = value


def bulk(value: str, only_good: bool = False):
    for c in analysis["changes"]:
        if c["kind"] != "content":
            continue
        if not only_good or c["tests"]["verdict"] == "Looks good":
            st.session_state["agent_run"]["decisions"][c["id"]] = value


proposed, todo, accepted = agent.apply_decisions(analysis, decisions)
before, after = analysis["score_before"], agent.score_after(analysis, proposed)
content_changes = [c for c in analysis["changes"] if c["kind"] == "content"]
tech_changes = [c for c in analysis["changes"] if c["kind"] == "technical"]
n_acc = sum(1 for c in content_changes if decisions[c["id"]] == "accepted")

# ---- Improvement banner -------------------------------------------------------------------------
st.subheader("Expected improvement")
m1, m2, m3, m4 = st.columns(4)
m1.metric("SEO score before", f"{before['total']}/100", border=True)
m2.metric("SEO score with accepted changes", f"{after['total']}/100", delta=after["total"] - before["total"], border=True)
m3.metric("Accepted content changes", f"{n_acc}/{len(content_changes)}", border=True)
if accepted:
    m4.metric("Avg. revision test", f"{round(sum(c['tests']['overall'] for c in accepted) / len(accepted))}/100", border=True)
else:
    m4.metric("Avg. revision test", "-", border=True)
st.caption(f"Target keyword used: **{analysis['keyword']}**. The score adds up simple checks (title, description, H1, depth, structure, images, "
           "technical basics). It is a learning aid, not a Google score.")
with st.expander("How the score is built (before → after)"):
    rows = [{"Part": b["name"], "Before": f"{b['points']}/{b['max']}", "After": f"{a['points']}/{a['max']}",
             "Change": round(a["points"] - b["points"], 1), "Why": a["note"]} for b, a in zip(before["parts"], after["parts"])]
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

tab_changes, tab_tech, tab_bench = st.tabs(["Suggested changes", "Technical SEO check", "Benchmark insights"])

# ---- Suggested changes -------------------------------------------------------------------------
with tab_changes:
    st.caption("Each change is tested against the original for accuracy (no new unsupported facts), clarity, keyword relevance and useful detail.")
    b1, b2, b3, _ = st.columns([1.3, 1.1, 1.1, 2])
    b1.button("Accept all that look good", on_click=bulk, args=("accepted", True), width="stretch")
    b2.button("Reject all", on_click=bulk, args=("rejected",), width="stretch")
    b3.button("Reset", on_click=bulk, args=("pending",), width="stretch")

    if not content_changes:
        st.success("The agent found nothing worth changing in the title, description, H1 or introduction.")
    for c in content_changes:
        t, state = c["tests"], decisions[c["id"]]
        with st.container(border=True):
            head, verdict = st.columns([4, 1])
            status_txt = {"accepted": ":green[✔ Accepted]", "rejected": ":red[✖ Rejected]", "pending": ":gray[Pending]"}[state]
            head.markdown(f"**{c['label']}** · {status_txt}")
            verdict.markdown(f":{VERDICT_COLOR[t['verdict']]}[**{t['verdict']}** · {t['overall']}/100]  \nScore impact: **{c['score_delta']:+d}**")
            left, right = st.columns(2)
            left.caption("Original")
            left.write(c["original"] or "_(none; this adds a new paragraph)_")
            right.caption("Proposed")
            right.write(c["proposed"])
            q1, q2, q3, q4 = st.columns(4)
            q1.metric("Accuracy", t["accuracy"])
            q2.metric("Clarity", t["clarity"])
            q3.metric("Keyword relevance", t["keyword"])
            q4.metric("Useful detail", t["detail"])
            for note in t["notes"]:
                st.caption(f"• {note}")
            st.write(f"**Why:** {c['reason']}")
            a_col, r_col, _ = st.columns([1, 1, 4])
            a_col.button("Accept", key=f"acc_{c['id']}", type="primary" if state != "accepted" else "secondary",
                         disabled=state == "accepted", on_click=decide, args=(c["id"], "accepted"), width="stretch")
            r_col.button("Reject", key=f"rej_{c['id']}", disabled=state == "rejected", on_click=decide,
                         args=(c["id"], "rejected"), width="stretch")

    if tech_changes:
        st.markdown("#### Technical recommendations")
        st.caption("These need a developer or site-template change, so they cannot be published by this lab. Accepted items are added to the proposal as a developer to-do list.")
    for c in tech_changes:
        state = decisions[c["id"]]
        with st.container(border=True):
            st.markdown(f"{ICON[c['status']]} **{c['label']}** · " + {"accepted": ":green[✔ Accepted]", "rejected": ":red[✖ Rejected]", "pending": ":gray[Pending]"}[state])
            st.write(c["detail"])
            st.write(f"**Suggested fix:** {c['fix']}")
            a_col, r_col, _ = st.columns([1, 1, 4])
            a_col.button("Accept", key=f"acc_{c['id']}", type="primary" if state != "accepted" else "secondary",
                         disabled=state == "accepted", on_click=decide, args=(c["id"], "accepted"), width="stretch")
            r_col.button("Reject", key=f"rej_{c['id']}", disabled=state == "rejected", on_click=decide,
                         args=(c["id"], "rejected"), width="stretch")

    st.markdown("---")
    st.markdown("#### Send to the approval queue")
    if len(proposed["paragraphs"]) < 1:
        st.error("A proposal needs at least one body paragraph.")
    if st.button(f"Add {n_acc} accepted change(s) to the approval queue", type="primary", disabled=n_acc == 0):
        try:
            fresh = get_page(slug)
            if int(fresh.get("version", 1)) != int(run["version"]):
                st.error("The page was published again after this analysis. Run the analysis again so the proposal matches the current page.")
            else:
                reasons = "\n".join(f"- {c['label']}: {c['reason']} (revision test {c['tests']['overall']}/100, {c['tests']['verdict']})" for c in accepted)
                rationale = f"Agent-proposed changes (keyword: {analysis['keyword']}).\n{reasons}\nEstimated SEO score: {before['total']} → {after['total']}."
                if todo:
                    rationale += "\nDeveloper to-do (not published by this tool):\n" + "\n".join(f"- {t}" for t in todo)
                proposal_id = create_proposal(DOTNET_BASE_URL, fresh, proposed, rationale, analysis["keyword"])
                st.success(f"Saved proposal #{proposal_id}. It is pending and has not been published.")
                st.page_link("pages/3_Approval_Queue.py", label="Go to Approval & publishing →")
                st.session_state.pop("agent_run", None)
        except Exception as exc:
            st.error(str(exc))

# ---- Technical SEO ----------------------------------------------------------------------------
with tab_tech:
    st.caption("Live checks of this page: crawlability, canonical URL, XML sitemap, image alt text, broken links (plus structured data).")
    for c in analysis["technical"]:
        st.markdown(f"{ICON[c['status']]} **{c['name']}** — {c['detail']}")
        if c["status"] != "pass":
            st.caption(f"Fix: {c['fix']}")
    missing = analysis["base_metrics"].get("missing_alt_srcs", [])
    if missing:
        with st.expander("Images without alt text"):
            for src in missing:
                st.code(src, language=None)

# ---- Benchmark insights -----------------------------------------------------------------------
with tab_bench:
    if not bench:
        st.info("Run the competitor benchmark to see how this site compares with travel sites.")
    else:
        for h in analysis["hints"]:
            st.write("• " + h)
        if bench.get("keyword_gaps"):
            st.write("**Terms competitors use that this site does not:** " + ", ".join(g["term"] for g in bench["keyword_gaps"]))
        if bench.get("insights"):
            st.dataframe(pd.DataFrame(bench["insights"]).rename(columns={"area": "Area", "local": "Ours", "competitors": "Competitors", "recommendation": "Recommendation", "priority": "Priority"}),
                         hide_index=True, width="stretch")
        st.page_link("pages/5_Competitor_Benchmark.py", label="Open competitor benchmark →")

st.caption("SEO terms: keyword = the phrase a page should answer; title = HTML title element; meta description = a possible search-snippet summary; H1 = the main visible heading. Google can choose different snippets from your page content.")
