import streamlit as st
import pandas as pd
import datetime
import pytz

# --- PERFORMANCE & CONSTANTS ---
PERF = {"tas": 330, "burn": 57, "climb_penalty": 12}
KSTS_TZ = pytz.timezone('US/Pacific')
KFFZ_TZ = pytz.timezone('US/Mountain') # Arizona (No DST)

def get_segmented_wind(fl, is_return, segment_index):
    # Simulated Feb 22 Jetstream behavior
    base = 40 + (fl - 260) // 2
    mountain = 25 if 4 <= segment_index <= 8 else 0
    total = base + mountain
    # Negative for headwind (Return), Positive for tailwind (Outbound)
    return -total if is_return else (total * 0.4)

def get_wind_qualifier(wind):
    abs_w = abs(wind)
    if abs_w > 55: return "++" if wind > 0 else "--" # Heavy
    if abs_w < 20: return "+" if wind > 0 else "-"   # Light
    return "" # Average (No marking)

# --- UI CONFIG ---
st.set_page_config(page_title="TBM 960 Tactical Brief", layout="wide")
st.markdown("<style>.block-container {padding-top: 1rem;}</style>", unsafe_allow_html=True)

# SIDEBAR: MISSION CONFIG
with st.sidebar:
    st.header("🗺️ Mission Control")
    # Leg selector moved to top as requested
    leg_select = st.radio("Active View", ["Outbound: KSTS -> KFFZ", "Return: KFFZ -> KSTS"])
    is_return = "Return" in leg_select
    
    st.divider()
    st.header("📍 Mission Timing")
    
    if not is_return:
        # Outbound Leg Controls
        dep_date = st.date_input("Departure Date", datetime.date(2026, 2, 22), key="out_date")
        dep_time_local = st.time_input("Departure (Local KSTS)", datetime.time(10, 0), key="out_time")
    else:
        # Return Leg - Auto-calculated based on Outbound Arrival
        out_dep_pst = KSTS_TZ.localize(datetime.datetime.combine(datetime.date(2026, 2, 22), datetime.time(10, 0)))
        
        # Calculate base arrival at KFFZ (using FL280 as baseline)
        out_ete_base = 0
        for i in range(12):
            gs = PERF["tas"] + get_segmented_wind(280, False, i)
            out_ete_base += (580/12) / gs
        
        out_arr_pst = out_dep_pst + datetime.timedelta(hours=out_ete_base)
        
        quick_turn = st.checkbox("Quick Turn (30 min)", value=True)
        if not quick_turn:
            turn_h = st.number_input("Turn Time (Hrs)", 0, 24, 1)
            turn_m = st.number_input("Turn Time (Mins)", 0, 59, 0)
            turn_delta = datetime.timedelta(hours=turn_h, minutes=turn_m)
        else:
            turn_delta = datetime.timedelta(minutes=30)
            
        ret_dep_pst = out_arr_pst + turn_delta
        # Prefill with calculated turn-around time
        dep_date = st.date_input("Departure Date", ret_dep_pst.astimezone(KFFZ_TZ).date())
        dep_time_local = st.time_input("Departure (Local KFFZ)", ret_dep_pst.astimezone(KFFZ_TZ).time())

    st.divider()
    st.header("⛽ Fuel")
    start_fuel = st.number_input("Starting Fuel (Gal)", value=292)
    land_min = st.number_input("Landing Min (Gal)", value=60)

# --- CALCULATIONS ---
current_dep_dt = (KFFZ_TZ if is_return else KSTS_TZ).localize(datetime.datetime.combine(dep_date, dep_time_local))
current_dep_pst = current_dep_dt.astimezone(KSTS_TZ)
dest_tz = KSTS_TZ if is_return else KFFZ_TZ

# Header Logic
st.title(f"✈️ TBM 960: {leg_select}")
col_header1, col_header2 = st.columns(2)

with col_header1:
    st.metric("Dep Time (Local)", current_dep_dt.strftime("%H:%M"), f"({current_dep_pst.strftime('%H:%M')} PST)")

# Data for table and Direction header
results = []
avg_wind_all = 0
for fl in [260, 270, 280, 290, 300, 310]:
    total_time, wind_sum = 0, 0
    for i in range(12):
        w = get_segmented_wind(fl, is_return, i)
        wind_sum += w
        total_time += (580/12) / (PERF["tas"] + w)
    
    avg_w = int(wind_sum/12)
    if fl == 280: avg_wind_all = avg_w # Baseline for header summary
    
    burn = int((total_time * PERF["burn"]) + PERF["climb_penalty"])
    land_fuel = int(start_fuel - burn)
    eta_dt = current_dep_dt + datetime.timedelta(hours=total_time)
    eta_pst = eta_dt.astimezone(KSTS_TZ)
    
    results.append({
        "FL": f"FL{fl}",
        "Avg Wind": f