import streamlit as st
import pandas as pd
import datetime
import pytz

# --- PERFORMANCE & CONSTANTS ---
PERF = {"tas": 330, "burn": 57, "climb_penalty": 12}
KSTS_TZ = pytz.timezone('US/Pacific')
KFFZ_TZ = pytz.timezone('US/Mountain') 

def get_segmented_wind(fl, is_return, segment_index):
    # Simulated Jetstream behavior
    base = 40 + (fl - 260) // 2
    mountain = 25 if 4 <= segment_index <= 8 else 0
    total = base + mountain
    return -total if is_return else (total * 0.4)

def get_wind_qualifier(wind):
    abs_w = abs(wind)
    if abs_w > 55: return "++" if wind > 0 else "--"
    if abs_w < 20: return "+" if wind > 0 else "-"
    return ""

# --- UI CONFIG ---
st.set_page_config(page_title="TBM 960 Tactical Brief", layout="wide")
# Adjusted top padding to fix the header being cut off
st.markdown("""
    <style>
    .block-container {padding-top: 2rem; padding-left: 1.5rem; padding-right: 1.5rem;}
    [data-testid="stMetricValue"] {font-size: 1.5rem;}
    [data-testid="stTable"] td {padding: 2px !important;}
    </style>
    """, unsafe_allow_html=True)

# SIDEBAR
with st.sidebar:
    st.header("🗺️ Mission Control")
    # Added Airport ICAO Inputs
    dep_icao = st.text_input("Departure ICAO", "KSTS").upper()
    arr_icao = st.text_input("Destination ICAO", "KFFZ").upper()
    
    st.divider()
    leg_select = st.radio("Active View", [f"Outbound: {dep_icao} -> {arr_icao}", f"Return: {arr_icao} -> {dep_icao}"])
    is_return = "Return" in leg_select
    
    st.divider()
    st.header("📍 Mission Timing")
    
    # Baseline timing for automated calculations
    out_dep_pst_fixed = KSTS_TZ.localize(datetime.datetime.combine(datetime.date(2026, 2, 22), datetime.time(10, 0)))
    out_ete_base = 1.63 # 1h 38m
    out_arr_pst = out_dep_pst_fixed + datetime.timedelta(hours=out_ete_base)

    if not is_return:
        dep_date = st.date_input("Outbound Date", datetime.date(2026, 2, 22))
        dep_time_local = st.time_input(f"Outbound Dep ({dep_icao})", datetime.time(10, 0))
    else:
        quick_turn = st.checkbox("Quick Turn (30 min)", value=True)
        if not quick_turn:
            turn_h = st.number_input("Turn Time (Hrs)", 0, 24, 1)
            turn_m = st.number_input("Turn Time (Mins)", 0, 59, 0)
            turn_delta = datetime.timedelta(hours=turn_h, minutes=turn_m)
        else:
            turn_delta = datetime.timedelta(minutes=30)
        
        ret_calc_dt = out_arr_pst + turn_delta
        dep_date = st.date_input("Return Date", ret_calc_dt.astimezone(KFFZ_TZ).date())
        dep_time_local = st.time_input(f"Return Dep ({arr_icao})", ret_calc_dt.astimezone(KFFZ_TZ).time())

    st.divider()
    st.header("⛽ Fuel")
    start_fuel = st.number_input("Starting Fuel (Gal)", value=292)
    land_min = st.number_input("Landing Min (Gal)", value=60)

# --- CALCULATIONS ---
# Local TZ lookup based on ICAO (simplification for current version)
dep_tz = KSTS_TZ if not is_return else KFFZ_TZ
dest_tz = KFFZ_TZ if not is_return else KSTS_TZ

current_dep_dt = dep_tz.localize(datetime.datetime.combine(dep_date, dep_time_local))
current_dep_pst = current_dep_dt.astimezone(KSTS_TZ)

# DASHBOARD HEADER
st.title(f"✈️ TBM 960: {leg_select}")
col_h1, col_h2 = st.columns(2)

with col_h1:
    st.metric("Dep Time (Local)", current_dep_dt.strftime("%H:%M"), f"({current_dep_pst.strftime('%H:%M')} PST)")

results = []
baseline_wind = 0
for fl in [260, 270, 280, 290, 300, 310]:
    total_time, wind_sum = 0, 0
    for i in range(12):
        w = get_segmented_wind(fl, is_return, i)
        wind_sum += w
        total_time += (580/12) / (PERF["tas"] + w)
    
    avg_w = int(wind_sum/12)
    if fl == 280: baseline_wind = avg_w
    
    burn = int((total_time * PERF["burn"]) + PERF["climb_penalty"])
    land_fuel = int(start_fuel - burn)
    eta_dt = current_dep_dt + datetime.timedelta(hours=total_time)
    
    results.append({
        "FL": f"FL{fl}",
        "Wind": f"{avg_w}k",
        "ETE": f"{int(total_time)}h {int((total_time%1)*60)}m",
        "ETA Loc": eta_dt.astimezone(dest_tz).strftime("%H:%M"),
        "ETA PST": eta_dt.astimezone(KSTS_TZ).strftime("%H:%M"),
        "Fuel Burn": burn,
        "Fuel at Dest": land_fuel
    })

with col_h2:
    w_type = "Headwind" if is_return else "Tailwind"
    qual = get_wind_qualifier(baseline_wind)
    st.metric("Direction", f"{'Westbound' if is_return else 'Eastbound'} ({w_type})", qual)

# --- COMPACT TABLE ---
df = pd.DataFrame(results)
st.dataframe(
    df.style.applymap(lambda x: 'color: red' if isinstance(x, int) and x < land_min else '', subset=['Fuel at Dest']),
    use_container_width=False,
    hide_index=True,
    column_config={
        "FL": st.column_config.TextColumn("FL", width=50),
        "Wind": st.column_config.TextColumn("Wind", width=60),
        "ETE": st.column_config.TextColumn("ETE", width=70),
        "ETA Loc": st.column_config.TextColumn("ETA Loc", width=70),
        "ETA PST": st.column_config.TextColumn("ETA PST", width=70),
        "Fuel Burn": st.column_config.NumberColumn("Fuel Burn", width=85),
        "Fuel at Dest": st.column_config.NumberColumn("Fuel at Dest", width=95),
    }
)