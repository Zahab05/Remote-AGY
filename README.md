# 🎓 Remote-AGY: Sistem Otomatis Pendeteksi Tugas SLCM & AI Task Executor

Workspace bersama antara **Laptop Lokal** (`C:\Users\zahir\projects\remote-AGY`) dan **GitHub Codespaces** untuk pengerjaan project menggunakan agent Antigravity (`agy`). Terhubung langsung dengan portal akademik kampus (**SATU / EMAS Universitas Indonesia**). Sistem ini memantau tugas baru secara berkala, menganalisis batas waktu dan tingkat kesulitan tugas dengan AI, mengirimkan notifikasi interaktif ke **Telegram / WhatsApp**, serta mengeksekusi pengerjaan tugas secara otonom di terminal setelah disetujui (*approval*).

---

## 🔄 Alur Kerja Sinkronisasi Laptop & Codespaces
1. **Di Laptop:**
   ```bash
   git add .
   git commit -m "Update dari laptop"
   git push origin main
   ```
2. **Di GitHub Codespaces (Smartphone / Web):**
   ```bash
   git pull
   agy -p "Perintah tugas untuk agent..."
   ```
3. **Mengambil hasil dari Codespaces ke Laptop:**
   ```bash
   git pull
   ```

---

## 🌟 Fitur Utama

1. **Pendeteksi Tugas Otomatis (SLCM Watcher)**:
   - Terintegrasi langsung dengan portal **SSO UI** (`sso.ui.ac.id`), **SATU UI** (`satu.ui.ac.id`), dan **EMAS 3 UI** (`emas3.ui.ac.id`).
   - Mendukung login otomatis via Playwright Headless dan persistensi *session cookies* untuk efisiensi tanpa login berulang.
   - Dilengkapi database lokal SQLite untuk mencegah duplikasi notifikasi tugas yang sama.

2. **AI Task Analyzer (Tingkat Kesulitan & Estimasi Waktu)**:
   - Mengekstrak informasi penting: **Mata Kuliah**, **Batas Waktu (Due Date)**, dan **Sisa Waktu**.
   - Menganalisis tingkat kesulitan tugas secara otomatis:
     - 🟢 **Easy**: Kuis, rangkuman, review jurnal, esai singkat.
     - 🟡 **Medium**: Coding REST API, algoritma/struktur data, analisis ERD, studi kasus.
     - 🔴 **Hard**: Fullstack / microservice, deep learning / AI pipeline, proyek besar, arsitektur kompleks.
   - Merumuskan panduan dan *prompt instruksi* teknis untuk AGY.

3. **Notifikasi Interaktif (Telegram & WhatsApp)**:
   - **Telegram (Utama)**: Mengirim kartu tugas lengkap dengan tombol interaktif:
     - `[ ✅ Setujui & Kerjakan ]`
     - `[ ⏳ Ingatkan Nanti ]`
     - `[ ❌ Abaikan ]`
   - **WhatsApp (Sekunder)**: Mendukung HTTP Gateway (Fonnte, Wablas, atau generic webhook) dengan format persetujuan cepat `!approve <task_id>`.

4. **Headless AGY Terminal Runner**:
   - Setelah disetujui, AGY langsung dieksekusi secara otonom di latar belakang (`agy -p` dengan izin auto-approve aman).
   - Setiap tugas dikerjakan dalam direktori terisolasi (`tasks/<task_id>/`).
   - Berkas hasil pengerjaan (kode, dokumen, README) otomatis dikompres ke format `.zip` dan dikirimkan kembali ke chat Telegram pengguna.

---

## 📁 Struktur Direktori

```
Remote-AGY/
├── config/
│   ├── config.yaml            # Konfigurasi sistem, portal, dan bot
│   ├── config.example.yaml    # Template konfigurasi
│   ├── .env.example           # Template kredensial rahasia
│   └── ui_session.json        # Cookies session SSO UI (otomatis dibuat)
├── src/
│   ├── storage/db.py          # SQLite task manager & state tracker
│   ├── watcher/
│   │   ├── base.py            # Interface dasar adapter portal
│   │   ├── ui_satu_adapter.py # Adapter SSO UI & EMAS UI (Universitas Indonesia)
│   │   └── mock_watcher.py    # Simulator tugas untuk testing
│   ├── analyzer/
│   │   └── task_analyzer.py   # Klasifikasi kesulitan & formulasi prompt
│   ├── bot/
│   │   ├── telegram_bot.py    # Telegram Bot handler & callback buttons
│   │   ├── whatsapp_bot.py    # WhatsApp Gateway integration
│   │   └── notifier_manager.py# Manajer distribusi notifikasi
│   ├── executor/
│   │   └── agy_runner.py      # Eksekutor AGY headless & zip packaging
│   └── main.py                # Core orchestrator daemon
├── tasks/                     # Workspace folder pengerjaan tugas oleh AGY
├── tests/                     # Unit test otomatis
├── run.py                     # Entry point CLI
├── requirements.txt
└── setup-remote-access.sh     # Konfigurasi Tailscale, SSH, & Termius iPhone
```

---

## 🚀 Panduan Instalasi & Penggunaan

### 1. Konfigurasi Kredensial (`.env`)
Salin file `.env.example` ke `config/.env`:
```bash
cp config/.env.example config/.env
```
Buka `config/.env` dan lengkapi:
```ini
# Kredensial SSO Universitas Indonesia
UI_SSO_USERNAME=username_sso_anda
UI_SSO_PASSWORD=password_sso_anda

# Telegram Bot (Dapatkan token dari @BotFather dan ID dari @userinfobot)
TELEGRAM_BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRstuVWXyz
TELEGRAM_CHAT_ID=987654321

# Opsional: Gemini API Key (Jika ingin analisis LLM yang lebih detail)
GEMINI_API_KEY=AIzaSy...
```

### 2. Menguji Sistem dengan Tugas Simulasi
Untuk memastikan alur notifikasi dan tombol persetujuan berjalan sempurna:
```bash
./run.py --simulate-task
```
Pesan kartu tugas akan masuk ke bot Telegram Anda dengan tombol **[✅ Setujui & Kerjakan]**.

### 3. Menjalankan Pengecekan Manual
Periksa apakah ada tugas aktif di portal saat ini:
```bash
./run.py --check-now
```

### 4. Melihat Daftar Tugas & Status di Database
```bash
./run.py --list-tasks
```

### 5. Menjalankan Background Daemon Penuh
Jalankan daemon agar sistem memeriksa portal secara otomatis setiap 15 menit dan bot Telegram terus aktif mendengarkan perintah:
```bash
./run.py --daemon
```

---

## 📲 Alur Persetujuan di Telegram

1. Bot mengirimkan kartu tugas baru:
   ```text
   🚨 [TUGAS BARU TERDETEKSI DI SLCM] 🚨
   
   📚 Mata Kuliah: Pemrograman Berbasis Web
   📝 Judul Tugas: Tugas 2: FastAPI Auth & Product CRUD REST API
   ⏰ Batas Waktu: 10 September 2026, 23:59 WIB
   ⏳ Sisa Waktu: Sisa 5 hari 7 jam
   ⚡ Tingkat Kesulitan: 🟡 Medium
   💡 Catatan Analisis: Memerlukan implementasi logika fungsional, database SQLite, dan pengujian.
   
   Apakah Anda ingin AGY mengerjakan tugas ini sekarang?
   [ ✅ Setujui & Kerjakan ]  [ ⏳ Ingatkan Nanti ]  [ ❌ Abaikan ]
   ```

2. Ketika Anda menekan **[ ✅ Setujui & Kerjakan ]**:
   - Status tugas berubah menjadi `APPROVED`.
   - AGY mulai mengeksekusi tugas di folder `tasks/<task_id>/`.
   - Bot mengirimkan pembaruan progres: *"⚙️ AGY sedang mengeksekusi pengerjaan tugas di terminal..."*.

3. Setelah AGY selesai:
   - Berkas hasil kerja (kode `.py`, dokumentasi `README.md`, unit test, dan dokumen laporan) dikompres ke file `.zip`.
   - Bot mengirimkan pesan selesai beserta lampiran file `.zip` langsung ke chat Telegram Anda!

---

## ⚡ Otomatisasi 24/7 dengan GitHub Actions (Tanpa Komputer Menyala)

Workflow [`.github/workflows/check_tasks.yml`](.github/workflows/check_tasks.yml) telah disiapkan agar GitHub secara mandiri memeriksa tugas portal kampus setiap **4 jam** (hemat kuota GitHub Actions).

### Cara Menghubungkan Kredensial ke GitHub Actions:
1. Buka repositori Anda di GitHub melalui browser.
2. Masuk ke menu **Settings** > **Secrets and variables** > **Actions**.
3. Klik tombol **New repository secret** dan tambahkan variabel berikut:
   - `UI_SSO_USERNAME` : Username SSO Universitas Indonesia
   - `UI_SSO_PASSWORD` : Password SSO Universitas Indonesia
   - `TELEGRAM_BOT_TOKEN` : Token bot Telegram dari @BotFather
   - `TELEGRAM_CHAT_ID` : ID chat Telegram Anda dari @userinfobot
   - `GEMINI_API_KEY` : (Opsional) API key Gemini AI
4. Selesai! GitHub Actions akan otomatis aktif dan mengirimkan notifikasi ke Telegram setiap kali ada tugas baru di portal kampus, meskipun laptop dan Codespace Anda mati total.
