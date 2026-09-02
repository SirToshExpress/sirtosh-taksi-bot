import logging
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

# 1. Log yuritish va O'zgaruvchilar
logging.basicConfig(level=logging.INFO)
# SIZNING TAXSI BOT TOKENINGIZ:
BOT_TOKEN = "8858307934:AAHlQjO0CMg9q1bTlm1SUKS8vC2GVQ__Nzc" 
# SIZNING REAL TELEGRAM ID RAQAMINGIZ JOYLASHTIRILDI:
ADMIN_ID = 8316399371  

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Vaqtincha ma'lumotlar bazasi
DRIVERS = {} 
BALANCES = {} # Haydovchilar balansi
ORDERS = {}
order_counter = 1

# 2. Narxlar va Komissiya Matritsasi
PRICE_MATRIX = {
    "Toshkent yo'nalishi": {
        "1-Zona (Guliston, Sirdaryo sh, Baxt)": {"Eko": 35000, "Standart": 55000, "Komfort": 75000, "komissiya": 5000},
        "2-Zona (Sayxunobod, Mirzaobod, Oqoltin)": {"Eko": 45000, "Standart": 65000, "Komfort": 85000, "komissiya": 5000},
        "3-Zona (Sardoba, Xovos, Shirin)": {"Eko": 55000, "Standart": 75000, "Komfort": 95000, "komissiya": 5000}
    },
    "Sirdaryo ichida": {
        "1-Zona (Yaqin masofalar)": {"Eko": 9000, "Standart": 18000, "komissiya": 1500},
        "2-Zona (O'rtacha masofalar)": {"Eko": 13000, "Standart": 23000, "komissiya": 2000},
        "3-Zona (Uzoq masofalar)": {"Eko": 16000, "Standart": 28000, "komissiya": 2500}
    }
}

# 3. FSM (Ssenariylar holati)
class DriverReg(StatesGroup):
    name = State()
    phone = State()
    car_model = State()
    car_number = State()
    passport_photo = State()

class ClientOrder(StatesGroup):
    direction = State()
    zone = State()
    tariff = State()
    phone = State()
    location_details = State()

# --- START BUYRUQI ---
@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    builder = ReplyKeyboardBuilder()
    builder.button(text="🚹 Men Yo'lovchiman")
    builder.button(text="🚘 Men Haydovchiman")
    builder.button(text="📜 Ommaviy Oferta")
    builder.adjust(2)
    
    await message.answer(
        "👋 **SirTosh Express** Sirdaryo taksi tizimiga xush kelibsiz!\n"
        "Tizim ichkarida murakkab, tashqarida esa juda oddiy ishlaydi.\n"
        "Iltimos, o'z rolingizni tanlang:",
        reply_markup=builder.as_markup(resize_keyboard=True)
    )

# --- OMMAVIY OFERTA ---
@dp.message(F.text == "📜 Ommaviy Oferta")
async def show_oferta(message: types.Message):
    await message.answer(
        "⚖️ **Ommaviy Oferta Shartnomasi (Qisqacha):**\n\n"
        "1. Tizim faqat vositachi (agregator) hisoblanadi.\n"
        "2. Haydovchi zakazni olgach, mijozni tashlab ketishi taqiqlanadi.\n"
        "3. Kelisha olinmagan taqdirda, komissiya haydovchiga 1 daqiqada qaytariladi.\n"
        "4. Yo'ldagi har qanday holatga haydovchi javobgardir."
    )

# --- HAYDOVCHI RO'YXATDAN O'TISHI (TEXPASPORT FILTRI) ---
@dp.message(F.text == "🚘 Men Haydovchiman")
async def driver_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id in DRIVERS:
        if DRIVERS[user_id]['status'] == 'pending':
            await message.answer("⏳ Arizangiz admin tomonidan tekshirilmoqda. Iltimos, kuting.")
        else:
            bal = BALANCES.get(user_id, 0)
            await message.answer(f"🚀 Xush kelibsiz, {DRIVERS[user_id]['name']}!\n💰 Balansingiz: {bal} so'm.\nHolatingiz: FAOL.")
        return

    await message.answer("📝 Ro'yxatdan o'tishni boshlaymiz. Ism va familiyangizni kiriting:")
    await state.set_state(DriverReg.name)

@dp.message(DriverReg.name)
async def dr_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("📞 Telefon raqamingizni kiriting:")
    await state.set_state(DriverReg.phone)

@dp.message(DriverReg.phone)
async def dr_phone(message: types.Message, state: FSMContext):
    await state.update_data(phone=message.text)
    await message.answer("🚗 Mashinangiz rusumi nima? (Cobalt, Gentra, Nexia-3, Damas):")
    await state.set_state(DriverReg.car_model)

@dp.message(DriverReg.car_model)
async def dr_car(message: types.Message, state: FSMContext):
    await state.update_data(car_model=message.text)
    await message.answer("🔢 Mashinangiz davlat raqamini kiriting (Masalan: 40 A 777 AA):")
    await state.set_state(DriverReg.car_number)

@dp.message(DriverReg.car_number)
async def dr_num(message: types.Message, state: FSMContext):
    await state.update_data(car_number=message.text)
    await message.answer("📸 **DIQQAT FILTR!** Mashina texpasportining rasmini (yoki moshina rasmini) yuboring:")
    await state.set_state(DriverReg.passport_photo)

@dp.message(DriverReg.passport_photo, F.photo)
async def dr_photo(message: types.Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    data = await state.get_data()
    user_id = message.from_user.id
    
    DRIVERS[user_id] = {
        "name": data['name'], "phone": data['phone'],
        "car_model": data['car_model'], "car_number": data['car_number'],
        "status": "pending"
    }
    
    await message.answer("✅ Hujjatlar qabul qilindi! Admin tekshiruvidan so'ng sizga buyurtmalar ochiladi.")
    
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Tasdiqlash (Ruxsat)", callback_data=f"approve_{user_id}")
    builder.button(text="❌ Rad etish", callback_data=f"reject_{user_id}")
    
    try:
        await bot.send_photo(
            chat_id=ADMIN_ID, photo=photo_id,
            caption=f"🔔 **Yangi haydovchi arizasi!**\n👤 Ismi: {data['name']}\n📞 Tel: {data['phone']}\n🚗 Moshina: {data['car_model']} ({data['car_number']})",
            reply_markup=builder.as_markup()
        )
    except Exception as e:
        logging.error(f"Admin xabar yuborishda xatolik: {e}")
    await state.clear()

@dp.callback_query(F.data.startswith("approve_"))
async def approve_driver(call: types.CallbackQuery):
    dr_id = int(call.data.split("_")[1])
    if dr_id in DRIVERS:
        DRIVERS[dr_id]['status'] = 'approved'
        BALANCES[dr_id] = 50000 # Test uchun boshida 50 000 so'm bonus beriladi
        await call.message.answer("🟢 Haydovchi tasdiqlandi va tizimga qo'shildi.")
        await bot.send_message(chat_id=dr_id, text="🎉 Tabriklaymiz! Arizangiz tasdiqlandi. Balansingizga test uchun 50,000 so'm berildi. Zakazlar kutishingiz mumkin.")

# --- YO'LOVCHI BUYURTMA TIZIMI ---
@dp.message(F.text == "🚹 Men Yo'lovchiman")
async def client_start(message: types.Message, state: FSMContext):
    builder = ReplyKeyboardBuilder()
    builder.button(text="🇺🇿 Toshkent yo'nalishi")
    builder.button(text="🏡 Sirdaryo ichida")
    await message.answer("📍 Qayerga bormoqchisiz? Yo'nalishni tanlang:", reply_markup=builder.as_markup(resize_keyboard=True))
    await state.set_state(ClientOrder.direction)

@dp.message(ClientOrder.direction)
async def client_dir(message: types.Message, state: FSMContext):
    await state.update_data(direction=message.text)
    builder = ReplyKeyboardBuilder()
    if "Toshkent" in message.text:
        builder.button(text="1-Zona (Guliston, Sirdaryo sh, Baxt)")
        builder.button(text="2-Zona (Sayxunobod, Mirzaobod, Oqoltin)")
        builder.button(text="3-Zona (Sardoba, Xovos, Shirin)")
    else:
        builder.button(text="1-Zona (Yaqin masofalar)")
        builder.button(text="2-Zona (O'rtacha masofalar)")
        builder.button(text="3-Zona (Uzoq masofalar)")
    
    await message.answer("🏡 Hozir qaysi zonada (tuman/shahar) turibsiz?", reply_markup=builder.as_markup(resize_keyboard=True))
    await state.set_state(ClientOrder.zone)

@dp.message(ClientOrder.zone)
async def client_zone(message: types.Message, state: FSMContext):
    await state.update_data(zone=message.text)
    builder = ReplyKeyboardBuilder()
    builder.button(text="🚐 Eko")
    builder.button(text="Standart")
    builder.button(text="✨ Komfort")
    await message.answer("🚗 O'zingizga mos tarifni (Mashina turini) tanlang:", reply_markup=builder.as_markup(resize_keyboard=True))
    await state.set_state(ClientOrder.tariff)

@dp.message(ClientOrder.tariff)
async def client_tariff(message: types.Message, state: FSMContext):
    tariff_clean = message.text.replace("✨ ", "")
    await state.update_data(tariff=tariff_clean)
    await message.answer("📞 Siz bilan bog'lanish uchun telefon raqamingizni yozing:")
    await state.set_state(ClientOrder.phone)

@dp.message(ClientOrder.phone)
async def client_phone(message: types.Message, state: FSMContext):
    await state.update_data(phone=message.text)
    await message.answer("🏡 Aniq qayerdan olib ketish kerak? (Qishloq, ko'cha yoki uy raqami):")
    await state.set_state(ClientOrder.location_details)

@dp.message(ClientOrder.location_details)
async def client_final(message: types.Message, state: FSMContext):
    global order_counter
    data = await state.get_data()
    
    direction = data['direction']
    zone = data['zone']
    tariff = data['tariff']
    
    try:
        final_price = PRICE_MATRIX[direction][zone][tariff]
        comission = PRICE_MATRIX[direction][zone]["komissiya"]
    except KeyError:
        final_price = 55000
        comission = 5000

    ORDERS[order_counter] = {
        "client_id": message.from_user.id, "direction": direction, "zone": zone,
        "tariff": tariff, "phone": data['phone'], "details": message.text,
        "price": final_price, "comission": comission, "status": "active"
    }

    await message.answer(
        f"✅ **Buyurtmangiz qabul qilindi!**\n"
        f"💰 Safar narxi: {final_price} so'm (Uydan olib ketish ichida).\n"
        f"⏳ Haydovchilarimiz hozir siz bilan bog'lanishadi."
    )

    builder = InlineKeyboardBuilder()
    builder.button(text="✅ QABUL QILISH", callback_data=f"take_{order_counter}")
    
    for dr_id, dr_info in DRIVERS.items():


