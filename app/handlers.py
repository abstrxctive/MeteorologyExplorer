from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, FSInputFile

import os
import re
import time
import aiohttp
import requests

from bs4 import BeautifulSoup
from datetime import datetime
from dotenv import load_dotenv
from typing import Optional, Dict

from load import city_data
import app.keyboards as kb
from app.db.requests import set_user


# Загрузка переменных из .env файла
load_dotenv('other/.env')

# Получение токена
WEATHER_TOKEN = os.getenv('WEATHER_TOKEN')
router = Router()

LOGIN = os.getenv('PIK_LOGIN')
PASSWORD = os.getenv('PIK_PASSWORD')
LOGIN_URL = "http://www.pogodaiklimat.ru/login.php"

# Класс состояний
class RequestWeather(StatesGroup):
    location_user = State()
    request_weather_one_day = State()
    request_weather = State()
    forecast_for_one_city = State()
    forecast_for_more_cities = State()
    summary = State()
    weather_ams = State()

# Обработчик приветствия
@router.message(CommandStart())
async def command_start(message: Message):
    await set_user(message.from_user.id)
    await message.answer(
        "Привет! Я — Meteorology Explorer. Для навигации используйте клавиатуру ниже.",
        reply_markup=kb.main_menu)

# Кнопки клавиатуры
@router.message(F.text == "Список команд")
async def request_commands(message: Message):
    await message.answer("Выберите опцию:", reply_markup=kb.inline_menu)

@router.message(F.text == "Контакты")
async def get_contacts(message: Message):
    await message.answer("📡 Наши контакты\n\n"
                        "Тех. поддержка: ✉️ meteovrn@inbox.ru\n\n"
                        "YouTube: ▶️ youtube.com/@MeteoVrn\n\n"
                        "Telegram: 📲 t.me/meteovrn\n\n"
                        "ВКонтакте: 🌐 vk.com/meteoexplorer\n\n"
                        "Веб-сайт:  💻  meteovrn.ru\n\n"
                        "─────────────────────────────────────────────\n\n"
                        "Разработчики 👨‍💻\n\n"
                        "Abstrxctive\n"
                        "🔗GitHub: github.com/abstrxctive\n\n"
                        "Aron Sky:\n"
                        "🌐 ВКонтакте: vk.com/6om6a_fantastuk\n"
                        "💬 Telegram: @Andrey179ha"
                        )

@router.message(F.text == "Отправить геолокацию")
async def get_forecast_loc(message: Message, state: FSMContext):
    await state.set_state(RequestWeather.location_user)
    await message.answer(f"Вы можете поделиться местоположением для быстрого определения погоды",
                         reply_markup=kb.share_location)
    
def login_pik():
    session = requests.Session()
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 ' 
                      '(KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
    }

    resp = session.get(LOGIN_URL, headers=headers)
    resp.encoding = 'utf-8'
    soup = BeautifulSoup(resp.text, 'html.parser')

    hidden_inputs = soup.find_all("input", type="hidden")
    data = {inp['name']: inp.get('value', '') for inp in hidden_inputs}

    data.update({
        'username': LOGIN,
        'password': PASSWORD,
        'submit': 'Войти',
    })

    login_response = session.post(LOGIN_URL, data=data, headers=headers)
    login_response.encoding = 'utf-8'

    if "Выход" in login_response.text or "logout" in login_response.text.lower():
        print("Успешно авторизовались на сайте.")
        return session
    else:
        print("Не удалось авторизоваться. Проверь логин и пароль.")
        return None

API_KEYS = {
    "армавир": os.getenv("ARMAVIR_API_KEY"),
    "похвистнево": os.getenv("POHVISTNEVO_API_KEY")
}

STATION_IDS = {
    "армавир": "IARMAV7",
    "похвистнево": "IPOKHV1"
}

CITY_NAMES = {
    "армавир": "Армавире",
    "похвистнево": "Похвистнево"
}

def check_api_keys():
    print("Проверка API ключей и stationId...")
    for city in API_KEYS:
        api_key = API_KEYS[city]
        station_id = STATION_IDS[city]
        url = f"https://api.weather.com/v2/pws/observations/current?stationId={station_id}&format=json&units=m&apiKey={api_key}"
        try:
            response = requests.get(url, timeout=10)
            if response.status_code != 200:
                print(f"❌ Проверка не пройдена для '{city}': статус {response.status_code} - {response.text}")
            elif not response.content:
                print(f"❌ Проверка не пройдена для '{city}': пустой ответ.")
            else:
                print(f"✅ Проверка успешна для '{city}'.")
        except Exception as e:
            print(f"❌ Ошибка при проверке '{city}': {e}")

def safe_get(data, path, default="н/д"):
    try:
        for key in path:
            data = data[key]
        return data
    except (KeyError, TypeError):
        return default

def get_risk_level(temperature, wind_speed_ms, wind_gust_ms, uv_index, pressure, humidity, dew_point):
    levels = []

    # Температура
    if temperature >= 45 or temperature <= -45:
        levels.append(5)
    elif temperature >= 40 or temperature <= -35:
        levels.append(4)
    elif temperature >= 35 or temperature <= -25:
        levels.append(3)
    elif temperature >= 30 or temperature <= -15:
        levels.append(2)
    else:
        levels.append(1)

    # Скорость ветра (постоянная)
    if wind_speed_ms >= 25:
        levels.append(5)
    elif wind_speed_ms >= 20:
        levels.append(4)
    elif wind_speed_ms >= 15:
        levels.append(3)
    elif wind_speed_ms >= 7:
        levels.append(2)
    else:
        levels.append(1)

    # Порывы ветра
    if wind_gust_ms >= 33:
        levels.append(5)
    elif wind_gust_ms >= 25:
        levels.append(4)
    elif wind_gust_ms >= 20:
        levels.append(3)
    elif wind_gust_ms >= 10:
        levels.append(2)
    else:
        levels.append(1)

    # УФ-индекс
    if uv_index >= 11:
        levels.append(5)
    elif uv_index >= 9:
        levels.append(4)
    elif uv_index >= 7:
        levels.append(3)
    elif uv_index >= 3:
        levels.append(2)
    else:
        levels.append(1)

    # Давление
    if pressure <= 950 or pressure >= 1080:
        levels.append(5)
    elif pressure <= 970 or pressure >= 1060:
        levels.append(4)
    elif pressure <= 980 or pressure >= 1040:
        levels.append(3)
    elif pressure <= 990 or pressure >= 1020:
        levels.append(2)
    else:
        levels.append(1)

    # Влажность — всегда 1 (удалены уровни опасности)
    levels.append(1)

    # Точка росы (высокая - опасность)
    if dew_point >= 25:
        levels.append(5)
    elif dew_point >= 20:
        levels.append(4)
    elif dew_point >= 16:
        levels.append(3)
    elif dew_point >= 12:
        levels.append(2)
    else:
        levels.append(1)

    max_level = max(levels)

    level_map = {
        1: "🟢 Дискомфорт отсутвует",
        2: "🟡 Лёгкий дискомфорт",
        3: "🟠 Повышенный дискомфорт",
        4: "🔴 Дискомфорт высокой опасности",
        5: "🟣 Дискомфорт экстремальной опасности"
    }

    return level_map[max_level]

def get_wind_direction(degree):
    dirs = ['С', 'ССВ', 'СВ', 'ВСВ', 'В', 'ВЮВ', 'ЮВ', 'ЮЮВ', 'Ю', 'ЮЮЗ', 'ЮЗ', 'ЗЮЗ', 'З', 'ЗСЗ', 'СЗ', 'ССЗ']
    ix = round(degree / 22.5) % 16
    return dirs[ix]

@router.callback_query(F.data == "meteostation_data")
async def get_meteostation_data(callback: CallbackQuery, state: FSMContext):
    await state.set_state(RequestWeather.weather_ams)
    await callback.message.answer("Введите название станции\n"
                                  "Пример ввода: Армавир")
    await callback.answer()

@router.message(RequestWeather.weather_ams)
async def set_meteostation_data(message: Message, state: FSMContext):
    await state.update_data(weather_ams=message.text)
    tg_data = await state.get_data()
    city_key = tg_data['weather_ams'].lower()
    
    try:
        if city_key not in API_KEYS:
            print(f"Ошибка: город '{city_key}' не найден в конфигурации.")
            await message.answer(f"Данной АМС ({city_key.capitalize()}) нету в нашей базе.\n"
                                "Если вы хотите её добавить, свяжитесь с нами:\n"
                                "─────────────────────────────────────────────\n"
                                "E-mail: ✉️ meteovrn@inbox.ru\n"
                                "Telegram: 📲 t.me/meteovrn\n"
                                "ВКонтакте: 🌐 vk.com/meteoexplorer"
                                )

        api_key = API_KEYS[city_key]
        station_id = STATION_IDS[city_key]
        url = f"https://api.weather.com/v2/pws/observations/current?stationId={station_id}&format=json&units=m&apiKey={api_key}"

        try:
            response = requests.get(url, timeout=10)
        except Exception as e:
            print(f"Ошибка запроса к API: {e}")
            return "⚠️ Не удалось связаться с сервером погоды."

        if response.status_code != 200 or not response.content:
            print(f"Ошибка API: {response.status_code} - {response.text}")
            return "⚠️ Не удалось получить данные о погоде."

        try:
            data = response.json()
            obs = data['observations'][0]
            temperature = round(float(safe_get(obs, ['metric', 'temp'], 0)))
            humidity = round(float(safe_get(obs, ['humidity'], 0)))
            dewpt = round(float(safe_get(obs, ['metric', 'dewpt'], 0)))
            wind_speed_kmh = float(safe_get(obs, ['metric', 'windSpeed'], 0))
            wind_gust_kmh = float(safe_get(obs, ['metric', 'windGust'], 0))
            wind_speed_ms = round(wind_speed_kmh / 3.6, 1)
            wind_gust_ms = round(wind_gust_kmh / 3.6, 1)
            wind_dir = safe_get(obs, ['winddir'], 0)
            feelslike = round(float(safe_get(obs, ['metric', 'heatIndex'], 0)))
            uv_index = round(float(safe_get(obs, ['uv'], 0)))
            solar_radiation = round(float(safe_get(obs, ['solarRadiation'], 0)), 1)
            pressure = round(float(safe_get(obs, ['metric', 'pressure'], 0)), 1)
            precip_rate = round(float(safe_get(obs, ['metric', 'precipRate'], 0)), 1)
            precip_total = round(float(safe_get(obs, ['metric', 'precipTotal'], 0)), 1)
            obs_time = safe_get(obs, ['obsTimeLocal'])

            wind_direction = get_wind_direction(wind_dir)

            risk = get_risk_level(temperature, wind_speed_ms, wind_gust_ms, uv_index, pressure, humidity, dewpt)

            result = (
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🌍 Погода в {CITY_NAMES[city_key]}\n"
                f"🕑 Дата и время: {obs_time}\n"
                f"📡 Источник: АМС (автоматическая метеостанция)\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"\n"
                f"{risk}\n"
                f"\n"
                f"🌡 Температура воздуха: {temperature}°C\n"
                f"🤗 Ощущается как: {feelslike}°C\n"
                f"💧 Влажность воздуха: {humidity}%\n"
                f"💦 Точка росы: {dewpt}°C\n"
                f"🌬 Ветер: {wind_direction} {wind_speed_ms} м/с (порывы до {wind_gust_ms} м/с)\n"
                f"📈 Атм. давление: {pressure} гПа\n"
                f"🌧 Интенсивность осадков: {precip_rate} мм/ч\n"
                f"💦 Суммарные осадки: {precip_total} мм\n"
                f"🌞 УФ-индекс: {uv_index} ☀️\n"
                f"🔆 Солнечная радиация: {solar_radiation} Вт/м²\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            )
            print(f"Данные для {CITY_NAMES[city_key]} успешно получены.")
            await message.answer(result)

        except Exception as e:
            print(f"Ошибка обработки данных: {e}")
            await message.answer("⚠️ Ошибка обработки данных погоды.")
        
    except Exception as e:
        print(f"Что-то пошло не так...\n\n{e}")
        
    await message.answer("Выберите опцию:", reply_markup=kb.inline_menu)
    await state.clear()

def get_weather_icon(condition: str) -> str:
    condition = condition.lower()
    if "солнечно" in condition or "ясно" in condition:
        return "☀️"
    elif "облачно" in condition and "переменная" in condition:
        return "⛅"
    elif "облачно" in condition:
        return "☁️"
    elif "дожд" in condition:
        return "🌧"
    elif "гроза" in condition:
        return "⛈"
    elif "снег" in condition:
        return "❄️"
    elif "туман" in condition or "мгла" in condition:
        return "🌫"
    elif "морось" in condition:
        return "🌦"
    elif "метель" in condition or "позёмок" in condition:
        return "🌨"
    else:
        return "🌤"

def group_hours_by_period(hours_data):
    """Группирует почасовой прогноз по временам суток"""
    periods = {
        "🌅 Утро": [],
        "☀ День": [],
        "🌇 Вечер": [],
        "🌙 Ночь": []
    }
    for hour in hours_data:
        time_str = hour['time'][-5:]
        h = int(time_str[:2])
        entry = f"{get_weather_icon(hour['condition']['text'])} {hour['temp_c']}°C, {hour['condition']['text']}, 💨 {hour['wind_kph']} км/ч, 🌦 {hour['precip_mm']} мм"
        if 6 <= h < 12:
            periods["🌅 Утро"].append(entry)
        elif 12 <= h < 18:
            periods["☀ День"].append(entry)
        elif 18 <= h < 24:
            periods["🌇 Вечер"].append(entry)
        else:
            periods["🌙 Ночь"].append(entry)
    return periods

# Обработка геолокации пользователя
@router.message(RequestWeather.location_user, F.location)
async def get_fast_weather(message: Message, state: FSMContext):
    async def get_weather_by_coords(lt: float, ln: float, api_key: str) -> Optional[Dict]:
        base_url = "http://api.weatherapi.com/v1/current.json"
        params = {
            'key': api_key,
            'q': f"{lt},{ln}",
            'lang': 'ru'
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(base_url, params=params) as rp:
                rp.raise_for_status()
                data = await rp.json()
                return {
                    'city': data['location']['name'],
                    'region': data['location']['region'],
                    'country': data['location']['country'],
                    'temp': data['current']['temp_c'],
                    'feels_like': data['current']['feelslike_c'],
                    'condition': data['current']['condition']['text'],
                    'humidity': data['current']['humidity'],
                    'wind_kph': data['current']['wind_kph'],
                    'wind_dir': data['current']['wind_dir'],
                    'pressure_mb': data['current']['pressure_mb'],
                    'precip_mm': data['current']['precip_mm'],
                    'cloud': data['current']['cloud'],
                    'last_updated': data['current']['last_updated']
                }

    lat, lon = message.location.latitude, message.location.longitude
    await state.update_data(loc=message.location)

    try:
        weather_data = await get_weather_by_coords(lat, lon, WEATHER_TOKEN)
        if weather_data:
            icon = get_weather_icon(weather_data['condition'])
            response = (
                f"📍 *Местоположение:* {weather_data['city']}, {weather_data['region']} ({weather_data['country']})\n"
                f"⏱ Обновлено: {weather_data['last_updated']}\n"
                f"{'─'*30}\n"
                f"🌡 *Температура:* {weather_data['temp']}°C (ощущается как {weather_data['feels_like']}°C)\n"
                f"{icon} *Состояние:* {weather_data['condition']}\n"
                f"💧 *Влажность:* {weather_data['humidity']}%\n"
                f"💨 *Ветер:* {weather_data['wind_kph']} км/ч, {weather_data['wind_dir']}\n"
                f"📈 *Давление:* {round(weather_data['pressure_mb'] * 0.75, 1)} мм рт. ст.\n"
                f"🌦 *Осадки:* {weather_data['precip_mm']} мм\n"
                f"☁ *Облачность:* {weather_data['cloud']}%"
            )
        else:
            response = "⚠ Не удалось получить данные о погоде"

        await message.answer(response, parse_mode="Markdown")
    except Exception:
        raise

    await message.answer("Выберите опцию:", reply_markup=kb.inline_menu)
    await state.clear()

# Возврат к опциям
@router.message(F.text == "Назад")
async def back(message: Message):
    await message.answer("Вы вернулись назад", reply_markup=kb.main_menu)

# Прогноз погоды на 1 день по вводу
@router.callback_query(F.data == "get_weather_one")
async def request_one_day(callback: CallbackQuery, state: FSMContext):
    await state.set_state(RequestWeather.request_weather_one_day)
    await callback.message.answer("Введите название населённого пункта")
    await callback.answer()

@router.message(RequestWeather.request_weather_one_day)
async def weather_one_day(message: Message, state: FSMContext):
    await state.update_data(request_weather_one_day=message.text)
    tg_data = await state.get_data()
    city_name = tg_data['request_weather_one_day']
    url = f"http://api.weatherapi.com/v1/forecast.json?key={WEATHER_TOKEN}&q={city_name}&days=1&lang=ru"

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                location = data["location"]
                forecast = data["forecast"]["forecastday"][0]
                day = forecast["day"]
                hours = forecast["hour"]

                icon = get_weather_icon(day['condition']['text'])
                forecast_text = (
                    f"📍 *Местоположение:* {location['name']}, {location['country']}\n"
                    f"📅 *Дата:* {forecast['date']}\n"
                    f"{'─'*30}\n"
                    f"🌡 *Макс:* {day['maxtemp_c']}°C\n"
                    f"🌡❄️ *Мин:* {day['mintemp_c']}°C\n"
                    f"{icon} *Состояние:* {day['condition']['text']}\n"
                    f"💧 *Влажность:* {day['avghumidity']}%\n"
                    f"💨 *Ветер:* {day['maxwind_kph']} км/ч\n"
                    f"🌦 *Осадки:* {day['totalprecip_mm']} мм\n"
                    f"{'─'*30}\n"
                    f"🕒 *Периоды суток:*"
                )

                periods = group_hours_by_period(hours)
                for period_name, entries in periods.items():
                    if entries:
                        forecast_text += f"\n\n{period_name}:\n" + "\n".join(entries)

                await message.answer(forecast_text, parse_mode="Markdown")
            else:
                await message.answer("⚠ Указан неизвестный населённый пункт")

    await message.answer("Выберите опцию:", reply_markup=kb.inline_menu)
    await state.clear()

# Прогноз погоды на 3 дня по вводу
@router.callback_query(F.data == "get_weather")
async def get_weather(callback: CallbackQuery, state: FSMContext):
    await state.set_state(RequestWeather.request_weather)
    await callback.message.answer("Введите название населённого пункта")
    await callback.answer()

# Обработка состояния
@router.message(RequestWeather.request_weather)
async def weather(message: Message, state: FSMContext):
    await state.update_data(request_weather=message.text)
    tg_data = await state.get_data()
    city_name = tg_data['request_weather']
    url = f"http://api.weatherapi.com/v1/forecast.json?key={WEATHER_TOKEN}&q={city_name}&days=3&lang=ru"

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                location = data["location"]
                result = f"📍 *Местоположение:* {location['name']}, {location['country']}\nПрогноз на 3 дня:\n"

                for forecast in data["forecast"]["forecastday"]:
                    d = forecast["day"]
                    hours = forecast["hour"]
                    icon = get_weather_icon(d['condition']['text'])

                    result += (
                        f"\n{'─'*30}\n"
                        f"📅 *{forecast['date']}*\n"
                        f"🌡 Макс: {d['maxtemp_c']}°C | Мин: {d['mintemp_c']}°C\n"
                        f"{icon} Состояние: {d['condition']['text']}\n"
                        f"💧 Влажность: {d['avghumidity']}%\n"
                        f"💨 Ветер: {d['maxwind_kph']} км/ч\n"
                        f"🌦 Осадки: {d['totalprecip_mm']} мм\n"
                        f"{'─'*30}\n"
                        f"🕒 *Периоды суток:*"
                    )

                    periods = group_hours_by_period(hours)
                    for period_name, entries in periods.items():
                        if entries:
                            result += f"\n\n{period_name}:\n" + "\n".join(entries)

                await message.answer(result, parse_mode="Markdown")
            else:
                await message.answer("⚠ Указан неизвестный населённый пункт")

    await message.answer("Выберите опцию:", reply_markup=kb.inline_menu)
    await state.clear()

# Комплексный прогноз от ГМЦ для нескольких населённых пунктов
@router.callback_query(F.data == "gmc_forecast_more")
async def get_forecast_for_more_cities(callback: CallbackQuery, state:FSMContext):
    await state.set_state(RequestWeather.forecast_for_more_cities)
    await callback.message.answer("Введите названия городов через запятую (Максимум 10 городов)")
    await callback.answer()

# Обработка ввода
@router.message(RequestWeather.forecast_for_more_cities)
async def set_forecast_for_more_cities(message: Message, state: FSMContext):
    await state.update_data(forecast_for_more_cities=message.text)

    # Начало отсчёта работы скрипта
    start_time = time.time()
    tg_data = await state.get_data()

    # Работа с вводом от пользователя
    weather_city = tg_data['forecast_for_more_cities']
    cities = [city.strip().upper() for city in weather_city.split(',') if city.strip()]
    cities = cities[:10]

    if not cities:
        await message.answer("Не указано ни одного города. Попробуйте снова")

    # Получение данных из city_data
    for city_name in cities:
        city_info = next((city for city in city_data if city['eng_name'] == city_name), None)

        if city_info:
            city_url = city_info['url']

            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(city_url) as response:
                        if response.status == 200:

                            # Обработка изображения
                            image_data = await response.read()
                            temp_file = f"images/temp_{city_name.lower()}.png"

                            # Открытие изображения
                            with open(temp_file, 'wb') as f:
                                f.write(image_data)

                            # Подсчёт времени работы скрипта
                            end_time = time.time()
                            elapsed_time = end_time - start_time

                            # Отправка сообщения о погоде
                            await message.answer_photo(
                                photo=FSInputFile(temp_file),
                                caption=f"Прогноз на 5 дней для населённого пункта: {city_name.capitalize()}"
                                        f"\nВремя, затраченное на отправку: {elapsed_time:.2f} секунд")
                        else:
                            await message.answer("Ошибка загрузки данных!")

            except Exception as e:
                await message.answer(f"Произошла ошибка: {e}")
        else:
            await message.answer("Город не найден")

    await message.answer("Выберите опцию:", reply_markup=kb.inline_menu)
    await state.clear()

def get_clean_text(td_element):
    if td_element is None:
        return "нет данных"
    text = td_element.get_text(strip=True)
    if text.startswith('+'):
        text = text[1:]
    return text

@router.callback_query(F.data == "summary_search")
async def get_summary(callback: CallbackQuery, state:FSMContext):
    await state.set_state(RequestWeather.summary)
    await callback.message.answer(
        "Формат ввода: Факт.данные _код_станции_ _дата_\n"
        "Пример ввода: Факт.данные 34123 11.08.2025"
        )
    await callback.answer()

@router.message(RequestWeather.summary)
async def set_summary(message: Message, state: FSMContext):
    await state.update_data(summary=message.text)
    
    # Начало отсчёта работы скрипта
    start_time = time.time()
    
    session = login_pik()
    if not session:
        print('Программа остановлена из-за ошибки авторизации')

    tg_data = await state.get_data()
    summary_text = tg_data['summary']
    
    match = re.match(r"Факт\.данные\s+(\S+)\s+(\d{2}\.\d{2}\.\d{4})", summary_text)
    if match:
        input_id_or_name = match.group(1)
        date_str = match.group(2)

        if input_id_or_name.isdigit():
            station_id = input_id_or_name
    
    try:
        date_obj = datetime.strptime(date_str, "%d.%m.%Y")
        month = date_obj.month
        year = date_obj.year
        
        url = f"http://www.pogodaiklimat.ru/summary.php?m={month}&y={year}&id={station_id}"
        
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = session.get(url, headers=headers)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, "html.parser")

        table = soup.find("table", {"class": "tab"})
        if not table:
            await message.answer("⚠️ Таблица не найдена. Проверь код станции или дату.")

        rows = table.find_all("tr")[2:]

        for row in rows:
            cols = row.find_all("td")
            if not cols or len(cols) < 15:
                continue

            date_in_row = cols[2].get_text(strip=True)

            if date_in_row == date_str:
                station_name = get_clean_text(cols[1])
                temp_avg = get_clean_text(cols[3])
                temp_dt_avg = get_clean_text(cols[4])
                temp_min = get_clean_text(cols[6])
                temp_max = get_clean_text(cols[7])
                humidity = get_clean_text(cols[8])
                humidity_min = get_clean_text(cols[9])
                eff_te_min = get_clean_text(cols[10])
                eff_te_max = get_clean_text(cols[11])
                eff_tes_max = get_clean_text(cols[12])
                wind = get_clean_text(cols[13])
                wind_gust = get_clean_text(cols[14])
                min_view = get_clean_text(cols[15])
                
                # Перевод из ГПА в ММ. РТ. СТ.
                avg_pressure = float(get_clean_text(cols[16])) * 0.75
                min_pressure = float(get_clean_text(cols[17])) * 0.75
                max_pressure = float(get_clean_text(cols[18])) * 0.75
                
                avg_mark_cloud = get_clean_text(cols[22])
                low_mark_cloud = get_clean_text(cols[23])
                night_precip = get_clean_text(cols[24])
                day_precip = get_clean_text(cols[25])
                sum_precip = get_clean_text(cols[26])
                snow_cover = get_clean_text(cols[27])
                case_rain = get_clean_text(cols[29])
                case_snow = get_clean_text(cols[30])
                case_fog = get_clean_text(cols[31])
                case_mist = get_clean_text(cols[32])
                case_snowstorm = get_clean_text(cols[33])
                case_snowfall = get_clean_text(cols[34])
                case_thunderstorm = get_clean_text(cols[35])
                case_tornado = get_clean_text(cols[36])
                case_dust_storm = get_clean_text(cols[37])
                case_dustfall = get_clean_text(cols[38])
                case_hail = get_clean_text(cols[39])
                case_black_ice = get_clean_text(cols[40])
                
                elapsed = time.time() - start_time
                
                await message.answer(
                    f"📊 Данные МС {station_id} — {station_name} за {date_str}:\n\n"

                    f"🌡 Температуры:\n"
                    f"  • Максимальная: {temp_max} °C\n"
                    f"  • Средняя: {temp_avg} °C\n"
                    f"  • Минимальная: {temp_min} °C\n"
                    f"  • Температурная аномалия: {temp_dt_avg} °С\n"
                    f"  • Эффективная температура в тени (мин.): {eff_te_min} °С\n"
                    f"  • Эффективная температура в тени (макс.): {eff_te_max} °С\n"
                    f"  • Эффективная температура на Солнце (макс.): {eff_tes_max} °С\n\n"

                    f"📈 Давление (мм рт. ст.):\n"
                    f"  • Среднее: {str(avg_pressure)[:5]}\n"
                    f"  • Минимальное: {str(min_pressure)[:5]}\n"
                    f"  • Максимальное: {str(max_pressure)[:5]}\n\n"

                    f"💨 Ветер:\n"
                    f"  • Средняя скорость: {wind} м/с\n"
                    f"  • Порывы: {wind_gust} м/с\n\n"

                    f"👁 Видимость:\n"
                    f"  • Минимальная: {min_view}\n\n"

                    f"💦 Влажность:\n"
                    f"  • Средняя: {humidity} %\n"
                    f"  • Минимальная: {humidity_min} %\n\n"

                    f"🌧 Осадки (мм):\n"
                    f"  • Ночью: {night_precip if night_precip else '0.0'}\n"
                    f"  • Днём: {day_precip if day_precip else '0.0'}\n"
                    f"  • Суммарно: {sum_precip}\n\n"

                    f"☁️ Облачность (в баллах):\n"
                    f"  • Средняя: {avg_mark_cloud} км\n"
                    f"  • Нижняя: {low_mark_cloud} км\n\n"

                    f"❄️ Снежный покров (см): {snow_cover if snow_cover else '—'}\n\n"

                    f"🌀 Явления (сроки):\n"
                    f"  • Снег: {case_snow if case_snow else '—'}\n"
                    f"  • Дождь: {case_rain if case_rain else '—'}\n"
                    f"  • Гололёд: {case_black_ice if case_black_ice else '—'}\n"
                    f"  • Туман: {case_fog if case_fog else '—'}\n"
                    f"  • Мгла: {case_mist if case_mist else '—'}\n"
                    f"  • Метель: {case_snowstorm if case_snowstorm else '—'}\n"
                    f"  • Позёмок: {case_snowfall if case_snowfall else '—'}\n"
                    f"  • Торнадо: {case_tornado if case_tornado else '—'}\n"
                    f"  • Пылевая буря: {case_dust_storm if case_dust_storm else '—'}\n"
                    f"  • Пылевой позёмок: {case_dustfall if case_dustfall else '—'}\n"
                    f"  • Гроза: {case_thunderstorm if case_thunderstorm else '—'}\n"
                    f"  • Град: {case_hail + ' мм' if case_hail else '—'}\n\n"
                    f"⏱ Затрачено: {elapsed:.2f} сек."
                )
        
        await message.answer("Выберите опцию:", reply_markup=kb.inline_menu)
        await state.clear()
            
    except Exception as e:
        await message.answer(f"❌ Ошибка при обработке данных: {e}")
