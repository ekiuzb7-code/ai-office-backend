import os
import asyncio
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from crewai import Agent, Task, Crew
from langchain_google_genai import ChatGoogleGenerativeAI
import uvicorn

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# Websocket ulanishlarni saqlash
active_websockets = []

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_websockets.append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        active_websockets.remove(websocket)

async def broadcast_to_office(message: dict):
    for ws in active_websockets:
        await ws.send_text(json.dumps(message))

# Telegram Bot Qismi
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "SIZNING_TOKENINGIZ")
GEMINI_KEY = os.getenv("GOOGLE_API_KEY", "SIZNING_GEMINI_KALITINGIZ")

llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", google_api_key=GEMINI_KEY)

async def handle_telegram_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prompt = update.message.text
    await update.message.reply_text("🚀 Verceldagi saytga qarang, agentlar ishga tushdi!")

    # 1. Boss buyruq beradi
    await broadcast_to_office({"action": "chat", "character": "Boss", "text": f"Julia, yangi topshiriq: {prompt}"})
    await asyncio.sleep(2)

    # 2. Julia kofe ichishga ketadi
    await broadcast_to_office({"action": "move", "character": "Julia", "destination": "coffee_maker"})
    await asyncio.sleep(2)
    await broadcast_to_office({"action": "sprite", "character": "Julia", "image": "Julia_Drinking_Coffee.png"})

    # 3. Fonda AI kod yozadi
    def step_callback(step_out):
        asyncio.run_coroutine_threadsafe(
            broadcast_to_office({"action": "chat", "character": "Julia", "text": "Kod yozyapman..."}),
            asyncio.get_event_loop()
        )

    coder = Agent(
        role='Developer',
        goal='Kod yozish',
        backstory='Ismi Julia. U daho dasturchi.',
        llm=llm,
        step_callback=step_callback
    )
    task = Task(description=f"Shu vazifani Python'da yoz: {prompt}", expected_output="Faqat kod.", agent=coder)
    crew = Crew(agents=[coder], tasks=[task])
    result = crew.kickoff()

    # 4. Julia ishni tugatib qaytadi
    await broadcast_to_office({"action": "move", "character": "Julia", "destination": "desk"})
    await broadcast_to_office({"action": "sprite", "character": "Julia", "image": "Julia_PC.png"})
    await broadcast_to_office({"action": "code_result", "code": str(result)})

    await update.message.reply_text(f"✅ Kod tayyor:\n\n```python\n{result}\n```", parse_mode="Markdown")

def run_bot():
    bot_app = Application.builder().token(TELEGRAM_TOKEN).build()
    bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_telegram_msg))
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    bot_app.run_polling(close_loop=False)

@app.on_event("startup")
def start_background_bot():
    import threading
    threading.Thread(target=run_bot, daemon=True).start()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))