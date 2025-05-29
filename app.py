import streamlit as st
import pandas as pd
import numpy as np
import requests
import json
from datetime import datetime, timedelta
import plotly.express as px
import time
import os

# --- KONFIGURASI SERVER FLASK ---
FLASK_SERVER_URL = os.environ.get("FLASK_SERVER_URL", "http://localhost:5000")

# --- KONFIGURASI HALAMAN STREAMLIT ---
st.set_page_config(page_title="Smart Home Dashboard", layout="wide", initial_sidebar_state="expanded")
st.title("🏡 Smart Home Dashboard (Agregat)") # Nama dashboard berubah

# --- FUNGSI UNTUK MENGAMBIL DATA DARI FLASK SERVER ---
@st.cache_data(ttl=3)
def fetch_data_from_flask():
    try:
        response = requests.get(f"{FLASK_SERVER_URL}/data", timeout=5)
        response.raise_for_status()
        data = response.json()

        # Asumsi: data[0] adalah current_status, data[1:] adalah historis
        if data and len(data) > 1:
            for entry in data[1:]:
                if "timestamp" in entry and isinstance(entry["timestamp"], str):
                    try:
                        entry["timestamp"] = datetime.fromisoformat(entry["timestamp"])
                    except ValueError:
                        try:
                            entry["timestamp"] = datetime.strptime(entry["timestamp"], "%Y-%m-%d %H:%M:%S")
                        except ValueError:
                            entry["timestamp"] = None
        return data
    except requests.exceptions.Timeout:
        st.error("Gagal mengambil data: Waktu koneksi ke server Flask habis.")
        return None
    except requests.exceptions.ConnectionError:
        st.error("Gagal mengambil data: Tidak dapat terhubung ke server Flask. Pastikan server berjalan di " + FLASK_SERVER_URL)
        return None
    except requests.exceptions.HTTPError as e:
        st.error(f"Gagal mengambil data dari server Flask: HTTP Error {e.response.status_code}")
        return None
    except json.JSONDecodeError:
        st.error("Gagal mengurai respons JSON dari server Flask.")
        return None
    except Exception as e:
        st.error(f"Terjadi kesalahan tidak terduga saat mengambil data: {e}")
        return None

# --- FUNGSI UNTUK MENGIRIM PERINTAH ---
# Parameter target_node_id dihilangkan atau dijadikan opsional jika ingin kontrol global
def send_command_to_flask(device_type, state): # target_node_id dihilangkan
    try:
        # Endpoint Flask diasumsikan /control/{device_type}/{state} untuk kontrol global
        response = requests.get(f"{FLASK_SERVER_URL}/control/{device_type}/{state}", timeout=5)
        response.raise_for_status()
        result = response.json()
        if result.get("status") == "sent":
            st.toast(f"Perintah '{state}' untuk {device_type} berhasil dikirim.", icon="✅")
            return result.get("current_state")
        else:
            st.toast(f"Perintah gagal dikirim: {result.get('message', 'Pesan tidak diketahui')}", icon="❌")
            return None
    except requests.exceptions.Timeout:
        st.toast("Gagal mengirim perintah: Waktu koneksi ke server Flask habis.", icon="❌")
        return None
    except requests.exceptions.ConnectionError:
        st.toast("Gagal mengirim perintah: Tidak dapat terhubung ke server Flask.", icon="❌")
        return None
    except requests.exceptions.HTTPError as e:
        st.toast(f"Gagal mengirim perintah: HTTP Error {e.response.status_code}", icon="❌")
        return None
    except json.JSONDecodeError:
        st.toast("Gagal mengurai respons JSON dari server Flask saat mengirim perintah.", icon="❌")
        return None
    except Exception as e:
        st.toast(f"Terjadi kesalahan tidak terduga saat mengirim perintah: {e}")
        return None

# --- SIDEBAR ---
st.sidebar.title("⚙️ Pengaturan")
tanggal_awal_input = st.sidebar.date_input("Mulai Tanggal Rekap & Histori", datetime.now().date() - timedelta(days=7))
tanggal_akhir_input = st.sidebar.date_input("Sampai Tanggal Rekap & Histori", datetime.now().date())
tanggal_awal = datetime.combine(tanggal_awal_input, datetime.min.time())
tanggal_akhir = datetime.combine(tanggal_akhir_input, datetime.max.time()) 
biaya_per_kwh = st.sidebar.number_input("Biaya per kWh (Rp)", min_value=0, value=1500, step=100)

# --- LOAD DATA ---
data = fetch_data_from_flask()
current_status = {}
df_combined = pd.DataFrame()

if data:
    current_status = data[0] if len(data) >= 1 else {}
    df_all = pd.DataFrame(data[1:]) if len(data) > 1 else pd.DataFrame()

    if not df_all.empty:
        df_all["timestamp"] = pd.to_datetime(df_all["timestamp"])
        df_all = df_all[(df_all["timestamp"] >= tanggal_awal) &
                        (df_all["timestamp"] <= tanggal_akhir)]

        if 'source' not in df_all.columns:
            df_all['source'] = 'sensor'

        df_sensor = df_all[df_all["source"] != "dummy"].copy()
        df_dummy = df_all[df_all["source"] == "dummy"].copy()

        df_combined = pd.concat([df_dummy, df_sensor]).sort_values("timestamp")
        df_combined = df_combined.drop_duplicates("timestamp", keep="last").reset_index(drop=True)

        # Penanganan renaming: Hanya rename jika kolom asli ada
        if "suhu" in df_combined.columns:
            df_combined.rename(columns={"suhu": "Suhu"}, inplace=True)
        if "kelembaban" in df_combined.columns:
            df_combined.rename(columns={"kelembaban": "Kelembaban"}, inplace=True)
        if "lux" in df_combined.columns:
            df_combined.rename(columns={"lux": "Pencahayaan"}, inplace=True)

        df_combined.rename(columns={"timestamp": "Waktu"}, inplace=True)

        if "daya" in df_combined.columns:
            interval_seconds = 5 # Asumsi interval pengiriman data dari ESP32
            df_combined["Energi (kWh)"] = (df_combined["daya"] * interval_seconds / 3600) / 1000
            df_combined["Biaya (Rp)"] = df_combined["Energi (kWh)"] * biaya_per_kwh
            df_combined.rename(columns={"daya": "Daya (Watt)"}, inplace=True)
        else:
            df_combined["Energi (kWh)"] = 0
            df_combined["Biaya (Rp)"] = 0
            df_combined["Daya (Watt)"] = 0
    else:
        df_combined = pd.DataFrame()

# available_nodes logic is removed as we are not displaying per node
# If you still need a single representative status, you'd define how to get it
# For now, let's assume current_status directly holds the global/primary device status

# --- STATUS PERANGKAT DENGAN METRIC CARDS (GLOBAL/PRIMER) ---
st.markdown("### 💡 Status Sensor & Perangkat (Terbaru)")

col_lux, col_temp, col_humidity = st.columns(3)

# Akses kunci tanpa prefiks node_id
lux_val = current_status.get('lux', 'N/A')
temp_val = current_status.get('temp', 'N/A')
humidity_val = current_status.get('kelembaban', 'N/A')
lampu_status = current_status.get('lampu', 'N/A') # Asumsi Flask akan menyimpan status lampu global
kipas_status = current_status.get('kipas', 'N/A') # Asumsi Flask akan menyimpan status kipas global

try:
    lux_val_display = float(lux_val)
except (ValueError, TypeError):
    lux_val_display = "N/A"

try:
    temp_val_display = float(temp_val)
except (ValueError, TypeError):
    temp_val_display = "N/A"

try:
    humidity_val_display = float(humidity_val)
except (ValueError, TypeError):
    humidity_val_display = "N/A"

col_lux.metric("Pencahayaan (Lux)", f"{lux_val_display} lx")
col_temp.metric("Suhu (°C)", f"{temp_val_display}°C")
col_humidity.metric("Kelembaban (%)", f"{humidity_val_display}%")

st.write("")
col_lampu_status, col_kipas_status = st.columns(2)
lampu_icon = "💡" if lampu_status == "ON" else "⚫"
kipas_icon = "🌀" if kipas_status == "ON" else "🚫"

col_lampu_status.success(f"{lampu_icon} Lampu: **{lampu_status}**")
col_kipas_status.info(f"{kipas_icon} Kipas: **{kipas_status}**")

st.caption(f"Diperbarui: {current_status.get('timestamp', 'N/A')}")
st.write("---") # Separator

# --- TOGGLE KONTROL (GLOBAL) ---
st.markdown("### 🎛️ Kontrol Manual Perangkat")

c_lampu, c_kipas = st.columns(2)

# Ambil status dari Flask sebagai nilai default.
initial_lampu_state_from_flask = (lampu_status == "ON")
initial_kipas_state_from_flask = (kipas_status == "ON")

# Inisialisasi atau update st.session_state dengan nilai terkini dari Flask.
if lampu_status != "N/A":
    st.session_state["lampu_state"] = initial_lampu_state_from_flask
else:
    if "lampu_state" not in st.session_state:
        st.session_state["lampu_state"] = False

if kipas_status != "N/A":
    st.session_state["kipas_state"] = initial_kipas_state_from_flask
else:
    if "kipas_state" not in st.session_state:
        st.session_state["kipas_state"] = False

# Define callback functions for toggles without node_id
def toggle_lampu_callback_global():
    new_state = "ON" if st.session_state["toggle_global_lampu"] else "OFF"
    # send_command_to_flask tanpa target_node_id
    returned_state = send_command_to_flask("lampu", new_state)
    if returned_state is not None:
        st.session_state["lampu_state"] = (returned_state == "ON")
        # Update current_status in session state to reflect change immediately
        st.session_state.current_status_override = {"lampu": returned_state}

def toggle_kipas_callback_global():
    new_state = "ON" if st.session_state["toggle_global_kipas"] else "OFF"
    # send_command_to_flask tanpa target_node_id
    returned_state = send_command_to_flask("kipas", new_state)
    if returned_state is not None:
        st.session_state["kipas_state"] = (returned_state == "ON")
        st.session_state.current_status_override = {"kipas": returned_state}

# Apply the overrides to current_status BEFORE displaying the metric cards
if "current_status_override" in st.session_state:
    for key, value in st.session_state.current_status_override.items():
        current_status[key] = value
    del st.session_state.current_status_override # Clear after use

# Display toggles with callbacks, global keys
c_lampu.toggle("Nyalakan / Matikan Lampu",
               value=st.session_state["lampu_state"],
               key="toggle_global_lampu",
               on_change=toggle_lampu_callback_global,
               disabled=(lampu_status == "N/A"))
if lampu_status == "N/A":
    c_lampu.warning("Status lampu tidak tersedia.")

c_kipas.toggle("Nyalakan / Matikan Kipas",
               value=st.session_state["kipas_state"],
               key="toggle_global_kipas",
               on_change=toggle_kipas_callback_global,
               disabled=(kipas_status == "N/A"))
if kipas_status == "N/A":
    c_kipas.warning("Status kipas tidak tersedia.")

# --- GRAFIK KONSUMSI DAYA ---
st.markdown("### 📉 Konsumsi Daya 24 Jam Terakhir")
# Filter data for 24h plot
if not df_combined.empty and "Daya (Watt)" in df_combined.columns:
    df_24h_plot = df_combined[df_combined["Waktu"] >= datetime.now() - timedelta(hours=24)]

    # Tidak ada filtering per node lagi
    if not df_24h_plot.empty:
        fig = px.line(df_24h_plot, x="Waktu", y="Daya (Watt)",
                      title="Daya (Watt) (24 Jam Terakhir)", # Judul global
                      labels={"Daya (Watt)": "Daya (Watt)"}, template="streamlit")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Tidak ada data daya dalam 24 jam terakhir.")
else:
    st.info("Data daya tidak tersedia atau format tidak sesuai untuk grafik konsumsi daya.")


# --- REKAP KONSUMSI ENERGI & DATA HISTORIS (Dalam Bentuk Rekap) ---
st.markdown("### 📊 Rekap Data Konsumsi & Sensor")

if not df_combined.empty:
    df_combined['Tahun'] = df_combined['Waktu'].dt.year
    df_combined['Bulan'] = df_combined['Waktu'].dt.strftime('%Y-%m')
    df_combined['Minggu'] = df_combined['Waktu'].dt.strftime('%Y-W%W')

    # group_by_cols hanya berdasarkan waktu, bukan device_id
    group_by_cols_daily = [df_combined['Waktu'].dt.date]
    group_by_cols_weekly = ['Minggu']
    group_by_cols_monthly = ['Bulan']
    group_by_cols_yearly = ['Tahun']

    agg_funcs = {}
    if 'Suhu' in df_combined.columns: agg_funcs['Avg_Suhu'] = ('Suhu', 'mean')
    if 'Kelembaban' in df_combined.columns: agg_funcs['Avg_Kelembaban'] = ('Kelembaban', 'mean')
    if 'Pencahayaan' in df_combined.columns: agg_funcs['Avg_Pencahayaan'] = ('Pencahayaan', 'mean')
    if 'Energi (kWh)' in df_combined.columns: agg_funcs['Total_Energi_kWh'] = ('Energi (kWh)', 'sum')
    if 'Biaya (Rp)' in df_combined.columns: agg_funcs['Estimasi_Biaya_Rp'] = ('Biaya (Rp)', 'sum')

    if agg_funcs:
        # Rekap Harian
        rekap_harian = df_combined.groupby(group_by_cols_daily).agg(**agg_funcs).reset_index()
        rekap_harian.rename(columns={'Waktu': 'Tanggal'}, inplace=True)

        # Rekap Mingguan
        rekap_mingguan = df_combined.groupby(group_by_cols_weekly).agg(**agg_funcs).reset_index()

        # Rekap Bulanan
        rekap_bulanan = df_combined.groupby(group_by_cols_monthly).agg(**agg_funcs).reset_index()

        # Rekap Tahunan
        rekap_tahunan = df_combined.groupby(group_by_cols_yearly).agg(**agg_funcs).reset_index()

        def format_rekap_df(df_rekap):
            if 'Estimasi_Biaya_Rp' in df_rekap.columns:
                df_rekap['Estimasi_Biaya_Rp'] = df_rekap['Estimasi_Biaya_Rp'].apply(lambda x: f"Rp {int(x):,}")
            if 'Total_Energi_kWh' in df_rekap.columns:
                df_rekap['Total_Energi_kWh'] = df_rekap['Total_Energi_kWh'].apply(lambda x: f"{x:.2f} kWh")
            if 'Avg_Suhu' in df_rekap.columns:
                df_rekap['Avg_Suhu'] = df_rekap['Avg_Suhu'].apply(lambda x: f"{x:.1f}°C")
            if 'Avg_Kelembaban' in df_rekap.columns:
                df_rekap['Avg_Kelembaban'] = df_rekap['Avg_Kelembaban'].apply(lambda x: f"{x:.1f}%")
            if 'Avg_Pencahayaan' in df_rekap.columns:
                df_rekap['Avg_Pencahayaan'] = df_rekap['Avg_Pencahayaan'].apply(lambda x: f"{x:.1f} lx")
            return df_rekap

        rekap_harian = format_rekap_df(rekap_harian)
        rekap_mingguan = format_rekap_df(rekap_mingguan)
        rekap_bulanan = format_rekap_df(rekap_bulanan)
        rekap_tahunan = format_rekap_df(rekap_tahunan)

        tab_summary_harian, tab_summary_mingguan, tab_summary_bulanan, tab_summary_tahunan = st.tabs(["Harian", "Mingguan", "Bulanan", "Tahunan"])

        with tab_summary_harian:
            st.subheader("Ringkasan Harian dalam Rentang Terpilih")
            if not rekap_harian.empty:
                st.dataframe(rekap_harian, use_container_width=True)
            else:
                st.info("Tidak ada data rekap harian dalam rentang tanggal yang dipilih.")

        with tab_summary_mingguan:
            st.subheader("Ringkasan Mingguan dalam Rentang Terpilih")
            if not rekap_mingguan.empty:
                st.dataframe(rekap_mingguan, use_container_width=True)
            else:
                st.info("Tidak ada data rekap mingguan dalam rentang tanggal yang dipilih.")

        with tab_summary_bulanan:
            st.subheader("Ringkasan Bulanan dalam Rentang Terpilih")
            if not rekap_bulanan.empty:
                st.dataframe(rekap_bulanan, use_container_width=True)
            else:
                st.info("Tidak ada data rekap bulanan dalam rentang tanggal yang dipilih.")

        with tab_summary_tahunan:
            st.subheader("Ringkasan Tahunan dalam Rentang Terpilih")
            if not rekap_tahunan.empty:
                st.dataframe(rekap_tahunan, use_container_width=True)
            else:
                st.info("Tidak ada data rekap tahunan dalam rentang tanggal yang dipilih.")

    else:
        st.info("Tidak ada kolom data yang sesuai untuk menampilkan rekap (Suhu, Kelembaban, Pencahayaan, Energi, Biaya) dalam rentang tanggal yang dipilih.")
else:
    st.info("Tidak ada data untuk menampilkan rekap dalam rentang tanggal yang dipilih.")

# --- REFRESH OTOMATIS ---
time.sleep(3)
st.rerun()