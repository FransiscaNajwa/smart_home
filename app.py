import streamlit as st
import pandas as pd
import numpy as np
import requests
import json
from datetime import datetime, timedelta
import plotly.express as px
import time

# --- KONFIGURASI SERVER FLASK ---
FLASK_SERVER_URL = "http://localhost:5000"

# --- KONFIGURASI HALAMAN STREAMLIT ---
st.set_page_config(page_title="Smart Home Dashboard", layout="wide", initial_sidebar_state="expanded")
st.title("🏡 Smart Home Dashboard")

# --- FUNGSI UNTUK MENGAMBIL DATA DARI FLASK SERVER ---
@st.cache_data(ttl=3) # Cache data selama 3 detik untuk mengurangi panggilan ke Flask
def fetch_data_from_flask():
    try:
        response = requests.get(f"{FLASK_SERVER_URL}/data", timeout=5)
        response.raise_for_status() # Akan menimbulkan HTTPError untuk status kode 4xx/5xx
        data = response.json()
        
        # Perbaiki format timestamp pada data historis jika masih ISO format string
        # data[0] adalah current_status, data[1:] adalah historis
        if data and len(data) > 1: # Pastikan data tidak kosong dan ada entri historis
            for entry in data[1:]: # Iterasi dari elemen kedua (data historis)
                if "timestamp" in entry and isinstance(entry["timestamp"], str):
                    try:
                        entry["timestamp"] = datetime.fromisoformat(entry["timestamp"])
                    except ValueError:
                        # Fallback for older formats if ISO format fails
                        try:
                            entry["timestamp"] = datetime.strptime(entry["timestamp"], "%Y-%m-%d %H:%M:%S")
                        except ValueError:
                            # Jika tidak bisa diurai, set ke None atau datetime.now() sebagai fallback
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
def send_command_to_flask(device, state):
    try:
        response = requests.get(f"{FLASK_SERVER_URL}/control/{device}/{state}", timeout=5)
        response.raise_for_status()
        result = response.json()
        if result.get("status") == "sent":
            st.toast(f"Perintah '{state}' untuk {device} berhasil dikirim.", icon="✅")
            # Flask sekarang mengembalikan 'current_state' yang akurat
            return result.get("current_state") # Ini adalah yang paling penting!
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
df_combined = pd.DataFrame() # Inisialisasi df_combined di awal

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
        
        df_combined.rename(columns={"timestamp": "Waktu"}, inplace=True) # timestamp selalu ada

        if "daya" in df_combined.columns:
            interval_seconds = 5
            df_combined["Energi (kWh)"] = (df_combined["daya"] * interval_seconds / 3600) / 1000
            df_combined["Biaya (Rp)"] = df_combined["Energi (kWh)"] * biaya_per_kwh
            df_combined.rename(columns={"daya": "Daya (Watt)"}, inplace=True)
        else:
            df_combined["Energi (kWh)"] = 0
            df_combined["Biaya (Rp)"] = 0
            df_combined["Daya (Watt)"] = 0
    else:
        df_combined = pd.DataFrame()

# Inisialisasi default jika data tidak ada atau gagal diambil
if not data:
    current_status = {"lampu": "N/A", "kipas": "N/A", "lux": "N/A", "temp": "N/A", "kelembaban": "N/A", "timestamp": "N/A"}

# --- STATUS PERANGKAT DENGAN METRIC CARDS UNTUK LUX & SUHU ---
st.markdown("### 💡 Status Sensor & Perangkat (Terbaru)")
col_lux, col_temp, col_humidity = st.columns(3)

lux_val = current_status.get('lux', 'N/A')
temp_val = current_status.get('temp', 'N/A')
humidity_val = current_status.get('kelembaban', 'N/A')

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
lampu_icon = "💡" if current_status.get("lampu") == "ON" else "🌑"
kipas_icon = "🌀" if current_status.get("kipas") == "ON" else "🚫"

col_lampu_status.success(f"{lampu_icon} Lampu: **{current_status.get('lampu', 'N/A')}**")
# PERBAIKAN: Menggunakan kipas_icon, bukan kipas_status yang tidak terdefinisi
col_kipas_status.info(f"{kipas_icon} Kipas: **{current_status.get('kipas', 'N/A')}**") 

st.caption(f"Diperbarui: {current_status.get('timestamp', 'N/A')}")


# --- TOGGLE KONTROL ---
st.markdown("### 🎛️ Kontrol Manual Perangkat")
c5, c6 = st.columns(2)

# Ambil status dari Flask sebagai nilai default.
# current_status sudah diambil di awal script.
initial_lampu_state_from_flask = (current_status.get("lampu", "OFF") == "ON")
initial_kipas_state_from_flask = (current_status.get("kipas", "OFF") == "ON")

# Inisialisasi atau update st.session_state dengan nilai terkini dari Flask.
# Ini penting agar toggle selalu merefleksikan status asli saat halaman di-load atau refresh.
# Gunakan current_status.get("lampu") untuk memastikan status N/A tidak menyebabkan error
if current_status.get("lampu") != "N/A":
    st.session_state.lampu_state = initial_lampu_state_from_flask
else:
    if "lampu_state" not in st.session_state: # Default jika status N/A dan belum ada di session_state
        st.session_state.lampu_state = False # Default ke OFF (False)

if current_status.get("kipas") != "N/A":
    st.session_state.kipas_state = initial_kipas_state_from_flask
else:
    if "kipas_state" not in st.session_state: # Default jika status N/A dan belum ada di session_state
        st.session_state.kipas_state = False # Default ke OFF (False)

# Define callback functions for toggles
def toggle_lampu_callback():
    new_state = "ON" if st.session_state.toggle_lampu else "OFF"
    returned_state = send_command_to_flask("lampu", new_state)
    
    if returned_state is not None:
        # Perbarui st.session_state.lampu_state agar toggle segera berubah
        st.session_state.lampu_state = (returned_state == "ON")
        # Update current_status secara langsung untuk feedback di metric card
        st.session_state["current_status_lampu_override"] = returned_state
        # print(f"DEBUG APP.PY: Lampu toggle callback, set session_state.lampu_state to {st.session_state.lampu_state}")


def toggle_kipas_callback():
    new_state = "ON" if st.session_state.toggle_kipas else "OFF"
    returned_state = send_command_to_flask("kipas", new_state)
    
    if returned_state is not None:
        st.session_state.kipas_state = (returned_state == "ON")
        st.session_state["current_status_kipas_override"] = returned_state
        # print(f"DEBUG APP.PY: Kipas toggle callback, set session_state.kipas_state to {st.session_state.kipas_state}")


# Apply the overrides to current_status BEFORE displaying the metric cards
# This ensures instant visual feedback on the metric cards after a toggle click
if "current_status_lampu_override" in st.session_state:
    current_status["lampu"] = st.session_state.current_status_lampu_override
    # Hapus override setelah digunakan agar tidak terus-menerus menimpa data baru dari Flask
    # Pertimbangkan kapan harus menghapus ini. Jika dihapus terlalu cepat,
    # dan fetch_data_from_flask belum update, status bisa balik ke lama.
    # Biarkan saja jika TTL cache 3 detik sudah cukup cepat.
    # del st.session_state["current_status_lampu_override"] 

if "current_status_kipas_override" in st.session_state:
    current_status["kipas"] = st.session_state.current_status_kipas_override
    # del st.session_state["current_status_kipas_override"]


# Display toggles with callbacks
c5.toggle("Nyalakan / Matikan Lampu", value=st.session_state.lampu_state, key="toggle_lampu", on_change=toggle_lampu_callback, disabled=(current_status.get("lampu") == "N/A"))
if current_status.get("lampu") == "N/A":
    c5.warning("Status lampu tidak tersedia.")

c6.toggle("Nyalakan / Matikan Kipas", value=st.session_state.kipas_state, key="toggle_kipas", on_change=toggle_kipas_callback, disabled=(current_status.get("kipas") == "N/A"))
if current_status.get("kipas") == "N/A":
    c6.warning("Status kipas tidak tersedia.")


# --- GRAFIK KONSUMSI DAYA ---
st.markdown("### 📉 Konsumsi Daya 24 Jam Terakhir")
# Fetch data for 24h plot independent of sidebar date filter
all_raw_data_for_24h_plot = fetch_data_from_flask()
df_all_raw_for_24h_plot = pd.DataFrame(all_raw_data_for_24h_plot[1:]) if all_raw_data_for_24h_plot and len(all_raw_data_for_24h_plot) > 1 else pd.DataFrame()

if not df_all_raw_for_24h_plot.empty:
    df_all_raw_for_24h_plot["timestamp"] = pd.to_datetime(df_all_raw_for_24h_plot["timestamp"])
    
    if 'daya' in df_all_raw_for_24h_plot.columns:
        df_all_raw_for_24h_plot.rename(columns={'daya': 'Daya (Watt)'}, inplace=True)
    
    df_24h_plot = df_all_raw_for_24h_plot[df_all_raw_for_24h_plot["timestamp"] >= datetime.now() - timedelta(hours=24)]

    if not df_24h_plot.empty and "Daya (Watt)" in df_24h_plot.columns:
        fig = px.line(df_24h_plot, x="timestamp", y="Daya (Watt)", title="Daya (Watt)", labels={"Daya (Watt)": "Daya (Watt)"}, template="streamlit")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Tidak ada data daya untuk 24 jam terakhir.")
else:
    st.info("Data daya tidak tersedia atau format tidak sesuai untuk grafik konsumsi daya.")


# --- REKAP KONSUMSI ENERGI & DATA HISTORIS (Dalam Bentuk Rekap) ---
# Bagian ini dipindahkan ke paling bawah
st.markdown("### 📊 Rekap Data Konsumsi & Sensor")

if not df_combined.empty:
    df_combined['Tahun'] = df_combined['Waktu'].dt.year
    df_combined['Bulan'] = df_combined['Waktu'].dt.strftime('%Y-%m')
    df_combined['Minggu'] = df_combined['Waktu'].dt.strftime('%Y-W%W')

    agg_funcs = {}
    if 'Suhu' in df_combined.columns: agg_funcs['Avg_Suhu'] = ('Suhu', 'mean')
    if 'Kelembaban' in df_combined.columns: agg_funcs['Avg_Kelembaban'] = ('Kelembaban', 'mean')
    if 'Pencahayaan' in df_combined.columns: agg_funcs['Avg_Pencahayaan'] = ('Pencahayaan', 'mean')
    if 'Energi (kWh)' in df_combined.columns: agg_funcs['Total_Energi_kWh'] = ('Energi (kWh)', 'sum')
    if 'Biaya (Rp)' in df_combined.columns: agg_funcs['Estimasi_Biaya_Rp'] = ('Biaya (Rp)', 'sum')

    if agg_funcs:
        rekap_harian = df_combined.groupby(df_combined['Waktu'].dt.date).agg(**agg_funcs).reset_index()
        rekap_harian.rename(columns={'Waktu': 'Tanggal'}, inplace=True)
        
        rekap_mingguan = df_combined.groupby('Minggu').agg(**agg_funcs).reset_index()

        rekap_bulanan = df_combined.groupby('Bulan').agg(**agg_funcs).reset_index()
        
        rekap_tahunan = df_combined.groupby('Tahun').agg(**agg_funcs).reset_index()

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