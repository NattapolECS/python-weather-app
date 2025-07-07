# ==============================================================================
# สคริปต์ดึงข้อมูลพยากรณ์อากาศจาก TMD API และบันทึกลง PostgreSQL
# ปรับปรุงสำหรับรันบน GitHub Actions
# ==============================================================================

import logging
import os
from datetime import datetime
import psycopg2
import requests
from dotenv import load_dotenv

# --- 1. SETUP LOGGING ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

# --- 2. LOAD ENVIRONMENT VARIABLES ---
# ใน GitHub Actions จะโหลดจาก Secrets ที่ตั้งค่าไว้
# ใน Local จะโหลดจากไฟล์ .env
load_dotenv()
logging.info("Attempting to load environment variables...")

# --- 3. CONFIGURATION ---
DATABASE_URL = os.getenv("DATABASE_URL")
TMD_TOKEN = os.getenv("TMD_TOKEN")
TABLE_NAME = os.getenv("TABLE_NAME", "Weather") # ใช้ค่า "Weather" เป็น default

# ตรวจสอบว่าโหลดตัวแปรที่จำเป็นสำเร็จหรือไม่
if not DATABASE_URL or not TMD_TOKEN:
    logging.critical("❌ CRITICAL: ไม่พบ DATABASE_URL หรือ TMD_TOKEN ใน Environment Variables!")
    exit(1) # หยุดการทำงานทันทีหากไม่มีข้อมูลสำคัญ
else:
    logging.info("✅ Environment variables loaded successfully.")


# --- 4. STATIC DATA & API SETUP ---
cond_dict = {
    1: "ท้องฟ้าแจ่มใส (Clear)", 2: "มีเมฆบางส่วน (Partly cloudy)", 3: "เมฆเป็นส่วนมาก (Cloudy)", 4: "มีเมฆมาก (Overcast)",
    5: "ฝนตกเล็กน้อย (Light rain)", 6: "ฝนปานกลาง (Moderate rain)", 7: "ฝนตกหนัก (Heavy rain)", 8: "ฝนฟ้าคะนอง (Thunderstorm)",
    9: "อากาศหนาวจัด (Very cold)", 10: "อากาศหนาว (Cold)", 11: "อากาศเย็น (Cool)", 12: "อากาศร้อนจัด (Very hot)"
}
provinces = [
    "กรุงเทพมหานคร", "กระบี่", "กาญจนบุรี", "กาฬสินธุ์", "กำแพงเพชร", "ขอนแก่น", "จันทบุรี", "ฉะเชิงเทรา", "ชลบุรี", "ชัยนาท",
    "ชัยภูมิ", "ชุมพร", "เชียงราย", "เชียงใหม่", "ตรัง", "ตราด", "ตาก", "นครนายก", "นครปฐม", "นครพนม", "นครราชสีมา",
    "นครศรีธรรมราช", "นครสวรรค์", "นนทบุรี", "นราธิวาส", "น่าน", "บึงกาฬ", "บุรีรัมย์", "ปทุมธานี", "ประจวบคีรีขันธ์",
    "ปราจีนบุรี", "ปัตตานี", "พระนครศรีอยุธยา", "พะเยา", "พังงา", "พัทลุง", "พิจิตร", "พิษณุโลก", "เพชรบุรี", "เพชรบูรณ์",
    "แพร่", "ภูเก็ต", "มหาสารคาม", "มุกดาหาร", "แม่ฮ่องสอน", "ยโสธร", "ยะลา", "ร้อยเอ็ด", "ระนอง", "ระยอง", "ราชบุรี",
    "ลพบุรี", "ลำปาง", "ลำพูน", "เลย", "ศรีสะเกษ", "สกลนคร", "สงขลา", "สตูล", "สมุทรปราการ", "สมุทรสงคราม", "สมุทรสาคร",
    "สระแก้ว", "สระบุรี", "สิงห์บุรี", "สุโขทัย", "สุพรรณบุรี", "สุราษฎร์ธานี", "สุรินทร์", "หนองคาย", "หนองบัวลำภู",
    "อ่างทอง", "อำนาจเจริญ", "อุดรธานี", "อุตรดิตถ์", "อุทัยธานี", "อุบลราชธานี"
]
API_URL = "https://data.tmd.go.th/nwpapi/v1/forecast/location/hourly/place"
API_HEADERS = {
    "accept": "application/json",
    "authorization": f"Bearer {TMD_TOKEN}"
}
API_PARAMS_TEMPLATE = { "fields": "tc,rh,cond" }

# --- 5. DATABASE FUNCTIONS ---
def check_and_create_table_if_needed():
    conn = None
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS "{TABLE_NAME}" (
                "id" SERIAL PRIMARY KEY,
                "Province" TEXT,
                "Date" DATE,
                "Time" TIME,
                "Temperature_c" REAL,
                "Humidity_percent" REAL,
                "Condition" TEXT,
                UNIQUE ("Province", "Date", "Time")
            );
        """)
        conn.commit()
        cur.close()
        logging.info(f"✅ Table \"{TABLE_NAME}\" is ready.")
    except psycopg2.Error as e:
        logging.critical(f"❌ CRITICAL: Could not create table: {e}")
        exit(1)
    finally:
        if conn:
            conn.close()

# --- 6. DATA COLLECTION FUNCTION ---
def collect_weather_data():
    logging.info("📥 Starting data collection process...")
    rows_to_insert = []
    for province in provinces:
        params = API_PARAMS_TEMPLATE.copy()
        params["province"] = province
        try:
            response = requests.get(API_URL, headers=API_HEADERS, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            forecasts = data["WeatherForecasts"][0]["forecasts"]
            location = data["WeatherForecasts"][0]["location"]
            for item in forecasts:
                dt = datetime.fromisoformat(item["time"])
                cond_code = item["data"].get("cond")
                cond_desc = cond_dict.get(cond_code, "ไม่ทราบ")
                rows_to_insert.append((
                    location.get("province"), dt.date(), dt.time(),
                    item["data"].get("tc"), item["data"].get("rh"), cond_desc
                ))
        except requests.exceptions.RequestException as e:
            logging.warning(f"API Request Error @ {province}: {e}. Skipping...")
        except (KeyError, IndexError, ValueError) as e:
            logging.warning(f"JSON Parsing Error @ {province}: {e}. Skipping...")

    if rows_to_insert:
        conn = None
        try:
            conn = psycopg2.connect(DATABASE_URL)
            cur = conn.cursor()
            insert_query = f"""
                INSERT INTO "{TABLE_NAME}" ("Province", "Date", "Time", "Temperature_c", "Humidity_percent", "Condition")
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT ("Province", "Date", "Time") DO NOTHING;
            """
            cur.executemany(insert_query, rows_to_insert)
            conn.commit()
            logging.info(f"✅ Successfully inserted/updated {cur.rowcount} rows.")
            cur.close()
        except psycopg2.Error as e:
            logging.error(f"❌ ERROR saving to DB: {e}")
        finally:
            if conn:
                conn.close()
    else:
        logging.warning("⚠️ No data to insert after collection.")

# --- 7. MAIN EXECUTION BLOCK ---
if __name__ == "__main__":
    logging.info("🚀 Starting weather data collection process via GitHub Actions...")
    check_and_create_table_if_needed()
    collect_weather_data()
    logging.info("✅ Weather data collection process finished.")