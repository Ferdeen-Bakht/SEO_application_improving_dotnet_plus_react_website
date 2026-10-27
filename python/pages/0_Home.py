import streamlit as st
from seo_lab.config import DOTNET_BASE_URL, OLLAMA_BASE_URL, OLLAMA_MODEL
from seo_lab.dotnet_client import get_pages
import httpx

st.title("AI SEO Learning Lab")
st.write("A small, local playground for learning SEO automation one step at a time.")
st.info("Recommended learning order: crawl a site → inspect findings → draft content with the local model → review → approve → publish to the local .NET demo site.")

left, right = st.columns(2)
with left:
    st.subheader("Your local .NET test website")
    st.code(DOTNET_BASE_URL)
    if st.button("Test .NET website connection", use_container_width=True):
        try:
            pages = get_pages()
            st.success(f"Connected. Found {len(pages)} sample pages.")
            st.dataframe([{"path": p["path"], "title": p["title"], "version": p["version"]} for p in pages], use_container_width=True)
        except Exception as exc:
            st.error(f"Could not connect: {exc}. Start the .NET site first.")
with right:
    st.subheader("Your local AI model")
    st.code(f"{OLLAMA_BASE_URL}\nModel: {OLLAMA_MODEL}")
    if st.button("Test Ollama connection", use_container_width=True):
        try:
            with httpx.Client(timeout=10) as client:
                response = client.get(f"{OLLAMA_BASE_URL}/api/tags")
                response.raise_for_status()
                models = [m["name"] for m in response.json().get("models", [])]
            st.success("Ollama is reachable.")
            st.write("Installed models:", ", ".join(models) if models else "No models found — pull the model from the terminal.")
        except Exception as exc:
            st.error(f"Cannot reach Ollama: {exc}. Open Ollama and pull the configured model.")

st.subheader("What each page does")
st.markdown("""
- **Crawl & audit:** visits linked pages on one site and checks observable HTML basics.
- **Content optimizer:** asks the local model to suggest changes for a selected .NET demo page.
- **Approval & publishing:** lets you edit, approve, reject, or explicitly publish a draft to the local demo website.
- **SEO concepts:** plain-English explanations of the ideas and why the application uses them.

This is a local learning prototype, not an unattended production SEO service. It does not guarantee search rankings and it does not connect to Google Search Console yet.
""")
