# Sistem Manajemen Gaji Karyawan (GajiPro)

Sistem manajemen gaji karyawan profesional dengan fitur lengkap untuk mengelola gaji, hutang, dan slip gaji karyawan.

## Fitur Utama

### 1. Sistem Autentikasi
- Login dengan session yang bertahan lama
- Register untuk karyawan baru (otomatis role: KARYAWAN)
- Role-based access control (BOS dan KARYAWAN)
- Password hashing dengan Werkzeug
- Flash message notifikasi

**Akun Default BOS:**
- Username: `bos`
- Password: `bos123`

### 2. Dashboard Karyawan
- Total gaji kotor
- Total hutang aktif
- Total bonus
- Total gaji bersih
- Leaderboard gaji semua karyawan
- Riwayat input hasil kerja

### 3. Input Hasil Kerja
- Input jumlah hasil kerja
- Pilihan ukuran: kecil, besar, sepeda, sepeda mini, jumbo
- Pilihan jenis: semi, tipis (sepeda & sepeda mini tanpa jenis)
- Perhitungan otomatis jumlah x harga
- Status awal: PENDING
- BOS harus approve untuk masuk ke total gaji

**Harga Default:**
- Besar Tipis: Rp 33.000
- Besar Semi: Rp 37.000
- Kecil Tipis: Rp 27.000
- Kecil Semi: Rp 30.000
- Sepeda: Rp 25.000
- Sepeda Mini: Rp 22.000
- Jumbo Tipis: Rp 37.000
- Jumbo Semi: Rp 40.000

### 4. Sistem Bon / Hutang
- Ditambahkan oleh BOS
- Field: Nominal, Keterangan, Tanggal, Status (aktif/lunas)
- Perhitungan: Total Gaji Bersih = Total Kerja + Bonus − Hutang Aktif

### 5. Slip Gaji PDF
- Generate slip gaji per periode
- Isi: Nama, Periode, Total kerja, Bonus, Hutang, Potongan, Gaji bersih
- Download PDF
- Simpan riwayat slip

### 6. Dashboard BOS
- Grafik statistik gaji (Chart.js)
- Total gaji semua karyawan
- Total hutang semua karyawan
- Total uang yang harus dibayar
- Approve/reject kerja
- Edit harga
- Tambah ukuran & jenis baru
- Lihat semua riwayat kerja
- Lihat semua hutang
- Reset gaji per periode
- Riwayat reset

### 7. PWA (Progressive Web App)
- Manifest.json
- Service Worker
- Bisa di-install ke HP Android
- Icon aplikasi
- Splash screen
- Cache untuk offline mode dasar

### 8. Profile Management
- Edit foto profil
- Edit username
- Edit password
- Edit nomor WhatsApp
- Total gaji bersih dan bon
- Riwayat input hasil kerja dan reset gaji

## Teknologi

- **Backend:** Flask (Python)
- **Database:** SQLite3
- **Frontend:** HTML, CSS, Bootstrap 5
- **Authentication:** Flask-Login
- **Security:** Werkzeug (password hashing), CSRF Protection
- **Charts:** Chart.js
- **PDF:** fpdf2

## Instalasi

### 1. Clone Repository
```bash
cd gaji-karyawan
```

### 2. Buat Virtual Environment
```bash
python -m venv venv
```

### 3. Aktifkan Virtual Environment
**Windows:**
```bash
venv\Scripts\activate
```

**Linux/Mac:**
```bash
source venv/bin/activate
```

### 4. Install Dependencies
```bash
pip install -r requirements.txt
```

### 5. Inisialisasi Database
```bash
python -c "from app import init_db; init_db()"
```

### 6. Jalankan Aplikasi
```bash
python app.py
```

Aplikasi akan berjalan di `http://localhost:5000`

## Struktur Folder

```
gaji-karyawan/
├── app.py                  # Main Flask application
├── schema.sql              # Database schema
├── requirements.txt        # Python dependencies
├── .env                    # Environment variables
├── README.md               # This file
├── instance/               # Database folder
│   └── gaji_karyawan.db    # SQLite database
├── static/                 # Static assets
│   ├── css/                # CSS files
│   ├── js/                 # JavaScript files
│   ├── images/             # Images
│   ├── icons/              # PWA icons
│   ├── uploads/            # User uploads
│   │   └── profile_photos/ # Profile photos
│   ├── manifest.json       # PWA manifest
│   └── sw.js               # Service Worker
└── templates/              # HTML templates
    ├── auth/               # Authentication templates
    ├── dashboard/          # Dashboard templates
    ├── bos/                # BOS panel templates
    └── errors/             # Error pages
```

## Keamanan

- Password hashing dengan Werkzeug
- CSRF protection dengan Flask-WTF
- Role-based access control
- Validasi form
- Proteksi upload file (hanya gambar)
- Pagination dan search pada tabel

## Lisensi

MIT License

## Kontribusi

Silakan buat pull request atau issue untuk kontribusi.

## Dukungan

Untuk pertanyaan atau bantuan, silakan hubungi admin.
