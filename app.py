import streamlit as st
import pandas as pd
import requests
import plotly.express as px
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

# URL Flask
FLASK_API_URL = "http://localhost:5000/api"

# Inisialisasi session state untuk tarif listrik
if 'tariff' not in st.session_state:
    st.session_state.tariff = 1500  # Default Rp 1.500/kWh

# Fungsi untuk memeriksa data
def check_data(data):
    if not data:
        st.warning("😔 Data kosong dari Flask")
        return False
    if not isinstance(data, list):
        st.error(f"❌ Format data tidak valid: {data}")
        return False
    for item in data:
        required_keys = ['device', 'timestamp', 'received_at']
        if not all(key in item for key in required_keys):
            st.error(f"❌ Data tidak memiliki kunci yang diperlukan: {item}")
            return False
    return True

# Fungsi untuk menghasilkan data dummy otomatis
def init_dummy_data():
    try:
        from dummy_sender import generate_dummy_data
        # Periksa jumlah data di MongoDB
        response = requests.get(FLASK_API_URL, params={"action": "data", "limit": 1}, timeout=5)
        response.raise_for_status()
        data = response.json()
        if not data:
            st.write("ℹ️ Koleksi kosong, menghasilkan data dummy...")
            if generate_dummy_data(20):  # Hasilkan 20 record dummy
                st.success("✅ Berhasil menghasilkan 20 data dummy")
            else:
                st.error("❌ Gagal menghasilkan data dummy")
    except ImportError:
        st.error("❌ Modul dummy_sender tidak ditemukan")
    except requests.exceptions.RequestException as e:
        st.error(f"❌ Gagal memeriksa data di Flask: {e}")
    except Exception as e:
        st.error(f"❌ Error saat inisialisasi data dummy: {e}")

# Inisialisasi data dummy saat aplikasi dimulai
init_dummy_data()

# Aplikasi Streamlit
st.title("🏠 Dashboard IoT Smart Home 🌐")

# Sidebar untuk pengaturan tarif
st.sidebar.header("⚙️ Pengaturan Tarif Listrik")
tariff = st.sidebar.number_input("💸 Tarif per kWh (Rp)", min_value=0, value=st.session_state.tariff, step=100)
if st.sidebar.button("💾 Simpan Tarif"):
    st.session_state.tariff = tariff
    st.sidebar.success(f"✅ Tarif diatur ke Rp {tariff}/kWh")

# Status Sensor Terkini (Visual dengan Kotak)
st.subheader("📡 Status Sensor Terkini")
try:
    response = requests.get(FLASK_API_URL, params={"action": "data", "limit": 100}, timeout=5)
    response.raise_for_status()
    data = response.json()
    if check_data(data):
        df = pd.DataFrame(data)
        st.write(f"ℹ️ Berhasil mengambil {len(df)} record dari MongoDB (dummy dan sensor)")
        latest_data = df.sort_values('received_at', ascending=False).groupby('device').first().reset_index()

        # Layout dengan kolom untuk ESP32 dan ESP8266
        col1, col2 = st.columns(2)
        
        with col1:
            for _, row in latest_data.iterrows():
                if row['device'] == 'ESP32':
                    with st.container():
                        st.markdown(f"<div style='background-color: #e6ffe6; padding: 10px; border-radius: 5px;'>", unsafe_allow_html=True)
                        st.markdown(f"💡 **Lampu**")
                        lux = row.get('lux', 'N/A')
                        if lux != 'N/A':
                            st.markdown(f"Lux: {lux}")
                        actuator_state = '🟢 ON' if row.get('actuator_state', False) else '🔴 OFF'
                        st.markdown(f"Status: {actuator_state}")
                        st.markdown("</div>", unsafe_allow_html=True)

        with col2:
            for _, row in latest_data.iterrows():
                if row['device'] == 'ESP8266':
                    with st.container():
                        st.markdown(f"<div style='background-color: #e6ffe6; padding: 10px; border-radius: 5px;'>", unsafe_allow_html=True)
                        st.markdown(f"⚙️ **Kipas**")
                        temp = row.get('temperature', 'N/A')
                        if temp != 'N/A':
                            st.markdown(f"Suhu: {temp} °C")
                        hum = row.get('humidity', 'N/A')
                        if hum != 'N/A':
                            st.markdown(f"Kelembapan: {hum} %")
                        actuator_state = '🟢 ON' if row.get('actuator_state', False) else '🔴 OFF'
                        st.markdown(f"Status: {actuator_state}")
                        st.markdown("</div>", unsafe_allow_html=True)
    else:
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"<div style='background-color: #e6ffe6; padding: 10px; border-radius: 5px;'>", unsafe_allow_html=True)
            st.markdown(f"💡 **Lampu**")
            st.markdown("Status: UNKNOWN")
            st.markdown("</div>", unsafe_allow_html=True)
        with col2:
            st.markdown(f"<div style='background-color: #e6ffe6; padding: 10px; border-radius: 5px;'>", unsafe_allow_html=True)
            st.markdown(f"⚙️ **Kipas**")
            st.markdown("Status: UNKNOWN")
            st.markdown("</div>", unsafe_allow_html=True)
except requests.exceptions.RequestException as e:
    st.error(f"❌ Gagal menghubungi Flask: {e}")
    data = []
except Exception as e:
    st.error(f"❌ Error saat memproses data: {e}")
    data = []

# Total Biaya
st.subheader("💰 Total Biaya")
if data and check_data(data):
    try:
        df = pd.DataFrame(data)
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', errors='coerce')
        df = df.dropna(subset=['timestamp'])
        df = df.sort_values('timestamp')  # Urutkan berdasarkan timestamp
        df['power_w'] = 0
        df.loc[(df['device'] == 'ESP32') & (df['actuator_state'] == True), 'power_w'] = 5
        df.loc[(df['device'] == 'ESP8266') & (df['actuator_state'] == True), 'power_w'] = 10
        df['duration_h'] = df['timestamp'].diff().dt.total_seconds() / 3600
        df['duration_h'].fillna(0, inplace=True)
        df['duration_h'] = df['duration_h'].clip(lower=0)  # Pastikan tidak ada durasi negatif
        df['energy_kwh'] = df['power_w'] * df['duration_h'] / 1000
        df['cost'] = df['energy_kwh'] * st.session_state.tariff
        total_cost = df['cost'].sum()
        if total_cost < 0:
            total_cost = 0  # Pastikan total biaya tidak negatif
        st.write(f"💸 **Total Biaya Hingga Saat Ini**: Rp {total_cost:,.2f}")
    except Exception as e:
        st.error(f"❌ Error saat menghitung total biaya: {e}")
else:
    st.write("😔 Tidak ada data untuk total biaya")

# Rekap dan Estimasi Konsumsi
st.subheader("📊 Rekap & Estimasi Konsumsi ⚡")
period = st.selectbox("📅 Pilih Periode", ["Mingguan", "Bulanan", "Tahunan"])
try:
    period_map = {"Mingguan": "weekly", "Bulanan": "monthly", "Tahunan": "yearly"}
    days_map = {"Mingguan": 7, "Bulanan": 30, "Tahunan": 365}

    # Ambil data rekap dari Flask
    response = requests.get(FLASK_API_URL, params={"action": "cost_summary", "period": period_map[period], "tariff": st.session_state.tariff}, timeout=5)
    response.raise_for_status()
    summary = response.json()
    st.write(f"⚡ **Total Energi ({period})**: {summary.get('total_energy_kwh', 0):.3f} kWh")
    st.write(f"💸 **Total Biaya ({period})**: Rp {summary.get('total_cost', 0):,.2f}")

    # Grafik Konsumsi
    daily_df = pd.DataFrame(summary.get('daily_summary', []))
    if not daily_df.empty:
        daily_df['date'] = pd.to_datetime(daily_df['date'])
        fig = px.line(daily_df, x='date', y=['energy_kwh', 'cost'], title=f"📈 Rekap Konsumsi {period}",
                      labels={'value': 'Nilai', 'date': 'Tanggal', 'variable': 'Metrik'})
        st.plotly_chart(fig)
    else:
        st.warning("😔 Tidak ada data untuk grafik konsumsi")

    # Estimasi berdasarkan periode yang dipilih
    if data and check_data(data):
        df = pd.DataFrame(data)
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', errors='coerce')
        df = df.dropna(subset=['timestamp'])
        df = df.sort_values('timestamp')
        df['power_w'] = 0
        df.loc[(df['device'] == 'ESP32') & (df['actuator_state'] == True), 'power_w'] = 5
        df.loc[(df['device'] == 'ESP8266') & (df['actuator_state'] == True), 'power_w'] = 10
        df['duration_h'] = df['timestamp'].diff().dt.total_seconds() / 3600
        df['duration_h'].fillna(0, inplace=True)
        df['duration_h'] = df['duration_h'].clip(lower=0)
        df['energy_kwh'] = df['power_w'] * df['duration_h'] / 1000
        total_energy = df['energy_kwh'].sum()
        if total_energy < 0:
            total_energy = 0

        days = (df['timestamp'].max() - df['timestamp'].min()).total_seconds() / (3600 * 24)
        if days <= 0:
            days = 1
        daily_avg_energy = total_energy / days if total_energy > 0 else 0
        if daily_avg_energy < 0:
            daily_avg_energy = 0

        # Estimasi untuk periode yang dipilih
        estimated_days = days_map[period]
        estimated_energy = daily_avg_energy * estimated_days
        estimated_cost = estimated_energy * st.session_state.tariff
        if estimated_cost < 0:
            estimated_cost = 0
        st.write(f"🔮 **Estimasi Energi ({period})**: {estimated_energy:.3f} kWh")
        st.write(f"💰 **Estimasi Biaya ({period})**: Rp {estimated_cost:,.2f}")
    else:
        st.write("😔 Tidak ada data untuk estimasi")
except requests.exceptions.RequestException as e:
    st.error(f"❌ Gagal mengambil rekap: {e}")
except Exception as e:
    st.error(f"❌ Error saat memproses rekap: {e}")

# Kontrol Manual
st.subheader("🎮 Kontrol Manual")
col1, col2 = st.columns(2)
with col1:
    st.write("💡 ESP32 - Kontrol LED")
    if st.button("🟢 Nyalakan LED"):
        payload = {"device": "ESP32", "actuator": "LED", "state": True}
        try:
            response = requests.post(FLASK_API_URL, params={"action": "control"}, json=payload, timeout=5)
            response.raise_for_status()
            st.success("✅ Perintah Nyalakan LED dikirim")
        except requests.exceptions.RequestException as e:
            st.error(f"❌ Gagal mengirim perintah: {e}")
        except Exception as e:
            st.error(f"❌ Error: {e}")
    if st.button("🔴 Matikan LED"):
        payload = {"device": "ESP32", "actuator": "LED", "state": False}
        try:
            response = requests.post(FLASK_API_URL, params={"action": "control"}, json=payload, timeout=5)
            response.raise_for_status()
            st.success("✅ Perintah Matikan LED dikirim")
        except requests.exceptions.RequestException as e:
            st.error(f"❌ Gagal mengirim perintah: {e}")
        except Exception as e:
            st.error(f"❌ Error: {e}")
with col2:
    st.write("⚙️ ESP8266 - Kontrol Motor")
    if st.button("🟢 Nyalakan Motor"):
        payload = {"device": "ESP8266", "actuator": "MOTOR", "state": True}
        try:
            response = requests.post(FLASK_API_URL, params={"action": "control"}, json=payload, timeout=5)
            response.raise_for_status()
            st.success("✅ Perintah Nyalakan Motor dikirim")
        except requests.exceptions.RequestException as e:
            st.error(f"❌ Gagal mengirim perintah: {e}")
        except Exception as e:
            st.error(f"❌ Error: {e}")
    if st.button("🔴 Matikan Motor"):
        payload = {"device": "ESP8266", "actuator": "MOTOR", "state": False}
        try:
            response = requests.post(FLASK_API_URL, params={"action": "control"}, json=payload, timeout=5)
            response.raise_for_status()
            st.success("✅ Perintah Matikan Motor dikirim")
        except requests.exceptions.RequestException as e:
            st.error(f"❌ Gagal mengirim perintah: {e}")
        except Exception as e:
            st.error(f"❌ Error: {e}")