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
    return -total if is_return else (total * 0.4)

# --- UI CONFIG ---
st.set_page_config(page_title="TBM 960 Tactical Brief", layout="wide")
st.markdown("<style>.block-container {padding-top: 1rem;}</style>", unsafe_allow_html=True)

# SIDEBAR
with st.sidebar:
    st.header("📍 Mission Timing")
    dep_date = st.date_input("Outbound Date", datetime.date(2026, 2, 22))
    dep_time_local = st.time_input("Outbound Dep (KSTS Local)", datetime.time(10, 0))
    
    st.divider()
    quick_turn = st.checkbox("Quick Turn (30 min)")
    if not quick_turn:
        turn_h = st.number_input("Turn Time (Hrs)", 0, 24, 1)
        turn_m = st.number_input("Turn Time (Mins)", 0, 59, 0)
    
    st.divider()
    start_fuel = st.number_input("Starting Fuel (Gal)", value=292)
    land_min = st.number_input("Landing Min (Gal)", value=60)
    leg_select = st.radio("Active View", ["Outbound: KSTS -> KFFZ", "Return: KFFZ -> KSTS"])

# --- TIME CALCULATIONS ---
# 1. Outbound Timing
out_dep_pst = KSTS_TZ.localize(datetime.datetime.combine(dep_date, dep_time_local))

# We'll use FL280 as the 'baseline' to calculate the arrival for the turn-around
_, _, out_ete_base = 0, 0, 0
for i in range(12):
    gs = PERF["tas"] + get_segmented_wind(280, False, i)
    out_ete_base += (580/12) / gs

out_arr_pst = out_dep_pst + datetime.timedelta(hours=out_ete_base)
turn_delta = datetime.timedelta(minutes=30) if quick_turn else datetime.timedelta(hours=turn_h, minutes=turn_m)
ret_dep_pst = out_arr_pst + turn_delta

# --- MAIN DISPLAY ---
st.title(f"✈️ TBM 960: {leg_select}")
is_return = "Return" in leg_select
current_dep_pst = ret_dep_pst if is_return else out_dep_pst
current_tz = KFFZ_TZ if is_return else KSTS_TZ
dest_tz = KSTS_TZ if is_return else KFFZ_TZ

# Display Dynamic Header
col_a, col_b = st.columns(2)
col_a.metric("Dep Time (Local)", current_dep_pst.astimezone(current_tz).strftime("%H:%M"), 
             f"({current_dep_pst.strftime('%H:%M')} PST)")
col_b.metric("Leg Setting", "Westbound Headwind" if is_return else "Eastbound Tailwind")

# --- CALCULATION TABLE ---
results = []
for fl in [260, 270, 280, 290, 300, 310]:
    total_time, wind_sum = 0, 0
    for i in range(12):
        w = get_segmented_wind(fl, is_return, i)
        wind_sum += w
        total_time += (580/12) / (PERF["tas"] + w)
    
    burn = int((total_time * PERF["burn"]) + PERF["climb_penalty"])
    land_fuel = int(start_fuel - burn)
    eta_pst = current_dep_pst + datetime.timedelta(hours=total_time)
    
    results.append({
        "FL": f"FL{fl}",
        "Avg Wind": f"{int(wind_sum/12)}k",
        "ETE": f"{int(total_time)}h {int((total_time%1)*60)}m",
        "ETA (Local)": eta_pst.astimezone(dest_tz).strftime("%H:%M"),
        "ETA (PST)": eta_pst.strftime("%H:%M"),
        "Burn": burn,
        "Landing": land_fuel
    })

# Format Table
df = pd.DataFrame(results)
st.dataframe(df.style.applymap(lambda x: 'color: red' if isinstance(x, int) and x < land_min else '', subset=['Landing']),
             use_container_width=True, hide_index=True)

st.info(f"💡 **Turn-around Intel:** Arrival at KFFZ est. {out_arr_pst.astimezone(KFFZ_TZ).strftime('%H:%M')} local. " +
        f"{'30m Quick Turn' if quick_turn else 'Custom turn'} results in {ret_dep_pst.astimezone(KFFZ_TZ).strftime('%H:%M')} departure.")