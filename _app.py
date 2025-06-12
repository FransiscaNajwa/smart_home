import streamlit as st
import pandas as pd
import requests
import plotly.express as px
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

# Flask API URL
FLASK_API_URL = "http://localhost:5000/api"

# Initialize session state for tariff
if 'tariff' not in st.session_state:
    st.session_state.tariff = 1500  # Default Rp 1.500/kWh

# Function to check data validity
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

# Function to generate dummy data
def init_dummy_data():
    try:
        from dummy_sender import generate_dummy_data
        response = requests.get(FLASK_API_URL, params={"action": "data", "limit": 1}, timeout=5)
        response.raise_for_status()
        data = response.json()
        if not data:
            st.write("ℹ️ Koleksi kosong, menghasilkan data dummy...")
            if generate_dummy_data(20):
                st.success("✅ Berhasil menghasilkan 20 data dummy")
            else:
                st.error("❌ Gagal menghasilkan data dummy")
    except ImportError:
        st.error("❌ Modul dummy_sender tidak ditemukan")
    except requests.exceptions.RequestException as e:
        st.error(f"❌ Gagal memeriksa data di Flask: {e}")
    except Exception as e:
        st.error(f"❌ Error saat inisialisasi data dummy: {e}")

# Initialize dummy data on app start
init_dummy_data()

# Streamlit app title
st.title("🏠 Dashboard IoT Smart Home 🌐")

# Sidebar for tariff settings
st.sidebar.header("⚙️ Pengaturan Tarif Listrik")
tariff = st.sidebar.number_input("💸 Tarif per kWh (Rp)", min_value=0, value=st.session_state.tariff, step=100)
if st.sidebar.button("💾 Simpan Tarif"):
    st.session_state.tariff = tariff
    st.sidebar.success(f"✅ Tarif diatur ke Rp {tariff}/kWh")

# Include CSS and Font Awesome
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
.bg-yellow { background-color: #f59e0b; }
.bg-blue { background-color: #3b82f6; }
.bg-green { background-color: #10b981; }
.bg-purple { background-color: #8b5cf6; }
.bg-red { background-color: #ef4444; }
.bg-orange { background-color: #f97316; }
.metric-title { font-size: 0.875rem; font-weight: 600; }
.metric-value { font-size: 1.25rem; font-weight: 700; }
.metric-icon { font-size: 1.5rem; }
.text-content { display: flex; flex-direction: column; }
</style>
""", unsafe_allow_html=True)

# Current Sensor Status
st.subheader("📡 Status Sensor Terkini")
try:
    response = requests.get(FLASK_API_URL, params={"action": "data", "limit": 100}, timeout=5)
    response.raise_for_status()
    data = response.json()
    if check_data(data):
        df = pd.DataFrame(data)
        latest_data = df.sort_values('received_at', ascending=False).groupby('device').first().reset_index()

        col1, col2 = st.columns(2)

        with col1:
            esp32_data = latest_data[latest_data['device'] == 'ESP32']
            if not esp32_data.empty:
                row = esp32_data.iloc[0]
                lux = row.get('lux', 'N/A')
                actuator_state = '🟢 ON' if row.get('actuator_state', False) else '🔴 OFF'
                card_html = f"""
                <div class="metric-card bg-yellow">
                    <i class="fas fa-lightbulb metric-icon"></i>
                    <div class="text-content">
                        <div class="metric-title">Lampu</div>
                        <div class="metric-value">Lux: {lux}</div>
                        <div class="metric-value">Status: {actuator_state}</div>
                    </div>
                </div>
                """
                st.markdown(card_html, unsafe_allow_html=True)
            else:
                st.markdown("""
                <div class="metric-card bg-yellow">
                    <i class="fas fa-lightbulb metric-icon"></i>
                    <div class="text-content">
                        <div class="metric-title">Lampu</div>
                        <div class="metric-value">Status: UNKNOWN</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

        with col2:
            esp8266_data = latest_data[latest_data['device'] == 'ESP8266']
            if not esp8266_data.empty:
                row = esp8266_data.iloc[0]
                temp = row.get('temperature', 'N/A')
                hum = row.get('humidity', 'N/A')
                actuator_state = '🟢 ON' if row.get('actuator_state', False) else '🔴 OFF'
                card_html = f"""
                <div class="metric-card bg-blue">
                    <i class="fas fa-fan metric-icon"></i>
                    <div class="text-content">
                        <div class="metric-title">Kipas</div>
                        <div class="metric-value">Suhu: {temp} °C</div>
                        <div class="metric-value">Kelembapan: {hum} %</div>
                        <div class="metric-value">Status: {actuator_state}</div>
                    </div>
                </div>
                """
                st.markdown(card_html, unsafe_allow_html=True)
            else:
                st.markdown("""
                <div class="metric-card bg-blue">
                    <i class="fas fa-fan metric-icon"></i>
                    <div class="text-content">
                        <div class="metric-title">Kipas</div>
                        <div class="metric-value">Status: UNKNOWN</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
except requests.exceptions.RequestException as e:
    st.error(f"❌ Gagal menghubungi Flask: {e}")
except Exception as e:
    st.error(f"❌ Error saat memproses data: {e}")

# Total Cost
st.subheader("💰 Total Biaya")
if data and check_data(data):
    try:
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
        df['cost'] = df['energy_kwh'] * st.session_state.tariff
        total_cost = df['cost'].sum()
        if total_cost < 0:
            total_cost = 0
        card_html = f"""
        <div class="metric-card bg-green">
            <i class="fas fa-money-bill-wave metric-icon"></i>
            <div class="text-content">
                <div class="metric-title">Total Biaya Hingga Saat Ini</div>
                <div class="metric-value">Rp {total_cost:,.2f}</div>
            </div>
        </div>
        """
        st.markdown(card_html, unsafe_allow_html=True)
    except Exception as e:
        st.error(f"❌ Error saat menghitung total biaya: {e}")
else:
    st.write("😔 Tidak ada data untuk total biaya")

# Consumption Summary and Estimation
st.subheader("📊 Rekap & Estimasi Konsumsi ⚡")
period = st.selectbox("📅 Pilih Periode", ["Mingguan", "Bulanan", "Tahunan"])
try:
    period_map = {"Mingguan": "weekly", "Bulanan": "monthly", "Tahunan": "yearly"}
    days_map = {"Mingguan": 7, "Bulanan": 30, "Tahunan": 365}

    response = requests.get(FLASK_API_URL, params={"action": "cost_summary", "period": period_map[period], "tariff": st.session_state.tariff}, timeout=5)
    response.raise_for_status()
    summary = response.json()

    energy_card = f"""
    <div class="metric-card bg-purple">
        <i class="fas fa-bolt metric-icon"></i>
        <div class="text-content">
            <div class="metric-title">Total Energi ({period})</div>
            <div class="metric-value">{summary.get('total_energy_kwh', 0):.3f} kWh</div>
        </div>
    </div>
    """
    cost_card = f"""
    <div class="metric-card bg-red">
        <i class="fas fa-wallet metric-icon"></i>
        <div class="text-content">
            <div class="metric-title">Total Biaya ({period})</div>
            <div class="metric-value">Rp {summary.get('total_cost', 0):,.2f}</div>
        </div>
    </div>
    """
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(energy_card, unsafe_allow_html=True)
    with col2:
        st.markdown(cost_card, unsafe_allow_html=True)

    daily_df = pd.DataFrame(summary.get('daily_summary', []))
    if not daily_df.empty:
        daily_df['date'] = pd.to_datetime(daily_df['date'])
        fig = px.line(daily_df, x='date', y=['energy_kwh', 'cost'], title=f"📈 Rekap Konsumsi {period}")
        st.plotly_chart(fig)
    else:
        st.warning("😔 Tidak ada data untuk grafik konsumsi")

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
        estimated_days = days_map[period]
        estimated_energy = daily_avg_energy * estimated_days
        estimated_cost = estimated_energy * st.session_state.tariff
        if estimated_cost < 0:
            estimated_cost = 0
        estimation_card = f"""
        <div class="metric-card bg-orange">
            <i class="fas fa-chart-line metric-icon"></i>
            <div class="text-content">
                <div class="metric-title">Estimasi ({period})</div>
                <div class="metric-value">Energi: {estimated_energy:.3f} kWh</div>
                <div class="metric-value">Biaya: Rp {estimated_cost:,.2f}</div>
            </div>
        </div>
        """
        st.markdown(estimation_card, unsafe_allow_html=True)
    else:
        st.write("😔 Tidak ada data untuk estimasi")
except requests.exceptions.RequestException as e:
    st.error(f"❌ Gagal mengambil rekap: {e}")
except Exception as e:
    st.error(f"❌ Error saat memproses rekap: {e}")

# Manual Control
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
    if st.button("🔴 Matikan LED"):
        payload = {"device": "ESP32", "actuator": "LED", "state": False}
        try:
            response = requests.post(FLASK_API_URL, params={"action": "control"}, json=payload, timeout=5)
            response.raise_for_status()
            st.success("✅ Perintah Matikan LED dikirim")
        except requests.exceptions.RequestException as e:
            st.error(f"❌ Gagal mengirim perintah: {e}")
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
    if st.button("🔴 Matikan Motor"):
        payload = {"device": "ESP8266", "actuator": "MOTOR", "state": False}
        try:
            response = requests.post(FLASK_API_URL, params={"action": "control"}, json=payload, timeout=5)
            response.raise_for_status()
            st.success("✅ Perintah Matikan Motor dikirim")
        except requests.exceptions.RequestException as e:
            st.error(f"❌ Gagal mengirim perintah: {e}")