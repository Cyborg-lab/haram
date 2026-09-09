"""MongoDB bilan telefon e'lonlari uchun Telegram bot."""
import asyncio
import logging
import os
from datetime import datetime, timezone

from aiogram import Bot, Dispatcher, F, Router
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.types import CallbackQuery, KeyboardButton, Message, ReplyKeyboardMarkup, ReplyKeyboardRemove, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
DATABASE = os.getenv("MONGODB_DATABASE", "phone_ads_bot")
WEBAPP_URL = os.getenv("WEBAPP_URL", "").rstrip("/")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN .env faylida berilmagan")

client = AsyncIOMotorClient(MONGODB_URI)
db = client[DATABASE]
users = db.users
ads = db.ads
router = Router()


class Registration(StatesGroup):
    name = State()
    phone = State()


class AddAd(StatesGroup):
    brand = State()
    model = State()
    storage = State()
    ram = State()
    camera = State()
    screen = State()
    battery = State()
    condition = State()
    price = State()
    description = State()
    photo = State()


class Search(StatesGroup):
    text = State()


def menu_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(text="➕ E'lon qo'shish"), KeyboardButton(text="📋 E'lonlarim")],
        [KeyboardButton(text="🔎 Qidirish")],
    ]
    if WEBAPP_URL:
        keyboard.append([KeyboardButton(text="🌐 Mini App", web_app=WebAppInfo(url=WEBAPP_URL))])
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

BRANDS = ["🍎 Apple", "📱 Samsung", "🔵 Xiaomi", "🟣 Redmi", "✍️ Boshqa brend"]
MODELS = {
    "Apple": ["iPhone 11", "iPhone 12", "iPhone 13", "iPhone 14", "iPhone 15"],
    "Samsung": ["Galaxy A14", "Galaxy A24", "Galaxy A34", "Galaxy S21", "Galaxy S23"],
    "Xiaomi": ["Xiaomi 12", "Xiaomi 13", "Xiaomi 14", "Poco X5", "Poco X6"],
    "Redmi": ["Redmi Note 11", "Redmi Note 12", "Redmi Note 13", "Redmi 12", "Redmi 13"],
}


def choices_keyboard(items: list[str], rows: int = 2) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=item) for item in items[i:i + rows]] for i in range(0, len(items), rows)],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


SPEC_OPTIONS = {
    "storage": ["64 GB", "128 GB", "256 GB", "512 GB"],
    "ram": ["4 GB RAM", "6 GB RAM", "8 GB RAM", "12 GB RAM"],
    "camera": ["12 MP", "48 MP", "50 MP", "108 MP"],
    "screen": ["60 Hz", "90 Hz", "120 Hz", "144 Hz"],
    "battery": ["4000 mAh", "4500 mAh", "5000 mAh", "6000 mAh"],
}


def phone_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Telefon raqamni yuborish", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def ad_keyboard(ad_id: str, active: bool):
    builder = InlineKeyboardBuilder()
    action = "noaktiv" if active else "aktiv"
    # Telegram Bot API tugma fon rangini boshqarishga ruxsat bermaydi.
    # Shu sababli holat yashil/qizil indikator bilan beriladi.
    label = "🔴 NOAKTIV QILISH" if active else "🟢 AKTIV QILISH"
    builder.button(text=label, callback_data=f"status:{ad_id}:{action}")
    return builder.as_markup()


def clean(value: str) -> str:
    return value.strip()


def ad_text(ad: dict) -> str:
    status = "🟢 Aktiv" if ad["is_active"] else "🔴 Noaktiv"
    return (
        f"<b>{ad['brand']} {ad['model']}</b>\n"
        f"📱 Xarakteristika: {ad['specs']}\n"
        f"✨ Holati: {ad['condition']}\n"
        f"💰 Narxi: {ad['price']}\n"
        f"📝 Qo'shimcha: {ad['description']}\n"
        f"📞 Aloqa: {ad['seller_phone']}\n"
        f"{status}"
    )


async def send_ad(message: Message, ad: dict, controls: bool = False):
    markup = ad_keyboard(str(ad["_id"]), ad["is_active"]) if controls else None
    if ad.get("photo_file_id"):
        await message.answer_photo(ad["photo_file_id"], caption=ad_text(ad), reply_markup=markup)
    else:
        await message.answer(ad_text(ad), reply_markup=markup)


async def require_registered(message: Message, state: FSMContext) -> bool:
    user = await users.find_one({"telegram_id": message.from_user.id})
    if user:
        return True
    await state.clear()
    await state.set_state(Registration.name)
    await message.answer("Avval ro'yxatdan o'ting. Ism-familiyangizni yuboring:")
    return False


@router.message(CommandStart())
async def start(message: Message, state: FSMContext):
    if await users.find_one({"telegram_id": message.from_user.id}):
        await state.clear()
        await message.answer("Xush kelibsiz! Kerakli bo'limni tanlang.", reply_markup=menu_keyboard())
        return
    await state.set_state(Registration.name)
    await message.answer("Assalomu alaykum! Avval ro'yxatdan o'tamiz. Ism-familiyangizni yuboring:")


@router.message(Registration.name, F.text)
async def registration_name(message: Message, state: FSMContext):
    if len(clean(message.text)) < 2:
        await message.answer("Ism kamida 2 ta belgidan iborat bo'lsin.")
        return
    await state.update_data(name=clean(message.text))
    await state.set_state(Registration.phone)
    await message.answer("Telefon raqamingizni yuboring:", reply_markup=phone_keyboard())


@router.message(Registration.phone, F.contact)
async def registration_contact(message: Message, state: FSMContext):
    data = await state.get_data()
    await users.update_one(
        {"telegram_id": message.from_user.id},
        {"$set": {"telegram_id": message.from_user.id, "name": data["name"], "phone": message.contact.phone_number,
                  "username": message.from_user.username, "created_at": datetime.now(timezone.utc)}},
        upsert=True,
    )
    await state.clear()
    await message.answer("Ro'yxatdan o'tish tugadi.", reply_markup=menu_keyboard())


@router.message(Registration.phone, F.text)
async def registration_phone_text(message: Message, state: FSMContext):
    phone = clean(message.text)
    if len(phone) < 7:
        await message.answer("To'g'ri telefon raqamini yuboring yoki tugmani bosing.")
        return
    data = await state.get_data()
    await users.update_one(
        {"telegram_id": message.from_user.id},
        {"$set": {"telegram_id": message.from_user.id, "name": data["name"], "phone": phone,
                  "username": message.from_user.username, "created_at": datetime.now(timezone.utc)}}, upsert=True)
    await state.clear()
    await message.answer("Ro'yxatdan o'tish tugadi.", reply_markup=menu_keyboard())


@router.message(F.text == "➕ E'lon qo'shish")
async def add_ad_start(message: Message, state: FSMContext):
    if not await require_registered(message, state): return
    await state.set_state(AddAd.brand)
    await message.answer("Telefon brendini tanlang:", reply_markup=choices_keyboard(BRANDS))


@router.message(AddAd.brand, F.text)
async def add_brand(message: Message, state: FSMContext):
    brand = clean(message.text).replace("🍎 ", "").replace("📱 ", "").replace("🔵 ", "").replace("🟣 ", "")
    if brand == "✍️ Boshqa brend":
        await state.update_data(brand=None)
        await message.answer("Brend nomini yozing:", reply_markup=ReplyKeyboardRemove())
        return
    await show_models(message, state, brand)


async def show_models(message: Message, state: FSMContext, brand: str):
    await state.update_data(brand=brand)
    await state.set_state(AddAd.model)
    choices = MODELS.get(brand, []) + ["✍️ Boshqa model"]
    await message.answer("Telefon modelini tanlang:", reply_markup=choices_keyboard(choices))


@router.message(AddAd.model, F.text)
async def add_model(message: Message, state: FSMContext):
    data = await state.get_data()
    value = clean(message.text)
    if not data.get("brand"):
        await show_models(message, state, value)
        return
    if value == "✍️ Boshqa model":
        await message.answer("Model nomini yozing:", reply_markup=ReplyKeyboardRemove())
        return
    await state.update_data(model=value); await state.set_state(AddAd.storage)
    await message.answer("Xotirasini tanlang:", reply_markup=choices_keyboard(SPEC_OPTIONS["storage"]))


@router.message(AddAd.storage, F.text)
async def add_storage(message: Message, state: FSMContext):
    await state.update_data(storage=clean(message.text)); await state.set_state(AddAd.ram)
    await message.answer("RAM miqdorini tanlang:", reply_markup=choices_keyboard(SPEC_OPTIONS["ram"]))


@router.message(AddAd.ram, F.text)
async def add_ram(message: Message, state: FSMContext):
    await state.update_data(ram=clean(message.text)); await state.set_state(AddAd.camera)
    await message.answer("Asosiy kamera sifatini tanlang:", reply_markup=choices_keyboard(SPEC_OPTIONS["camera"]))


@router.message(AddAd.camera, F.text)
async def add_camera(message: Message, state: FSMContext):
    await state.update_data(camera=clean(message.text)); await state.set_state(AddAd.screen)
    await message.answer("Ekran yangilanish tezligini tanlang:", reply_markup=choices_keyboard(SPEC_OPTIONS["screen"]))


@router.message(AddAd.screen, F.text)
async def add_screen(message: Message, state: FSMContext):
    await state.update_data(screen=clean(message.text)); await state.set_state(AddAd.battery)
    await message.answer("Batareya sig'imini tanlang:", reply_markup=choices_keyboard(SPEC_OPTIONS["battery"]))


@router.message(AddAd.battery, F.text)
async def add_battery(message: Message, state: FSMContext):
    await state.update_data(battery=clean(message.text)); await state.set_state(AddAd.condition)
    await message.answer("Telefon holatini tanlang:", reply_markup=choices_keyboard(["✨ Yangi", "✅ Ideal", "♻️ Ishlatilgan"]))


@router.message(AddAd.condition, F.text)
async def add_condition(message: Message, state: FSMContext):
    condition = clean(message.text).replace("✨ ", "").replace("✅ ", "").replace("♻️ ", "")
    await state.update_data(condition=condition); await state.set_state(AddAd.price)
    await message.answer("Narxini yozing. Masalan: 3 500 000 so'm", reply_markup=ReplyKeyboardRemove())


@router.message(AddAd.price, F.text)
async def add_price(message: Message, state: FSMContext):
    await state.update_data(price=clean(message.text)); await state.set_state(AddAd.description)
    await message.answer("Qo'shimcha ma'lumot yozing yoki o'tkazib yuboring:", reply_markup=choices_keyboard(["⏭ O'tkazib yuborish"], 1))


@router.message(AddAd.description, F.text)
async def add_description(message: Message, state: FSMContext):
    description = "-" if message.text == "⏭ O'tkazib yuborish" else clean(message.text)
    await state.update_data(description=description); await state.set_state(AddAd.photo)
    await message.answer("Telefon rasmini yuboring yoki o'tkazib yuboring:", reply_markup=choices_keyboard(["⏭ Rasmni o'tkazib yuborish"], 1))


async def save_ad(message: Message, state: FSMContext, photo_file_id: str | None):
    data = await state.get_data()
    seller = await users.find_one({"telegram_id": message.from_user.id})
    specs = f"{data['storage']} · {data['ram']} · {data['camera']} kamera · {data['screen']} ekran · {data['battery']}"
    ad = {**data, "specs": specs, "photo_file_id": photo_file_id, "seller_id": message.from_user.id,
          "seller_phone": seller["phone"], "is_active": True, "created_at": datetime.now(timezone.utc),
          "updated_at": datetime.now(timezone.utc)}
    result = await ads.insert_one(ad)
    ad["_id"] = result.inserted_id
    await state.clear()
    await message.answer("✅ E'lon saqlandi va aktiv holatda e'lon qilindi.", reply_markup=menu_keyboard())
    await send_ad(message, ad, controls=True)


@router.message(AddAd.photo, F.photo)
async def add_photo(message: Message, state: FSMContext):
    await save_ad(message, state, message.photo[-1].file_id)


@router.message(AddAd.photo, F.text.in_({"/skip", "⏭ Rasmni o'tkazib yuborish"}))
async def skip_photo(message: Message, state: FSMContext):
    await save_ad(message, state, None)


@router.message(AddAd.photo)
async def invalid_photo(message: Message):
    await message.answer("Rasm yuboring yoki «Rasmni o'tkazib yuborish» tugmasini bosing.")


@router.message(F.text == "📋 E'lonlarim")
async def my_ads(message: Message, state: FSMContext):
    if not await require_registered(message, state): return
    found = [ad async for ad in ads.find({"seller_id": message.from_user.id}).sort("created_at", -1)]
    if not found:
        await message.answer("Sizda hali e'lon yo'q.")
        return
    await message.answer(f"Sizning e'lonlaringiz: {len(found)} ta")
    for ad in found: await send_ad(message, ad, controls=True)


@router.callback_query(F.data.startswith("status:"))
async def change_status(callback: CallbackQuery):
    _, ad_id, action = callback.data.split(":")
    from bson import ObjectId
    ad = await ads.find_one({"_id": ObjectId(ad_id), "seller_id": callback.from_user.id})
    if not ad:
        await callback.answer("Bu e'lon sizga tegishli emas.", show_alert=True); return
    active = action == "aktiv"
    await ads.update_one({"_id": ad["_id"]}, {"$set": {"is_active": active, "updated_at": datetime.now(timezone.utc)}})
    await callback.answer("E'lon holati o'zgartirildi.")
    if callback.message.photo:
        await callback.message.edit_caption(caption=ad_text({**ad, "is_active": active}), reply_markup=ad_keyboard(ad_id, active))
    else:
        await callback.message.edit_text(ad_text({**ad, "is_active": active}), reply_markup=ad_keyboard(ad_id, active))


@router.message(F.text == "🔎 Qidirish")
async def search_start(message: Message, state: FSMContext):
    if not await require_registered(message, state): return
    await state.set_state(Search.text)
    await message.answer("Brend, model yoki xarakteristika bo'yicha qidiring:")


@router.message(Search.text, F.text)
async def search_ads(message: Message, state: FSMContext):
    query = clean(message.text)
    await state.clear()
    # Qidiruv faqat is_active=True bo'lgan e'lonlar bilan cheklanadi.
    filter_ = {"is_active": True, "$or": [
        {"brand": {"$regex": query, "$options": "i"}}, {"model": {"$regex": query, "$options": "i"}},
        {"specs": {"$regex": query, "$options": "i"}}, {"description": {"$regex": query, "$options": "i"}},
    ]}
    found = [ad async for ad in ads.find(filter_).sort("created_at", -1).limit(20)]
    if not found:
        await message.answer("Aktiv e'lon topilmadi.", reply_markup=menu_keyboard()); return
    await message.answer(f"{len(found)} ta aktiv e'lon topildi:", reply_markup=menu_keyboard())
    for ad in found: await send_ad(message, ad)


async def main():
    await users.create_index("telegram_id", unique=True)
    await ads.create_index([("seller_id", 1), ("created_at", -1)])
    await ads.create_index([("is_active", 1), ("created_at", -1)])
    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    logging.info("Bot ishga tushdi")
    try:
        await dp.start_polling(bot)
    finally:
        client.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # Ctrl+C bosilganda Python traceback chiqarmaydi.
        print("\nBot to'xtatildi.")
