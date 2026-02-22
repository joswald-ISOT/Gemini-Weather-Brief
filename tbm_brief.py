import streamlit as st
import pandas as pd
import datetime

# --- TBM 960 PERFORMANCE DATA ---
PERF = {
    "tas_knots": 330,
    "burn_gph": 57,
    "climb_penalty_fuel": 12, # Extra fuel for the climb
}

def get_segmented_wind(icao, fl, is_return, segment_index):
    """
    Simulated dynamic wind logic. 
    In the final step, this will connect to the AWC API.
    """
    # Simulate Feb 22 Jetstream: Stronger at higher FLs and over mountains
    base_jetstream = 40 + (fl - 260) // 2
    # Increase wind over the Sierras (middle segments)
    mountain_effect = 25 if 4 <= segment_index <= 8 else 0
    total_wind = base_jetstream + mountain_effect
    
    return -total_wind if is_return else (total_wind * 0.4)

# --- UI INTERFACE ---
st.set_page_config(page_title="TBM 960 Tactical Brief", layout="wide")
st.title("✈️ TBM 960 Tactical Flight Advisor")

# SIDEBAR: FLIGHT SETTINGS
with st.sidebar:
    st.header("📍 Route & Time")
    dep_icao = st.text_input("Departure Airport", "KSTS").upper()
    arr_icao = st.text_input("Destination Airport", "KFFZ").upper()
    dep_date = st.date_input("Departure Date", datetime.date(2026, 2, 22))
    dep_time = st.time_input("Departure Time (Local)", datetime.time(10, 0))
    
    st.divider()
    st.header("⛽ Fuel & Payload")
    start_fuel = st.number_input("Starting Fuel (Gal)", value=292)
    land_min = st.number_input("Landing Min (Gal)", value=60)
    
    st.divider()
    mission_leg = st.radio("Select Leg", ["Outbound", "Return"])
    comfort = st.select_slider("Comfort Tolerance", ["Smooth Only", "Standard", "Experienced"])

# --- CORE CALCULATIONS ---
is_return = (mission_leg == "Return")
distance = 580 # KSTS to KFFZ
segments = 12
results = []

for fl in [260, 270, 280, 290, 300, 310]:
    total_time = 0
    wind_sum = 0
    
    for i in range(segments):
        w = get_segmented_wind(dep_icao, fl, is_return, i)
        wind_sum += w
        gs = PERF["tas_knots"] + w
        total_time += (distance / segments) / gs
    
    avg_wind = wind_sum / segments
    total_burn = (total_time * PERF["burn_gph"]) + PERF["climb_penalty_fuel"]
    land_fuel = start_fuel - total_burn
    
    results.append({
        "Flight Level": f"FL{fl}",
        "Avg Wind (kts)": int(avg_wind),
        "ETE": f"{int(total_time)}h {int((total_time%1)*60)}m",
        "Fuel Burn": int(total_burn),
        "Landing Fuel": int(land_fuel)
    })

# --- DISPLAY ---
st.header(f"📊 {dep_icao if not is_return else arr_icao} → {arr_icao if not is_return else dep_icao}")
df = pd.DataFrame(results)

# Safety Color Formatting
def highlight_safety(val):
    color = 'red' if val < land_min else 'white'
    return f'color: {color}'

st.table(df.style.applymap(highlight_safety, subset=['Landing Fuel']))

st.divider()
st.subheader("🛡️ Safety & Comfort Brief")
col1, col2 = st.columns(2)

with col1:
    st.write("**Weather Risk:**")
    if is_return:
        st.error(f"⚠️ **Headwind Alert:** Significant {int(abs(df.iloc[0,1]))}kt headwinds returning to {dep_icao}. Check fuel reserves.")
    else:
        st.success(f"✅ **Tailwind Benefit:** Favorable push toward {arr_icao} at FL290+.")

with col2:
    st.write("**Mission Timing:**")
    st.info(f"Scheduled Departure: {dep_date} at {dep_time}")