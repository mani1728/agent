# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

block_cipher = None

# جمع‌آوری تمام ساب‌ماژول‌های پروژه agent
agent_hidden_imports = collect_submodules('agent')

# ماژول‌های پنهان و C-Extensions بحرانی
hidden_imports = list(set(agent_hidden_imports + [
    'sqlite3',
    'json',
    'hashlib',
    'hmac',
    'threading',
    'confluent_kafka',
    'MetaTrader5',
    'agent.infrastructure.config_manager',
    'agent.transport.kafka_transport',
    'agent.transport.factory',
    'agent.reliability.idempotency',
    'agent.reliability.circuit_breaker',
    'agent.reliability.retry',
    'agent.reliability.backoff',
    'agent.core.worker',
    'agent.core.command_executor',
    'agent.core.dispatcher',
]))

# جمع‌آوری فایل‌های جانبی در صورت نیاز
datas = [
    ('agent/config.example.json', '.'),
]

a = Analysis(
    ['agent/main.py'],
    pathex=[os.path.abspath('.')],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'unittest', 'pytest', 'test'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='KafkaAgent',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # جهت پایداری DLLهای بانکی و C-bindings خاموش است
    console=True,  # برای مشاهده لاگ‌های استاندارد
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='KafkaAgent',
)
