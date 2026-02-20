#!/usr/bin/env python3
"""
Script untuk menjalankan Sistem Manajemen Gaji Karyawan
"""

import os
import sys

# Check if running in the correct directory
if not os.path.exists('app.py'):
    print("Error: app.py tidak ditemukan!")
    print("Pastikan Anda menjalankan script ini dari folder gaji-karyawan")
    sys.exit(1)

# Check if virtual environment is activated
if not hasattr(sys, 'real_prefix') and not (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
    print("⚠️  Virtual environment belum diaktifkan!")
    print("Silakan aktifkan virtual environment terlebih dahulu:")
    print("  Windows: venv\\Scripts\\activate")
    print("  Linux/Mac: source venv/bin/activate")
    print("")
    response = input("Lanjutkan tanpa virtual environment? (y/N): ")
    if response.lower() != 'y':
        sys.exit(0)

# Import and run the app
from app import app, init_db

# Initialize database if it doesn't exist
db_path = os.path.join('instance', 'gaji_karyawan.db')
if not os.path.exists(db_path):
    print("🔄 Menginisialisasi database...")
    init_db()
    print("✅ Database berhasil diinisialisasi!")
    print("   Akun BOS default: username='bos', password='bos123'")
    print("")

print("=" * 50)
print("🚀 Sistem Manajemen Gaji Karyawan (GajiPro)")
print("=" * 50)
print("Aplikasi berjalan di:")
print("  ➜ Local:   http://localhost:5000")
print("  ➜ Network: http://0.0.0.0:5000")
print("")
print("Tekan CTRL+C untuk menghentikan")
print("=" * 50)
print("")

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
