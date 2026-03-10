import streamlit as st
import requests
import time
import pandas as pd
from datetime import datetime, timedelta

st.set_page_config(page_title="Sweden Concert Radar", page_icon="🎵", layout="wide")

TM_API_KEY = st.secrets["TM_API_KEY"]
POPULAR_THRESHOLD = 10000


def safe_fans(val):
    return val if isinstance(val, (int, float)) else 0


COUNTRY_NAMES = {
    "SE": "Sweden","US":"United States","GB":"United Kingdom","JP":"Japan",
    "DE":"Germany","KR":"South Korea","FR":"France","BR":"Brazil",
    "AU":"Australia","CA":"Canada","NO":"Norway","DK":"Denmark",
    "FI":"Finland","NL":"Netherlands","IT":"Italy","ES":"Spain",
    "IE":"Ireland","AT":"Austria","CH":"Switzerland","BE":"Belgium",
    "NZ":"New Zealand","PT":"Portugal","PL":"Poland","CZ":"Czech Republic",
    "MX":"Mexico","AR":"Argentina","ZA":"South Africa","IS":"Iceland",
    "JM":"Jamaica","TT":"Trinidad","PR":"Puerto Rico","CO":"Colombia",
}

COUNTRY_FLAGS = {
    "SE":"🇸🇪","US":"🇺🇸","GB":"🇬🇧","JP":"🇯🇵","DE":"🇩🇪","KR":"🇰🇷",
    "FR":"🇫🇷","BR":"🇧🇷","AU":"🇦🇺","CA":"🇨🇦","NO":"🇳🇴","DK":"🇩🇰",
    "FI":"🇫🇮","NL":"🇳🇱","IT":"🇮🇹","ES":"🇪🇸","IE":"🇮🇪","AT":"🇦🇹",
    "CH":"🇨🇭","BE":"🇧🇪","NZ":"🇳🇿","PT":"🇵🇹","PL":"🇵🇱","CZ":"🇨🇿",
    "MX":"🇲🇽","AR":"🇦🇷","ZA":"🇿🇦","IS":"🇮🇸","JM":"🇯🇲","CO":"🇨🇴"
}

def cn(code):
    if not code or code == "N/A":
        return "Unknown"
    return COUNTRY_NAMES.get(code, code)

def flag(code):
    return COUNTRY_FLAGS.get(code, "🌍")


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

        res = requests.get(url, params=params)
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

        rows.append({
            "id": e.get("id"),
            "event": e.get("name"),
            "artists": [a.get("name") for a in attractions],
            "date": dates.get("localDate",""),
            "time": dates.get("localTime",""),
            "venue": v.get("name","N/A"),
            "city": v.get("city",{}).get("name","N/A"),
            "url": e.get("url",""),
        })

    return rows


@st.cache_data(ttl=86400)
def enrich_artist(name):

    info = {
        "country":None,
        "country_name":"Unknown",
        "tags":[],
        "genres":[],
        "fans":0,
        "is_popular":False,
        "is_real_artist":False,
    }

    try:

        res = requests.get(
            "https://api.deezer.com/search/artist",
            params={"q":name,"limit":1},
            timeout=10
        )

        data = res.json().get("data",[])

        if data:

            da = data[0]

            if name.lower() in da.get("name","").lower():

                info["is_real_artist"] = True

                fans = safe_fans(da.get("nb_fan"))

                info["fans"] = fans

                info["is_popular"] = fans >= POPULAR_THRESHOLD

    except:
        pass


    try:

        res = requests.get(
            "https://musicbrainz.org/ws/2/artist/",
            params={"query":name,"limit":1,"fmt":"json"},
            headers={"User-Agent":"ConcertRadar"},
            timeout=10
        )

        artists = res.json().get("artists",[])

        if artists:

            a = artists[0]

            if a.get("score",0) >= 80:

                info["country"] = a.get("country")

                info["country_name"] = cn(info["country"])

                info["tags"] = [
                    t["name"]
                    for t in sorted(
                        a.get("tags",[]),
                        key=lambda x:x.get("count",0),
                        reverse=True
                    )[:4]
                ]

                if a.get("type") in ("Person","Group"):
                    info["is_real_artist"] = True

    except:
        pass

    time.sleep(1)

    return info


st.markdown("# 🎵 Sweden Concert Radar")

with st.spinner("Loading concerts from Ticketmaster..."):
    concerts = fetch_concerts()

if not concerts:
    st.warning("No concerts found.")
    st.stop()


all_artist_names = list(dict.fromkeys(a for c in concerts for a in c["artists"] if a))


artist_data = {}

progress_bar = st.progress(0)

for i,name in enumerate(all_artist_names):

    artist_data[name] = enrich_artist(name)

    progress_bar.progress((i+1)/len(all_artist_names))

progress_bar.empty()


real_artists = {k:v for k,v in artist_data.items() if v["is_real_artist"]}

popular_artists = {k:v for k,v in real_artists.items() if v["is_popular"]}

not_popular_artists = {k:v for k,v in real_artists.items() if not v["is_popular"]}


tab_dash,tab_highlights,tab_concerts = st.tabs([
    "📊 Dashboard",
    "🔥 Highlights & Top Artists",
    f"🎵 All Concerts ({len(concerts)})"
])


with tab_dash:

    c1,c2,c3 = st.columns(3)

    c1.metric("Total Concerts",len(concerts))
    c2.metric("Verified Artists",len(real_artists))
    c3.metric("Popular Artists",len(popular_artists))


with tab_highlights:

    st.subheader("🔥 Upcoming Big Concerts")

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

            big_concerts.append({
                **c,
                "max_fans":max_fans
            })

    big_concerts.sort(key=lambda x:x["max_fans"], reverse=True)

    for c in big_concerts[:20]:

        st.markdown(f"""
### {c['event']}

📅 {c['date']}  
📍 {c['venue']} — {c['city']}  
⭐ {c['max_fans']:,} fans
""")


with tab_concerts:

    rows = []

    for c in concerts:

        max_fans = 0

        for a in c["artists"]:

            ai = real_artists.get(a)

            if not ai:
                continue

            fans = safe_fans(ai.get("fans"))

            if fans > max_fans:
                max_fans = fans

        rows.append({
            "Date":c["date"],
            "Event":c["event"],
            "Artists":", ".join(c["artists"]),
            "Venue":c["venue"],
            "City":c["city"],
            "Fans":max_fans if max_fans else None
        })

    df = pd.DataFrame(rows)

    st.dataframe(df,use_container_width=True)

    csv = df.to_csv(index=False).encode("utf-8")

    st.download_button(
        "📥 Download CSV",
        csv,
        "concerts_sweden.csv",
        "text/csv"
    )