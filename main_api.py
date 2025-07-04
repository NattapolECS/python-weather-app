from fastapi import FastAPI, Query
from typing import Optional
import asyncpg
import os
from dotenv import load_dotenv
from datetime import date

load_dotenv()
app = FastAPI()

# ---------- ENV config ----------
DB_NAME = "Weather_data"
DB_USER = "postgres"
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = "localhost"
DB_PORT = "5432"
TABLE_NAME = "Weather"

# ---------- DB Pool Setup ----------
@app.on_event("startup")
async def startup():
    app.state.db_pool = await asyncpg.create_pool(
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        host=DB_HOST,
        port=DB_PORT
    )

@app.on_event("shutdown")
async def shutdown():
    await app.state.db_pool.close()

# ---------- Root ----------
@app.get("/")
async def read_root():
    return {"message": "✅ ระบบ API พยากรณ์อากาศพร้อมใช้งาน!"}

# ---------- Weather API ----------
@app.get("/weather")
async def get_weather(
    province: Optional[str] = Query(default="กรุงเทพมหานคร", description="ชื่อจังหวัด"),
    date_exact: Optional[date] = Query(default=None, description="ดึงเฉพาะวันเดียว(YYYY-MM-DD)"),
    date_from: Optional[date] = Query(default=None, description="ดึงข้อมูลตั้งแต่วัน"),
    date_to: Optional[date] = Query(default=None, description="ถึงวัน"),
    include_temp: Optional[bool] = Query(default=True, description="แสดงอุณหภูมิ"),
    include_humidity: Optional[bool] = Query(default=True, description="แสดงความชื้น"),
    include_condition: Optional[bool] = Query(default=True, description="แสดงสภาพอากาศ"),
    limit: int = Query(default=100, description="จำนวนสูงสุดที่แสดง")
):
    query = 'SELECT "Province", "Date", "Time"'
    if include_temp:
        query += ', "Temperature_c"'
    if include_humidity:
        query += ', "Humidity_percent"'
    if include_condition:
        query += ', "Condition"'
    query += f' FROM "{TABLE_NAME}" WHERE TRUE'

    params = []

    if province:
        query += ' AND "Province" = $' + str(len(params)+1)
        params.append(province)
    if date_exact:
        query += ' AND "Date" = $' + str(len(params)+1)
        params.append(date_exact)
    if date_from:
        query += ' AND "Date" >= $' + str(len(params)+1)
        params.append(date_from)
    if date_to:
        query += ' AND "Date" <= $' + str(len(params)+1)
        params.append(date_to)

    query += ' ORDER BY "Date" DESC, "Time" DESC LIMIT $' + str(len(params)+1)
    params.append(limit)

    async with app.state.db_pool.acquire() as conn:
        rows = await conn.fetch(query, *params)

    result = []
    for r in rows:
        data = {
            "province": r["Province"],
            "date": r["Date"].isoformat(),
            "time": r["Time"].isoformat()
        }
        if include_temp:
            data["temperature_c"] = r["Temperature_c"]
        if include_humidity:
            data["humidity_percent"] = r["Humidity_percent"]
        if include_condition:
            data["condition"] = r["Condition"]
        result.append(data)

    return result
