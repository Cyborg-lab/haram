"""Telegram Mini App va bot uchun umumiy MongoDB API."""
import hashlib
import hmac
import json
import os
from datetime import datetime, timezone
from urllib.parse import parse_qsl

from bson import ObjectId
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
DATABASE = os.getenv("MONGODB_DATABASE", "phone_ads_bot")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN .env faylida berilmagan")

client = AsyncIOMotorClient(MONGODB_URI)
db = client[DATABASE]
users, ads = db.users, db.ads
app = FastAPI(title="Telefonlar Mini App API")
app.mount("/static", StaticFiles(directory="static"), name="static")


class Profile(BaseModel):
    phone: str = Field(min_length=7, max_length=30)


class AdInput(BaseModel):
    brand: str = Field(min_length=1, max_length=60)
    model: str = Field(min_length=1, max_length=80)
    storage: str
    ram: str
    camera: str
    screen: str
    battery: str
    condition: str
    price: str = Field(min_length=1, max_length=60)
    description: str = "-"
    image_data: str | None = None


def verify_init_data(init_data: str) -> dict:
    """Telegram yuborgan initData imzosini tekshiradi; soxta login o'tmaydi."""
    values = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = values.pop("hash", "")
    data_check = "\n".join(f"{key}={value}" for key, value in sorted(values.items()))
    secret = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
    if not received_hash or not hmac.compare_digest(expected, received_hash):
        raise HTTPException(401, "Telegram login ma'lumoti noto'g'ri")
    try:
        return json.loads(values["user"])
    except (KeyError, json.JSONDecodeError) as error:
        raise HTTPException(401, "Telegram foydalanuvchisi topilmadi") from error


async def current_user(x_telegram_init_data: str = Header(default="")) -> dict:
    telegram = verify_init_data(x_telegram_init_data)
    now = datetime.now(timezone.utc)
    await users.update_one(
        {"telegram_id": telegram["id"]},
        {"$setOnInsert": {"telegram_id": telegram["id"], "created_at": now},
         "$set": {"username": telegram.get("username"), "telegram_name": f"{telegram.get('first_name', '')} {telegram.get('last_name', '')}".strip(), "last_login_at": now}},
        upsert=True,
    )
    return await users.find_one({"telegram_id": telegram["id"]})


def serialize_ad(ad: dict) -> dict:
    return {"id": str(ad["_id"]), "brand": ad["brand"], "model": ad["model"], "storage": ad.get("storage", ""),
            "ram": ad.get("ram", ""), "camera": ad.get("camera", ""), "screen": ad.get("screen", ""),
            "battery": ad.get("battery", ""), "condition": ad["condition"], "price": ad["price"],
            "description": ad.get("description", "-"), "phone": ad.get("seller_phone", ""),
            "image_data": ad.get("image_data"), "is_active": ad["is_active"]}


@app.get("/")
async def index():
    return FileResponse("static/index.html")


@app.get("/api/me")
async def me(user: dict = Depends(current_user)):
    return {"id": user["telegram_id"], "name": user.get("name") or user.get("telegram_name", "Foydalanuvchi"), "phone": user.get("phone", "")}


@app.put("/api/me")
async def update_profile(profile: Profile, user: dict = Depends(current_user)):
    await users.update_one({"_id": user["_id"]}, {"$set": {"phone": profile.phone.strip(), "updated_at": datetime.now(timezone.utc)}})
    return {"ok": True}


@app.get("/api/ads")
async def list_active_ads(q: str = ""):
    query: dict = {"is_active": True}
    if q.strip():
        query["$or"] = [{field: {"$regex": q.strip(), "$options": "i"}} for field in ("brand", "model", "specs", "price")]
    return [serialize_ad(ad) async for ad in ads.find(query).sort("created_at", -1).limit(50)]


@app.get("/api/my-ads")
async def list_my_ads(user: dict = Depends(current_user)):
    return [serialize_ad(ad) async for ad in ads.find({"seller_id": user["telegram_id"]}).sort("created_at", -1)]


@app.post("/api/ads")
async def create_ad(payload: AdInput, user: dict = Depends(current_user)):
    if not user.get("phone"):
        raise HTTPException(400, "Avval telefon raqamingizni saqlang")
    if payload.image_data and (not payload.image_data.startswith("data:image/") or len(payload.image_data) > 4_000_000):
        raise HTTPException(400, "Rasm formati yoki hajmi noto'g'ri")
    data = payload.model_dump()
    data["specs"] = f"{data['storage']} · {data['ram']} · {data['camera']} kamera · {data['screen']} ekran · {data['battery']}"
    data.update({"seller_id": user["telegram_id"], "seller_phone": user["phone"], "is_active": True,
                 "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc)})
    result = await ads.insert_one(data)
    return {"ok": True, "id": str(result.inserted_id)}


@app.patch("/api/my-ads/{ad_id}/status")
async def toggle_ad(ad_id: str, user: dict = Depends(current_user)):
    try:
        object_id = ObjectId(ad_id)
    except Exception as error:
        raise HTTPException(400, "E'lon ID noto'g'ri") from error
    ad = await ads.find_one({"_id": object_id, "seller_id": user["telegram_id"]})
    if not ad:
        raise HTTPException(404, "E'lon topilmadi")
    active = not ad["is_active"]
    await ads.update_one({"_id": object_id}, {"$set": {"is_active": active, "updated_at": datetime.now(timezone.utc)}})
    return {"ok": True, "is_active": active}


@app.on_event("startup")
async def create_indexes():
    await users.create_index("telegram_id", unique=True)
    await ads.create_index([("is_active", 1), ("created_at", -1)])
    await ads.create_index([("seller_id", 1), ("created_at", -1)])
