import streamlit as st
import requests
import time
import pandas as pd
from datetime import datetime, timedelta

st.set_page_config(page_title="Sweden Concert Radar", page_icon="🎵", layout="wide")

TM_API_KEY = st.secrets["TM_API_KEY"]
POPULAR_THRESHOLD = 10000


def safe_fans(val):
    return int(val) if isinstance(val, (int, float)) else 0


# ─────────────────────────────────────────
# Fetch concerts
# ─────────────────────────────────────────
@st.cache_data(ttl=3600)
def fetch_concerts():

    all_events = []
    page = 0
    total_pages = 1

    while page < total_pages and page < 5:

        url = "https://app.ticketmaster.com/discovery/v2/events.json"

        params = {
            "apikey": TM_API_KEY,
            "countryCode": "SE",
            "classificationName": "music",
            "size": 200,
            "sort": "date,asc",
            "page": page,
        }

        res = requests.get(url, params=params, timeout=20)
        res.raise_for_status()

        data = res.json()

        events = data.get("_embedded", {}).get("events", [])

        all_events.extend(events)

        total_pages = data.get("page", {}).get("totalPages", 1)

        page += 1

    rows = []

    for e in all_events:

        venues = e.get("_embedded", {}).get("venues", [])
        v = venues[0] if venues else {}

        attractions = e.get("_embedded", {}).get("attractions", [])

        dates = e.get("dates", {}).get("start", {})

        rows.append(
            {
                "id": e.get("id"),
                "event": e.get("name"),
                "artists": [a.get("name") for a in attractions],
                "date": dates.get("localDate", ""),
                "time": dates.get("localTime", ""),
                "venue": v.get("name", "N/A"),
                "city": v.get("city", {}).get("name", "N/A"),
                "url": e.get("url", ""),
            }
        )

    return rows


# ─────────────────────────────────────────
# Artist enrichment
# ─────────────────────────────────────────
@st.cache_data(ttl=86400)
def enrich_artist(name):

    info = {
        "country": None,
        "fans": 0,
        "is_popular": False,
        "tags": [],
        "genres": [],
        "is_real_artist": False,
    }

    # Deezer
    try:

        res = requests.get(
            "https://api.deezer.com/search/artist",
            params={"q": name, "limit": 1},
            timeout=10,
        )

        data = res.json().get("data", [])

        if data:

            da = data[0]

            if name.lower() in da.get("name", "").lower():

                info["is_real_artist"] = True

                fans = safe_fans(da.get("nb_fan"))

                info["fans"] = fans

                info["is_popular"] = fans >= POPULAR_THRESHOLD

    except Exception:
        pass

    # Musicbrainz
    try:

        res = requests.get(
            "https://musicbrainz.org/ws/2/artist/",
            params={"query": name, "limit": 1, "fmt": "json"},
            headers={"User-Agent": "ConcertRadar"},
            timeout=10,
        )

        artists = res.json().get("artists", [])

        if artists:

            a = artists[0]

            if a.get("score", 0) >= 80:

                info["country"] = a.get("country")

                info["tags"] = [
                    t["name"]
                    for t in sorted(
                        a.get("tags", []),
                        key=lambda x: x.get("count", 0),
                        reverse=True,
                    )[:4]
                ]

                if a.get("type") in ("Person", "Group"):
                    info["is_real_artist"] = True

    except Exception:
        pass

    time.sleep(1)

    return info


# ─────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────
st.title("🎵 Sweden Concert Radar")

with st.spinner("Loading concerts..."):
    concerts = fetch_concerts()

if not concerts:
    st.warning("No concerts found")
    st.stop()

# Unique artists
all_artist_names = list(
    dict.fromkeys(a for c in concerts for a in c["artists"] if a)
)

artist_data = {}

progress = st.progress(0)

for i, name in enumerate(all_artist_names):

    artist_data[name] = enrich_artist(name)

    progress.progress((i + 1) / len(all_artist_names))

progress.empty()

# Filter real artists
real_artists = {k: v for k, v in artist_data.items() if v["is_real_artist"]}

# Stats
popular_artists = {
    k: v for k, v in real_artists.items() if v["is_popular"]
}

not_popular_artists = {
    k: v for k, v in real_artists.items() if not v["is_popular"]
}

# ─────────────────────────────────────────
# DASHBOARD
# ─────────────────────────────────────────
c1, c2, c3 = st.columns(3)

c1.metric("Concerts", len(concerts))
c2.metric("Artists", len(real_artists))
c3.metric("Popular Artists", len(popular_artists))

st.divider()

# ─────────────────────────────────────────
# BIG CONCERTS
# ─────────────────────────────────────────
st.subheader("🔥 Big Concerts")

big_concerts = []

for c in concerts:

    max_fans = 0

    for a in c["artists"]:

        info = real_artists.get(a)

        if not info:
            continue

        fans = safe_fans(info.get("fans"))

        if fans > max_fans:
            max_fans = fans

    if max_fans >= POPULAR_THRESHOLD:

        big_concerts.append((max_fans, c))

big_concerts.sort(key=lambda x: x[0], reverse=True)

for fans, c in big_concerts[:20]:

    st.markdown(
        f"""
**{c['event']}**

📅 {c['date']}  
📍 {c['venue']} — {c['city']}  

⭐ {fans:,} fans
"""
    )

# ─────────────────────────────────────────
# TABLE
# ─────────────────────────────────────────
rows = []

for c in concerts:

    max_fans = 0

    for a in c["artists"]:

        info = real_artists.get(a)

        if not info:
            continue

        fans = safe_fans(info.get("fans"))

        if fans > max_fans:
            max_fans = fans

    rows.append(
        {
            "Date": c["date"],
            "Event": c["event"],
            "Artists": ", ".join(c["artists"]),
            "Venue": c["venue"],
            "City": c["city"],
            "Fans": max_fans if max_fans else None,
        }
    )

df = pd.DataFrame(rows)

st.dataframe(df, use_container_width=True)

csv = df.to_csv(index=False).encode()

st.download_button(
    "Download CSV",
    csv,
    "concerts_sweden.csv",
    "text/csv",
)