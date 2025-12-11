# app.py
import streamlit as st
import pandas as pd
import requests
import plotly.express as px

# -------------------------------
# Page config
# -------------------------------
st.set_page_config(
    page_title="Saudi Cities Weather Dashboard",
    layout="wide"
)

st.title("🌤 Saudi Cities Live Weather Monitor")
st.caption("Data source: Open-Meteo.com (Free weather API – no API key required)")

# -------------------------------
# Sidebar controls
# -------------------------------
st.sidebar.header("Controls")

CITIES = {
    "Riyadh":  {"lat": 24.7136, "lon": 46.6753},
    "Jeddah":  {"lat": 21.4858, "lon": 39.1925},
    "Dammam":  {"lat": 26.3927, "lon": 49.9777},
    "Abha":    {"lat": 18.2465, "lon": 42.5117},
}

selected_cities = st.sidebar.multiselect(
    "Select cities",
    options=list(CITIES.keys()),
    default=["Riyadh", "Jeddah", "Dammam", "Abha"]
)

days_option = st.sidebar.selectbox(
    "Time window",
    options=[
        "Today only (0 past days)",
        "Today + Yesterday (1 past day)",
        "Last 3 days (3 past days)"
    ],
    index=1
)

if "0" in days_option:
    days_back = 0
elif "1" in days_option:
    days_back = 1
else:
    days_back = 3

refresh = st.sidebar.button("🔄 Refresh data")

st.sidebar.markdown("---")
st.sidebar.write("**Note:** Data is fetched directly from Open-Meteo hourly API (auto timezone).")

if not selected_cities:
    st.warning("Please select at least one city from the sidebar.")
    st.stop()

# -------------------------------
# Helper function to call Open-Meteo
# -------------------------------
@st.cache_data(ttl=300)
def fetch_city_hourly(city_name: str, lat: float, lon: float, days_back: int) -> pd.DataFrame:
    """
    Fetch hourly weather from Open-Meteo for a given city.
    Returns a DataFrame with columns: city, time, temp, windspeed, winddirection
    """
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        "&hourly=temperature_2m,windspeed_10m,winddirection_10m"
        f"&past_days={days_back}&forecast_days=1"
        "&timezone=auto"
    )

    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    hourly = data.get("hourly", {})
    if not hourly:
        return pd.DataFrame()

    times = hourly["time"]
    temps = hourly["temperature_2m"]
    winds = hourly["windspeed_10m"]
    winddirs = hourly["winddirection_10m"]

    df_city = pd.DataFrame({
        "city": city_name,
        "time": pd.to_datetime(times),
        "temp": temps,
        "windspeed": winds,
        "winddirection": winddirs,
    })
    return df_city

# Force refresh if button clicked
if refresh:
    fetch_city_hourly.clear()

# -------------------------------
# Fetch data for all selected cities
# -------------------------------
all_dfs = []
for city in selected_cities:
    info = CITIES[city]
    try:
        df_city = fetch_city_hourly(city, info["lat"], info["lon"], days_back)
        if not df_city.empty:
            all_dfs.append(df_city)
    except Exception as e:
        st.error(f"Error fetching data for {city}: {e}")

if not all_dfs:
    st.error("No data fetched. Check your internet connection or try again.")
    st.stop()

df = pd.concat(all_dfs, ignore_index=True)
df = df.sort_values("time")

# Extra time fields
df["date"] = df["time"].dt.date
df["hour"] = df["time"].dt.hour

# -------------------------------
# KPIs (top-level metrics)
# -------------------------------
st.subheader("Overview Metrics")

overall_avg_temp = df["temp"].mean()
overall_max_temp = df["temp"].max()
overall_min_temp = df["temp"].min()
overall_avg_wind = df["windspeed"].mean()
num_cities = df["city"].nunique()
num_records = len(df)

# hottest and windiest cities
hottest_row = df.loc[df["temp"].idxmax()]
windiest_row = df.loc[df["windspeed"].idxmax()]

col1, col2, col3, col4, col5 = st.columns(5)

col1.metric("Number of Cities", num_cities)
col2.metric("Total Records", num_records)
col3.metric("Avg Temperature", f"{overall_avg_temp:.1f} °C")
col4.metric("Max Temperature", f"{overall_max_temp:.1f} °C")
col5.metric("Avg Wind Speed", f"{overall_avg_wind:.1f} m/s")

col6, col7 = st.columns(2)
with col6:
    st.info(
        f"🔥 **Hottest city:** "
        f"{hottest_row['city']} ({hottest_row['temp']:.1f} °C at {hottest_row['time']})"
    )
with col7:
    st.info(
        f"💨 **Windiest city:** "
        f"{windiest_row['city']} ({windiest_row['windspeed']:.1f} m/s at {windiest_row['time']})"
    )

st.markdown("---")

# -------------------------------
# Latest snapshot table
# -------------------------------
st.subheader("Latest Snapshot per City")

latest_rows = (
    df.sort_values("time")
      .groupby("city", as_index=False)
      .tail(1)
      .sort_values("city")
)

latest_rows_display = latest_rows[["city", "time", "temp", "windspeed", "winddirection"]]
latest_rows_display.rename(columns={
    "temp": "Temperature (°C)",
    "windspeed": "Wind Speed (m/s)",
    "winddirection": "Wind Direction (°)"
}, inplace=True)

st.dataframe(latest_rows_display, use_container_width=True)

st.markdown("---")

# =====================================================
# 1) Small multiples: one time-series chart per city
# =====================================================
st.subheader("1️⃣ Hourly Temperature – Small Multiples")

fig_small = px.line(
    df,
    x="time",
    y="temp",
    facet_col="city",
    facet_col_wrap=2,
    labels={"time": "Time", "temp": "Temperature (°C)", "city": "City"},
    title="Hourly Temperature for Each City"
)
fig_small.update_layout(template="plotly_white", showlegend=False)
st.plotly_chart(fig_small, use_container_width=True)

st.markdown("---")

# =====================================================
# 2) Heatmaps: daily and hourly patterns
# =====================================================
st.subheader("2️⃣ Temperature Heatmaps")

# 2.a – Average daily temperature per city (city × date)
daily = df.groupby(["city", "date"]).agg(avg_temp=("temp", "mean")).reset_index()
pivot_daily = daily.pivot(index="city", columns="date", values="avg_temp")

fig_daily_heat = px.imshow(
    pivot_daily.values,
    x=[str(d) for d in pivot_daily.columns],
    y=pivot_daily.index,
    labels={"x": "Date", "y": "City", "color": "Avg Temp (°C)"},
    title="Average Daily Temperature (City × Date)"
)
fig_daily_heat.update_layout(template="plotly_white")
st.plotly_chart(fig_daily_heat, use_container_width=True)

# 2.b – Average hourly temperature pattern (city × hour)
hourly = df.groupby(["city", "hour"]).agg(avg_temp=("temp", "mean")).reset_index()
pivot_hourly = hourly.pivot(index="city", columns="hour", values="avg_temp")

fig_hour_heat = px.imshow(
    pivot_hourly.values,
    x=pivot_hourly.columns,
    y=pivot_hourly.index,
    labels={"x": "Hour of Day", "y": "City", "color": "Avg Temp (°C)"},
    title="Average Hour-of-Day Temperature (City × Hour)"
)
fig_hour_heat.update_layout(template="plotly_white")
st.plotly_chart(fig_hour_heat, use_container_width=True)

st.markdown("---")

# =====================================================
# 3) Temperature distribution per city (boxplot)
# =====================================================
st.subheader("3️⃣ Temperature Range per City")

fig_box = px.box(
    df,
    x="city",
    y="temp",
    points="all",
    labels={"city": "City", "temp": "Temperature (°C)"},
    title="Temperature Distribution by City"
)
fig_box.update_layout(template="plotly_white")
st.plotly_chart(fig_box, use_container_width=True)

st.markdown("---")

# =====================================================
# 4) Temp vs Wind – relationship
# =====================================================
st.subheader("4️⃣ Relationship Between Temperature and Wind Speed")

fig_scatter = px.scatter(
    df,
    x="temp",
    y="windspeed",
    color="city",
    marginal_x="histogram",
    marginal_y="box",
    labels={"temp": "Temperature (°C)", "windspeed": "Wind Speed (m/s)", "city": "City"},
    title="Temperature vs Wind Speed with Distributions"
)
fig_scatter.update_layout(template="plotly_white")
st.plotly_chart(fig_scatter, use_container_width=True)

st.markdown("---")

# =====================================================
# 5) Wind Rose (direction vs speed) per city
# =====================================================
st.subheader("5️⃣ Wind Rose (Direction vs Speed)")

wind_city = st.selectbox(
    "Select a city for wind rose",
    options=sorted(df["city"].unique())
)
wind_df = df[df["city"] == wind_city]

fig_rose = px.bar_polar(
    wind_df,
    r="windspeed",
    theta="winddirection",
    color="windspeed",
    labels={"windspeed": "Wind Speed (m/s)", "winddirection": "Direction (°)"},
    title=f"Wind Rose – {wind_city}"
)
fig_rose.update_layout(template="plotly_white")
st.plotly_chart(fig_rose, use_container_width=True)

st.markdown("---")
st.write("Data last fetched for the selected time window. Click **Refresh data** in the sidebar to update.")
