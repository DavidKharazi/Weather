import requests
import logging
from fastapi import FastAPI
from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler
from telegram.ext import ContextTypes
import uvicorn
import asyncio
from config import WEATHER_API_KEY, TELEGRAM_TOKEN

"""  1. В config.py в переменной TELEGRAM_TOKEN поместите токен бота
     2. Установте зависимости: pip install -r requirements.txt
     3. Запустите бота python.bot.py   """



# Настройка логирования
logging.basicConfig(level=logging.INFO)



# Настройка базы данных (SQLite)
DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# Модель для логов запросов
class Log(Base):
    __tablename__ = "logs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer)
    command = Column(String)
    response = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)


# Создание таблиц
Base.metadata.create_all(bind=engine)

# FastAPI приложение
app = FastAPI()



# Функция для запроса погоды
def get_weather(city: str):
    url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={WEATHER_API_KEY}&units=metric&lang=ru"
    response = requests.get(url)
    if response.status_code != 200:
        return None
    data = response.json()
    weather_info = {
        "temp": data["main"]["temp"],
        "feels_like": data["main"]["feels_like"],
        "description": data["weather"][0]["description"],
        "humidity": data["main"]["humidity"],
        "wind_speed": data["wind"]["speed"],
    }
    return weather_info


# Telegram-бот команды
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_message = (
        "Привет! Я могу помочь узнать погоду в любом городе. "
        "Для этого используй команду /weather <город>, например: /weather Минск."
    )
    await update.message.reply_text(welcome_message)



async def weather(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        city = context.args[0]
    except IndexError:
        await update.message.reply_text("Пожалуйста, укажи город после команды /weather.")
        return

    weather_info = get_weather(city)
    if weather_info:
        response = (f"Погода в г. {city}:\n"
                    f"Температура: {weather_info['temp']}°C\n"
                    f"Ощущается как: {weather_info['feels_like']}°C\n"
                    f"Описание: {weather_info['description']}\n"
                    f"Влажность: {weather_info['humidity']}%\n"
                    f"Скорость ветра: {weather_info['wind_speed']} м/с")
    else:
        response = "Не удалось получить погоду для указанного города."

    # Логирование в БД
    db = SessionLocal()
    log_entry = Log(user_id=update.effective_user.id, command=f"/weather {city}", response=response)
    db.add(log_entry)
    db.commit()
    db.close()

    await update.message.reply_text(response)


# Инициализация и запуск Telegram-бота
async def run_bot():
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Инициализация приложения
    await application.initialize()

    # Добавление обработчиков команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("weather", weather))

    # Запуск процесса поллинга
    await application.start()
    await application.updater.start_polling()


# Запуск FastAPI и Telegram-бота
async def main():
    # Запуск Telegram-бота и FastAPI параллельно
    bot_task = asyncio.create_task(run_bot())

    # Запуск FastAPI сервера
    config = uvicorn.Config(app, host="0.0.0.0", port=8000)
    server = uvicorn.Server(config)

    api_task = asyncio.create_task(server.serve())

    await asyncio.gather(bot_task, api_task)


if __name__ == "__main__":
    asyncio.run(main())


