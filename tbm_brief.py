import streamlit as st
import pandas as pd
import datetime
import pytz
import math

# --- 1. COORDINATE DATABASE & DISTANCE ENGINE ---
# Real-world coordinates for accurate mission distance
AIRPORTS = {
    "KSTS": (38.5089, -122.8128, "US/Pacific"),
    "KFFZ": (33.4608, -111.7283, "US/Mountain"),
    "KJFK": (40.6413, -73.7781, "US/Eastern"),
    "KSDL": (33.6228, -111.9105, "US/Mountain"),
    "KDEN": (39.8561, -104.6737, "US/Mountain")
}

def get_distance(dep, arr):
    if dep not in AIRPORTS or arr not in AIRPORTS: return 580 # Default if unknown
    lat1, lon1 = math.radians(AIRPORTS[dep][0]), math.radians(AIRPORTS[dep][1])
    lat2, lon2 = math.radians(AIRPORTS[arr][0]), math.radians(AIRPORTS[arr][1])
    return 3440.06 * math.acos(math.sin(lat1)*math.sin(lat2) + math.cos(lat1)*math.cos(lat2)*math.cos(lon1-lon2))

# --- 2. DYNAMIC WEATHER ENGINE (SEGMENTED) ---
def get_live_segmented_wind(fl, is_return, seg_idx, total_segs):
    # Simulated jetstream core for Feb 22, 2026
    base_jet = 45 + (fl - 260) // 1.5
    # Mountain wave effect peaks mid-flight (Sierras)
    mountain_wave = 30 * math.sin(math.pi * (seg_idx / total_segs))
    total_w = base_jet + mountain_wave
    return -total_w if is_return else (total_w * 0.45)

# --- 3. UI SETUP ---
st.set_page_config(page_title="TBM 960 Mission Command", layout="wide")
st.markdown("<style>.block-container {padding-top: 2rem;}</style>", unsafe_allow_html=True)

# SIDEBAR: REACTIVE INPUTS
with st.sidebar:
    st.header("🗺️ Mission Control")
    # Instant Uppercase Conversion
    dep_icao = st.text_input("Departure ICAO", value="KSTS").upper()
    arr_icao = st.text_input("Destination ICAO", value="KFFZ").upper()
    
    if dep_icao not in AIRPORTS or arr_icao not in AIRPORTS:
        st.warning(f"Note: {dep_icao if dep_icao not in AIRPORTS else arr_icao} coordinates not in DB. Using default 580NM.")
    
    st.divider()
    leg_select = st.radio("Active View", ["Outbound", "Return"])
    is_return = (leg_select == "Return")
    
    st.divider()
    st.header("📍 Timing")
    dep_date = st.date_input("Date", datetime.date(2026, 2, 22))
    
    # Timezone Logic
    dep_tz_str = AIRPORTS.get(dep_icao if not is_return else arr_icao, [0,0,"US/Pacific"])[2]
    dep_tz = pytz.timezone(dep_tz_str)
    dep_time_local = st.time_input(f"Departure ({dep_tz_str})", datetime.time(10, 0))

    st.divider()
    quick_turn = st.checkbox("Quick Turn (30m)", value=True)
    turn_h = st.number_input("Custom Turn (H)", 0, 24, 1) if not quick_turn else 0.5
    
    st.divider()
    start_fuel = st.number_input("Fuel Load (Gal)", value=292)
    land_min = st.number_input("Landing Min (Gal)", value=60)

# --- 4. CORE MISSION CALCULATIONS ---
# Calculate Distance
mission_dist = get_distance(dep_icao if not is_return else arr_icao, arr_icao if not is_return else dep_icao)

# Departure Time Setup
current_dep_dt = dep_tz.localize(datetime.datetime.combine(dep_date, dep_time_local))
pst_tz = pytz.timezone("US/Pacific")
dest_tz_str = AIRPORTS.get(arr_icao if not is_return else dep_icao, [0,0,"US/Pacific"])[2]
dest_tz = pytz.timezone(dest_tz_str)

# Build Table
results = []
baseline_avg_wind = 0
for fl in [260, 270, 280, 290, 300, 310]:
    t_time, w_sum = 0, 0
    segs = 15
    for i in range(segs):
        w = get_live_segmented_wind(fl, is_return, i, segs)
        w_sum += w
        t_time += (mission_dist / segs) / (330 + w)
    
    avg_w = int(w_sum / segs)
    if fl == 280: baseline_avg_wind = avg_w
    
    f_burn = int((t_time * 57) + 12)
    f_dest = start_fuel - f_burn
    eta_dt = current_dep_dt + datetime.timedelta(hours=t_time)
    
    results.append({
        "FL": f"FL{fl}", "Wind": f"{avg_w}k", "ETE": f"{int(t_time)}h {int((t_time%1)*60)}m",
        "ETA Loc": eta_dt.astimezone(dest_tz).strftime("%H:%M"), 
        "ETA PST": eta_dt.astimezone(pst_tz).strftime("%H:%M"),
        "Fuel Burn": f_burn, "Fuel at Dest": f_dest
    })

# --- 5. DASHBOARD DISPLAY ---
st.title(f"✈️ TBM 960: {dep_icao if not is_return else arr_icao} → {arr_icao if not is_return else dep_icao}")

c1, c2 = st.columns(2)
with c1:
    st.metric("Dep Time (Local)", current_dep_dt.strftime("%H:%M"), f"({current_dep_dt.astimezone(pst_tz).strftime('%H:%M')} PST)")
with c2:
    w_type = "Headwind" if is_return else "Tailwind"
    qual = "++" if abs(baseline_avg_wind) > 55 else "+" if abs(baseline_avg_wind) < 20 else ""
    st.metric("Direction", f"{'Westbound' if is_return else 'Eastbound'} ({w_type})", f"{baseline_avg_wind}k {qual}")

# Table Output with Formatting
df = pd.DataFrame(results)
st.dataframe(
    df.style.applymap(lambda x: 'color: red' if isinstance(x, int) and x < land_min else '', subset=['Fuel at Dest']),
    use_container_width=False, hide_index=True,
    column_config={
        "FL": st.column_config.TextColumn("FL", width=50),
        "Wind": st.column_config.TextColumn("Wind", width=60),
        "ETE": st.column_config.TextColumn("ETE", width=80),
        "ETA Loc": st.column_config.TextColumn("ETA Loc", width=80),
        "ETA PST": st.column_config.TextColumn("ETA PST", width=80),
        "Fuel Burn": st.column_config.NumberColumn("Fuel Burn", width=90),
        "Fuel at Dest": st.column_config.NumberColumn("Fuel at Dest", width=100),
    }
)

if results[0]['Fuel at Dest'] < 0:
    st.error(f"🚨 MISSION IMPOSSIBLE: Calculated burn ({results[0]['Fuel Burn']}g) exceeds fuel on board ({start_fuel}g). Plan fuel stop.")