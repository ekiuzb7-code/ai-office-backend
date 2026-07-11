import os
import asyncio
import json
import zipfile
import tempfile
import re
from pathlib import Path
from dotenv import load_dotenv

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes
from crewai import Agent, Task, Crew, Process
from langchain_google_genai import ChatGoogleGenerativeAI
import uvicorn

load_dotenv()

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

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
    for ws in list(active_websockets):
        try:
            await ws.send_text(json.dumps(message))
        except:
            active_websockets.remove(ws)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "SIZNING_TOKENINGIZ")
GEMINI_KEY = os.getenv("GOOGLE_API_KEY", "SIZNING_GEMINI_KALITINGIZ")

llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", google_api_key=GEMINI_KEY)

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚀 Salom! Antigravity AI Coding Factory'ga xush kelibsiz.\nMenga qanday dastur yoki loyiha kerakligini yozing (Masalan: 'Menga oddiy kalkulyator yaratib ber').")

async def handle_telegram_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prompt = update.message.text
    await update.message.reply_text("🚀 Topshiriq qabul qilindi! Agentlar jamoasi ishga tushdi, Verceldagi saytingizni kuzating...")

    await broadcast_to_office({"action": "chat", "character": "boss", "text": f"Jamoa, yangi topshiriq keldi: {prompt}"})
    await asyncio.sleep(2)

    loop = asyncio.get_running_loop()

    def make_step_callback(character_name, action_text):
        def callback(step_out):
            asyncio.run_coroutine_threadsafe(
                broadcast_to_office({"action": "chat", "character": character_name, "text": action_text}),
                loop
            )
        return callback

    architect = Agent(
        role='Lead Software & Cloud Solutions Architect',
        goal='Optimal texnologiyalar va fayllar iyerarxiyasini yaratish.',
        backstory="Siz dunyodagi eng kuchli dasturiy ta'minot arxitektorisiz.",
        llm=llm,
        step_callback=make_step_callback("architect", "Arxitektura o'ylanmoqda...")
    )
    
    developer = Agent(
        role='Universal Senior Full-Stack Developer',
        goal='Tizim Arxitektori bergan reja asosida barcha kodlarni to\'liq yozish.',
        backstory='Siz barcha dasturlash tillarini eng oliy darajada biladigan daho dasturchisiz.',
        llm=llm,
        step_callback=make_step_callback("developer", "Kodni yozyapman...")
    )

    qa_reviewer = Agent(
        role='Lead Quality Assurance Engineer & Cyber Security Auditor',
        goal='Yozilgan kodlarni tekshirish va tasdiqlash.',
        backstory='Siz kodlarni xavfsizlik va mantiqiy jihatdan tekshiruvchi qattiqqo\'l nazoratchisiz.',
        llm=llm,
        step_callback=make_step_callback("qa", "Xatoliklarni tekshiryapman...")
    )

    task_architect = Task(
        description=f"Quyidagi so'rov bo'yicha eng zo'r texnologiyalar yordamida loyiha iyerarxiyasini (Folder Structure) tuzing: {prompt}",
        expected_output="Loyiha iyerarxiyasi, tanlangan texnologiyalar.",
        agent=architect
    )

    task_developer = Task(
        description="Arxitektor bergan fayllar daraxti (Folder Structure) ga qarab, har bir fayl uchun to'liq kodlarni yozib chiqing. \nShartlar:\n1. Hech qanday qisqartmalar qilmang!\n2. Har bir fayl kodini aynan mana shu teglarga o'rang:\n[START_FILE: papka_nomi/fayl_nomi.kengaytma]\n// Kod...\n[END_FILE: papka_nomi/fayl_nomi.kengaytma]",
        expected_output="Barcha kodlarning to'liq ro'yxati (START_FILE va END_FILE teglari bilan).",
        agent=developer
    )

    task_qa = Task(
        description="Dasturchi yozgan kodlarni tahlil qiling. Xavfsizlik, Mantiq, Sintaksisni tekshiring. \nAgar hammasi to'g'ri bo'lsa 'STATUS: APPROVED' yozuvini qo'shing va teglarni saqlagan holda yakuniy kodni taqdim eting.",
        expected_output="Tasdiqlangan yakuniy kod oqimi.",
        agent=qa_reviewer
    )

    crew = Crew(
        agents=[architect, developer, qa_reviewer],
        tasks=[task_architect, task_developer, task_qa],
        process=Process.sequential
    )

    # CrewAI is blocking, so run it in a thread
    result = await asyncio.to_thread(crew.kickoff)
    result_text = str(result)

    await broadcast_to_office({"action": "chat", "character": "boss", "text": "Ajoyib ish bo'ldi jamoa! Loyiha mijozga jo'natilmoqda."})
    await broadcast_to_office({"action": "code_result", "code": result_text})
    
    with tempfile.TemporaryDirectory() as temp_dir:
        files_created = False
        pattern = r"\[START_FILE:\s*(.+?)\](.*?)\[END_FILE:\s*\1\]"
        matches = re.finditer(pattern, result_text, re.DOTALL)
        
        for match in matches:
            filepath = match.group(1).strip()
            content = match.group(2).strip()
            
            full_path = Path(temp_dir) / filepath
            full_path.parent.mkdir(parents=True, exist_ok=True)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)
            files_created = True
        
        if files_created:
            zip_path = Path(temp_dir) / "project.zip"
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, _, files in os.walk(temp_dir):
                    for file in files:
                        if file != "project.zip":
                            abs_file = os.path.join(root, file)
                            rel_file = os.path.relpath(abs_file, temp_dir)
                            zipf.write(abs_file, rel_file)
            
            with open(zip_path, 'rb') as f:
                await update.message.reply_document(document=f, filename="project.zip", caption="✅ Loyihangiz arxitektura, yozish va QA tekshiruvidan muvaffaqiyatli o'tib, to'liq fayllar shaklida tayyorlandi!")
        else:
            await update.message.reply_text(f"✅ Kod tayyor, lekin fayl teglari topilmadi. Javob:\n\n```\n{result_text[:4000]}\n```", parse_mode="Markdown")

bot_app = Application.builder().token(TELEGRAM_TOKEN).build()
bot_app.add_handler(CommandHandler("start", start_cmd))
bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_telegram_msg))

@app.on_event("startup")
async def startup_event():
    await bot_app.initialize()
    await bot_app.start()
    await bot_app.updater.start_polling()

@app.on_event("shutdown")
async def shutdown_event():
    await bot_app.updater.stop()
    await bot_app.stop()
    await bot_app.shutdown()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))