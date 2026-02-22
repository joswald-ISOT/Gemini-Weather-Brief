import streamlit as st
import pandas as pd
import datetime

# --- AIRCRAFT SPECIFICATIONS (TBM 960) ---
PERF = {
    "max_fuel": 292.0,
    "burn_gph": 57.0,  # Recommended cruise
    "tas_knots": 330.0,
    "climb_fuel_penalty": 12.0  # Extra gal for the climb to FL280
}

def get_segmented_weather(segment_index, is_return, fl):
    """
    Simulation of AWC API response for Feb 22, 2026.
    In production, this calls: aviationweather.gov/api/data/windtemp
    """
    # Jetstream is typically stronger over the Sierras (segments 3-6)
    base_wind = 45 if fl > 250 else 30
    sierra_boost = 20 if 3 <= segment_index <= 6 else 0
    
    wind = -(base_wind + sierra_boost) if is_return else (base_wind * 0.5)
    temp = -35 if fl > 250 else -15 # Celsius
    turb = "Moderate" if (3 <= segment_index <= 6 and fl < 290) else "Light"
    
    return wind, temp, turb

# --- USER INTERFACE ---
st.set_page_config(page_title="TBM 960 Mission Command", layout="wide")
st.title("✈️ TBM 960 Tactical Flight Advisor")

# Sidebar Inputs
st.sidebar.header("⛽ Fuel & Payload")
starting_fuel = st.sidebar.number_input("Starting Fuel (Gallons)", value=292.0, max_value=292.0)
landing_min = st.sidebar.number_input("Desired Landing Min (Gallons)", value=60.0)

st.sidebar.header("🗺️ Mission Profile")
mission = st.sidebar.selectbox("Leg", ["KSTS -> KFFZ (Outbound)", "KFFZ -> KSTS (Return)"])
comfort_pref = st.sidebar.select_slider("Comfort Tolerance", ["Smooth Only", "Standard", "Experienced"])

# --- CORE LOGIC: SEGMENTED CALCULATION ---
st.header(f"📊 Performance Analysis: {mission}")

distance = 580.0
segments = 12 # ~48nm per segment
is_return = "Return" in mission
results = []

for fl in [260, 270, 280, 290, 300, 310]:
    total_time = 0
    ice_risk = False
    max_turb = "Light"
    
    for i in range(segments):
        wind, temp, turb = get_segmented_weather(i, is_return, fl)
        gs = PERF["tas_knots"] + wind
        total_time += (distance / segments) / gs
        if turb == "Moderate": max_turb = "Moderate"
    
    total_burn = (total_time * PERF["burn_gph"]) + PERF["climb_fuel_penalty"]
    rem_fuel = starting_fuel - total_burn
    
    results.append({
        "FL": f"FL{fl}",
        "ETE": f"{int(total_time)}h {int((total_time%1)*60)}m",
        "Fuel Burn": round(total_burn, 1),
        "Landing Fuel": round(rem_fuel, 1),
        "Ride Quality": max_turb
    })

# --- DISPLAY RESULTS ---
df = pd.DataFrame(results)

def highlight_safety(row):
    # Red if below your 60-gal min, Yellow if comfort doesn't match
    style = [''] * len(row)
    if row['Landing Fuel'] < landing_min:
        style[3] = 'background-color: #ff4b4b; color: white'
    if comfort_pref == "Smooth Only" and row['Ride Quality'] == "Moderate":
        style[4] = 'background-color: #ffa500'
    return style

st.table(df.style.apply(highlight_safety, axis=1))

# --- RISK ASSESSMENT SUMMARY ---
st.divider()
st.subheader("🛡️ Safety & Comfort Brief")

col1, col2 = st.columns(2)
with col1:
    st.write("**Weather Risk:**")
    if is_return:
        st.error("⚠️ **Headwind Alert:** Returning to KSTS faces a 65kt jetstream segment over the Sierras. FL300+ is mandatory for fuel reserves.")
    else:
        st.success("✅ **Outbound:** Favorable tailwinds. Recommend FL290 for optimal TAS.")

with col2:
    st.write("**Pilot Comfort:**")
    if comfort_pref == "Smooth Only":
        st.info("💡 To stay in 'Smooth Only' conditions, avoid FL260-FL280 where mountain wave chop is forecasted.")