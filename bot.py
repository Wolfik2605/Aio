import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message, InputFile
from config import settings
from openai_client import OpenAIClient

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация бота и диспетчера
bot = Bot(token=settings.BOT_TOKEN.get_secret_value())
dp = Dispatcher()

# Инициализация OpenAI клиента
openai_client = OpenAIClient()

# Создаем директорию для временных файлов
TEMP_DIR = "temp"
os.makedirs(TEMP_DIR, exist_ok=True)

# Обработчик команды /start
@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "👋 Привет! Я голосовой AI-бот.\n"
        "Отправь мне голосовое сообщение, и я отвечу на него!"
    )

# Обработчик голосовых сообщений
@dp.message()
async def handle_voice(message: Message):
    voice_path = None
    response_audio_path = None
    
    if not message.voice:
        await message.answer("Пожалуйста, отправьте голосовое сообщение!")
        return
    
    try:
        # Отправляем статус "печатает..."
        await message.answer("🎤 Обрабатываю ваше голосовое сообщение...")
        
        # Скачиваем голосовое сообщение
        voice_file = await bot.get_file(message.voice.file_id)
        voice_path = os.path.join(TEMP_DIR, f"voice_{message.message_id}.ogg")
        await bot.download_file(voice_file.file_path, voice_path)
        
        # Транскрибируем голос в текст
        text = await openai_client.transcribe_audio(voice_path)
        await message.answer(f"🎯 Распознанный текст: {text}")
        
        # Получаем ответ от ассистента
        response = await openai_client.get_assistant_response(text)
        await message.answer(f"🤖 Ответ: {response}")
        
        # Преобразуем ответ в речь
        response_audio_path = os.path.join(TEMP_DIR, f"response_{message.message_id}.mp3")
        await openai_client.text_to_speech(response, response_audio_path)
        
        # Отправляем голосовое сообщение с ответом
        with open(response_audio_path, "rb") as audio:
            await message.answer_voice(
                voice=types.FSInputFile(response_audio_path),
                caption=response
            )
            
    except Exception as e:
        logging.error(f"Error processing voice message: {e}")
        await message.answer("😔 Произошла ошибка при обработке сообщения. Попробуйте еще раз.")
    
    finally:
        # Удаляем временные файлы
        for file_path in [voice_path, response_audio_path]:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)

async def send_voice_response(message: types.Message, text: str):
    """Send voice response using OpenAI TTS"""
    try:
        # Generate speech
        response = openai_client.audio.speech.create(
            model="tts-1",
            voice="alloy",
            input=text
        )
        
        # Save to temporary file
        temp_file = "temp_response.mp3"
        with open(temp_file, "wb") as f:
            f.write(response.content)
        
        # Send voice message
        with open(temp_file, "rb") as voice:
            await message.reply_voice(
                voice=types.InputFile(voice),
                caption=text
            )
        
        # Clean up
        os.remove(temp_file)
        
    except Exception as e:
        logging.error(f"Error sending voice response: {str(e)}")
        await message.reply("Извините, произошла ошибка при отправке голосового сообщения.")

async def main():
    # Запуск бота
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main()) 