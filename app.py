import streamlit as st
import requests
import time
import pandas as pd
from datetime import datetime, timedelta

st.set_page_config(page_title="Sweden Concert Radar", page_icon="🎵", layout="wide")

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
    "JM": "Jamaica", "TT": "Trinidad", "PR": "Puerto Rico", "CO": "Colombia",
}

COUNTRY_FLAGS = {
    "SE": "🇸🇪", "US": "🇺🇸", "GB": "🇬🇧", "JP": "🇯🇵", "DE": "🇩🇪",
    "KR": "🇰🇷", "FR": "🇫🇷", "BR": "🇧🇷", "AU": "🇦🇺", "CA": "🇨🇦",
    "NO": "🇳🇴", "DK": "🇩🇰", "FI": "🇫🇮", "NL": "🇳🇱", "IT": "🇮🇹",
    "ES": "🇪🇸", "IE": "🇮🇪", "AT": "🇦🇹", "CH": "🇨🇭", "BE": "🇧🇪",
    "NZ": "🇳🇿", "PT": "🇵🇹", "PL": "🇵🇱", "CZ": "🇨🇿", "MX": "🇲🇽",
    "AR": "🇦🇷", "ZA": "🇿🇦", "IS": "🇮🇸", "JM": "🇯🇲", "CO": "🇨🇴",
}

def cn(code):
    if not code or code == "N/A":
        return "Unknown"
    return COUNTRY_NAMES.get(code, code)

def flag(code):
    return COUNTRY_FLAGS.get(code, "🌍")

def fmt_price(mn, mx, cur):
    if mn is None:
        return None
    cur = cur or "SEK"
    if mx and mx != mn:
        return f"{cur} {mn:.0f}–{mx:.0f}"
    return f"from {cur} {mn:.0f}"


# ── Styling ──
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;700&family=Playfair+Display:wght@400;700&display=swap');

    .block-container { padding-top: 1.5rem; max-width: 1200px; }

    h1 { font-family: 'Playfair Display', serif !important; font-weight: 700 !important; }
    h2, h3 { font-family: 'DM Sans', sans-serif !important; font-weight: 600 !important; }

    div[data-testid="stMetric"] {
        background: linear-gradient(135deg, #16161a 0%, #1a1a2e 100%);
        border: 1px solid #2a2a3d;
        border-radius: 12px;
        padding: 18px 20px;
    }
    div[data-testid="stMetric"] label { color: #8888aa !important; font-size: 13px !important; }
    div[data-testid="stMetric"] [data-testid="stMetricValue"] { color: #e2e2f0 !important; }

    .highlight-card {
        background: linear-gradient(135deg, #16161a 0%, #1a1a2e 100%);
        border: 1px solid #2a2a3d;
        border-radius: 14px;
        padding: 18px 22px;
        margin-bottom: 10px;
        transition: border-color 0.2s;
    }
    .highlight-card:hover { border-color: #4a4a6d; }

    .highlight-card .date {
        font-size: 12px;
        color: #6c72cb;
        font-weight: 600;
        letter-spacing: 0.05em;
        text-transform: uppercase;
    }
    .highlight-card .event-name {
        font-size: 17px;
        font-weight: 700;
        color: #e8e8f0;
        margin: 4px 0;
        font-family: 'DM Sans', sans-serif;
    }
    .highlight-card .venue {
        font-size: 13px;
        color: #7a7a99;
    }
    .highlight-card .artist-info {
        margin-top: 8px;
        display: flex;
        align-items: center;
        gap: 8px;
        flex-wrap: wrap;
    }
    .highlight-card .artist-tag {
        display: inline-block;
        background: #252540;
        border: 1px solid #35355a;
        border-radius: 20px;
        padding: 3px 12px;
        font-size: 12px;
        color: #b8b8d0;
    }
    .highlight-card .fans-badge {
        display: inline-block;
        background: linear-gradient(135deg, #6c72cb22, #cb69c122);
        border: 1px solid #6c72cb44;
        border-radius: 20px;
        padding: 3px 10px;
        font-size: 11px;
        color: #a8a0d0;
        font-weight: 600;
    }
    .highlight-card .genre-tag {
        display: inline-block;
        font-size: 10px;
        color: #cb69c1;
        background: #2a1a2a;
        border-radius: 4px;
        padding: 2px 7px;
        margin: 1px 3px 1px 0;
    }
    .highlight-card.popular { border-left: 3px solid #6c72cb; }

    .top-artist-row {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 10px 0;
        border-bottom: 1px solid #1f1f33;
    }
    .top-artist-row .rank {
        font-size: 22px;
        font-weight: 700;
        color: #35355a;
        min-width: 32px;
        text-align: right;
        font-family: 'Playfair Display', serif;
    }
    .top-artist-row .rank.gold { color: #d4a843; }
    .top-artist-row .rank.silver { color: #8888aa; }
    .top-artist-row .rank.bronze { color: #a0705a; }
    .top-artist-row .name {
        font-size: 15px;
        font-weight: 600;
        color: #e2e2f0;
        flex: 1;
    }
    .top-artist-row .meta {
        font-size: 12px;
        color: #7a7a99;
    }
    .top-artist-row .fan-count {
        font-size: 13px;
        font-weight: 700;
        color: #6c72cb;
        min-width: 80px;
        text-align: right;
    }

    .summary-line {
        font-size: 15px;
        color: #b0b0cc;
        padding: 6px 0;
        line-height: 1.6;
    }
    .summary-line strong { color: #e2e2f0; }
    .summary-line .accent { color: #6c72cb; font-weight: 700; }
    .summary-line .pink { color: #cb69c1; font-weight: 700; }

    section[data-testid="stSidebar"] { background: #12121a; }

    .highlight-card .price-badge {
        display: inline-block;
        background: #1a2a1a;
        border: 1px solid #3a5a3a;
        border-radius: 20px;
        padding: 3px 10px;
        font-size: 11px;
        color: #80c080;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)


# ── Data fetching ──
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_concerts():
    all_events = []
    page = 0
    total_pages = 1

    while page < total_pages and page < 10:
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

        prices = e.get("priceRanges", [])
        price_min = prices[0].get("min") if prices else None
        price_max = prices[0].get("max") if prices else None
        price_currency = prices[0].get("currency", "SEK") if prices else None

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
            "price_min": price_min,
            "price_max": price_max,
            "price_currency": price_currency,
        })
    return rows


@st.cache_data(ttl=86400, show_spinner=False)
def enrich_artist(name):
    info = {
        "country": None, "country_name": "Unknown", "tags": [],
        "genres": [], "fans": None, "is_popular": None, "is_real_artist": False,
    }

    # Deezer first — also validates it's a real artist
    try:
        res = requests.get(
            "https://api.deezer.com/search/artist",
            params={"q": name, "limit": 1},
            timeout=10,
        )
        data = res.json().get("data", [])
        if data:
            da = data[0]
            # Check name similarity to filter false matches
            if name.lower() in da.get("name", "").lower() or da.get("name", "").lower() in name.lower():
                info["is_real_artist"] = True
                info["fans"] = da.get("nb_fan", 0)
                info["is_popular"] = info["fans"] >= POPULAR_THRESHOLD if info["fans"] is not None else None

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

    # MusicBrainz for country + tags
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
            if a.get("score", 0) >= 80:
                info["country"] = a.get("country") or None
                info["country_name"] = cn(info["country"])
                info["tags"] = sorted(
                    a.get("tags", []), key=lambda x: x.get("count", 0), reverse=True
                )[:4]
                info["tags"] = [t["name"] for t in info["tags"]]
                if not info["is_real_artist"] and a.get("type") in ("Person", "Group"):
                    info["is_real_artist"] = True
    except Exception:
        pass

    time.sleep(1.1)
    return info


# ── Main App ──
st.markdown("# 🎵 Sweden Concert Radar")
st.caption("Upcoming concerts in Sweden • Artist origins, genres & popularity")

with st.spinner("Loading concerts from Ticketmaster..."):
    concerts = fetch_concerts()

if not concerts:
    st.warning("No concerts found.")
    st.stop()

# Unique artists
all_artist_names = list(dict.fromkeys(a for c in concerts for a in c["artists"] if a))

# Enrich
artist_data = {}
total = len(all_artist_names)
if total > 0:
    progress_text = st.empty()
    progress_bar = st.empty()
    progress_text.caption(f"Enriching {total} artists with country, genre & fan data...")
    bar = progress_bar.progress(0)
    for i, name in enumerate(all_artist_names):
        artist_data[name] = enrich_artist(name)
        bar.progress((i + 1) / total)
    progress_text.empty()
    progress_bar.empty()

# Filter out non-real artists
real_artists = {k: v for k, v in artist_data.items() if v.get("is_real_artist")}
fake_names = set(artist_data.keys()) - set(real_artists.keys())

# Clean concerts — remove fake artist names
clean_concerts = []
for c in concerts:
    cleaned = [a for a in c["artists"] if a not in fake_names]
    if cleaned or c["artists"]:  # keep concert even if no verified artist
        clean_concerts.append({**c, "artists": cleaned if cleaned else c["artists"]})
concerts = clean_concerts

# Stats
now = datetime.now()
popular_artists = {k: v for k, v in real_artists.items() if v.get("is_popular")}
not_popular_artists = {k: v for k, v in real_artists.items() if v.get("is_popular") is False}
na_artists_count = len(all_artist_names) - len(real_artists)

# Country counts
country_counts = {}
for v in real_artists.values():
    c = v.get("country") or "N/A"
    country_counts[c] = country_counts.get(c, 0) + 1

# ── TABS ──
tab_next30, tab_dash, tab_highlights, tab_concerts = st.tabs([
    f"📅 Next 30 Days",
    f"📊 Dashboard",
    f"🔥 Highlights & Top Artists",
    f"🎵 All Concerts ({len(concerts)})",
])


# ═══════════════════════════════════════════
# NEXT 30 DAYS
# ═══════════════════════════════════════════
with tab_next30:
    today_str = now.strftime("%Y-%m-%d")
    cutoff_str = (now + timedelta(days=30)).strftime("%Y-%m-%d")
    next30 = [c for c in concerts if c["date"] and today_str <= c["date"] <= cutoff_str]
    next30_popular = [c for c in next30 if any(real_artists.get(a, {}).get("is_popular") for a in c["artists"])]
    next30_priced = [c for c in next30 if c.get("price_min") is not None]

    n1, n2, n3, n4 = st.columns(4)
    n1.metric("Concerts", len(next30))
    n2.metric("With popular artists", len(next30_popular))
    n3.metric("Cities", len(set(c["city"] for c in next30)))
    cheapest = min((c["price_min"] for c in next30_priced), default=None)
    n4.metric("Cheapest ticket", f"{next30_priced[0]['price_currency'] if next30_priced else 'SEK'} {cheapest:.0f}" if cheapest else "—")

    st.markdown("---")

    # Build table for next 30 days
    n30_rows = []
    for c in sorted(next30, key=lambda x: x["date"]):
        primary = c["artists"][0] if c["artists"] else ""
        info = real_artists.get(primary, {})
        max_fans = max((real_artists.get(a, {}).get("fans") or 0 for a in c["artists"]), default=0)
        price_str = fmt_price(c.get("price_min"), c.get("price_max"), c.get("price_currency"))
        n30_rows.append({
            "Date": c["date"],
            "Event": c["event"],
            "Artists": ", ".join(c["artists"]),
            "Venue": c["venue"],
            "City": c["city"],
            "Price": price_str if price_str else "—",
            "Fans": max_fans if max_fans else None,
            "Popular": "⭐" if any(real_artists.get(a, {}).get("is_popular") for a in c["artists"]) else "",
            "Origin": f'{flag(info.get("country"))} {info.get("country_name", "?")}' if info else "?",
            "Tickets": c["url"],
        })

    if n30_rows:
        n30_df = pd.DataFrame(n30_rows)
        n30_df["Fans"] = n30_df["Fans"].apply(lambda x: f"{x:,.0f}" if pd.notnull(x) and x else "—")
        st.dataframe(
            n30_df[["Date", "Event", "Artists", "Venue", "City", "Price", "Fans", "Popular", "Origin"]],
            use_container_width=True,
            height=600,
            column_config={
                "Date": st.column_config.TextColumn("📅 Date", width="small"),
                "Event": st.column_config.TextColumn("Event", width="medium"),
                "Artists": st.column_config.TextColumn("Artists", width="medium"),
                "Venue": st.column_config.TextColumn("Venue", width="medium"),
                "City": st.column_config.TextColumn("City", width="small"),
                "Price": st.column_config.TextColumn("🎟️ Price", width="small"),
                "Fans": st.column_config.TextColumn("Fans", width="small"),
                "Popular": st.column_config.TextColumn("⭐", width="small"),
                "Origin": st.column_config.TextColumn("Origin", width="small"),
            },
        )
    else:
        st.info("No concerts in the next 30 days.")


# ═══════════════════════════════════════════
# DASHBOARD
# ═══════════════════════════════════════════
with tab_dash:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Concerts", len(concerts))
    c2.metric("Verified Artists", len(real_artists))
    c3.metric("Popular Artists", len(popular_artists), help="≥ 10,000 Deezer fans")
    c4.metric("Emerging / N/A", f"{len(not_popular_artists)} / {na_artists_count}")

    st.markdown("")

    # This month
    this_month = [c for c in concerts if c["date"] and
                  datetime.strptime(c["date"], "%Y-%m-%d").month == now.month and
                  datetime.strptime(c["date"], "%Y-%m-%d").year == now.year]

    if this_month:
        st.subheader(f"📅 This Month — {now.strftime('%B %Y')}")
        tm_artists = list(dict.fromkeys(a for c in this_month for a in c["artists"] if a in real_artists))
        tm_countries = {}
        for a in tm_artists:
            c_code = real_artists[a].get("country") or "N/A"
            c_name = cn(c_code)
            tm_countries[c_name] = tm_countries.get(c_name, 0) + 1
        tm_sorted = sorted(tm_countries.items(), key=lambda x: x[1], reverse=True)[:6]

        cols = st.columns(2 + len(tm_sorted))
        cols[0].metric("Concerts", len(this_month))
        cols[1].metric("Artists", len(tm_artists))
        for i, (country, count) in enumerate(tm_sorted):
            cols[i + 2].metric(f"From {country}", count)

    st.markdown("---")

    # Two columns
    col_l, col_r = st.columns(2)

    with col_l:
        st.subheader("🌍 Artists by Country of Origin")
        sorted_countries = sorted(country_counts.items(), key=lambda x: x[1], reverse=True)
        sorted_countries = [(c, n) for c, n in sorted_countries if c != "N/A"][:15]

        if sorted_countries:
            labels = [f"{flag(c)} {cn(c)}" for c, _ in sorted_countries]
            values = [n for _, n in sorted_countries]
            chart_df = pd.DataFrame({"Country": labels, "Artists": values})
            chart_df = chart_df.set_index("Country").sort_values("Artists", ascending=True)
            st.bar_chart(chart_df, horizontal=True, color="#6c72cb")

    with col_r:
        st.subheader("🏷️ Top Genres & Tags")
        tag_counter = {}
        for a in real_artists.values():
            for t in list(a.get("tags", [])) + list(a.get("genres", [])):
                key = t.lower()
                tag_counter[key] = tag_counter.get(key, 0) + 1
        if tag_counter:
            tag_sorted = sorted(tag_counter.items(), key=lambda x: x[1], reverse=True)[:15]
            tag_df = pd.DataFrame(tag_sorted, columns=["Genre", "Count"]).set_index("Genre")
            tag_df = tag_df.sort_values("Count", ascending=True)
            st.bar_chart(tag_df, horizontal=True, color="#cb69c1")

    # Monthly timeline
    st.subheader("📈 Concerts by Month")
    month_data = {}
    for c in concerts:
        if c["date"]:
            try:
                d = datetime.strptime(c["date"], "%Y-%m-%d")
                key = d.strftime("%Y-%m")
                month_data[key] = month_data.get(key, 0) + 1
            except ValueError:
                pass
    if month_data:
        month_df = pd.DataFrame(
            sorted(month_data.items()),
            columns=["Month", "Concerts"]
        ).set_index("Month")
        st.bar_chart(month_df, color="#6c72cb")

    # Quick summary
    st.subheader("📋 Summary")
    sorted_c = sorted(country_counts.items(), key=lambda x: x[1], reverse=True)
    lines = []
    for code, count in sorted_c[:8]:
        if code != "N/A":
            lines.append(f'<span class="accent">{count}</span> artists from <strong>{flag(code)} {cn(code)}</strong>')
    lines.append(f'<span class="accent">{len(popular_artists)}</span> popular artists (≥ 10k fans)')
    lines.append(f'<span class="pink">{len(not_popular_artists)}</span> emerging / smaller artists')
    lines.append(f'{na_artists_count} unverified or non-artist entries filtered out')

    for line in lines:
        st.markdown(f'<div class="summary-line">• {line}</div>', unsafe_allow_html=True)

    st.caption(f"Last updated: {now.strftime('%Y-%m-%d %H:%M')} • Data from Ticketmaster, MusicBrainz & Deezer")


# ═══════════════════════════════════════════
# HIGHLIGHTS & TOP ARTISTS
# ═══════════════════════════════════════════
with tab_highlights:
    hl_col1, hl_col2 = st.columns([3, 2])

    with hl_col1:
        st.subheader("🔥 Upcoming Big Concerts")
        st.caption("Concerts with popular artists (≥ 10k fans), sorted by date")

        # Get concerts with popular artists
        big_concerts = []
        for c in concerts:
            max_fans = 0
            pop_names = []
            for a in c["artists"]:
                info = real_artists.get(a)
                if info and info.get("is_popular"):
                    pop_names.append(a)
                    if (info.get("fans") or 0) > max_fans:
                        max_fans = info["fans"] or 0
            if pop_names:
                big_concerts.append({**c, "max_fans": max_fans, "popular_artists": pop_names})

        big_concerts.sort(key=lambda x: x["date"])

        for c in big_concerts[:20]:
            tags_all = set()
            for a in c["artists"]:
                info = real_artists.get(a, {})
                tags_all.update(info.get("tags", []))
                tags_all.update(info.get("genres", []))

            artist_chips = ""
            for a in c["artists"]:
                info = real_artists.get(a, {})
                f_str = flag(info.get("country", ""))
                fans = info.get("fans")
                fan_str = f'<span class="fans-badge">{fans:,.0f} fans</span>' if fans else ""
                artist_chips += f'<span class="artist-tag">{f_str} {a}</span> {fan_str} '

            tag_chips = ""
            for t in list(tags_all)[:5]:
                tag_chips += f'<span class="genre-tag">{t}</span>'

            price_label = fmt_price(c.get("price_min"), c.get("price_max"), c.get("price_currency"))
            price_html = f'<span class="price-badge">🎟️ {price_label}</span>' if price_label else ""

            st.markdown(f"""
            <div class="highlight-card popular">
                <div class="date">{c["date"]} • {c["time"][:5] if c["time"] else ""} {price_html}</div>
                <div class="event-name">{c["event"]}</div>
                <div class="venue">📍 {c["venue"]}, {c["city"]}</div>
                <div class="artist-info">{artist_chips}</div>
                <div style="margin-top:6px">{tag_chips}</div>
            </div>
            """, unsafe_allow_html=True)

        if not big_concerts:
            st.info("No concerts with popular artists found.")

    with hl_col2:
        st.subheader("⭐ Top Artists Coming to Sweden")
        st.caption("Ranked by Deezer fan count")

        # Sort real artists by fans
        artists_with_fans = [
            (name, info) for name, info in real_artists.items()
            if info.get("fans") and info["fans"] > 0
        ]
        artists_with_fans.sort(key=lambda x: x[1]["fans"], reverse=True)

        for i, (name, info) in enumerate(artists_with_fans[:25]):
            rank_class = "gold" if i < 1 else "silver" if i < 3 else "bronze" if i < 5 else ""
            c_flag = flag(info.get("country", ""))
            c_name = info.get("country_name", "Unknown")
            fans = info.get("fans", 0)
            tags = ", ".join(info.get("tags", [])[:2])

            st.markdown(f"""
            <div class="top-artist-row">
                <div class="rank {rank_class}">{i+1}</div>
                <div class="name">{c_flag} {name}</div>
                <div class="meta">{c_name} • {tags}</div>
                <div class="fan-count">{fans:,.0f}</div>
            </div>
            """, unsafe_allow_html=True)

        if not artists_with_fans:
            st.info("No artist data yet.")



# ═══════════════════════════════════════════
# ALL CONCERTS TABLE
# ═══════════════════════════════════════════
with tab_concerts:
    fc1, fc2, fc3 = st.columns([3, 1, 1])
    with fc1:
        search = st.text_input("🔍 Search artist, venue, city...", key="search")
    with fc2:
        all_country_names = sorted(set(
            real_artists[a].get("country_name", "Unknown")
            for c in concerts for a in c["artists"] if a in real_artists
        ))
        country_sel = st.selectbox("Country", ["All"] + all_country_names, key="country_sel")
    with fc3:
        pop_sel = st.selectbox("Popularity", ["All", "Popular (≥10k)", "Emerging (<10k)", "Unknown"], key="pop_sel")

    # Build dataframe
    rows = []
    for c in concerts:
        primary = c["artists"][0] if c["artists"] else ""
        info = real_artists.get(primary, {})
        all_tags = set()
        all_genres = set()
        max_fans = 0
        for a in c["artists"]:
            ai = real_artists.get(a, {})
            all_tags.update(ai.get("tags", []))
            all_genres.update(ai.get("genres", []))
            f = ai.get("fans") or 0
            if f > max_fans:
                max_fans = f

        price_str = fmt_price(c.get("price_min"), c.get("price_max"), c.get("price_currency"))
        rows.append({
            "Date": c["date"],
            "Time": c["time"][:5] if c["time"] else "",
            "Event": c["event"],
            "Artists": ", ".join(c["artists"]),
            "Venue": c["venue"],
            "City": c["city"],
            "Origin": f'{flag(info.get("country"))} {info.get("country_name", "?")}' if info else "?",
            "Country Name": info.get("country_name", "Unknown") if info else "Unknown",
            "Fans": max_fans if max_fans else None,
            "Popular": "Yes" if any(real_artists.get(a, {}).get("is_popular") for a in c["artists"]) else (
                "No" if any(a in real_artists for a in c["artists"]) else "Unknown"
            ),
            "Price": price_str if price_str else "—",
            "Tags": ", ".join(all_tags) if all_tags else "",
            "Genres": ", ".join(all_genres) if all_genres else "",
            "Tickets": c["url"],
        })

    df = pd.DataFrame(rows)

    # Apply filters
    if search:
        mask = (
            df["Artists"].str.contains(search, case=False, na=False) |
            df["Event"].str.contains(search, case=False, na=False) |
            df["Venue"].str.contains(search, case=False, na=False) |
            df["City"].str.contains(search, case=False, na=False)
        )
        df = df[mask]
    if country_sel != "All":
        df = df[df["Country Name"] == country_sel]
    if pop_sel == "Popular (≥10k)":
        df = df[df["Popular"] == "Yes"]
    elif pop_sel == "Emerging (<10k)":
        df = df[df["Popular"] == "No"]
    elif pop_sel == "Unknown":
        df = df[df["Popular"] == "Unknown"]

    st.caption(f"{len(df)} concerts")

    display = df[["Date", "Time", "Event", "Artists", "Venue", "City", "Origin", "Fans", "Popular", "Price", "Tags", "Genres"]].copy()
    display["Fans"] = display["Fans"].apply(lambda x: f"{x:,.0f}" if pd.notnull(x) and x else "—")

    st.dataframe(
        display,
        use_container_width=True,
        height=600,
        column_config={
            "Date": st.column_config.TextColumn("📅 Date", width="small"),
            "Time": st.column_config.TextColumn("⏰", width="small"),
            "Event": st.column_config.TextColumn("Event", width="medium"),
            "Artists": st.column_config.TextColumn("Artists", width="medium"),
            "Venue": st.column_config.TextColumn("Venue", width="medium"),
            "City": st.column_config.TextColumn("City", width="small"),
            "Origin": st.column_config.TextColumn("Origin", width="small"),
            "Fans": st.column_config.TextColumn("Fans", width="small"),
            "Popular": st.column_config.TextColumn("Pop?", width="small"),
            "Price": st.column_config.TextColumn("🎟️ Price", width="small"),
            "Tags": st.column_config.TextColumn("Tags", width="medium"),
            "Genres": st.column_config.TextColumn("Genres", width="small"),
        },
    )

    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("📥 Download CSV", csv, "concerts_sweden.csv", "text/csv")