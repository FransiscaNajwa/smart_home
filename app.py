import streamlit as st
import pandas as pd
import requests
import plotly.express as px
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

# URL Flask
FLASK_API_URL = "http://localhost:5000/control"

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
        required_keys = ['device', 'timestamp', 'status', 'watt']
        missing_keys = [key for key in required_keys if key not in item]
        if missing_keys:
            st.error(f"❌ Data tidak memiliki kunci yang diperlukan: {missing_keys}, data: {item}")
            return False
        if item['device'] == 'lampu' and 'arus_lampu' not in item:
            st.error(f"❌ Data lampu tidak memiliki 'arus_lampu': {item}")
            return False
        if item['device'] == 'kipas' and 'arus_kipas' not in item:
            st.error(f"❌ Data kipas tidak memiliki 'arus_kipas': {item}")
            return False
    return True

# Fungsi untuk mengambil data dari Flask
def fetch_data(period):
    try:
        response = requests.get(FLASK_API_URL, params={"action": "data"}, timeout=5)
        response.raise_for_status()
        data = response.json()
        if check_data(data):
            df = pd.DataFrame(data)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.drop_duplicates().sort_values(by='timestamp')
            now = datetime.utcnow()
            if period == "weekly":
                start = now - timedelta(days=7)
            elif period == "monthly":
                start = now - timedelta(days=30)
            elif period == "yearly":
                start = now - timedelta(days=365)
            else:
                start = now - timedelta(days=1)
            df = df[df['timestamp'] >= start]
            return df
    except requests.exceptions.RequestException as e:
        st.error(f"❌ Gagal mengambil data dari Flask: {e}")
    return pd.DataFrame()

# Aplikasi Streamlit
st.title("🏠 Dashboard Smart Home IoT 🌐")

# Kontrol Manual
st.subheader("🎮 Kontrol Manual")
col1, col2 = st.columns(2)
with col1:
    st.write("💡 ESP32 - Kontrol Lampu")
    if st.button("🟢 Nyalakan Lampu"):
        try:
            response = requests.post(FLASK_API_URL, json={"device": "lampu", "state": "ON"}, timeout=5)
            response.raise_for_status()
            st.success("✅ Perintah Nyalakan Lampu dikirim")
        except requests.exceptions.RequestException as e:
            st.error(f"❌ Gagal mengirim perintah: {e}")
    if st.button("🔴 Matikan Lampu"):
        try:
            response = requests.post(FLASK_API_URL, json={"device": "lampu", "state": "OFF"}, timeout=5)
            response.raise_for_status()
            st.success("✅ Perintah Matikan Lampu dikirim")
        except requests.exceptions.RequestException as e:
            st.error(f"❌ Gagal mengirim perintah: {e}")
with col2:
    st.write("⚙️ ESP8266 - Kontrol Kipas")
    if st.button("🟢 Nyalakan Kipas"):
        try:
            response = requests.post(FLASK_API_URL, json={"device": "kipas", "state": "ON"}, timeout=5)
            response.raise_for_status()
            st.success("✅ Perintah Nyalakan Kipas dikirim")
        except requests.exceptions.RequestException as e:
            st.error(f"❌ Gagal mengirim perintah: {e}")
    if st.button("🔴 Matikan Kipas"):
        try:
            response = requests.post(FLASK_API_URL, json={"device": "kipas", "state": "OFF"}, timeout=5)
            response.raise_for_status()
            st.success("✅ Perintah Matikan Kipas dikirim")
        except requests.exceptions.RequestException as e:
            st.error(f"❌ Gagal mengirim perintah: {e}")

# Sidebar untuk pengaturan tarif
st.sidebar.header("⚙️ Pengaturan Tarif Listrik")
tariff = st.sidebar.number_input("💸 Tarif per kWh (Rp)", min_value=0, value=st.session_state.tariff, step=100)
if st.sidebar.button("💾 Simpan Tarif"):
    st.session_state.tariff = tariff
    st.sidebar.success(f"✅ Tarif diatur ke Rp {tariff}/kWh")

# Status Sensor Terkini
st.subheader("📡 Status Sensor Terkini")
try:
    df = fetch_data("daily")
    if not df.empty:
        latest_data = df.sort_values('timestamp', ascending=False).groupby('device').first().reset_index()

        col1, col2 = st.columns(2)
        with col1:
            if 'lampu' in latest_data['device'].values:
                lampu_data = latest_data[latest_data['device'] == 'lampu'].iloc[0]
                st.markdown("💡 **Lampu**")
                st.write(f"Arus: {lampu_data.get('arus_lampu', 0):.2f} A")
                st.write(f"Daya: {lampu_data.get('watt', 0):.2f} W")
                status = '🟢 ON' if lampu_data.get('status') == 'ON' else '🔴 OFF'
                st.write(f"Status: {status}")
                st.write(f"Kondisi: {lampu_data.get('kondisi_lampu', 'N/A')}")
            else:
                st.markdown("💡 **Lampu**")
                st.write("Status: UNKNOWN")

        with col2:
            if 'kipas' in latest_data['device'].values:
                kipas_data = latest_data[latest_data['device'] == 'kipas'].iloc[0]
                st.markdown("⚙️ **Kipas**")
                st.write(f"Arus: {kipas_data.get('arus_kipas', 0):.2f} A")
                st.write(f"Daya: {kipas_data.get('watt', 0):.2f} W")
                status = '🟢 ON' if kipas_data.get('status') == 'ON' else '🔴 OFF'
                st.write(f"Status: {status}")
                st.write(f"Kondisi: {kipas_data.get('kondisi_kipas', 'N/A')}")
            else:
                st.markdown("⚙️ **Kipas**")
                st.write("Status: UNKNOWN")
    else:
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("💡 **Lampu**")
            st.write("Status: UNKNOWN")
        with col2:
            st.markdown("⚙️ **Kipas**")
            st.write("Status: UNKNOWN")
except Exception as e:
    st.error(f"❌ Error saat memproses status: {e}")

# Total Biaya
st.subheader("💰 Total Biaya")
df = fetch_data("daily")
if not df.empty:
    try:
        df['duration_s'] = df.groupby('device')['timestamp'].diff().dt.total_seconds().fillna(0)
        df['energy_kwh'] = (df['watt'] * df['duration_s'] / 3600) / 1000
        df['cost'] = df['energy_kwh'] * st.session_state.tariff
        total_cost = df['cost'].sum()
        if total_cost < 0:
            total_cost = 0
        st.write(f"💸 **Total Biaya Hingga Saat Ini**: Rp {total_cost:,.2f}")
        st.write(f"🕒 Terakhir diperbarui: {df['timestamp'].max().strftime('%Y-%m-%d %H:%M:%S')}")
    except Exception as e:
        st.error(f"❌ Error saat menghitung total biaya: {e}")
else:
    st.write("😔 Tidak ada data untuk total biaya")

# Rekap dan Estimasi Konsumsi
st.subheader("📊 Rekap & Estimasi Konsumsi ⚡")
period = st.selectbox("📅 Pilih Periode", ["Mingguan", "Bulanan", "Tahunan"])
try:
    response = requests.get(FLASK_API_URL, params={
        "action": "cost_summary",
        "period": period.lower(),
        "tariff": st.session_state.tariff
    }, timeout=5)
    response.raise_for_status()
    summary = response.json()
    df = pd.DataFrame(summary.get('daily_summary', []))
    if not df.empty and 'timestamp' in df.columns:
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df['date'] = df['timestamp'].dt.date
        df = df.drop_duplicates().sort_values(by='date')

        rekap_df = df[['date', 'energy_kwh']].copy()
        rekap_df['harga'] = rekap_df['energy_kwh'] * st.session_state.tariff
        st.write(f"### Tabel Rekap {period}")
        st.table(rekap_df.style.format({
            'energy_kwh': '{:.3f}',
            'harga': 'Rp{:.2f}'
        }))

        st.write(f"⚡ **Total Energi ({period})**: {summary['total_energy_kwh']:.3f} kWh")
        st.write(f"💸 **Total Biaya ({period})**: Rp {summary['total_cost']:,.2f}")

        fig = px.line(df, x='date', y='energy_kwh', title=f"📈 Rekap Konsumsi {period}",
                      labels={'value': 'Energi (kWh)', 'date': 'Tanggal'})
        fig.update_traces(mode="lines+markers")
        st.plotly_chart(fig)

        days = (df['date'].max() - df['date'].min()).days if not df.empty and (df['date'].max() != df['date'].min()) else 1
        daily_avg_energy = summary['total_energy_kwh'] / days if summary['total_energy_kwh'] > 0 and days > 0 else 0
        period_days = {"Mingguan": 7, "Bulanan": 30, "Tahunan": 365}[period]
        estimated_energy = daily_avg_energy * period_days
        estimated_cost = estimated_energy * st.session_state.tariff
        if estimated_cost < 0:
            estimated_cost = 0
        st.write(f"🔮 **Estimasi Energi ({period})**: {estimated_energy:.3f} kWh")
        st.write(f"💰 **Estimasi Biaya ({period})**: Rp {estimated_cost:,.2f}")
    else:
        st.warning("😔 Tidak ada data untuk rekap atau estimasi")
except requests.exceptions.RequestException as e:
    st.error(f"❌ Gagal mengambil rekap: {e}")
except Exception as e:
    st.error(f"❌ Error saat memproses rekap: {e}")