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

# CHANGED: use discrete options instead of raw slider
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

# NEW: hottest and windiest cities
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
        f"🔥 **Hottest city in this window:** "
        f"{hottest_row['city']} ({hottest_row['temp']:.1f} °C at {hottest_row['time']})"
    )
with col7:
    st.info(
        f"💨 **Windiest city in this window:** "
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

# -------------------------------
# Line chart: Time series by city (selectable metric)
# -------------------------------
st.subheader("Time Series by City")

metric_choice = st.radio(
    "Select metric to visualize:",
    options=["Temperature (°C)", "Wind Speed (m/s)"],
    horizontal=True
)

if metric_choice.startswith("Temperature"):
    y_col = "temp"
    y_label = "Temperature (°C)"
    title_line = "Hourly Temperature by City"
else:
    y_col = "windspeed"
    y_label = "Wind Speed (m/s)"
    title_line = "Hourly Wind Speed by City"

fig_line = px.line(
    df,
    x="time",
    y=y_col,
    color="city",
    markers=False,
    labels={"time": "Time", y_col: y_label, "city": "City"},
    title=title_line
)
fig_line.update_layout(template="plotly_white", legend_title_text="City")
st.plotly_chart(fig_line, use_container_width=True)

st.markdown("---")

# -------------------------------
# Aggregations per city
# -------------------------------
summary = df.groupby("city").agg(
    avg_temp=("temp", "mean"),
    max_temp=("temp", "max"),
    min_temp=("temp", "min"),
    avg_wind=("windspeed", "mean")
).reset_index()

colA, colB = st.columns(2)

with colA:
    st.subheader("Average Temperature per City")
    fig_bar_temp = px.bar(
        summary,
        x="city",
        y="avg_temp",
        text_auto=".1f",
        labels={"city": "City", "avg_temp": "Avg Temperature (°C)"},
        title="Average Temperature by City"
    )
    fig_bar_temp.update_layout(template="plotly_white")
    st.plotly_chart(fig_bar_temp, use_container_width=True)

with colB:
    st.subheader("Average Wind Speed per City")
    fig_bar_wind = px.bar(
        summary,
        x="city",
        y="avg_wind",
        text_auto=".1f",
        labels={"city": "City", "avg_wind": "Avg Wind Speed (m/s)"},
        title="Average Wind Speed by City"
    )
    fig_bar_wind.update_layout(template="plotly_white")
    st.plotly_chart(fig_bar_wind, use_container_width=True)

st.markdown("---")

# -------------------------------
# Detailed per-city view (select box)
# -------------------------------
st.subheader("Detailed City View")

city_selected = st.selectbox("Select a city for detailed analysis", options=sorted(df["city"].unique()))
city_df = df[df["city"] == city_selected].copy()

tab1, tab2, tab3 = st.tabs(["Time Series", "Distribution", "Temp vs Wind"])

with tab1:
    st.write(f"### {city_selected} – Temperature Trend")
    fig_city_line = px.line(
        city_df,
        x="time",
        y="temp",
        labels={"time": "Time", "temp": "Temperature (°C)"},
        title=f"Hourly Temperature in {city_selected}"
    )
    fig_city_line.update_layout(template="plotly_white")
    st.plotly_chart(fig_city_line, use_container_width=True)

with tab2:
    st.write(f"### {city_selected} – Temperature Distribution")
    fig_hist = px.histogram(
        city_df,
        x="temp",
        nbins=15,
        labels={"temp": "Temperature (°C)"},
        title=f"Temperature Histogram - {city_selected}"
    )
    fig_hist.update_layout(template="plotly_white")
    st.plotly_chart(fig_hist, use_container_width=True)

with tab3:
    st.write(f"### {city_selected} – Temperature vs Wind Speed")
    fig_scatter = px.scatter(
        city_df,
        x="temp",
        y="windspeed",
        labels={"temp": "Temperature (°C)", "windspeed": "Wind Speed (m/s)"},
        title=f"Temperature vs Wind Speed - {city_selected}"
    )
    fig_scatter.update_layout(template="plotly_white")
    st.plotly_chart(fig_scatter, use_container_width=True)

st.markdown("---")
st.write("Data last fetched for the selected time window. Click **Refresh data** in the sidebar to update.")
