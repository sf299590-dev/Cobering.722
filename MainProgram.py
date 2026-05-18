import streamlit as st
import ee
import folium
from streamlit_folium import folium_static
import datetime

# 1. TEMA & CSS (Versi Terang & Bersih)
st.set_page_config(page_title="COBERING-722", page_icon="🪸", layout="wide")

st.markdown("""
    <style>
    [data-testid="stSidebar"] {
        background-color: #f8f9fa !important;
        min-width: 260px !important;
        max-width: 260px !important;
        border-right: 1px solid #e0e0e0;
    }
    [data-testid="stSidebar"] .stMarkdown, 
    [data-testid="stSidebar"] label, 
    [data-testid="stSidebar"] .stRadio div {
        color: #1f2937 !important;
        font-weight: 500;
    }
    .stHorizontalBlock { gap: 12px !important; }
    
    /* Style untuk kotak kontainer utama */
    div[data-testid="stVerticalBlock"] > div[style*="border"] {
        padding: 18px !important;
        border-radius: 12px !important;
        background-color: #ffffff;
        border: 1px solid #eaeaea !important;
        box-shadow: 0 2px 4px rgba(0,0,0,0.04);
    }
    .main-title {
        color: #0e3a66;
        font-weight: bold;
        text-align: center;
        margin-top: -40px;
    }
    .caption-text {
        font-size: 11px;
        color: #6b7280;
        line-height: 1.4;
        margin-top: -8px;
    }
    
    /* Style kustom untuk kotak informasi baris bawah agar tingginya seragam dan rapi */
    .info-card {
        padding: 12px !important;
        border-radius: 8px !important;
        font-size: 11px !important;
        line-height: 1.4 !important;
        height: 105px; /* Kunci tinggi kotak informasi agar sejajar rata */
        display: flex;
        align-items: flex-start;
    }
    .info-blue { background-color: #eff6ff; border-left: 4px solid #2563eb; color: #1e40af; }
    .info-green { background-color: #f0fdf4; border-left: 4px solid #16a34a; color: #166534; }
    .info-orange { background-color: #fff7ed; border-left: 4px solid #ea580c; color: #9a3412; }
    </style>
    """, unsafe_allow_html=True)



# 2. INIT GEE (Versi Kunci Total: Kebal Gcloud di Cloud & Lokal)
@st.cache_resource
def init_ee():
    # 1. Coba deteksi lingkungan Cloud secara aman tanpa memicu error mleduk di lokal
    try:
        if hasattr(st, "secrets") and st.secrets.get("client_email") and st.secrets.get("private_key"):
            client_email = st.secrets["client_email"]
            raw_key = st.secrets["private_key"]
            
            # Memastikan karakter \n dibaca dengan benar sebagai baris baru oleh Google API
            private_key = raw_key.replace('\\n', '\n')
            
            # Inisialisasi kredensial Service Account untuk Server Cloud
            credentials = ee.ServiceAccountCredentials(client_email, key_data=private_key)
            ee.Initialize(credentials, project='coral-monitoring-prd')
            return  # Sukses di cloud, langsung keluar fungsi
    except Exception as cloud_err:
            # st.warning(f"Gagal Inisialisasi Cloud: {cloud_err}. Mencoba fallback ke lokal...")
            pass  # Kita ganti pakai pass agar dia silent/diam-diam saja saat fallback di lokal

    # 2. Opsi fallback otomatis khusus untuk Laptop Lokal (localhost)
    # Ini yang bikin laptop lokal kamu lancar jaya pakai akun gcloud sendiri
    try:
        ee.Initialize(project='coral-monitoring-prd')
    except Exception:
        try:
            ee.Authenticate()
            ee.Initialize(project='coral-monitoring-prd')
        except Exception as local_err:
            st.error(f"Gagal Inisialisasi Earth Engine Lokal: {local_err}")

init_ee()


# 3. SIDEBAR
with st.sidebar:
    st.title("COBERING-722")
    st.markdown('<p class="caption-text">Platform berbasis web untuk monitoring kesehatan terumbu karang dengan memanfaatkan data penginderaan jauh satelit.</p>', unsafe_allow_html=True)
    st.markdown("---")
    
    lokasi_pilihan = st.selectbox("Pilih Lokasi", ["Raja Ampat", "Bunaken", "Lombok", "Pangandaran", 
        "Wakatobi", "Kepulauan Derawan", "Karimunjawa", 
        "Pulau Weh", "Bali", "Taman Laut Banda"
])
    date_input = st.date_input("Tanggal", datetime.date.today() - datetime.timedelta(days=3))
    mode_peta = st.radio("Mode:", ["Suhu Laut (SST)", "Sentinel-2"])
    
    if mode_peta == "Sentinel-2":
        st.markdown('<p class="caption-text" style="color: #047857; font-weight: normal;">ℹ️ <b>Sentinel-2:</b> Menyediakan citra untuk pemetaan vegetasi, lamun, dan perubahan garis pantai terkait ekosistem di laut.</p>', unsafe_allow_html=True)
        
    st.markdown("---")
    st.caption("Platform Monitoring")

# 4. KOORDINAT
daftar_koordinat = {
    "Raja Ampat": [-0.71, 130.65], "Bunaken": [1.68, 124.72],
    "Lombok": [-8.38, 116.03], "Pangandaran": [-7.85, 108.50], "Bali": [-8.90, 115.15], 'Pulau Weh': [5.95, 95.30],'Karimunjawa': [-5.75, 110.45],'Taman Laut Banda': [-4.60, 129.90],  'Kepulauan Derawan': [2.35, 118.35]
}
coords = daftar_koordinat.get(lokasi_pilihan)

# 5. FUNGSI AMBIL DATA
def get_gee_data(target_date, coords, mode):
    ee_date = ee.Date(target_date.strftime('%Y-%m-%d'))
    point = ee.Geometry.Point([coords[1], coords[0]])
    
    if mode == "Suhu Laut (SST)":
        ds = ee.ImageCollection("NOAA/CDR/OISST/V2_1") \
               .filterDate(ee_date.advance(-2, 'day'), ee_date.advance(1, 'day'))
        if ds.size().getInfo() == 0: return None, None
        img = ds.sort('system:time_start', False).first().select('sst').multiply(0.01)
        vis = {'min': 26, 'max': 31, 'palette': ['blue', 'cyan', 'green', 'yellow', 'red']}
        return img, vis
    else:
        s2 = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED") \
               .filterBounds(point.buffer(5000)) \
               .filterDate(ee_date.advance(-90, 'day'), ee_date.advance(1, 'day')) \
               .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 30)) \
               .sort('system:time_start', False)
        if s2.size().getInfo() == 0: return None, None
        img = s2.first()
        vis = {'min': 0, 'max': 3000, 'bands': ['B4', 'B3', 'B2'], 'gamma': 1.4}
        return img, vis

# 6. PETA
st.markdown("<h1 class='main-title'>COBERING-722 🪸</h1>", unsafe_allow_html=True)
display_img, vis_params = get_gee_data(date_input, coords, mode_peta)

with st.container(border=True):
    st.write(f"**Peta Wilayah:** {lokasi_pilihan} ({mode_peta})")
    m = folium.Map(location=coords, zoom_start=13 if mode_peta == "Sentinel-2" else 9)
    
    if display_img:
        map_id = display_img.getMapId(vis_params)
        folium.TileLayer(tiles=map_id['tile_fetcher'].url_format, attr='GEE', overlay=True).add_to(m)
        
    folium.Marker(
        location=coords,
        popup=f"Titik Pengamatan: {lokasi_pilihan}",
        tooltip=f"Lokasi: {lokasi_pilihan}",
        icon=folium.Icon(color="blue", icon="info-sign")
    ).add_to(m)
    
    folium_static(m, width=1100, height=400)

# 7. BAR BAWAH
anomaly = None 

# --- BARIS UTAMA (Metrik & Angka) ---
c1, c2, c3, c4 = st.columns(4)
with c1:
    with st.container(border=True):
        st.write("**INFO WILAYAH**")
        st.write(f"📍 {lokasi_pilihan}")
        st.write(f"📅 {date_input}")
with c2:
    with st.container(border=True):
        st.write("**ANOMALI SUHU**")
        if mode_peta == "Suhu Laut (SST)" and display_img:
            point_geom = ee.Geometry.Point([coords[1], coords[0]])
            sample = display_img.sample(point_geom, 30).first().getInfo()
            if sample:
                val = sample['properties']['sst']
                hist = ee.ImageCollection("NOAA/CDR/OISST/V2_1") \
                        .filter(ee.Filter.calendarRange(date_input.month, date_input.month, 'month')) \
                        .filter(ee.Filter.calendarRange(2010, 2020, 'year')) \
                        .select('sst').median().multiply(0.01)
                hist_val = hist.sample(point_geom, 30).first().getInfo()['properties']['sst']
                anomaly = val - hist_val
                st.metric("SST", f"{val:.1f}°C", f"{anomaly:.2f}°C")
        else:
            st.write("N/A (Pilih Mode SST)")
with c3:
    with st.container(border=True):
        st.write("**DETEKSI**")
        if anomaly is None:
            st.write("N/A (Butuh Data SST)")
        elif anomaly > 1: 
            st.error("⚠️ STATUS: ALERT LEVEL 1")
        elif anomaly > 0: 
            st.warning("🟡 STATUS: WASPADA")
        else: 
            st.success("✅ STATUS: AMAN")
with c4:
    with st.container(border=True):
        st.write("**LEGENDA**")
        # Bar warna gradien dengan margin bawah yang pas
        st.markdown('<div style="height:15px; background:linear-gradient(to right, blue, cyan, green, yellow, red); border-radius:5px; margin-bottom:8px;"></div>', unsafe_allow_html=True)
        
        # Keterangan Angka Suhu dengan tambahan jarak vertikal (margin-top)
        st.markdown('''
            <div style="display:flex; justify-content:space-between; font-size:11px; font-weight:600; color:#333333; margin-top:6px; margin-bottom:4px;">
                <span>26°C</span>
                <span>28.5°C</span>
                <span>31°C</span>
            </div>
        ''', unsafe_allow_html=True)

# --- BARIS KEDUA (Khusus Kotak Informasi / Deskripsi Keterangan) ---
st.markdown("<div style='margin-top: -10px;'></div>", unsafe_allow_html=True) # Merapatkan jarak antar baris kotak
inf1, inf2, inf3, inf4 = st.columns(4)
with inf1:
    st.markdown('<div class="info-card info-blue">ℹ️ Pemilihan tanggal minimum H-3 direkomendasikan karena transmisi dan pemrosesan komputasi data satelit membutuhkan waktu penyediaan data tepat waktu.</div>', unsafe_allow_html=True)
with inf2:
    if mode_peta == "Suhu Laut (SST)" and anomaly is not None:
        st.markdown('<div class="info-card info-green">💡 Perhitungan: Nilai Suhu Permukaan Laut (SST) aktual dikurangi rata-rata batas historis klimatologi (median bulanan) perairan pada rentang 2010–2020.</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="info-card info-green">💡 Perhitungan: Menunggu data Suhu Permukaan Laut (SST) aktif untuk menghitung selisih nilai anomali suhu perairan.</div>', unsafe_allow_html=True)
with inf3:
    if anomaly is None:
        st.markdown('<div class="info-card info-orange">🔍 Kriteria: Menunggu input data SST. Status bleaching dihitung berdasarkan besaran deviasi nilai anomali terhadap ambang toleransi karang.</div>', unsafe_allow_html=True)
    elif anomaly > 1:
        st.markdown('<div class="info-card info-orange">🔍 Kriteria: Anomali &gt; 1°C. Suhu air laut melonjak tinggi di atas batas wajar bulanan, memicu stres termal akut dan pemutihan karang massal.</div>', unsafe_allow_html=True)
    elif anomaly > 0:
        st.markdown('<div class="info-card info-orange">🔍 Kriteria: Anomali 0°C s.d 1°C. Perairan terindikasi mengalami pemanasan ringan di atas rata-rata acuan lokal, membutuhkan pengawasan.</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="info-card info-orange">🔍 Kriteria: Anomali &le; 0°C. Suhu perairan terpantau normal atau lebih dingin dari rata-rata historisnya, kondisi terumbu karang aman.</div>', unsafe_allow_html=True)
with inf4:
    st.markdown('<div class="info-card info-blue">🌏 Karakteristik: Rata-rata suhu permukaan laut Indonesia cenderung hangat dan berada di atas 26°C disebabkan oleh letak astronomisnya di garis ekuator.</div>', unsafe_allow_html=True)