import os
import sqlite3
from datetime import datetime, timedelta
from functools import wraps
from io import BytesIO

from dotenv import load_dotenv
from flask import (Flask, flash, g, jsonify, make_response, redirect,
                   render_template, request, send_file, session, url_for)
from flask_login import LoginManager, current_user, login_required, login_user, logout_user
from flask_wtf import FlaskForm, CSRFProtect
from flask_wtf.file import FileAllowed, FileField
from fpdf import FPDF
from PIL import Image
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from wtforms import (DateField, FloatField, IntegerField, PasswordField,
                     SelectField, StringField, SubmitField, TextAreaField)
from wtforms.validators import DataRequired, EqualTo, Length, NumberRange, Optional

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'gaji-karyawan-secret-key-2024')
app.config['DATABASE'] = os.path.join(app.root_path, 'instance', 'gaji_karyawan.db')
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'uploads', 'profile_photos')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

csrf = CSRFProtect(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth_login'
login_manager.login_message = 'Silakan login terlebih dahulu.'
login_manager.login_message_category = 'warning'

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# ==================== DATABASE ====================

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(app.config['DATABASE'])
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(error):
    if 'db' in g:
        g.db.close()

def init_db():
    with app.app_context():
        db = get_db()
        with app.open_resource('schema.sql', mode='r') as f:
            db.cursor().executescript(f.read())
        db.commit()
        
        # Create default BOS account
        cursor = db.cursor()
        cursor.execute('SELECT * FROM users WHERE username = ?', ('bos',))
        if not cursor.fetchone():
            cursor.execute('''
                INSERT INTO users (username, password_hash, role, nama_lengkap, created_at)
                VALUES (?, ?, ?, ?, ?)
            ''', ('bos', generate_password_hash('bos123'), 'bos', 'Bos Utama', datetime.now()))
            db.commit()
            print("Default BOS account created: username='bos', password='bos123'")
        
        # Insert default harga if empty
        cursor.execute('SELECT COUNT(*) FROM harga')
        if cursor.fetchone()[0] == 0:
            default_harga = [
                ('besar', 'tipis', 33000),
                ('besar', 'semi', 37000),
                ('kecil', 'tipis', 27000),
                ('kecil', 'semi', 30000),
                ('sepeda', None, 25000),
                ('sepeda_mini', None, 22000),
                ('jumbo', 'tipis', 37000),
                ('jumbo', 'semi', 40000),
            ]
            cursor.executemany('''
                INSERT INTO harga (ukuran, jenis, harga)
                VALUES (?, ?, ?)
            ''', default_harga)
            db.commit()

# ==================== USER MODEL ====================

class User:
    def __init__(self, id, username, role, nama_lengkap, whatsapp=None, foto_profil=None):
        self.id = id
        self.username = username
        self.role = role
        self.nama_lengkap = nama_lengkap
        self.whatsapp = whatsapp
        self.foto_profil = foto_profil
    
    def is_authenticated(self):
        return True
    
    def is_active(self):
        return True
    
    def is_anonymous(self):
        return False
    
    def get_id(self):
        return str(self.id)
    
    def is_bos(self):
        return self.role == 'bos'

@login_manager.user_loader
def load_user(user_id):
    db = get_db()
    user = db.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    if user:
        return User(user['id'], user['username'], user['role'], 
                   user['nama_lengkap'], user['whatsapp'], user['foto_profil'])
    return None

# ==================== FORMS ====================

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class RegisterForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=50)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Konfirmasi Password', 
                                     validators=[DataRequired(), EqualTo('password')])
    nama_lengkap = StringField('Nama Lengkap', validators=[DataRequired()])
    whatsapp = StringField('Nomor WhatsApp', validators=[Optional()])
    submit = SubmitField('Daftar')

class HasilKerjaForm(FlaskForm):
    jumlah = IntegerField('Jumlah', validators=[DataRequired(), NumberRange(min=1)])
    ukuran = SelectField('Ukuran', validators=[DataRequired()], coerce=str)
    jenis = SelectField('Jenis', validators=[Optional()], coerce=str)
    submit = SubmitField('Simpan')

class HutangForm(FlaskForm):
    user_id = SelectField('Karyawan', validators=[DataRequired()], coerce=int)
    nominal = FloatField('Nominal', validators=[DataRequired(), NumberRange(min=0)])
    keterangan = TextAreaField('Keterangan', validators=[DataRequired()])
    tanggal = DateField('Tanggal', validators=[DataRequired()], default=datetime.now)
    submit = SubmitField('Simpan')

class HargaForm(FlaskForm):
    ukuran = StringField('Ukuran', validators=[DataRequired()])
    jenis = StringField('Jenis', validators=[Optional()])
    harga = IntegerField('Harga', validators=[DataRequired(), NumberRange(min=0)])
    submit = SubmitField('Simpan')

class ProfileForm(FlaskForm):
    nama_lengkap = StringField('Nama Lengkap', validators=[DataRequired()])
    username = StringField('Username', validators=[DataRequired()])
    whatsapp = StringField('Nomor WhatsApp', validators=[Optional()])
    foto_profil = FileField('Foto Profil', validators=[FileAllowed(['jpg', 'jpeg', 'png'], 'Images only!')])
    submit = SubmitField('Simpan')

class PasswordForm(FlaskForm):
    current_password = PasswordField('Password Saat Ini', validators=[DataRequired()])
    new_password = PasswordField('Password Baru', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Konfirmasi Password Baru', 
                                     validators=[DataRequired(), EqualTo('new_password')])
    submit = SubmitField('Ubah Password')

class BonusForm(FlaskForm):
    user_id = SelectField('Karyawan', validators=[DataRequired()], coerce=int)
    nominal = FloatField('Nominal Bonus', validators=[DataRequired(), NumberRange(min=0)])
    keterangan = TextAreaField('Keterangan', validators=[DataRequired()])
    submit = SubmitField('Tambah Bonus')

# ==================== UPLOADED FILES ROUTE ====================

@app.route('/uploads/profile_photos/<filename>')
def uploaded_file(filename):
    """Serve uploaded profile photos"""
    return send_file(os.path.join(app.config['UPLOAD_FOLDER'], filename))

# ==================== HELPER FUNCTIONS ====================

def bos_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_bos():
            flash('Akses ditolak. Halaman ini hanya untuk BOS.', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def get_harga(ukuran, jenis):
    db = get_db()
    if jenis:
        harga = db.execute('''
            SELECT harga FROM harga WHERE ukuran = ? AND jenis = ?
        ''', (ukuran, jenis)).fetchone()
    else:
        harga = db.execute('''
            SELECT harga FROM harga WHERE ukuran = ? AND jenis IS NULL
        ''', (ukuran,)).fetchone()
    return harga['harga'] if harga else 0

def get_total_gaji_kotor(user_id):
    db = get_db()
    result = db.execute('''
        SELECT COALESCE(SUM(total_harga), 0) as total 
        FROM hasil_kerja 
        WHERE user_id = ? AND status = 'approved'
    ''', (user_id,)).fetchone()
    return result['total'] or 0

def get_total_hutang_aktif(user_id):
    db = get_db()
    result = db.execute('''
        SELECT COALESCE(SUM(nominal), 0) as total 
        FROM hutang 
        WHERE user_id = ? AND status = 'aktif'
    ''', (user_id,)).fetchone()
    return result['total'] or 0

def get_total_bonus(user_id):
    db = get_db()
    result = db.execute('''
        SELECT COALESCE(SUM(nominal), 0) as total 
        FROM bonus 
        WHERE user_id = ?
    ''', (user_id,)).fetchone()
    return result['total'] or 0

def get_gaji_bersih(user_id):
    return get_total_gaji_kotor(user_id) + get_total_bonus(user_id) - get_total_hutang_aktif(user_id)

def get_ukuran_choices():
    db = get_db()
    ukuran_list = db.execute('''
        SELECT DISTINCT ukuran FROM harga ORDER BY ukuran
    ''').fetchall()
    return [(u['ukuran'], u['ukuran'].replace('_', ' ').title()) for u in ukuran_list]

def get_jenis_choices(ukuran=None):
    db = get_db()
    if ukuran:
        jenis_list = db.execute('''
            SELECT DISTINCT jenis FROM harga WHERE ukuran = ? AND jenis IS NOT NULL ORDER BY jenis
        ''', (ukuran,)).fetchall()
    else:
        jenis_list = db.execute('''
            SELECT DISTINCT jenis FROM harga WHERE jenis IS NOT NULL ORDER BY jenis
        ''').fetchall()
    return [(j['jenis'], j['jenis'].title()) for j in jenis_list if j['jenis']]

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg'}

# ==================== AUTH ROUTES ====================

@app.route('/login', methods=['GET', 'POST'])
def auth_login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    form = LoginForm()
    if form.validate_on_submit():
        db = get_db()
        user = db.execute('SELECT * FROM users WHERE username = ?', (form.username.data,)).fetchone()
        
        if user and check_password_hash(user['password_hash'], form.password.data):
            user_obj = User(user['id'], user['username'], user['role'], 
                          user['nama_lengkap'], user['whatsapp'], user['foto_profil'])
            login_user(user_obj, remember=True, duration=timedelta(days=30))
            flash(f'Selamat datang, {user["nama_lengkap"]}!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page if next_page else url_for('dashboard'))
        else:
            flash('Username atau password salah.', 'danger')
    
    return render_template('auth/login.html', form=form)

@app.route('/register', methods=['GET', 'POST'])
def auth_register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    form = RegisterForm()
    if form.validate_on_submit():
        db = get_db()
        
        # Check if username exists
        existing = db.execute('SELECT id FROM users WHERE username = ?', (form.username.data,)).fetchone()
        if existing:
            flash('Username sudah digunakan.', 'danger')
            return render_template('auth/register.html', form=form)
        
        # Create new user with role 'karyawan'
        db.execute('''
            INSERT INTO users (username, password_hash, role, nama_lengkap, whatsapp, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (form.username.data, generate_password_hash(form.password.data), 
              'karyawan', form.nama_lengkap.data, form.whatsapp.data, datetime.now()))
        db.commit()
        
        flash('Registrasi berhasil! Silakan login.', 'success')
        return redirect(url_for('auth_login'))
    
    return render_template('auth/register.html', form=form)

@app.route('/logout')
@login_required
def auth_logout():
    logout_user()
    flash('Anda telah logout.', 'info')
    return redirect(url_for('auth_login'))

# ==================== DASHBOARD ROUTES ====================

@app.route('/')
@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.is_bos():
        return redirect(url_for('bos_dashboard'))
    
    db = get_db()
    
    # Get statistics
    total_gaji_kotor = get_total_gaji_kotor(current_user.id)
    total_hutang = get_total_hutang_aktif(current_user.id)
    total_bonus = get_total_bonus(current_user.id)
    gaji_bersih = total_gaji_kotor + total_bonus - total_hutang
    
    # Get leaderboard
    leaderboard = db.execute('''
        SELECT u.id, u.nama_lengkap, u.foto_profil,
               COALESCE(SUM(h.total_harga), 0) as total_gaji
        FROM users u
        LEFT JOIN hasil_kerja h ON u.id = h.user_id AND h.status = 'approved'
        WHERE u.role = 'karyawan'
        GROUP BY u.id
        ORDER BY total_gaji DESC
        LIMIT 10
    ''').fetchall()
    
    # Get recent hasil kerja
    recent_kerja = db.execute('''
        SELECT hk.*, h.ukuran as ukuran_nama, h.jenis as jenis_nama
        FROM hasil_kerja hk
        LEFT JOIN harga h ON hk.harga_id = h.id
        WHERE hk.user_id = ?
        ORDER BY hk.created_at DESC
        LIMIT 5
    ''', (current_user.id,)).fetchall()
    
    return render_template('dashboard/karyawan.html',
                         total_gaji_kotor=total_gaji_kotor,
                         total_hutang=total_hutang,
                         total_bonus=total_bonus,
                         gaji_bersih=gaji_bersih,
                         leaderboard=leaderboard,
                         recent_kerja=recent_kerja)

# ==================== HASIL KERJA ROUTES ====================

@app.route('/hasil-kerja', methods=['GET', 'POST'])
@login_required
def hasil_kerja():
    if current_user.is_bos():
        return redirect(url_for('bos_hasil_kerja'))
    
    form = HasilKerjaForm()
    form.ukuran.choices = get_ukuran_choices()
    form.jenis.choices = [('', '-- Tanpa Jenis --')] + get_jenis_choices()
    
    db = get_db()
    
    if form.validate_on_submit():
        ukuran = form.ukuran.data
        jenis = form.jenis.data if form.jenis.data else None
        jumlah = form.jumlah.data
        
        # Get harga_id
        if jenis:
            harga_row = db.execute('''
                SELECT id, harga FROM harga WHERE ukuran = ? AND jenis = ?
            ''', (ukuran, jenis)).fetchone()
        else:
            harga_row = db.execute('''
                SELECT id, harga FROM harga WHERE ukuran = ? AND jenis IS NULL
            ''', (ukuran,)).fetchone()
        
        if harga_row:
            total_harga = jumlah * harga_row['harga']
            db.execute('''
                INSERT INTO hasil_kerja (user_id, harga_id, jumlah, total_harga, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (current_user.id, harga_row['id'], jumlah, total_harga, 'pending', datetime.now()))
            db.commit()
            flash('Hasil kerja berhasil disimpan. Menunggu approval BOS.', 'success')
            return redirect(url_for('hasil_kerja'))
        else:
            flash('Harga tidak ditemukan.', 'danger')
    
    # Get all hasil kerja for this user
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    total = db.execute('SELECT COUNT(*) FROM hasil_kerja WHERE user_id = ?', 
                      (current_user.id,)).fetchone()[0]
    
    hasil_kerja_list = db.execute('''
        SELECT hk.*, h.ukuran, h.jenis, h.harga as harga_satuan
        FROM hasil_kerja hk
        JOIN harga h ON hk.harga_id = h.id
        WHERE hk.user_id = ?
        ORDER BY hk.created_at DESC
        LIMIT ? OFFSET ?
    ''', (current_user.id, per_page, (page - 1) * per_page)).fetchall()
    
    total_pages = (total + per_page - 1) // per_page
    
    return render_template('dashboard/hasil_kerja.html', form=form, 
                         hasil_kerja_list=hasil_kerja_list, 
                         page=page, total_pages=total_pages, total=total)

@app.route('/api/get-jenis/<ukuran>')
@login_required
def api_get_jenis(ukuran):
    db = get_db()
    jenis_list = db.execute('''
        SELECT jenis FROM harga WHERE ukuran = ? AND jenis IS NOT NULL
    ''', (ukuran,)).fetchall()
    return jsonify([{'jenis': j['jenis']} for j in jenis_list])

# ==================== HUTANG ROUTES ====================

@app.route('/hutang')
@login_required
def hutang_list():
    if current_user.is_bos():
        return redirect(url_for('bos_hutang'))
    
    db = get_db()
    
    hutang_list = db.execute('''
        SELECT * FROM hutang WHERE user_id = ? ORDER BY created_at DESC
    ''', (current_user.id,)).fetchall()
    
    total_aktif = get_total_hutang_aktif(current_user.id)
    total_lunas = db.execute('''
        SELECT COALESCE(SUM(nominal), 0) as total FROM hutang 
        WHERE user_id = ? AND status = 'lunas'
    ''', (current_user.id,)).fetchone()['total'] or 0
    
    return render_template('dashboard/hutang.html', 
                         hutang_list=hutang_list, 
                         total_aktif=total_aktif,
                         total_lunas=total_lunas)

# ==================== SLIP GAJI ROUTES ====================

@app.route('/slip-gaji')
@login_required
def slip_gaji():
    if current_user.is_bos():
        return redirect(url_for('bos_slip_gaji'))
    
    db = get_db()
    
    slip_list = db.execute('''
        SELECT * FROM slip_gaji WHERE user_id = ? ORDER BY created_at DESC
    ''', (current_user.id,)).fetchall()
    
    return render_template('dashboard/slip_gaji.html', slip_list=slip_list)

@app.route('/slip-gaji/generate', methods=['POST'])
@login_required
def generate_slip():
    if current_user.is_bos():
        return redirect(url_for('bos_dashboard'))
    
    db = get_db()
    
    # Get periode from form
    periode = request.form.get('periode', datetime.now().strftime('%B %Y'))
    
    # Calculate totals
    total_kerja = get_total_gaji_kotor(current_user.id)
    bonus = get_total_bonus(current_user.id)
    hutang = get_total_hutang_aktif(current_user.id)
    gaji_bersih = total_kerja + bonus - hutang
    
    # Save slip to database
    cursor = db.execute('''
        INSERT INTO slip_gaji (user_id, periode, total_kerja, bonus, hutang, gaji_bersih, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (current_user.id, periode, total_kerja, bonus, hutang, gaji_bersih, datetime.now()))
    db.commit()
    
    slip_id = cursor.lastrowid
    flash('Slip gaji berhasil dibuat!', 'success')
    return redirect(url_for('download_slip', slip_id=slip_id))

@app.route('/slip-gaji/download/<int:slip_id>')
@login_required
def download_slip(slip_id):
    db = get_db()
    
    slip = db.execute('''
        SELECT sg.*, u.nama_lengkap, u.whatsapp
        FROM slip_gaji sg
        JOIN users u ON sg.user_id = u.id
        WHERE sg.id = ? AND sg.user_id = ?
    ''', (slip_id, current_user.id)).fetchone()
    
    if not slip and not current_user.is_bos():
        flash('Slip gaji tidak ditemukan.', 'danger')
        return redirect(url_for('slip_gaji'))
    
    if not slip:
        slip = db.execute('''
            SELECT sg.*, u.nama_lengkap, u.whatsapp
            FROM slip_gaji sg
            JOIN users u ON sg.user_id = u.id
            WHERE sg.id = ?
        ''', (slip_id,)).fetchone()
    
    # Generate PDF
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    # Header
    pdf.set_font('Arial', 'B', 16)
    pdf.cell(0, 10, 'SLIP GAJI KARYAWAN', 0, 1, 'C')
    pdf.set_font('Arial', '', 12)
    pdf.cell(0, 10, 'Sistem Manajemen Gaji', 0, 1, 'C')
    pdf.line(10, 35, 200, 35)
    pdf.ln(10)
    
    # Info
    pdf.set_font('Arial', '', 11)
    pdf.cell(0, 8, f'Nama: {slip["nama_lengkap"]}', 0, 1)
    pdf.cell(0, 8, f'Periode: {slip["periode"]}', 0, 1)
    pdf.cell(0, 8, f'Tanggal: {slip["created_at"]}', 0, 1)
    pdf.ln(5)
    
    # Details
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, 'RINCIAN GAJI', 0, 1)
    pdf.set_font('Arial', '', 11)
    
    pdf.cell(100, 8, 'Total Kerja', 0, 0)
    pdf.cell(0, 8, f'Rp {slip["total_kerja"]:,.0f}', 0, 1, 'R')
    
    pdf.cell(100, 8, 'Bonus', 0, 0)
    pdf.cell(0, 8, f'Rp {slip["bonus"]:,.0f}', 0, 1, 'R')
    
    pdf.cell(100, 8, 'Potongan Hutang', 0, 0)
    pdf.cell(0, 8, f'Rp {slip["hutang"]:,.0f}', 0, 1, 'R')
    
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(100, 10, 'GAJI BERSIH', 0, 0)
    pdf.cell(0, 10, f'Rp {slip["gaji_bersih"]:,.0f}', 0, 1, 'R')
    
    pdf.ln(20)
    pdf.set_font('Arial', '', 10)
    pdf.cell(0, 8, 'Dicetak pada: ' + datetime.now().strftime('%d-%m-%Y %H:%M'), 0, 1, 'C')
    
    # Output
    output = BytesIO()
    pdf.output(output)
    output.seek(0)
    
    return send_file(output, mimetype='application/pdf', 
                    as_attachment=True, download_name=f'slip_gaji_{slip_id}.pdf')

# ==================== PROFILE ROUTES ====================

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    form = ProfileForm()
    password_form = PasswordForm()
    
    db = get_db()
    
    if form.validate_on_submit():
        # Check username uniqueness if changed
        if form.username.data != current_user.username:
            existing = db.execute('SELECT id FROM users WHERE username = ? AND id != ?',
                                (form.username.data, current_user.id)).fetchone()
            if existing:
                flash('Username sudah digunakan.', 'danger')
                return redirect(url_for('profile'))
        
        # Handle foto profil upload
        foto_profil = current_user.foto_profil
        if form.foto_profil.data:
            file = form.foto_profil.data
            if file and allowed_file(file.filename):
                filename = secure_filename(f'user_{current_user.id}_{file.filename}')
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                
                # Resize image
                img = Image.open(file)
                img.thumbnail((300, 300))
                img.save(filepath)
                
                foto_profil = filename
        
        db.execute('''
            UPDATE users SET username = ?, nama_lengkap = ?, whatsapp = ?, foto_profil = ?
            WHERE id = ?
        ''', (form.username.data, form.nama_lengkap.data, form.whatsapp.data, 
              foto_profil, current_user.id))
        db.commit()
        
        # Update current user
        current_user.username = form.username.data
        current_user.nama_lengkap = form.nama_lengkap.data
        current_user.whatsapp = form.whatsapp.data
        current_user.foto_profil = foto_profil
        
        flash('Profil berhasil diperbarui.', 'success')
        return redirect(url_for('profile'))
    
    elif request.method == 'GET':
        form.username.data = current_user.username
        form.nama_lengkap.data = current_user.nama_lengkap
        form.whatsapp.data = current_user.whatsapp
    
    # Get user's work history
    kerja_history = db.execute('''
        SELECT hk.*, h.ukuran, h.jenis
        FROM hasil_kerja hk
        JOIN harga h ON hk.harga_id = h.id
        WHERE hk.user_id = ?
        ORDER BY hk.created_at DESC
        LIMIT 10
    ''', (current_user.id,)).fetchall()
    
    # Get reset history
    reset_history = db.execute('''
        SELECT * FROM reset_gaji WHERE user_id = ? ORDER BY created_at DESC
    ''', (current_user.id,)).fetchall()
    
    return render_template('dashboard/profile.html', form=form, password_form=password_form,
                         kerja_history=kerja_history, reset_history=reset_history)

@app.route('/profile/change-password', methods=['POST'])
@login_required
def change_password():
    password_form = PasswordForm()
    
    if password_form.validate_on_submit():
        db = get_db()
        user = db.execute('SELECT * FROM users WHERE id = ?', (current_user.id,)).fetchone()
        
        if not check_password_hash(user['password_hash'], password_form.current_password.data):
            flash('Password saat ini salah.', 'danger')
            return redirect(url_for('profile'))
        
        new_hash = generate_password_hash(password_form.new_password.data)
        db.execute('UPDATE users SET password_hash = ? WHERE id = ?', 
                  (new_hash, current_user.id))
        db.commit()
        
        flash('Password berhasil diubah.', 'success')
    else:
        for error in password_form.errors.values():
            flash(error[0], 'danger')
    
    return redirect(url_for('profile'))

# ==================== BOS ROUTES ====================

@app.route('/bos/dashboard')
@login_required
@bos_required
def bos_dashboard():
    db = get_db()
    
    # Statistics
    total_karyawan = db.execute('SELECT COUNT(*) FROM users WHERE role = ?', ('karyawan',)).fetchone()[0]
    
    total_gaji_semua = db.execute('''
        SELECT COALESCE(SUM(total_harga), 0) FROM hasil_kerja WHERE status = 'approved'
    ''').fetchone()[0] or 0
    
    total_hutang_semua = db.execute('''
        SELECT COALESCE(SUM(nominal), 0) FROM hutang WHERE status = 'aktif'
    ''').fetchone()[0] or 0
    total_bonus_semua = db.execute('''
    SELECT COALESCE(SUM(nominal), 0) FROM bonus
''').fetchone()[0] or 0

    total_yang_harus_dibayar = (total_gaji_semua + total_bonus_semua) - total_hutang_semua
    total_gaji_semua_bonus = total_gaji_semua + total_bonus_semua

    #total_yang_harus_dibayar = total_gaji_semua - total_hutang_semua
    
    # Pending approvals
    pending_count = db.execute('''
        SELECT COUNT(*) FROM hasil_kerja WHERE status = 'pending'
    ''').fetchone()[0]
    
    # Chart data - Gaji per karyawan
    chart_data = db.execute('''
        SELECT u.nama_lengkap, COALESCE(SUM(hk.total_harga), 0) as total
        FROM users u
        LEFT JOIN hasil_kerja hk ON u.id = hk.user_id AND hk.status = 'approved'
        WHERE u.role = 'karyawan'
        GROUP BY u.id
        ORDER BY total DESC
        LIMIT 10
    ''').fetchall()
    
    # Recent activities
    recent_kerja = db.execute('''
        SELECT hk.*, u.nama_lengkap, h.ukuran, h.jenis
        FROM hasil_kerja hk
        JOIN users u ON hk.user_id = u.id
        JOIN harga h ON hk.harga_id = h.id
        ORDER BY hk.created_at DESC
        LIMIT 10
    ''').fetchall()
    
    # Karyawan list for reset dropdown
    karyawan_list = db.execute('''
        SELECT id, nama_lengkap FROM users WHERE role = ? ORDER BY nama_lengkap
    ''', ('karyawan',)).fetchall()
    
    return render_template('bos/dashboard.html',
                         total_karyawan=total_karyawan,
                         karyawan_list=karyawan_list,
                         total_gaji_semua=total_gaji_semua_bonus,
                         total_hutang_semua=total_hutang_semua,
                         total_yang_harus_dibayar=total_yang_harus_dibayar,
                         pending_count=pending_count,
                         chart_data=chart_data,
                         recent_kerja=recent_kerja)

@app.route('/bos/hasil-kerja')
@login_required
@bos_required
def bos_hasil_kerja():
    db = get_db()
    
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', '')
    search = request.args.get('search', '')
    per_page = 15
    
    query = '''
        SELECT hk.*, u.nama_lengkap, h.ukuran, h.jenis, h.harga as harga_satuan
        FROM hasil_kerja hk
        JOIN users u ON hk.user_id = u.id
        JOIN harga h ON hk.harga_id = h.id
        WHERE 1=1
    '''
    params = []
    
    if status_filter:
        query += ' AND hk.status = ?'
        params.append(status_filter)
    
    if search:
        query += ' AND u.nama_lengkap LIKE ?'
        params.append(f'%{search}%')
    
    query += ' ORDER BY hk.created_at DESC'
    
    total = db.execute(f'SELECT COUNT(*) FROM ({query})', params).fetchone()[0]
    
    query += ' LIMIT ? OFFSET ?'
    params.extend([per_page, (page - 1) * per_page])
    
    hasil_kerja_list = db.execute(query, params).fetchall()
    total_pages = (total + per_page - 1) // per_page
    
    return render_template('bos/hasil_kerja.html',
                         hasil_kerja_list=hasil_kerja_list,
                         page=page, total_pages=total_pages, total=total,
                         status_filter=status_filter, search=search)

@app.route('/bos/hasil-kerja/approve/<int:kerja_id>', methods=['POST'])
@login_required
@bos_required
def approve_kerja(kerja_id):
    db = get_db()
    db.execute('UPDATE hasil_kerja SET status = ? WHERE id = ?', ('approved', kerja_id))
    db.commit()
    flash('Hasil kerja telah di-approve.', 'success')
    return redirect(url_for('bos_hasil_kerja'))

@app.route('/bos/hasil-kerja/reject/<int:kerja_id>', methods=['POST'])
@login_required
@bos_required
def reject_kerja(kerja_id):
    db = get_db()
    db.execute('UPDATE hasil_kerja SET status = ? WHERE id = ?', ('rejected', kerja_id))
    db.commit()
    flash('Hasil kerja telah di-reject.', 'info')
    return redirect(url_for('bos_hasil_kerja'))

@app.route('/bos/harga', methods=['GET', 'POST'])
@login_required
@bos_required
def bos_harga():
    form = HargaForm()
    db = get_db()
    
    if form.validate_on_submit():
        ukuran = form.ukuran.data.lower().replace(' ', '_')
        jenis = form.jenis.data.lower() if form.jenis.data else None
        harga = form.harga.data
        
        # Check if exists
        existing = db.execute('''
            SELECT id FROM harga WHERE ukuran = ? AND (jenis = ? OR (jenis IS NULL AND ? IS NULL))
        ''', (ukuran, jenis, jenis)).fetchone()
        
        if existing:
            db.execute('UPDATE harga SET harga = ? WHERE id = ?', (harga, existing['id']))
            flash('Harga berhasil diupdate.', 'success')
        else:
            db.execute('''
                INSERT INTO harga (ukuran, jenis, harga) VALUES (?, ?, ?)
            ''', (ukuran, jenis, harga))
            flash('Harga berhasil ditambahkan.', 'success')
        
        db.commit()
        return redirect(url_for('bos_harga'))
    
    harga_list = db.execute('SELECT * FROM harga ORDER BY ukuran, jenis').fetchall()
    return render_template('bos/harga.html', form=form, harga_list=harga_list)

@app.route('/bos/harga/delete/<int:harga_id>', methods=['POST'])
@login_required
@bos_required
def delete_harga(harga_id):
    db = get_db()
    db.execute('DELETE FROM harga WHERE id = ?', (harga_id,))
    db.commit()
    flash('Harga berhasil dihapus.', 'success')
    return redirect(url_for('bos_harga'))

@app.route('/bos/hutang', methods=['GET', 'POST'])
@login_required
@bos_required
def bos_hutang():
    form = HutangForm()
    db = get_db()
    
    # Populate karyawan choices
    karyawan_list = db.execute('SELECT id, nama_lengkap FROM users WHERE role = ?', ('karyawan',)).fetchall()
    form.user_id.choices = [(k['id'], k['nama_lengkap']) for k in karyawan_list]
    
    if form.validate_on_submit():
        db.execute('''
            INSERT INTO hutang (user_id, nominal, keterangan, tanggal, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (form.user_id.data, form.nominal.data, form.keterangan.data,
              form.tanggal.data, 'aktif', datetime.now()))
        db.commit()
        flash('Hutang berhasil ditambahkan.', 'success')
        return redirect(url_for('bos_hutang'))
    
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', '')
    per_page = 15
    
    query = '''
        SELECT h.*, u.nama_lengkap
        FROM hutang h
        JOIN users u ON h.user_id = u.id
        WHERE 1=1
    '''
    params = []
    
    if status_filter:
        query += ' AND h.status = ?'
        params.append(status_filter)
    
    query += ' ORDER BY h.created_at DESC'
    
    total = db.execute(f'SELECT COUNT(*) FROM ({query})', params).fetchone()[0]
    query += ' LIMIT ? OFFSET ?'
    params.extend([per_page, (page - 1) * per_page])
    
    hutang_list = db.execute(query, params).fetchall()
    total_pages = (total + per_page - 1) // per_page
    
    return render_template('bos/hutang.html', form=form, hutang_list=hutang_list,
                         page=page, total_pages=total_pages, total=total,
                         status_filter=status_filter)

@app.route('/bos/hutang/lunasi/<int:hutang_id>', methods=['POST'])
@login_required
@bos_required
def lunasi_hutang(hutang_id):
    db = get_db()
    db.execute('UPDATE hutang SET status = ? WHERE id = ?', ('lunas', hutang_id))
    db.commit()
    flash('Hutang telah dilunasi.', 'success')
    return redirect(url_for('bos_hutang'))

@app.route('/bos/karyawan')
@login_required
@bos_required
def bos_karyawan():
    db = get_db()
    
    total_bonus = get_total_bonus(current_user.id)
    karyawan_list = db.execute('''
        SELECT u.*,
               COALESCE(SUM(hk.total_harga), 0) +
               (SELECT COALESCE(SUM(nominal), 0) FROM bonus WHERE user_id = u.id) as total_gaji,
               (SELECT COALESCE(SUM(nominal), 0) FROM hutang WHERE user_id = u.id AND status = 'aktif') as total_hutang,
               (SELECT COALESCE(SUM(nominal), 0) FROM bonus WHERE user_id = u.id) as total_bonus
        FROM users u
        LEFT JOIN hasil_kerja hk ON u.id = hk.user_id AND hk.status = 'approved'
        WHERE u.role = 'karyawan'
        GROUP BY u.id
    ''').fetchall()
    
    return render_template('bos/karyawan.html', karyawan_list=karyawan_list, total_bonus=total_bonus)

@app.route('/bos/reset_gaji/<int:user_id>', methods=['POST'])
@login_required
@bos_required
def reset_gaji(user_id):
  
    db = get_db()

    # Pastikan karyawan ada
    user = db.execute('SELECT * FROM users WHERE id = ? AND role = ?', (user_id, 'karyawan')).fetchone()
    if not user:
        flash('Karyawan tidak ditemukan.', 'danger')
        return redirect(url_for('bos_dashboard'))
    
    # Hapus hasil kerja
    db.execute('DELETE FROM hasil_kerja WHERE user_id = ?', (user_id,))
    
    # Hapus bonus
    db.execute('DELETE FROM bonus WHERE user_id = ?', (user_id,))
    
    # Nonaktifkan atau hapus hutang aktif
    db.execute('UPDATE hutang SET status = "nonaktif" WHERE user_id = ?', (user_id,))
    
    db.commit()
    flash(f'Gaji dan data finansial {user["nama_lengkap"]} telah direset.', 'success')
    return redirect(url_for('bos_karyawan'))


"""@app.route('/bos/reset-gaji', methods=['POST'])
@login_required
@bos_required
def reset_gaji():
    db = get_db()
    
    user_id = request.form.get('user_id')
    keterangan = request.form.get('keterangan', 'Reset gaji periode baru')
    
    if user_id == 'all':
        # Reset all karyawan
        karyawan_list = db.execute('SELECT id FROM users WHERE role = ?', ('karyawan',)).fetchall()
        for k in karyawan_list:
            # Archive current data
            total_gaji = get_total_gaji_kotor(k['id'])
            total_hutang = get_total_hutang_aktif(k['id'])
            
            db.execute('''
                INSERT INTO reset_gaji (user_id, total_gaji_sebelumnya, total_hutang_sebelumnya, keterangan, created_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (k['id'], total_gaji, total_hutang, keterangan, datetime.now()))
            
            # Delete hasil kerja and bonus
            db.execute('DELETE FROM hasil_kerja WHERE user_id = ?', (k['id'],))
            db.execute('DELETE FROM bonus WHERE user_id = ?', (k['id'],))
        
        flash('Gaji semua karyawan telah direset.', 'success')
    else:
        user_id = int(user_id)
        total_gaji = get_total_gaji_kotor(user_id)
        total_hutang = get_total_hutang_aktif(user_id)
        
        db.execute('''
            INSERT INTO reset_gaji (user_id, total_gaji_sebelumnya, total_hutang_sebelumnya, keterangan, created_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, total_gaji, total_hutang, keterangan, datetime.now()))
        
        db.execute('DELETE FROM hasil_kerja WHERE user_id = ?', (user_id,))
        db.execute('DELETE FROM bonus WHERE user_id = ?', (user_id,))
        flash('Gaji karyawan telah direset.', 'success')
    
    db.commit()
    return redirect(url_for('bos_dashboard'))
"""
@app.route('/bos/riwayat-reset')
@login_required
@bos_required
def bos_riwayat_reset():
    db = get_db()
    
    riwayat = db.execute('''
        SELECT rg.*, u.nama_lengkap
        FROM reset_gaji rg
        JOIN users u ON rg.user_id = u.id
        ORDER BY rg.created_at DESC
    ''').fetchall()
    
    return render_template('bos/riwayat_reset.html', riwayat=riwayat)

@app.route('/bos/slip-gaji')
@login_required
@bos_required
def bos_slip_gaji():
    db = get_db()
    
    slip_list = db.execute('''
        SELECT sg.*, u.nama_lengkap
        FROM slip_gaji sg
        JOIN users u ON sg.user_id = u.id
        ORDER BY sg.created_at DESC
    ''').fetchall()
    
    return render_template('bos/slip_gaji.html', slip_list=slip_list)

# ==================== BONUS ROUTES ====================

@app.route('/bos/bonus', methods=['GET', 'POST'])
@login_required
@bos_required
def bos_bonus():
    form = BonusForm()
    db = get_db()
    
    # Populate karyawan choices
    karyawan_list = db.execute('SELECT id, nama_lengkap FROM users WHERE role = ? ORDER BY nama_lengkap', ('karyawan',)).fetchall()
    form.user_id.choices = [(k['id'], k['nama_lengkap']) for k in karyawan_list]
    
    if form.validate_on_submit():
        db.execute('''
            INSERT INTO bonus (user_id, nominal, keterangan, created_at)
            VALUES (?, ?, ?, ?)
        ''', (form.user_id.data, form.nominal.data, form.keterangan.data, datetime.now()))
        db.commit()
        flash('Bonus berhasil ditambahkan!', 'success')
        return redirect(url_for('bos_bonus'))
    
    # Get all bonus with karyawan info
    page = request.args.get('page', 1, type=int)
    per_page = 15
    
    total = db.execute('SELECT COUNT(*) FROM bonus').fetchone()[0]
    
    bonus_list = db.execute('''
        SELECT b.*, u.nama_lengkap
        FROM bonus b
        JOIN users u ON b.user_id = u.id
        ORDER BY b.created_at DESC
        LIMIT ? OFFSET ?
    ''', (per_page, (page - 1) * per_page)).fetchall()
    
    total_pages = (total + per_page - 1) // per_page
    
    return render_template('bos/bonus.html', form=form, bonus_list=bonus_list,
                         page=page, total_pages=total_pages, total=total)

@app.route('/bos/bonus/delete/<int:bonus_id>', methods=['POST'])
@login_required
@bos_required
def delete_bonus(bonus_id):
    db = get_db()
    db.execute('DELETE FROM bonus WHERE id = ?', (bonus_id,))
    db.commit()
    flash('Bonus berhasil dihapus.', 'success')
    return redirect(url_for('bos_bonus'))

# ==================== API ROUTES ====================

@app.route('/api/statistics')
@login_required
def api_statistics():
    if not current_user.is_bos():
        return jsonify({'error': 'Unauthorized'}), 403
    
    db = get_db()
    
    # Monthly data for chart
    monthly_data = db.execute('''
        SELECT strftime('%Y-%m', created_at) as bulan,
               SUM(total_harga) as total
        FROM hasil_kerja
        WHERE status = 'approved'
        GROUP BY bulan
        ORDER BY bulan DESC
        LIMIT 12
    ''').fetchall()
    
    return jsonify({
        'monthly': [{'bulan': m['bulan'], 'total': m['total']} for m in monthly_data]
    })

# ==================== ERROR HANDLERS ====================

@app.errorhandler(404)
def not_found(error):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('errors/500.html'), 500

# ==================== MAIN ====================

if __name__ == '__main__':
    if not os.path.exists(app.config['DATABASE']):
        init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
