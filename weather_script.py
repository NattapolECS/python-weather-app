# ==============================================================================
# สคริปต์ดึงข้อมูลพยากรณ์อากาศจาก TMD API และบันทึกลง PostgreSQL อัตโนมัติ
#
# คุณสมบัติ:
# - ดึงข้อมูลรายชั่วโมงสำหรับทุกจังหวัดในประเทศไทย
# - ทำงานอัตโนมัติตามตารางเวลาที่กำหนด (schedule)
# - จัดการข้อมูลลับ (API Token, DB Password) อย่างปลอดภัยผ่านไฟล์ .env
# - ป้องกันข้อมูลซ้ำซ้อนในฐานข้อมูลด้วย UNIQUE constraint และ ON CONFLICT
# - มีระบบบันทึกการทำงาน (Logging) ที่เป็นมาตรฐาน บันทึกลงไฟล์และแสดงผล
# ==============================================================================

import logging
import os
from datetime import datetime

import psycopg2
import requests
from dotenv import load_dotenv
from psycopg2 import sql

# ---------- 1. SETUP LOGGING ----------
# ตั้งค่าระบบ Logging ให้บันทึกลงไฟล์และแสดงผลบน Console
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("weather_collector.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# ---------- 2. LOAD ENVIRONMENT VARIABLES ----------
# โหลดข้อมูลลับจากไฟล์ .env
load_dotenv()
logging.info("โหลดตัวแปรจากไฟล์ .env สำเร็จ")

# ---------- 3. CONFIGURATION ----------
#----------------- Local DB -----------------
# ตั้งค่าการเชื่อมต่อฐานข้อมูลและ API โดยอ่านค่าจาก Environment Variables
# DB_NAME = os.getenv("DB_NAME")
# DB_USER = os.getenv("DB_USER")
# DB_PASSWORD = os.getenv("DB_PASSWORD")
# DB_HOST = os.getenv("DB_HOST")
# DB_PORT = os.getenv("DB_PORT")
#----------------- Render DB -----------------
DB_NAME = os.getenv("RENDER_DB_NAME")
DB_USER = os.getenv("RENDER_DB_USER")
DB_PASSWORD = os.getenv("RENDER_DB_PASSWORD")
DB_HOST = os.getenv("RENDER_DB_HOST")
DB_PORT = os.getenv("RENDER_DB_PORT")
# ตั้งชื่อตารางที่ต้องการบันทึกข้อมูล
# หากต้องการใช้ตารางอื่น สามารถแก้ไขได้ที่นี่
TABLE_NAME = os.getenv("TABLE_NAME")
TMD_TOKEN = os.getenv("TMD_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

# ตรวจสอบว่าโหลด Token และ Password สำเร็จหรือไม่
if not DB_PASSWORD or not TMD_TOKEN:
    logging.critical(
        "❌ ไม่พบ DB_PASSWORD หรือ TMD_TOKEN ในไฟล์ .env! กรุณาตรวจสอบไฟล์ .env")
    exit()  # หยุดการทำงานหากไม่มีข้อมูลสำคัญ

# ---------- 4. STATIC DATA & API SETUP ----------
# ข้อมูลสำหรับแปลงรหัสสภาพอากาศและรายชื่อจังหวัด
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

# ตั้งค่าสำหรับเรียก API
API_URL = "https://data.tmd.go.th/nwpapi/v1/forecast/location/hourly/place"
API_HEADERS = {
    "accept": "application/json",
    "authorization": f"Bearer {TMD_TOKEN}"
}
API_PARAMS_TEMPLATE = {
    "fields": "tc,rh,cond"
}

# ---------- 5. DATABASE FUNCTIONS ----------
def check_and_create_database_if_needed():
    """ตรวจสอบและสร้างฐานข้อมูลหากยังไม่มี"""
    try:
        conn = psycopg2.connect(DATABASE_URL)  # เชื่อมต่อกับ PostgreSQL โดยใช้ URL ที่กำหนดใน .env
        conn.autocommit = True # เปิดโหมด autocommit เพื่อให้สามารถสร้างฐานข้อมูลได้
        cur = conn.cursor() # ใช้ cursor เพื่อรันคำสั่ง SQL
        cur.execute("SELECT 1 FROM pg_database WHERE datname=%s;", (DB_NAME,))  # ตรวจสอบว่ามีฐานข้อมูลนี้อยู่หรือไม่
        # หากไม่มีฐานข้อมูลนี้ จะคืนค่า None
        if not cur.fetchone(): 
            cur.execute(sql.SQL("CREATE DATABASE {}").format( 
                sql.Identifier(DB_NAME))) # สร้างฐานข้อมูลใหม่
            logging.info(f"✅ สร้างฐานข้อมูล {DB_NAME} แล้ว")
        else:
            logging.info(f"✅ พบฐานข้อมูล {DB_NAME} แล้ว")
        cur.close()
        conn.close()
    except psycopg2.Error as e:
        logging.critical(
            "❌ CRITICAL: ไม่สามารถเชื่อมต่อ PostgreSQL เพื่อตรวจสอบ/สร้าง DB ได้: %s", e)
        exit()


def check_and_create_table_if_needed():  #ตรวจสอบและสร้างตารางหากยังไม่มี พร้อม UNIQUE constraint
    """ตรวจสอบและสร้างตารางหากยังไม่มี พร้อม UNIQUE constraint"""
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD, host=DB_HOST, port=DB_PORT)
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
        conn.commit()  # บันทึกการเปลี่ยนแปลง
        logging.info(f"✅ ตาราง \"{TABLE_NAME}\" ถูกสร้างหรืออัปเดตแล้ว")
        cur.close()  
        conn.close()
        logging.info(f"✅ ตาราง \"{TABLE_NAME}\" พร้อมใช้งานแล้ว")
    except psycopg2.Error as e:
        logging.critical(
            "❌ CRITICAL: ไม่สามารถเชื่อมต่อ DB หรือสร้างตารางได้: %s", e)
        exit()

# ---------- 6. DATA COLLECTION FUNCTION ----------
def collect_weather_data():
    """กระบวนการหลักในการดึงข้อมูลจาก API, ประมวลผล, และบันทึกลงฐานข้อมูล"""
    logging.info("📥 เริ่มต้นกระบวนการดึงข้อมูล...")
    rows_to_insert = []

    for province in provinces:
        params = API_PARAMS_TEMPLATE.copy()  # คัดลอกพารามิเตอร์เริ่มต้นเพื่อไม่ให้แก้ไขต้นฉบับ
        params["province"] = province  # กำหนดชื่อจังหวัดในพารามิเตอร์
        try:
            response = requests.get(
                API_URL, headers=API_HEADERS, params=params, timeout=10)
            response.raise_for_status()  # ทำให้เกิด Error หาก HTTP status ไม่ใช่ 2xx

            data = response.json()
            forecasts = data["WeatherForecasts"][0]["forecasts"]  # ดึงข้อมูลพยากรณ์อากาศ
            location = data["WeatherForecasts"][0]["location"] # ดึงข้อมูลตำแหน่ง

            for item in forecasts:
                dt = datetime.fromisoformat(item["time"]) # แปลงเวลาเป็น datetime object
                cond_code = item["data"].get("cond") # ดึงรหัสสภาพอากาศ
                cond_desc = cond_dict.get(cond_code, "ไม่ทราบ") # แปลงรหัสเป็นคำอธิบาย
                rows_to_insert.append((
                    location.get("province"), dt.date(), dt.time(),
                    item["data"].get("tc"), item["data"].get("rh"), cond_desc 
                )) # เก็บข้อมูลในรูปแบบ tuple
        except requests.exceptions.RequestException as e:
            logging.warning(
                f"API Request Error @ {province}: %s. ข้ามไปจังหวัดถัดไป...", e)
        except (KeyError, IndexError, ValueError) as e:
            logging.warning(
                f"JSON Parsing Error @ {province}: %s. ข้ามไปจังหวัดถัดไป...", e)

        time.sleep(1.5)  # หน่วงเวลาเล็กน้อยเพื่อไม่ให้ API ทำงานหนักเกินไป

    if rows_to_insert:
        logging.info(f"กำลังจะบันทึกข้อมูล {len(rows_to_insert)} แถว...")
        try:
            conn = psycopg2.connect(
                dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD, host=DB_HOST, port=DB_PORT)
            cur = conn.cursor()
            insert_query = f"""
                INSERT INTO "{TABLE_NAME}" ("Province", "Date", "Time", "Temperature_c", "Humidity_percent", "Condition")
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT ("Province", "Date", "Time") DO NOTHING;
            """
            cur.executemany(insert_query, rows_to_insert) # ใช้ executemany เพื่อเพิ่มประสิทธิภาพในการบันทึกข้อมูล
            logging.info(f"บันทึกข้อมูล {len(rows_to_insert)} แถวลงฐานข้อมูล {TABLE_NAME} สำเร็จ")
            conn.commit()
            logging.info(
                f"✅ บันทึกข้อมูลสำเร็จ! (อาจมีบางส่วนถูกข้ามไปเพราะซ้ำซ้อน)")
            cur.close()
            conn.close()
        except psycopg2.Error as e:
            logging.error("❌ ERROR บันทึกข้อมูลลง DB: %s", e)
    else:
        logging.warning("⚠️ ไม่พบข้อมูลให้บันทึกหลังจากการดึงข้อมูลทั้งหมด")


# ---------- 7. MAIN EXECUTION BLOCK ----------
if __name__ == "__main__":
    logging.info("🚀 Starting weather data collection process via GitHub Actions...")
    # ตรวจสอบและเตรียมความพร้อมของฐานข้อมูลก่อนเริ่ม
    check_and_create_database_if_needed()
    check_and_create_table_if_needed()
    # เรียกใช้ฟังก์ชันเก็บข้อมูลโดยตรง
    collect_weather_data()
    logging.info("✅ Weather data collection process finished.")
