import pandas as pd
import plotly.express as px
import streamlit as st

import paho.mqtt.client as mqtt
import time
import os

from pymongo import MongoClient
from datetime import datetime

MQTT_BROKER = "8bda2df24fea4d2c9aadeb89eedd2738.s1.eu.hivemq.cloud"
MQTT_PORT = 8883
MQTT_USER = "hivemq.webclient.1749548766220"
MQTT_PASSWORD = "1uBpWUE9<:jAq5>6d#bY"
MQTT_CONTROL_TOPIC_RELAY_ON_OFF = "iot/perintah/relay_on_off"
MQTT_CONTROL_TOPIC_RELAY_LAMPU = "iot/perintah/relay_lampu"

TOGGLE_STATUS_FILE = ".streamlit_kipas_toggle_status.txt"
TOGGLE_LED_FILE = ".streamlit_led_toggle_status.txt"

# === Koneksi MongoDB ===
client = MongoClient("mongodb+srv://alfarrelmahardika:Z.iLkvVg7Ep6!uP@cluster0.lnbl9.mongodb.net/")
collection = client["manajemen_listrik"]["kipas_dan_lampu"]
data = list(collection.find().sort("timestamp", 1))

def parse_time(s):
    return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")

last_seen = {}
energi_per_entry = []

# === Hitung energi ===
for entry in data:
    dev_id = entry["device_id"]
    ts = parse_time(entry["timestamp"])
    watt = entry["watt"]

    if dev_id in last_seen:
        delta = (ts - last_seen[dev_id]["timestamp"]).total_seconds() / 60
        energi = last_seen[dev_id]["watt"] * delta
        energi_per_entry.append({
            "timestamp": last_seen[dev_id]["timestamp"],
            "device_id": dev_id,
            "watt": last_seen[dev_id]["watt"],
            "energi": energi
        })

    last_seen[dev_id] = {"timestamp": ts, "watt": watt}

# === Konversi DataFrame ===
df = pd.DataFrame(energi_per_entry)
if df.empty:
    st.warning("Data tidak tersedia.")
    st.stop()

df["tanggal"] = df["timestamp"].dt.date
df["bulan"] = df["timestamp"].dt.to_period("M")
df["perangkat"] = df["device_id"].map({1: "lampu", 2: "kipas"})
tarif_per_kwh = 1444
df["tarif"] = (df["energi"] / 1000) * tarif_per_kwh

# === CSS Card UI ===
st.markdown("""
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css">
<style>
.metric-card {
    padding: 1rem;
    border-radius: 0.5rem;
    color: white;
    display: flex;
    align-items: center;
    gap: 0.75rem;
    height: 100px;
    box-sizing: border-box;
    margin-bottom: 1rem;
}
.bg-blue { background-color: #3b82f6; }
.bg-green { background-color: #10b981; }
.bg-yellow { background-color: #f59e0b; }
.bg-red { background-color: #ef4444; }
.metric-title { font-size: 0.875rem; font-weight: 600; }
.metric-value { font-size: 1.25rem; font-weight: 700; }
.metric-icon { font-size: 1.5rem; }
.text-content { display: flex; flex-direction: column; }
</style>
""", unsafe_allow_html=True)

# === Filter data hari & bulan ===
last_date = df["tanggal"].max()
bulan_ini = df["bulan"].max()

df_today = df[df["tanggal"] == last_date].copy()
df_bulan = df[df["bulan"] == bulan_ini].copy()

def simpan_status_kipas(status: str):
    with open(TOGGLE_STATUS_FILE, "w") as f:
        f.write(status)

def muat_status_kipas():
    if os.path.exists(TOGGLE_STATUS_FILE):
        with open(TOGGLE_STATUS_FILE, "r") as f:
            return f.read().strip()
    else:
        return "1"

def simpan_status_led(status: str):
    with open(TOGGLE_LED_FILE, "w") as f:
        f.write(status)

def muat_status_led():
    if os.path.exists(TOGGLE_LED_FILE):
        with open(TOGGLE_LED_FILE, "r") as f:
            return f.read().strip()
    else:
        return "1"

def publish_mqtt_command(topic: str, message: str):
    client = mqtt.Client()
    client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
    client.tls_set()
    client.connect(MQTT_BROKER, MQTT_PORT)
    client.loop_start()
    client.publish(topic, message)
    time.sleep(1)
    client.loop_stop()
    client.disconnect()


# === Dropdown visualisasi ===
st.title("📊 Konsumsi Energi & Tarif Listrik")

# === Card Container: 2 Kolom x 2 Baris ===
col1, col2 = st.columns(2)
with col1:
    st.markdown(f"""
    <div class="metric-card bg-blue">
        <i class="fas fa-money-bill-wave metric-icon"></i>
        <div class="text-content">
            <div class="metric-title">Total Tarif Hari Ini</div>
            <div class="metric-value">Rp {df_today['tarif'].sum():,.2f}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
with col2:
    st.markdown(f"""
    <div class="metric-card bg-green">
        <i class="fas fa-coins metric-icon"></i>
        <div class="text-content">
            <div class="metric-title">Total Tarif Bulan Ini</div>
            <div class="metric-value">Rp {df_bulan['tarif'].sum():,.2f}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

col3, col4 = st.columns(2)
with col3:
    energi_hari_kwh = round(df_today["energi"].sum() / 1000, 5)
    st.markdown(f"""
    <div class="metric-card bg-yellow">
        <i class="fas fa-battery-half metric-icon"></i>
        <div class="text-content">
            <div class="metric-title">Total Energi Hari Ini</div>
            <div class="metric-value">{energi_hari_kwh} kWh</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
with col4:
    energi_bulan_kwh = round(df_bulan["energi"].sum() / 1000, 5)
    st.markdown(f"""
    <div class="metric-card bg-red">
        <i class="fas fa-battery-full metric-icon"></i>
        <div class="text-content">
            <div class="metric-title">Total Energi Bulan Ini</div>
            <div class="metric-value">{energi_bulan_kwh} kWh</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("### 🔧 Kontrol Perangkat")

# Status saat ini
status_kipas = muat_status_kipas()
status_lampu = muat_status_led()
kipas_nyala = status_kipas == "0"
lampu_nyala = status_lampu == "0"

col_toggle_kipas, col_toggle_lampu, col_refresh = st.columns([2, 2, 1])

with col_toggle_kipas:
    toggle_kipas = st.toggle("Kipas", value=kipas_nyala)

with col_toggle_lampu:
    toggle_lampu = st.toggle("Lampu", value=lampu_nyala)

with col_refresh:
    if st.button("🔄 Refresh"):
        st.rerun()

# === Tangani aksi toggle Kipas ===
if toggle_kipas and status_kipas == "1":
    publish_mqtt_command(MQTT_CONTROL_TOPIC_RELAY_ON_OFF, "0")  # Hidupkan kipas
    simpan_status_kipas("0")
    st.success("✅ Kipas dihidupkan.")
elif not toggle_kipas and status_kipas == "0":
    publish_mqtt_command(MQTT_CONTROL_TOPIC_RELAY_ON_OFF, "1")  # Matikan kipas
    simpan_status_kipas("1")
    st.warning("⛔ Kipas dimatikan.")

# === Tangani aksi toggle Lampu ===
if toggle_lampu and status_lampu == "1":
    publish_mqtt_command(MQTT_CONTROL_TOPIC_RELAY_LAMPU, "0")  # Hidupkan lampu
    simpan_status_led("0")
    st.success("💡 Lampu dinyalakan.")
elif not toggle_lampu and status_lampu == "0":
    publish_mqtt_command(MQTT_CONTROL_TOPIC_RELAY_LAMPU, "1")  # Matikan lampu
    simpan_status_led("1")
    st.warning("💡 Lampu dimatikan.")



pilihan = st.selectbox("Pilih rentang waktu:", ["Hari Ini", "Bulan Ini"])

# === Visualisasi Energi ===
if pilihan == "Hari Ini":
    df_plot = df_today
    formatted_date = last_date.strftime("%A, %d %B %Y")
    title = f"Energi Konsumsi - {formatted_date}"
else:
    df_plot = df_bulan
    formatted_month = bulan_ini.strftime("%B %Y")
    title = f"Energi Konsumsi Bulan Ini - {formatted_month}"

fig = px.line(
    df_plot,
    x="timestamp",
    y="energi",
    color="perangkat",
    title=title,
    labels={"timestamp": "Waktu", "energi": "Energi (Wh)", "perangkat": "Perangkat"},
    markers=True
)
fig.update_traces(line=dict(width=2))
st.plotly_chart(fig, use_container_width=True)

# === Tabel di bawah grafik ===
st.subheader("📄 Data Konsumsi Energi")

tabel_data = df_plot.copy()
tabel_data["perangkat"] = tabel_data["device_id"].map({1: "lampu", 2: "kipas"})
tabel_data = tabel_data[["timestamp", "perangkat", "watt", "energi", "tarif"]].copy()
tabel_data["tarif"] = tabel_data["tarif"].round(2)
tabel_data["energi"] = tabel_data["energi"].round(5)
tabel_data = tabel_data.sort_values(by="timestamp", ascending=False).reset_index(drop=True)
st.dataframe(tabel_data, use_container_width=True)