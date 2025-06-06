import asyncio
import logging
import os
import signal
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message, InputFile
from config import settings
from openai_client import OpenAIClient

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация бота и диспетчера
bot = Bot(token=settings.BOT_TOKEN.get_secret_value())
dp = Dispatcher()

# Инициализация OpenAI клиента
openai_client = OpenAIClient()

# Создаем директорию для временных файлов
TEMP_DIR = "temp"
os.makedirs(TEMP_DIR, exist_ok=True)

# Флаг для отслеживания состояния бота
is_running = False

async def on_shutdown():
    """Обработчик завершения работы бота"""
    global is_running
    is_running = False
    logger.info("Bot is shutting down...")
    await bot.session.close()

async def main():
    """Основная функция запуска бота"""
    global is_running
    
    if is_running:
        logger.warning("Bot is already running!")
        return
        
    is_running = True
    
    # Регистрируем обработчик завершения
    dp.shutdown.register(on_shutdown)
    
    try:
        # Запуск бота
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    except Exception as e:
        logger.error(f"Error while polling: {e}")
    finally:
        is_running = False

# Обработчик команды /start
@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "👋 Привет! Я голосовой AI-бот.\n"
        "Отправь мне голосовое сообщение, и я отвечу на него!"
    )

# Обработчик голосовых сообщений
@dp.message()
async def handle_voice(message: types.Message):
    """Handle voice messages"""
    try:
        # Download voice message
        file_id = message.voice.file_id
        file = await bot.get_file(file_id)
        file_path = file.file_path
        
        # Create temp directory if it doesn't exist
        os.makedirs("temp", exist_ok=True)
        
        # Download file
        local_path = f"temp/{file_id}.ogg"
        await bot.download_file(file_path, local_path)
        
        # Convert to text using Whisper
        text = await openai_client.transcribe_audio(local_path)
        logger.info(f"Transcribed text: {text}")
        
        # Get response from OpenAI
        response = await openai_client.get_assistant_response(text)
        logger.info(f"Assistant response: {response}")
        
        # Convert response to speech
        response_audio_path = f"temp/response_{file_id}.mp3"
        await openai_client.text_to_speech(response, response_audio_path)
        
        # Отправляем голосовое сообщение с ответом
        with open(response_audio_path, "rb") as audio:
            # Ограничиваем длину описания до 1024 символов
            caption = response[:1024] if len(response) > 1024 else response
            await message.answer_voice(
                voice=types.FSInputFile(response_audio_path),
                caption=caption
            )
            
    except Exception as e:
        logger.error(f"Error processing voice message: {e}")
        await message.answer("Произошла ошибка при обработке голосового сообщения. Попробуйте еще раз.")
    finally:
        # Cleanup
        if os.path.exists(local_path):
            os.remove(local_path)
        if 'response_audio_path' in locals() and os.path.exists(response_audio_path):
            os.remove(response_audio_path)

async def send_voice_message(message: types.Message, text: str, voice_path: str):
    """Send voice message with text caption"""
    try:
        # Limit caption length to 1024 characters (Telegram's limit)
        caption = text[:1024] if len(text) > 1024 else text
        
        with open(voice_path, 'rb') as voice:
            await message.answer_voice(
                voice=types.FSInputFile(voice_path),
                caption=caption
            )
    except Exception as e:
        logger.error(f"Error sending voice message: {e}")
        await message.answer("Виникла помилка при відправці голосового повідомлення. Спробуйте ще раз.")

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

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}") 