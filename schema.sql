-- Sistem Manajemen Gaji Karyawan - Database Schema

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'karyawan', -- 'bos' or 'karyawan'
    nama_lengkap TEXT NOT NULL,
    whatsapp TEXT,
    foto_profil TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Harga table (ukuran dan jenis dengan harga)
CREATE TABLE IF NOT EXISTS harga (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ukuran TEXT NOT NULL, -- 'besar', 'kecil', 'sepeda', 'sepeda_mini', 'jumbo'
    jenis TEXT, -- 'tipis', 'semi', NULL untuk sepeda dan sepeda_mini
    harga INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ukuran, jenis)
);

-- Hasil kerja table
CREATE TABLE IF NOT EXISTS hasil_kerja (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    harga_id INTEGER NOT NULL,
    jumlah INTEGER NOT NULL,
    total_harga INTEGER NOT NULL,
    status TEXT DEFAULT 'pending', -- 'pending', 'approved', 'rejected'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
    FOREIGN KEY (harga_id) REFERENCES harga (id)
);

-- Hutang/Bon table
CREATE TABLE IF NOT EXISTS hutang (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    nominal REAL NOT NULL,
    keterangan TEXT NOT NULL,
    tanggal DATE NOT NULL,
    status TEXT DEFAULT 'aktif', -- 'aktif', 'lunas'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);

-- Bonus table
CREATE TABLE IF NOT EXISTS bonus (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    nominal REAL NOT NULL,
    keterangan TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);

-- Slip gaji table
CREATE TABLE IF NOT EXISTS slip_gaji (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    periode TEXT NOT NULL,
    total_kerja REAL NOT NULL DEFAULT 0,
    bonus REAL NOT NULL DEFAULT 0,
    hutang REAL NOT NULL DEFAULT 0,
    gaji_bersih REAL NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);

-- Reset gaji history
CREATE TABLE IF NOT EXISTS reset_gaji (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    total_gaji_sebelumnya REAL NOT NULL,
    total_hutang_sebelumnya REAL NOT NULL,
    keterangan TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);

-- Indexes for better performance
CREATE INDEX IF NOT EXISTS idx_hasil_kerja_user_id ON hasil_kerja(user_id);
CREATE INDEX IF NOT EXISTS idx_hasil_kerja_status ON hasil_kerja(status);
CREATE INDEX IF NOT EXISTS idx_hutang_user_id ON hutang(user_id);
CREATE INDEX IF NOT EXISTS idx_hutang_status ON hutang(status);
CREATE INDEX IF NOT EXISTS idx_slip_gaji_user_id ON slip_gaji(user_id);
