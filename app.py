import streamlit as st
import requests
import json
from groq import Groq

# --- CONFIG ---
st.set_page_config(page_title="Media Assistant", page_icon="🎥", layout="wide")
st.title("🧠 Media Assistant")
st.markdown("**Your AI streaming buddy — precise matches!**")

# Service name mapping
SERVICE_MAP = {
    "netflix": "Netflix",
    "prime": "Amazon Prime Video",
    "disney": "Disney+",
    "hulu": "Hulu",
    "espnplus": "ESPN+",
    "max": "Max",
    "paramountplus": "Paramount+",
    "youtube": "YouTube Premium",
    "apple": "Apple TV+",
}

# Sidebar
st.sidebar.header("🎬 Your Streaming Apps")
apps = st.sidebar.multiselect(
    "Select your subs (all enabled by default):",
    [
        "Netflix",
        "Amazon Prime Video",
        "Hulu",
        "Disney+",
        "ESPN+",
        "Max",
        "Paramount+",
        "YouTube Premium"
    ],
    default=[
        "Netflix",
        "Amazon Prime Video",
        "Hulu",
        "Disney+",
        "ESPN+",
        "Max",
        "Paramount+",
        "YouTube Premium"
    ]
)

# Load secrets
TMDB_API_KEY = st.secrets.get("TMDB_API_KEY")
STREAM_API_KEY = st.secrets.get("STREAM_API_KEY")
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY")

if GROQ_API_KEY:
    client = Groq(api_key=GROQ_API_KEY)
else:
    st.error("❌ GROQ_API_KEY missing in secrets.toml")

# --- CHAT HISTORY ---
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "Hi! Ask 'Where to watch Cool Runnings?' or 'Board game night playlist'."}]

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# --- USER INPUT ---
if prompt := st.chat_input("Type your query..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.spinner("🧠 Searching across your apps..."):
        try:
            # AI: Parse intent
            intent_prompt = f"""User query: '{prompt}'. 
            Respond ONLY in JSON: {{"intent": "search_title" or "recommend", "title": "exact title if search, else null", "theme": "if recommend, e.g. holiday"}}"""
            intent_resp = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": intent_prompt}],
                response_format={"type": "json_object"}
            )
            intent = json.loads(intent_resp.choices[0].message.content)

            if intent.get("intent") == "search_title" and intent.get("title"):
                # TMDB: Get top result + ID
                tmdb_resp = requests.get(
                    f"https://api.themoviedb.org/3/search/multi?api_key={TMDB_API_KEY}&query={intent['title']}&language=en-US"
                ).json()
                if tmdb_resp.get("results"):
                    item = tmdb_resp["results"][0]
                    tmdb_id = item["id"]

                    # Streaming: Search by title, filter exact match
                    stream_resp = requests.get(
                        "https://streaming-availability.p.rapidapi.com/shows/search/title",
                        headers={"X-RapidAPI-Key": STREAM_API_KEY, "X-RapidAPI-Host": "streaming-availability.p.rapidapi.com"},
                        params={"title": intent["title"], "country": "us", "output_language": "en"}
                    ).json()

                    results = stream_resp if isinstance(stream_resp, list) else stream_resp.get("result", [])

                    # Filter to exact TMDB ID
                    matching = [r for r in results if str(r.get("tmdbId")) == str(tmdb_id)]
                    r = matching[0] if matching else (results[0] if results else {})

                    # Extract services from streamingOptions.us
                    services = []
                    if 'streamingOptions' in r and 'us' in r.get('streamingOptions', {}):
                        for option in r['streamingOptions']['us']:
                            service = option.get('service', {})
                            key = service.get('id', '').lower()
                            display = SERVICE_MAP.get(key, service.get('name', key.capitalize()))
                            if display in apps:
                                services.append(f"**{display}**")  # Bold your subs
                            else:
                                services.append(display)
                    service_str = ", ".join(services) if services else "Rent/buy only (check paid options)"

                    response = f"🎥 **Found: {intent['title']}**\n\nAvailable on your subs: {service_str}"
                    # Poster
                    if item.get("poster_path"):
                        poster = f"https://image.tmdb.org/t/p/w200{item['poster_path']}"
                        st.image(poster, width=150)
                else:
                    response = "❌ Title not found."
            else:
                # Recommend: AI playlists
                rec_prompt = f"Recommend 5 media items for '{prompt}' from {', '.join(apps)}. Format as bullet list: * Title (App) - short description."
                rec_resp = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "user", "content": rec_prompt}]
                )
                response = f"🌟 **AI Recs for {prompt}**:\n\n" + rec_resp.choices[0].message.content

        except Exception as e:
            response = f"⚠️ Error: {str(e)[:150]}. Try again."

    st.session_state.messages.append({"role": "assistant", "content": response})
    with st.chat_message("assistant"):
        st.markdown(response)