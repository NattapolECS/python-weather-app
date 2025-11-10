# main_dashboard.py
# วิธีรัน:
# 1. ติดตั้งไลบรารีที่จำเป็น: pip install streamlit requests pandas
# 2. รันคำสั่งนี้ใน Terminal: streamlit run main_dashboard.py

import streamlit as st
import requests
import pandas as pd
import time

# --- CONFIGURATION ---
# URL ของ API ที่คุณสร้างและรันไว้บน Render
API_BASE_URL = 'https://weather-api-wj3x.onrender.com'

# รายชื่อจังหวัด (ควรจะตรงกับใน API ของคุณ)
PROVINCES = [
    "กรุงเทพมหานคร", "กระบี่", "กาญจนบุรี", "กาฬสินธุ์", "กำแพงเพชร", "ขอนแก่น", "จันทบุรี", "ฉะเชิงเทรา", "ชลบุรี", "ชัยนาท",
    "ชัยภูมิ", "ชุมพร", "เชียงราย", "เชียงใหม่", "ตรัง", "ตราด", "ตาก", "นครนายก", "นครปฐม", "นครพนม", "นครราชสีมา",
    "นครศรีธรรมราช", "นครสวรรค์", "นนทบุรี", "นราธิวาส", "น่าน", "บึงกาฬ", "บุรีรัมย์", "ปทุมธานี", "ประจวบคีรีขันธ์",
    "ปราจีนบุรี", "ปัตตานี", "พระนครศรีอยุธยา", "พะเยา", "พังงา", "พัทลุง", "พิจิตร", "พิษณุโลก", "เพชรบุรี", "เพชรบูรณ์",
    "แพร่", "ภูเก็ต", "มหาสารคาม", "มุกดาหาร", "แม่ฮ่องสอน", "ยโสธร", "ยะลา", "ร้อยเอ็ด", "ระนอง", "ระยอง", "ราชบุรี",
    "ลพบุรี", "ลำปาง", "ลำพูน", "เลย", "ศรีสะเกษ", "สกลนคร", "สงขลา", "สตูล", "สมุทรปราการ", "สมุทรสงคราม", "สมุทรสาคร",
    "สระแก้ว", "สระบุรี", "สิงห์บุรี", "สุโขทัย", "สุพรรณบุรี", "สุราษฎร์ธานี", "สุรินทร์", "หนองคาย", "หนองบัวลำภู",
    "อ่างทอง", "อำนาจเจริญ", "อุดรธานี", "อุตรดิตถ์", "อุทัยธานี", "อุบลราชธานี"
]

# --- FUNCTIONS ---

# ใช้ @st.cache_data เพื่อให้ Streamlit เก็บผลลัพธ์ไว้ ไม่ต้องดึงข้อมูลใหม่ทุกครั้งที่ผู้ใช้ทำอะไรเล็กๆ น้อยๆ
@st.cache_data(ttl=300) # เก็บ cache ไว้ 5 นาที (300 วินาที)
def fetch_weather_data(province, limit=24):
    """
    ดึงข้อมูลสภาพอากาศจาก API ของเรา
    """
    try:
        url = f"{API_BASE_URL}/weather?province={province}&limit={limit}"
        response = requests.get(url, timeout=60)
        response.raise_for_status() # ทำให้เกิด Error ถ้า HTTP status ไม่ใช่ 2xx
        data = response.json()
        
        # แปลงข้อมูล JSON เป็น Pandas DataFrame เพื่อให้ง่ายต่อการใช้งาน
        df = pd.DataFrame(data)
        # แปลงคอลัมน์ date และ time ให้เป็น datetime object
        df['datetime'] = pd.to_datetime(df['date'].str.split('T').str[0] + ' ' + df['time'])
        return df
    except requests.exceptions.RequestException as e:
        st.error(f"เกิดข้อผิดพลาดในการเชื่อมต่อ API: {e}")
        return pd.DataFrame() # คืนค่า DataFrame ว่างเปล่าถ้าเกิดข้อผิดพลาด

# --- STREAMLIT APP LAYOUT ---

# ตั้งค่าหน้าเว็บ
st.set_page_config(
    page_title="แดชบอร์ดสภาพอากาศ",
    page_icon="🌦️",
    layout="wide"
)

# --- การปรับปรุง: เพิ่ม CSS เพื่อเปลี่ยนฟอนต์ ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Sarabun:wght@400;700&display=swap');
    html, body, [class*="css"]  {
       font-family: 'Sarabun', sans-serif;
    }
    </style>
    """, unsafe_allow_html=True)


# ส่วนหัวของ Dashboard
st.title("🌦️ แดชบอร์ดข้อมูลสภาพอากาศประเทศไทย")
st.markdown("แสดงข้อมูลล่าสุดที่ดึงมาจาก API ของคุณ")

# ส่วนควบคุม (Control Panel)
st.sidebar.header("แผงควบคุม")
selected_province = st.sidebar.selectbox(
    "เลือกจังหวัด:",
    PROVINCES,
    index=PROVINCES.index("กรุงเทพมหานคร") # ตั้งค่าเริ่มต้นเป็นกรุงเทพฯ
)

# ดึงข้อมูลตามจังหวัดที่เลือก
data_df = fetch_weather_data(selected_province, limit=24)

if not data_df.empty:
    # ดึงข้อมูลแถวล่าสุด (ข้อมูลปัจจุบัน)
    latest_data = data_df.iloc[0]

    # แสดงเวลาที่อัปเดตล่าสุด
    st.sidebar.info(f"ข้อมูลล่าสุดของ {selected_province}")
    st.sidebar.write(f"ณ วันที่: {latest_data['datetime'].strftime('%d/%m/%Y')}")
    st.sidebar.write(f"เวลา: {latest_data['datetime'].strftime('%H:%M:%S')}")

    # แสดงข้อมูลหลัก (Key Metrics)
    col1, col2, col3 = st.columns(3)
    
    # --- การปรับปรุง: จัดรูปแบบตัวเลขให้มีทศนิยม 2 ตำแหน่ง ---
    temp_formatted = f"{latest_data['temperature_c']:.2f} °C"
    humidity_formatted = f"{latest_data['humidity_percent']:.2f} %"
    
    col1.metric("อุณหภูมิล่าสุด", temp_formatted)
    col2.metric("ความชื้นล่าสุด", humidity_formatted)
    
    # --- การปรับปรุง: ใช้ st.markdown แทน st.metric เพื่อให้ข้อความขึ้นบรรทัดใหม่ได้ ---
    with col3:
        st.write("สภาพอากาศล่าสุด")
        # ใช้ markdown เพื่อปรับขนาดและสไตล์ให้คล้ายกับ metric
        st.markdown(f"<p style='font-size: 1.875rem; font-weight: bold; line-height: 1.2;'>{latest_data['condition']}</p>", unsafe_allow_html=True)


    # เตรียมข้อมูลสำหรับกราฟ (เรียงจากเก่าไปใหม่)
    chart_df = data_df.sort_values(by='datetime').set_index('datetime')

    # แสดงกราฟ
    st.subheader(f"แนวโน้มสภาพอากาศย้อนหลัง (จังหวัด{selected_province})")
    
    # --- การปรับปรุง: เพิ่มชื่อให้กับกราฟ ---
    st.write("แนวโน้มอุณหภูมิ (°C)")
    st.line_chart(chart_df['temperature_c'])
    
    st.write("แนวโน้มความชื้น (%)")
    st.bar_chart(chart_df['humidity_percent'])

else:
    st.warning("ไม่สามารถโหลดข้อมูลได้ กรุณาลองใหม่อีกครั้ง")

