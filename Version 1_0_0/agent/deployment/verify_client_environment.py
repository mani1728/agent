"""
Client Environment Verification & Smoke Test Script
اجرای بررسی‌های پیش‌پرواز (Pre-flight checks) روی سیستم کلاینت ویندوزی.
"""

import os
import sys
import json
import sqlite3
from pathlib import Path


def test_config_exists():
    cfg_path = Path("config.json")
    if not cfg_path.exists():
        print("[FAIL] فایل config.json یافت نشد. لطفاً config.example.json را کپی و تنظیم کنید.")
        return False
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        print(f"[PASS] فایل config.json معتبر است (Application: {data.get('app', {}).get('name', 'N/A')}).")
        return True
    except Exception as e:
        print(f"[FAIL] خطای Parse در config.json: {e}")
        return False


def test_file_permissions():
    test_file = Path(".write_test.tmp")
    try:
        test_file.write_text("ok", encoding="utf-8")
        test_file.unlink()
        print("[PASS] مجوز خواندن/نوشتن در دایرکتوری جاری تأیید شد.")
        return True
    except Exception as e:
        print(f"[FAIL] عدم دسترسی نوشتن در دایرکتوری جاری: {e}")
        return False


def test_sqlite_wal():
    db_path = Path(".sqlite_test.db")
    try:
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("CREATE TABLE test (id INT);")
        conn.execute("INSERT INTO test VALUES (1);")
        conn.commit()
        conn.close()
        for p in [db_path, Path(f"{db_path}-wal"), Path(f"{db_path}-shm")]:
            if p.exists():
                p.unlink()
        print("[PASS] موتور SQLite و مد WAL با موفقیت تست شدند.")
        return True
    except Exception as e:
        print(f"[FAIL] خطای تست SQLite WAL: {e}")
        return False


def main():
    print("=" * 60)
    print("       Kafka Agent Client Verification Diagnostic")
    print("=" * 60)

    results = [
        test_file_permissions(),
        test_config_exists(),
        test_sqlite_wal(),
    ]

    print("-" * 60)
    if all(results):
        print("[SUCCESS] تمام تست‌های پایه کلاینت پاس شدند. آماده اجرای KafkaAgent.exe.")
        sys.exit(0)
    else:
        print("[ERROR] برخی پیش‌نیازها رعایت نشده‌اند. لطفاً موارد بالا را اصلاح کنید.")
        sys.exit(1)


if __name__ == "__main__":
    main()
