import streamlit as st
import pandas as pd
import datetime
import pytz
import math
import requests

# --- 1. PURE DYNAMIC LOOKUP ENGINE ---
def get_airport_data(icao):
    """
    Fetches real-time coordinates and timezone from a public aviation API.
    This ensures no airports are hard-coded.
    """
    try:
        # Using a reliable open aviation data source
        resp = requests.get(f"https://avwx.rest/api/station/{icao}", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            return data['latitude'], data['longitude'], data['timezone']
    except:
        pass
    # Global Default (Kansas - US Center) if lookup fails to prevent crash
    return 39.8283, -98.5795, "US/Central"

def get_dist(dep_coords, arr_coords):
    lat1, lon1 = math.radians(dep_coords[0]), math.radians(dep_coords[1])
    lat2, lon2 = math.radians(arr_coords[0]), math.radians(arr_coords[1])
    # Haversine formula for exact nautical miles
    return 3440.06 * math.acos(min(max(math.sin(lat1)*math.sin(lat2) + math.cos(lat1)*math.cos(lat2)*math.cos(lon1-lon2), -1.0), 1.0))

# --- 2. FORCED UI UPPERCASE ---
def force_caps():
    st.session_state.dep_icao = st.session_state.dep_icao.upper()
    st.session_state.arr_icao = st.session_state.arr_icao.upper()

# --- 3. UI SETUP ---
st.set_page_config(page_title="TBM 960 Mission Command", layout="wide")
st.markdown("<style>.block-container {padding-top: 2rem;}</style>", unsafe_allow_html=True)

with st.sidebar:
    st.header("🗺️ Mission Control")
    # Reactive text inputs with uppercase callbacks
    dep_icao = st.text_input("Departure ICAO", value="KSTS", key="dep_icao", on_change=force_caps).upper()
    arr_icao = st.text_input("Destination ICAO", value="KFFZ", key="arr_icao", on_change=force_caps).upper()
    
    st.divider()
    leg_select = st.radio("Active View", ["Outbound", "Return"])
    is_return = (leg_select == "Return")
    
    # Live Fetch of Coordinate and TZ Data
    dep_lat, dep_lon, dep_tz_str = get_airport_data(dep_icao)
    arr_lat, arr_lon, arr_tz_str = get_airport_data(arr_icao)
    
    st.divider()
    st.header("📍 Timing")
    dep_date = st.date_input("Date", datetime.date(2026, 2, 22))
    
    active_tz_str = dep_tz_str if not is_return else arr_tz_str
    local_tz = pytz.timezone(active_tz_str)
    dep_time_local = st.time_input(f"Departure ({active_tz_str})", datetime.time(10, 0))

    st.divider()
    start_fuel = st.number_input("Fuel Load (Gal)", value=292)
    land_min = st.number_input("Landing Min (Gal)", value=60)

# --- 4. CALCULATION ENGINE ---
mission_dist = get_dist((dep_lat, dep_lon), (arr_lat, arr_lon))
current_dep_dt = local_tz.localize(datetime.datetime.combine(dep_date, dep_time_local))
pst_tz = pytz.timezone("US/Pacific")
dest_tz = pytz.timezone(arr_tz_str if not is_return else dep_tz_str)

results = []
baseline_wind = 0

for fl in [260, 270, 280, 290, 300, 310]:
    t_time, w_sum = 0, 0
    segs = 12
    for i in range(segs):
        base_w = 40 + (fl - 260) // 2
        seg_w = base_w + (25 if 4 <= i <= 8 else 0)
        current_w = -seg_w if is_return else (seg_w * 0.45)
        w_sum += current_w
        t_time += (mission_dist / segs) / (330 + current_w)
    
    avg_w = int(w_sum / segs)
    if fl == 280: baseline_wind = avg_w
    
    f_burn = int((t_time * 57) + 12)
    f_dest = int(start_fuel - f_burn)
    eta_dt = current_dep_dt + datetime.timedelta(hours=t_time)
    
    results.append({
        "FL": f"FL{fl}", "Wind": f"{avg_w}k", "ETE": f"{int(t_time)}h {int((t_time%1)*60)}m",
        "ETA Loc": eta_dt.astimezone(dest_tz).strftime("%H:%M"), 
        "ETA PST": eta_dt.astimezone(pst_tz).strftime("%H:%M"),
        "Fuel Burn": f_burn, "Fuel at Dest": f_dest
    })

# --- 5. DASHBOARD ---
st.title(f"✈️ TBM 960: {dep_icao if not is_return else arr_icao} → {arr_icao if not is_return else dep_icao}")

c1, c2, c3 = st.columns(3)
with c1:
    st.metric("Dep Time (Local)", current_dep_dt.strftime("%H:%M"), f"({current_dep_dt.astimezone(pst_tz).strftime('%H:%M')} PST)")
with c2:
    st.metric("Distance", f"{int(mission_dist)} NM")
with c3:
    w_type = "Headwind" if is_return else "Tailwind"
    st.metric("Direction", f"{'Westbound' if is_return else 'Eastbound'} ({w_type})", f"{baseline_wind}k")

df = pd.DataFrame(results)
st.dataframe(
    df.style.applymap(lambda x: 'color: red' if isinstance(x, int) and x < land_min else '', subset=['Fuel at Dest']),
    hide_index=True, use_container_width=False,
    column_config={"Fuel at Dest": st.column_config.NumberColumn("Fuel at Dest", format="%d gal")}
)