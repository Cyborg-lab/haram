# Telefon e'lonlari Telegram boti

Bot foydalanuvchini birinchi marta ro'yxatdan o'tkazadi, telefon e'lonini MongoDB ga saqlaydi, o'z e'lonlarini ko'rsatadi va har bir e'lonni aktiv/noaktiv holatga o'tkaza oladi. Qidiruv natijalarida faqat aktiv e'lonlar chiqadi.

## O'rnatish

1. Python 3.10 yoki yangiroq versiyasini o'rnating.
2. MongoDB serverini ishga tushiring.
3. Kutubxonalarni o'rnating: `pip install -r requirements.txt`
4. `.env.example` faylidan nusxa olib, nomini `.env` qiling va `BOT_TOKEN` ni kiriting.
5. Botni ishga tushiring: `python bot.py`

MongoDB ma'lumotlari `users` va `ads` kolleksiyalarida saqlanadi. Bot ishga tushganda kerakli indekslar avtomatik yaratiladi.

## Mini App

Mini App bot bilan aynan bitta MongoDB bazasidan foydalanadi. `WEBAPP_URL` ga HTTPS domeningizni yozing. So'ng alohida terminalda quyidagini ishga tushiring:

`python run.py`

Telegram Mini App xavfsizligi uchun sayt faqat Telegram ichida ochiladi: foydalanuvchi `initData` imzosi bilan avtomatik taniladi. Botdan ro'yxatdan o'tgan telefon raqami Mini App profilida ham ko'rinadi; Mini App'da kiritilgan raqam ham o'sha `users` kolleksiyasiga saqlanadi.
# enigma
