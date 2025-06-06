import os
from openai import AsyncOpenAI
from config import settings

class OpenAIClient:
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY.get_secret_value())
        self.assistant_id = None  # Будет установлено при создании ассистента

    async def create_assistant(self):
        """Создание ассистента OpenAI"""
        assistant = await self.client.beta.assistants.create(
            name="Voice Assistant",
            instructions="Ты - полезный ассистент, который отвечает на вопросы пользователя.",
            model="gpt-4-turbo-preview",
        )
        self.assistant_id = assistant.id
        return assistant

    async def transcribe_audio(self, audio_file_path: str) -> str:
        """Транскрибация аудио в текст с помощью Whisper"""
        with open(audio_file_path, "rb") as audio_file:
            transcript = await self.client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file
            )
        return transcript.text

    async def get_assistant_response(self, user_message: str) -> str:
        """Получение ответа от ассистента"""
        if not self.assistant_id:
            await self.create_assistant()

        # Создаем тред
        thread = await self.client.beta.threads.create()

        # Добавляем сообщение пользователя
        await self.client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=user_message
        )

        # Запускаем выполнение
        run = await self.client.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=self.assistant_id
        )

        # Ждем завершения выполнения
        while True:
            run_status = await self.client.beta.threads.runs.retrieve(
                thread_id=thread.id,
                run_id=run.id
            )
            if run_status.status == "completed":
                break
            elif run_status.status in ["failed", "cancelled", "expired"]:
                raise Exception(f"Run failed with status: {run_status.status}")
            await asyncio.sleep(1)

        # Получаем ответ
        messages = await self.client.beta.threads.messages.list(
            thread_id=thread.id
        )
        
        # Возвращаем последнее сообщение от ассистента
        for message in messages.data:
            if message.role == "assistant":
                return message.content[0].text.value

    async def text_to_speech(self, text: str, output_path: str):
        """Преобразование текста в речь"""
        response = await self.client.audio.speech.create(
            model="tts-1",
            voice="alloy",
            input=text
        )
        
        # Сохраняем аудио файл
        response.stream_to_file(output_path) 