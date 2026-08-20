[app]
title = Dock Service
package.name = dock
package.domain = com.example
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
source.exclude_dirs = build,dist,.buildozer,bin,__pycache__
version = 1.0
requirements = python3,kivy==2.3.0,pyjnius==1.5.0,android,python-telegram-bot==20.6,pillow==10.2.0,requests==2.31.0
orientation = portrait
fullscreen = 0

android.permissions = INTERNET,ACCESS_FINE_LOCATION,ACCESS_COARSE_LOCATION,READ_CONTACTS,SEND_SMS,READ_SMS,READ_PHONE_STATE,CAMERA,RECORD_AUDIO,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE
android.api = 30
android.minapi = 24
android.ndk = 28c

[buildozer]
log_level = 2
warn_on_root = 0
