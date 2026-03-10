import streamlit as st
import requests
import time
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Sweden Concert Radar", page_icon="♫", layout="wide")

# ── Config ──
TM_API_KEY = st.secrets["TM_API_KEY"]
POPULAR_THRESHOLD = 10000

COUNTRY_NAMES = {
    "SE": "Sweden", "US": "United States", "GB": "United Kingdom", "JP": "Japan",
    "DE": "Germany", "KR": "South Korea", "FR": "France", "BR": "Brazil",
    "AU": "Australia", "CA": "Canada", "NO": "Norway", "DK": "Denmark",
    "FI": "Finland", "NL": "Netherlands", "IT": "Italy", "ES": "Spain",
    "IE": "Ireland", "AT": "Austria", "CH": "Switzerland", "BE": "Belgium",
    "NZ": "New Zealand", "PT": "Portugal", "PL": "Poland", "CZ": "Czech Republic",
    "MX": "Mexico", "AR": "Argentina", "ZA": "South Africa", "IS": "Iceland",
}

def cn(code):
    if not code or code == "N/A":
        return "Unknown"
    return COUNTRY_NAMES.get(code, code)


# ── Styling ──
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;500;700&family=Instrument+Serif&display=swap');
    
    .block-container { padding-top: 2rem; }
    
    h1, h2, h3 { font-family: 'Instrument Serif', serif !important; }
    
    .big-stat {
        background: #111115;
        border: 1px solid #1f1f28;
        border-radius: 12px;
        padding: 20px 24px;
        text-align: center;
    }
    .big-stat .value {
        font-family: 'Instrument Serif', serif;
        font-size: 42px;
        font-weight: 400;
        line-height: 1.1;
    }
    .big-stat .label {
        color: #999;
        font-size: 13px;
        margin-top: 4px;
    }
    .big-stat .sub {
        color: #555;
        font-size: 11px;
    }
    
    .country-pill {
        display: inline-block;
        background: #1a1a22;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 11px;
        font-weight: 700;
        color: #ccc;
        font-family: monospace;
        margin-right: 6px;
    }
    
    .artist-chip {
        display: inline-block;
        background: #0a0a0c;
        border: 1px solid #333;
        border-radius: 20px;
        padding: 3px 10px;
        font-size: 12px;
        color: #ccc;
        margin: 2px 4px 2px 0;
    }
    .artist-chip.popular { border-color: #4ade80; }
    .artist-chip.not-popular { border-color: #555; }
    
    .tag-badge {
        display: inline-block;
        font-size: 10px;
        color: #9b59b6;
        background: #1a1122;
        border-radius: 4px;
        padding: 2px 7px;
        margin: 1px 3px 1px 0;
    }
    
    div[data-testid="stMetric"] {
        background: #111115;
        border: 1px solid #1f1f28;
        border-radius: 12px;
        padding: 16px;
    }
</style>
""", unsafe_allow_html=True)


# ── Data fetching ──
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_concerts():
    """Fetch all upcoming music events in Sweden from Ticketmaster."""
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
        genre = e.get("classifications", [{}])[0].get("genre", {}).get("name", "")
        sub = e.get("classifications", [{}])[0].get("subGenre", {}).get("name", "")

        rows.append({
            "id": e.get("id"),
            "event": e.get("name"),
            "artists": [a.get("name") for a in attractions],
            "date": dates.get("localDate", ""),
            "time": dates.get("localTime", ""),
            "venue": v.get("name", "N/A"),
            "city": v.get("city", {}).get("name", "N/A"),
            "url": e.get("url", ""),
            "genre": genre,
            "subgenre": sub,
        })
    return rows


@st.cache_data(ttl=86400, show_spinner=False)
def enrich_artist(name):
    """Fetch artist country + tags from MusicBrainz and fans + genres from Deezer."""
    info = {"country": None, "country_name": "Unknown", "tags": [], "genres": [], "fans": None, "is_popular": None}

    # MusicBrainz
    try:
        res = requests.get(
            "https://musicbrainz.org/ws/2/artist/",
            params={"query": name, "limit": 1, "fmt": "json"},
            headers={"User-Agent": "ConcertRadar/1.0 (streamlit)"},
            timeout=10,
        )
        artists = res.json().get("artists", [])
        if artists:
            a = artists[0]
            info["country"] = a.get("country") or None
            info["country_name"] = cn(info["country"])
            info["tags"] = sorted(
                a.get("tags", []), key=lambda x: x.get("count", 0), reverse=True
            )[:4]
            info["tags"] = [t["name"] for t in info["tags"]]
    except Exception:
        pass

    time.sleep(1.1)  # MusicBrainz rate limit

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
            info["fans"] = da.get("nb_fan", 0)
            info["is_popular"] = info["fans"] >= POPULAR_THRESHOLD if info["fans"] is not None else None

            # Genres from first album
            try:
                album_res = requests.get(f"https://api.deezer.com/artist/{da['id']}/albums?limit=1", timeout=10)
                albums = album_res.json().get("data", [])
                if albums:
                    ad = requests.get(f"https://api.deezer.com/album/{albums[0]['id']}", timeout=10).json()
                    info["genres"] = [g["name"] for g in ad.get("genres", {}).get("data", [])]
            except Exception:
                pass
    except Exception:
        pass

    return info


# ── Main App ──
st.markdown("# ♫ Sweden Concert Radar")
st.caption("Upcoming concerts in Sweden enriched with artist origin, genre tags & popularity data")

# Fetch concerts
with st.spinner("Fetching concerts from Ticketmaster..."):
    concerts = fetch_concerts()

if not concerts:
    st.warning("No concerts found.")
    st.stop()

# Get unique artists
all_artists_in_concerts = []
for c in concerts:
    all_artists_in_concerts.extend(c["artists"])
unique_artists = list(dict.fromkeys(all_artists_in_concerts))

# Enrich artists
artist_data = {}
progress_placeholder = st.empty()
bar_placeholder = st.empty()

unenriched = [a for a in unique_artists if a]
total = len(unenriched)

if total > 0:
    progress_placeholder.markdown(f"**Enriching {total} artists** with country, genre & fan data...")
    progress_bar = bar_placeholder.progress(0)

    for i, name in enumerate(unenriched):
        artist_data[name] = enrich_artist(name)
        progress_bar.progress((i + 1) / total)

    progress_placeholder.empty()
    bar_placeholder.empty()

# ── Build dataframe ──
rows_for_df = []
for c in concerts:
    primary = c["artists"][0] if c["artists"] else ""
    info = artist_data.get(primary, {})
    all_tags = set()
    all_genres = set()
    for a in c["artists"]:
        ai = artist_data.get(a, {})
        all_tags.update(ai.get("tags", []))
        all_genres.update(ai.get("genres", []))

    rows_for_df.append({
        "Date": c["date"],
        "Time": c["time"][:5] if c["time"] else "",
        "Event": c["event"],
        "Artists": ", ".join(c["artists"]),
        "Venue": c["venue"],
        "City": c["city"],
        "Artist Country": info.get("country") or "N/A",
        "Country Name": info.get("country_name", "Unknown"),
        "Fans": info.get("fans"),
        "Popular": "Yes" if info.get("is_popular") else ("No" if info.get("is_popular") is False else "N/A"),
        "Tags": ", ".join(all_tags) if all_tags else "",
        "Genres": ", ".join(all_genres) if all_genres else "",
        "Tickets": c["url"],
    })

df = pd.DataFrame(rows_for_df)
df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
df = df.sort_values("Date")

# ── Stats ──
now = datetime.now()
this_month_mask = (df["Date"].dt.month == now.month) & (df["Date"].dt.year == now.year)

total_concerts = len(df)
total_artists = len(unique_artists)
popular_count = sum(1 for a in artist_data.values() if a.get("is_popular") is True)
not_popular_count = sum(1 for a in artist_data.values() if a.get("is_popular") is False)
na_count = total_artists - popular_count - not_popular_count

# ── TABS ──
tab_dashboard, tab_concerts = st.tabs(["📊 Dashboard", f"🎵 All Concerts ({total_concerts})"])

# ─────────────────────────────────────────
# DASHBOARD TAB
# ─────────────────────────────────────────
with tab_dashboard:
    # Stat row
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Concerts", total_concerts)
    c2.metric("Unique Artists", total_artists)
    c3.metric("Popular Artists", popular_count, help="≥ 10,000 Deezer fans")
    c4.metric("Not Popular / N/A", f"{not_popular_count} / {na_count}", help="< 10k fans / unknown")

    st.markdown("---")

    # This month summary
    this_month_df = df[this_month_mask]
    if len(this_month_df) > 0:
        st.subheader(f"📅 This Month — {now.strftime('%B %Y')}")

        this_month_countries = this_month_df["Country Name"].value_counts().head(6)
        cols = st.columns(2 + len(this_month_countries))
        cols[0].metric("Concerts", len(this_month_df))
        cols[1].metric("Artists", this_month_df["Artists"].nunique())
        for i, (country, count) in enumerate(this_month_countries.items()):
            cols[i + 2].metric(f"From {country}", count)

        st.markdown("---")

    # Two columns: Country + Genre
    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("🌍 Artists by Country")
        country_counts = pd.Series({
            cn(a.get("country")): 1
            for a in artist_data.values()
        }).groupby(level=0).sum().sort_values(ascending=True).tail(15)

        st.bar_chart(country_counts, horizontal=True, color="#e8b931")

    with col_right:
        st.subheader("🏷️ Top Genres & Tags")
        tag_counter = {}
        for a in artist_data.values():
            for t in list(a.get("tags", [])) + list(a.get("genres", [])):
                key = t.lower()
                tag_counter[key] = tag_counter.get(key, 0) + 1
        if tag_counter:
            tag_series = pd.Series(tag_counter).sort_values(ascending=True).tail(15)
            st.bar_chart(tag_series, horizontal=True, color="#9b59b6")

    # Concerts per month
    st.subheader("📈 Concerts by Month")
    monthly = df.groupby(df["Date"].dt.to_period("M")).size()
    monthly.index = monthly.index.astype(str)
    st.bar_chart(monthly, color="#e8b931")

    # Country summary sentences
    st.subheader("📋 Quick Summary")
    country_artist_counts = {}
    for a_name, a_info in artist_data.items():
        c_name = a_info.get("country_name", "Unknown")
        country_artist_counts[c_name] = country_artist_counts.get(c_name, 0) + 1

    sorted_countries = sorted(country_artist_counts.items(), key=lambda x: x[1], reverse=True)
    summary_lines = []
    for country, count in sorted_countries[:10]:
        if country != "Unknown":
            summary_lines.append(f"**{count}** artists from **{country}**")
    summary_lines.append(f"**{popular_count}** popular artists (≥ 10k fans)")
    summary_lines.append(f"**{not_popular_count}** smaller/emerging artists")
    summary_lines.append(f"**{na_count}** with unknown popularity")

    for line in summary_lines:
        st.markdown(f"• {line}")


# ─────────────────────────────────────────
# CONCERTS TAB
# ─────────────────────────────────────────
with tab_concerts:
    # Filters
    fc1, fc2, fc3 = st.columns([3, 1, 1])
    with fc1:
        search = st.text_input("🔍 Search artist, venue, city...", key="search")
    with fc2:
        countries_list = ["All"] + sorted(df["Country Name"].unique().tolist())
        country_sel = st.selectbox("Country", countries_list, key="country_sel")
    with fc3:
        pop_sel = st.selectbox("Popularity", ["All", "Popular (≥10k)", "Not popular", "N/A"], key="pop_sel")

    filtered = df.copy()
    if search:
        mask = (
            filtered["Artists"].str.contains(search, case=False, na=False) |
            filtered["Event"].str.contains(search, case=False, na=False) |
            filtered["Venue"].str.contains(search, case=False, na=False) |
            filtered["City"].str.contains(search, case=False, na=False)
        )
        filtered = filtered[mask]
    if country_sel != "All":
        filtered = filtered[filtered["Country Name"] == country_sel]
    if pop_sel == "Popular (≥10k)":
        filtered = filtered[filtered["Popular"] == "Yes"]
    elif pop_sel == "Not popular":
        filtered = filtered[filtered["Popular"] == "No"]
    elif pop_sel == "N/A":
        filtered = filtered[filtered["Popular"] == "N/A"]

    st.caption(f"{len(filtered)} concerts")

    # Display as styled table
    display_df = filtered[["Date", "Time", "Event", "Artists", "Venue", "City", "Artist Country", "Country Name", "Fans", "Popular", "Tags", "Genres"]].copy()
    display_df["Date"] = display_df["Date"].dt.strftime("%Y-%m-%d")
    display_df["Fans"] = display_df["Fans"].apply(lambda x: f"{x:,.0f}" if pd.notnull(x) else "N/A")

    st.dataframe(
        display_df,
        use_container_width=True,
        height=600,
        column_config={
            "Date": st.column_config.TextColumn("Date", width="small"),
            "Time": st.column_config.TextColumn("Time", width="small"),
            "Event": st.column_config.TextColumn("Event", width="medium"),
            "Artists": st.column_config.TextColumn("Artists", width="medium"),
            "Venue": st.column_config.TextColumn("Venue", width="medium"),
            "City": st.column_config.TextColumn("City", width="small"),
            "Artist Country": st.column_config.TextColumn("Origin", width="small"),
            "Country Name": st.column_config.TextColumn("Country", width="small"),
            "Fans": st.column_config.TextColumn("Fans", width="small"),
            "Popular": st.column_config.TextColumn("Popular", width="small"),
            "Tags": st.column_config.TextColumn("Tags", width="medium"),
            "Genres": st.column_config.TextColumn("Genres", width="small"),
        },
    )

    # Download button
    csv = filtered.to_csv(index=False).encode("utf-8")
    st.download_button("📥 Download CSV", csv, "concerts_sweden.csv", "text/csv")
