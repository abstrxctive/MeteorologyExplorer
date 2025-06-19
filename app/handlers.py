from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, FSInputFile

import os
import time
import aiohttp

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


# Класс состояний
class RequestWeather(StatesGroup):
    location_user = State()
    request_weather_one_day = State()
    request_weather = State()
    forecast_for_one_city = State()
    forecast_for_more_cities = State()


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
    await message.answer("Техническая поддержка: meteoexplorersupprt@inbox.ru\n\n"
                         "Telegram: t.me/VRN_stormchaser\n"
                         "YouTube: youtube.com/channel/UCiTDX0L17kd17lQlNmJjigQ\n")

@router.message(F.text == "Отправить геолокацию")
async def get_forecast_loc(message: Message, state: FSMContext):
    await state.set_state(RequestWeather.location_user)
    await message.answer(f"Вы можете поделиться местоположением для быстрого определения погоды",
                         reply_markup=kb.share_location)

# Обработка геолокации пользователя
@router.message(RequestWeather.location_user, F.location)
async def get_fast_weather(message: Message, state: FSMContext):
    async def get_weather_by_coords(lt: float, ln: float, api_key: str) -> Optional[Dict]:
        base_url = "http://api.weatherapi.com/v1/current.json"

        # Параметры обработки прогноза погоды
        params = {
            'key': api_key,
            'q': f"{lt},{ln}",
            'lang': 'ru'
        }

        try:
            # Создание и подключение сессии
            async with aiohttp.ClientSession() as session:
                async with session.get(base_url, params=params) as rp:
                    rp.raise_for_status()
                    data = await rp.json()

                    current = data['current']
                    location = data['location']

                    # Возврат параметров в JSON формате
                    return {
                        'city': location['name'],
                        'region': location['region'],
                        'country': location['country'],
                        'temp': current['temp_c'],
                        'feels_like': current['feelslike_c'],
                        'condition': current['condition']['text'],
                        'humidity': current['humidity'],
                        'wind_kph': current['wind_kph'],
                        'wind_dir': current['wind_dir'],
                        'pressure_mb': current['pressure_mb'],
                        'precip_mm': current['precip_mm'],
                        'cloud': current['cloud'],
                        'last_updated': current['last_updated']}

        except Exception:
            raise

    loc = message.location
    lat = loc.latitude
    lon = loc.longitude

    await state.update_data(loc=loc)
    try:
        weather_data = await get_weather_by_coords(lat, lon, WEATHER_TOKEN)

        # Отправка сообщения о погоде
        if weather_data:
            response = (f"🌤 Погода в {weather_data['city']}, {weather_data['region']}:\n\n"
                        f"🌡 Температура: {weather_data['temp']}°C (ощущается как {weather_data['feels_like']}°C)\n"
                        f"☁ Состояние: {weather_data['condition']}\n"
                        f"💧 Влажность: {weather_data['humidity']}%\n"
                        f"🌬 Ветер: {weather_data['wind_kph']} км/ч, {weather_data['wind_dir']}\n"
                        f"⏱ Обновлено: {weather_data['last_updated']}")
        else:
            response = "⚠ Не удалось получить данные о погоде"

        await message.answer(response)

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

# Обработка состояния
@router.message(RequestWeather.request_weather_one_day)
async def weather_one_day(message: Message, state: FSMContext):
    await state.update_data(request_weather_one_day=message.text)
    tg_data = await state.get_data()

    # Url для получения сведений о погоде
    url = f"http://api.weatherapi.com/v1/forecast.json?key={WEATHER_TOKEN}&q={tg_data}&days={1}&lang=ru"

    # Создание и подключение сессии
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                location = data["location"]["name"]

                # Обработка параметров в JSON формате
                for day in data["forecast"]["forecastday"]:
                    date = day["date"]
                    max_temp = day["day"]["maxtemp_c"]
                    min_temp = day["day"]["mintemp_c"]
                    condition = day["day"]["condition"]["text"]
                    forecast_text = (
                        f"📅 {date}:\nМакс: {max_temp}°C\nМин: {min_temp}°C\nПогода: {condition}")

                # Сообщение о погоде
                await message.answer(f"Прогноз на 1 день для населённого пункта {location}: \n\n{forecast_text}")
            else:

                await message.answer(f"Вы указали неизвестный населённый пункт")

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

    # Словарь для хранения данных о погоде
    forecasts = []

    # Url для получения сведений о погоде
    url = f"http://api.weatherapi.com/v1/forecast.json?key={WEATHER_TOKEN}&q={tg_data}&days={3}&lang=ru"

    # Создание и подключение сессии
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                location = data["location"]["name"]

                # Обработка параметров в JSON формате
                for day in data["forecast"]["forecastday"]:
                    date = day["date"]
                    max_temp = day["day"]["maxtemp_c"]
                    min_temp = day["day"]["mintemp_c"]
                    condition = day["day"]["condition"]["text"]
                    forecast_text = (
                        f"📅 {date}:\nМакс: {max_temp}°C\nМин: {min_temp}°C\nПогода: {condition}")

                    # Добавление данных в массив
                    forecasts.append(forecast_text)

                # Обработка текста и отправка данных о погоде
                await message.answer(
                f"Прогноз на {3} дня для населённого пункта {location}:\n\n{f'{chr(10)}{chr(10)}'.join(forecasts)}")
            else:
                await message.answer(f"Вы указали неизвестный населённый пункт")

    await message.answer("Выберите опцию:", reply_markup=kb.inline_menu)
    await state.clear()

# Комплексный прогноз от ГМЦ для 1 населённого пункта
@router.callback_query(F.data == "gmc_forecast")
async def get_gmc_forecast(callback: CallbackQuery, state: FSMContext):
    await state.set_state(RequestWeather.forecast_for_one_city)
    await callback.message.answer("Введите название населённого пункта")
    await callback.answer()

# Обработка ввода пользователя
@router.message(RequestWeather.forecast_for_one_city)
async def gmc_forecast(message: Message, state: FSMContext):
    await state.update_data(forecast_for_one_city=message.text)
    tg_data = await state.get_data()

    # Начало отсчёта работы скрипта
    start_time = time.time()

    # Обработка ввода пользователя
    weather_city = tg_data['forecast_for_one_city']
    city_name = weather_city.strip().upper()

    # Получение данных из city_data
    city_info = next((city for city in city_data if city['eng_name'] == city_name), None)

    if city_info:
        city_url = city_info['url']

        try:
            # Создание и подключение сессии
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
                            f"\nВремя затраченное на отправку: {elapsed_time:.2f} секунд")
                    else:
                        await message.answer("Ошибка загрузки данных!")

        except Exception as e:
            await message.answer(f"Произошла ошибка: {e}")
    else:
        await message.answer("Город не найден")

    await message.answer("Выберите опцию:", reply_markup=kb.inline_menu)
    await state.clear()

# Комплексный прогноз от ГМЦ для нескольких населённых пунктов
@router.callback_query(F.data == "gmc_forecast_more")
async def get_forecast_for_more_cities(callback: CallbackQuery, state:FSMContext):
    await state.set_state(RequestWeather.forecast_for_more_cities)
    await callback.message.answer("Введите названия городов через запятую (⚠️Максимум 10 городов)")
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
                                        f"\nВремя затраченное на отправку: {elapsed_time:.2f} секунд")
                        else:
                            await message.answer("Ошибка загрузки данных!")

            except Exception as e:
                await message.answer(f"Произошла ошибка: {e}")
        else:
            await message.answer("Город не найден")

    await message.answer("Выберите опцию:", reply_markup=kb.inline_menu)
    await state.clear()
