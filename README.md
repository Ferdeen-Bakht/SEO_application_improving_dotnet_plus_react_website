# AI SEO Learning Lab: Python + Local Ollama + ASP.NET Core

This is a beginner-oriented, local SEO automation lab. It deliberately separates work into distinct Python modules and dashboard pages so that you can understand what each part does.

## What is included

- **A local ASP.NET Core demo website** with four sample pages, an XML sitemap, `robots.txt`, and a protected local API for updating a page after approval.
- **A Python/Streamlit dashboard** with separate pages for crawling, content optimization, approval/publishing, and SEO concepts.
- **A crawler** that stays on the start host, parses basic HTML fields, respects `robots.txt`, and includes a crawl delay.
- **Explainable SEO checks** for missing titles/descriptions/H1, canonical review, robots noindex, status codes, and heading observations. These are warnings, not guarantees about Google rankings.
- **Local content generation** through Ollama (default model: `qwen3:4b`).
- **SQLite approval storage** that saves original values and suggested values before publishing.
- **Version checking** so publishing fails if the test page changed since its draft was created.

## Requirements

Install:

1. **.NET 10 SDK**: https://dotnet.microsoft.com/download/dotnet/10.0
2. **Python 3.11 or 3.12** (3.12 is a safe choice for broad package compatibility): https://www.python.org/downloads/
3. **Ollama**: https://ollama.com/download

This sample is designed to run locally. It is not production hardened and is not meant to be exposed to the internet.

## Start the ASP.NET Core test website

Open PowerShell or a terminal:

```powershell
cd path\to\ai_seo_lab\dotnet\SeoDemoSite\ClientApp
npm install
npm run build
cd ..
dotnet run
```

The site is "Explore the World", a travel site with 15 pages: an ASP.NET Core backend (API, sitemap, robots.txt) and a React (Vite) frontend in `ClientApp`. The backend injects each page's title, meta description, canonical URL and a plain-HTML copy of the content into the React shell, so the Python crawler (which does not run JavaScript) still sees real content. Page content is seeded from `seed-data.json`. After changing React code, run `npm run build` again.

The project binds to `http://127.0.0.1:5055`. Visit:

- Home: http://127.0.0.1:5055/
- Destinations: http://127.0.0.1:5055/destinations
- Paris guide: http://127.0.0.1:5055/destinations/paris
- Japan budget: http://127.0.0.1:5055/budget-travel/japan
- Sitemap: http://127.0.0.1:5055/sitemap.xml
- Robots: http://127.0.0.1:5055/robots.txt
- Demo JSON API: http://127.0.0.1:5055/api/pages

On first run the site creates `site-data.json`. The demo site's content edits are saved there. To reset the original example pages, stop the website, delete `site-data.json`, then run it again.

## Start the local AI

In another terminal:

```powershell
ollama pull qwen2.5:3b
```

You can leave Ollama running in the background. The Python app calls its local HTTP API; text is not sent to a hosted LLM provider by this code. Inference speed depends on your computer's CPU, RAM, and GPU.

If this model is too slow for your machine, check available model variants in the Ollama library and choose a smaller model. Ensure `OLLAMA_MODEL` matches the exact local model name reported by `ollama list`.

## Start the Python dashboard

Open a third terminal:

```powershell
cd path\to\ai_seo_lab\python
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
copy .env.example .env
streamlit run streamlit_app.py
```

If PowerShell blocks virtual environment activation, you can either adjust the execution policy for your user according to your organization's policy or call `.venv\Scripts\python.exe -m pip install -r requirements.txt` and `.venv\Scripts\python.exe -m streamlit run streamlit_app.py` directly.

Streamlit opens a browser tab, normally at http://localhost:8501.

## AI agent and competitor benchmark

- **2. Content optimizer** needs no prompt. Pick a page and click *Analyze page and suggest changes*. The agent runs technical SEO checks (crawlability, canonical, XML sitemap, image alt text, broken links), reads the competitor benchmark, and asks the local model for separate edits (title, description, H1, paragraphs). Every edit is tested against the original for accuracy, clarity, keyword relevance and useful detail, shows its estimated score impact, and has **Accept** / **Reject** buttons. Accepted edits go to the approval queue; nothing is published automatically.
- **5. Competitor benchmark** follows three steps: export a CSV of the local crawl, crawl public travel sites (robots.txt respected, a few pages each), and compare side by side. The gaps become recommendations for the agent. Re-run steps 1 and 2 after publishing to see how much the average score improved.
- CSV exports are written to `data/exports/`. The SEO score is a learning aid made of simple visible checks, not a Google score.

## Recommended first test

1. Confirm that the .NET site is running and its home page loads.
2. On the dashboard's Home page, test both the .NET and Ollama connections.
3. Open **Crawl & audit** and crawl `http://127.0.0.1:5055/`. Start with 10 pages.
4. Open **Content optimizer**, choose `/destinations/paris`, enter a phrase that reflects the page (for example, `Paris travel guide`), and add only verifiable business context. Generate a draft.
5. Edit the proposed title, description, H1, and paragraphs. Save it to the approval queue.
6. Open **Approval & publishing**. Compare original with proposed, edit if needed, and approve.
7. Use **Publish approved content to local .NET demo** only after review. Open the updated page and confirm its version incremented.
8. Reject another proposal to understand the alternative path.

## Project map

```text
ai_seo_lab/
├── README.md
├── docs/
│   └── SEO_CONCEPTS.md
├── data/                         # created when the app runs
└── dotnet/
    └── SeoDemoSite/
        ├── SeoDemoSite.csproj
        └── Program.cs
        # site-data.json is generated at first run
└── python/
    ├── streamlit_app.py          # dashboard navigation
    ├── pages/
    │   ├── 0_Home.py
    │   ├── 1_Crawl_Audit.py
    │   ├── 2_Content_Optimizer.py
    │   ├── 3_Approval_Queue.py
    │   └── 4_SEO_Concepts.py
    ├── seo_lab/
    │   ├── config.py
    │   ├── crawler.py
    │   ├── audit_rules.py
    │   ├── local_llm.py
    │   ├── dotnet_client.py
    │   └── repository.py
    ├── requirements.txt
    └── .env.example
```

The Python dashboard uses `st.navigation` with individual page scripts, matching the current Streamlit multipage-app pattern. See https://docs.streamlit.io/develop/concepts/multipage-apps/overview.

## Important safety notes

- Bind the demo site to loopback (`127.0.0.1`). Do not expose it with a public tunnel or public server.
- The included API key is a development placeholder. Change it for local experiments and never use it for a real production site.
- The demo API key is not a substitute for a production authentication system. Production publishing requires authenticated reviewers, authorization per website/page, proper secret storage, CSRF protection where relevant, audit logs, backups, and rollback.
- The crawler is designed for learning and checks public hosts or localhost, remains on the initial hostname, respects `robots.txt`, and limits crawl size. Audit only websites you own or are authorized to test.
- AI drafts can be inaccurate. Review facts, usefulness, and the target query before approval.
- A missing meta description, long title, multiple H1s, or missing canonical is not automatically a Google penalty. The code phrases these as review findings where appropriate.
- This project does not yet connect to Google Search Console. See the official API docs: https://developers.google.com/webmaster-tools/v1/searchanalytics/query

## Reset local test data

Stop Streamlit and the .NET app. Delete the Python `data/seo_lab.db` database to clear local proposals. Delete `dotnet/SeoDemoSite/site-data.json` to recreate original demo content the next time the .NET site starts. Keep backups if you wish to preserve any drafts.
