import streamlit as st
import pandas as pd
import requests
import plotly.express as px
from datetime import datetime, timedelta

# URL API backend Flask
FLASK_API_URL = "http://localhost:5000/control"

if 'tariff' not in st.session_state:
    st.session_state.tariff = 1500

def check_data(data):
    if not isinstance(data, list) or not data:
        st.warning("😔 Data kosong atau format salah dari Flask")
        return False
    for item in data:
        base = ['device', 'timestamp', 'status', 'watt']
        if any(k not in item for k in base):
            st.error(f"❌ Field dasar hilang: {item}")
            return False
        if item['device'] == 'lampu' and 'arus_lampu' not in item:
            st.error(f"❌ Data lampu tidak punya 'arus_lampu': {item}")
            return False
        if item['device'] == 'kipas' and 'arus_kipas' not in item:
            st.error(f"❌ Data kipas tidak punya 'arus_kipas': {item}")
            return False
    return True

def fetch_data(period):
    try:
        r = requests.get(FLASK_API_URL, params={"action": "data"}, timeout=10)  # Increased timeout
        r.raise_for_status()
        data = r.json()
        if not check_data(data):
            return pd.DataFrame()
        df = pd.DataFrame(data)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.drop_duplicates().sort_values('timestamp')
        cutoff = {"weekly": 7, "monthly": 30}.get(period, 1)
        return df[df['timestamp'] >= datetime.utcnow() - timedelta(days=cutoff)]
    except requests.exceptions.Timeout:
        st.error("❌ Gagal fetch data: Permintaan ke API terlalu lama (timeout). Coba lagi atau periksa server.")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Gagal fetch data: {e}")
        return pd.DataFrame()

# UI
st.title("🏠 Dashboard Smart Home IoT")

# Status terkini
st.subheader("📡 Status Sensor Terkini")
df = fetch_data("daily")
if not df.empty:
    latest = df.sort_values('timestamp').groupby('device').last().reset_index()
    c1, c2 = st.columns(2)
    for col, dev in zip([c1, c2], ['lampu', 'kipas']):
        col.markdown(f"**{dev.capitalize()}**")
        if dev in latest['device'].values:
            d = latest[latest['device'] == dev].iloc[0]
            col.write(f"Arus: {d.get(f'arus_{dev}', 0):.2f} A")
            col.write(f"Daya: {d['watt']:.2f} W")
            state = '🟢 ON' if d['status'] == 'ON' else '🔴 OFF'
            col.write(f"Status: {state}")
            cond = d.get(f'kondisi_{dev}', 'N/A')
            col.write(f"Kondisi: {cond}")
        else:
            col.write("Status: UNKNOWN")
else:
    st.write("😔 Tidak ada data sensor.")

# Total biaya
st.subheader("💰 Total Biaya")
if not df.empty:
    df['duration'] = df.groupby('device')['timestamp'].diff().dt.total_seconds().fillna(0)
    df['energy_kwh'] = (df['watt'] * df['duration'] / 3600) / 1000
    df['cost'] = df['energy_kwh'] * st.session_state.tariff
    total = df['cost'].sum()
    st.write(f"💸 Total Biaya: Rp {total:,.2f}")
    st.write(f"🕒 Terakhir update: {df['timestamp'].max().strftime('%Y-%m-%d %H:%M:%S')}")
else:
    st.write("Tidak ada data untuk menghitung biaya.")

# Rekap & estimasi
st.subheader("📊 Rekap & Estimasi Konsumsi")
period = st.selectbox("Periode", ["weekly", "monthly"])
params = {"action": "cost_summary", "period": period, "tariff": st.session_state.tariff}
try:
    r = requests.get(FLASK_API_URL, params=params, timeout=30)  # Increased timeout
    r.raise_for_status()
    res = r.json()
    if res.get('status') == 'error':
        st.error(f"❌ Gagal rekap: {res.get('message', 'Unknown error')}")
    else:
        rec = pd.DataFrame(res.get('daily_summary', []))
        if not rec.empty and 'timestamp' in rec.columns:
            try:
                # Parse timestamp with specific format
                rec['timestamp'] = pd.to_datetime(rec['timestamp'], format="%a, %d %b %Y %H:%M:%S GMT", errors='coerce')
                if rec['timestamp'].isna().any():
                    st.warning("⚠️ Beberapa timestamp tidak dapat diparse. Data mungkin tidak lengkap.")
                    rec = rec.dropna(subset=['timestamp'])
                rec['date'] = rec['timestamp'].dt.date
                rec = rec.sort_values('date')
                rec['harga'] = rec['energy_kwh'] * st.session_state.tariff
                st.write(f"### Rekap {period.capitalize()}")
                st.table(rec[['date', 'energy_kwh', 'harga']].style.format({'energy_kwh': '{:.3f}', 'harga': 'Rp{:,.2f}'}))
                st.write(f"⚡ Total Energi: {res['total_energy_kwh']:.3f} kWh")
                st.write(f"💰 Total Biaya: Rp {res['total_cost']:,.2f}")
                fig = px.line(rec, x='date', y='energy_kwh', title="Konsumsi Harian")
                st.plotly_chart(fig)
                avg = res['total_energy_kwh'] / len(rec) if len(rec) > 0 else 0
                days = {'weekly': 7, 'monthly': 30}[period]
                est = avg * days
                st.write(f"🔮 Estimasi energi {period}: {est:.3f} kWh")
                st.write(f"💰 Estimasi biaya: Rp {(est * st.session_state.tariff):,.2f}")
            except ValueError as ve:
                st.error(f"❌ Gagal memproses timestamp: {ve}")
        else:
            st.warning("⚠️ Tidak ada data rekap untuk periode ini.")
except requests.exceptions.Timeout:
    st.error("❌ Gagal rekap: Permintaan ke API terlalu lama (timeout). Coba lagi atau optimalkan server.")
except requests.exceptions.HTTPError as e:
    st.error(f"❌ Gagal rekap: HTTP Error - {e}")
except Exception as e:
    st.error(f"❌ Gagal rekap: {e}")