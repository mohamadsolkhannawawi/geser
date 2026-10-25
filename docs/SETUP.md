# Panduan Penyiapan Perangkat (Laptop & 2 HP Android Termux)

Dokumen ini menjelaskan langkah demi langkah penyiapan lingkungan di laptop (Windows, Linux, macOS) serta instalasi Termux di kedua HP Android (`body` dan `desk`).

---

## 1. Penyiapan di Laptop (Engine & Dashboard)

### Kebutuhan Sistem
- Python 3.10 atau lebih baru.
- Koneksi internet yang mengizinkan port TCP `8883` (MQTT over TLS). Bila Wi-Fi kampus memblokir port 8883, hubungkan laptop dan kedua HP ke **Hotspot Wi-Fi** yang sama.

### Langkah Instalasi Lintas OS

**Di Linux / macOS (Bash/Zsh):**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[dashboard,dev]"
cp .env.example .env
python tools/suggest_project_id.py
```

**Di Windows (PowerShell):**
```powershell
python -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -e ".[dashboard,dev]"
Copy-Item .env.example .env
python tools/suggest_project_id.py
```
Salin keluaran `PROJECT_ID=geser-kelompok-xxxx` ke dalam berkas `.env`.

---

## 2. Penyiapan di Kedua HP Android (Termux + Termux:API)

### Langkah 1: Instal Termux dan Termux:API dari F-Droid
> **Penting:** Jangan menginstal Termux dari Google Play Store karena versinya sudah dihentikan dan tidak kompatibel dengan Termux:API terbaru.

1. Buka peramban di HP Android dan unduh aplikasi **F-Droid** dari `https://f-droid.org`.
2. Di dalam F-Droid, cari dan pasang dua aplikasi berikut:
   - **Termux**
   - **Termux:API**

### Langkah 2: Pengaturan Izin dan Penghemat Baterai Android
Agar pembacaan sensor tidak berhenti saat layar HP mati di dalam saku baju:
1. Buka **Pengaturan (Settings) -> Aplikasi (Apps) -> Termux:API -> Izin (Permissions)**:
   - Aktifkan izin **Notifikasi (Notifications)** dan **Sensor Tubuh (Body Sensors)** bila tersedia.
2. Buka **Pengaturan -> Aplikasi -> Termux -> Baterai (Battery)**:
   - Pilih **Tidak Dibatasi (Unrestricted / Don't Optimize)**. Lakukan hal yang sama untuk aplikasi **Termux:API**.

### Langkah 3: Pasang Paket di Dalam Termux
Buka aplikasi Termux di masing-masing HP, lalu jalankan:
```bash
pkg update && pkg upgrade -y
pkg install python git termux-api -y

# Kunci CPU agar tidak tidur saat layar mati
termux-wake-lock
```

### Langkah 4: Periksa Sensor Akselerometer dan Giroskop
Jalankan perintah berikut untuk memastikan HP memiliki sensor `accelerometer` dan `gyroscope`:
```bash
termux-sensor -l
```
Jika nama sensor di HP Anda menggunakan huruf besar atau nama vendor khusus, Anda dapat menyesuaikannya di `configs/default.yaml` pada bagian `edge.accel_sensor` dan `edge.gyro_sensor`.

### Langkah 5: Pasang Repositori GESER di Termux
```bash
git clone <URL_GITHUB_REPO_KELOMPOK> geser
cd geser
pip install -e .
cp .env.example .env
```
Edit berkas `.env` (misalnya dengan `nano .env`) dan isi `PROJECT_ID` yang **sama persis** dengan di laptop.

Uji kesiapan sensor dengan alat pemeriksa:
```bash
python tools/check_sensors.py
```

### Langkah 6: Jalankan Peran Edge
- **Di HP A (masukkan ke saku baju dada):**
  ```bash
  geser-edge --role body
  ```
- **Di HP B (letakkan mendatar di atas meja kerja):**
  ```bash
  geser-edge --role desk
  ```

---

## 3. Alternatif Tanpa Termux (`browser_edge/index.html`)

Apabila salah satu HP anggota kelompok tidak dapat menjalankan Termux, gunakan antarmuka web cadangan:
1. Sajikan folder `browser_edge/` melalui HTTPS atau buka di Chrome Android.
2. Isi `PROJECT_ID`, pilih peran (`body` atau `desk`), lalu klik **Hubungkan & Mulai Kirim**.
3. Halaman tersebut menghitung fitur Processing 1 secara identik (konversi giroskop browser dari derajat/detik ke rad/detik) dan mengirimkannya lewat WebSocket TLS (`wss://broker.hivemq.com:8884/mqtt`).

---

## 4. Troubleshooting (Pemecahan Masalah)

| Masalah | Penyebab | Solusi |
|---|---|---|
| `GESER menolak berjalan: PROJECT_ID masih kosong atau placeholder` | Berkas `.env` belum dibuat atau masih tertulis `geser-kelompok-GANTI`. | Jalankan `python tools/suggest_project_id.py` lalu salin nilainya ke `.env`. |
| Pesan ditolak: `t_ms terlalu jauh dari waktu engine` | Jam di HP dan jam di laptop selisih lebih dari 30 detik. | Aktifkan pengaturan **Waktu Otomatis (Automatic Date & Time / NTP)** di HP dan laptop. |
| `termux-sensor` tidak mengeluarkan data sama sekali | Aplikasi pendamping **Termux:API** belum dipasang atau dihentikan oleh penghemat baterai. | Pasang APK Termux:API dari F-Droid, jalankan `termux-wake-lock`, dan matikan *Battery Saver*. |
| Getar tidak terasa di HP `body` pada Level 1 | Sesuai desain kebijakan pengingat, Level 1 hanya mengirim notifikasi ke `desk` dan kartu dashboard. | Tunggu hingga **Level 2** (getar pendek) atau **Level 3** (getar panjang berulang). Pastikan mode *Do Not Disturb* di HP tidak memblokir getaran. |
| Koneksi ke `broker.hivemq.com:8883` gagal / timeout | Firewall jaringan memblokir port 8883. | Gunakan koneksi *tethering/hotspot* dari salah satu HP untuk menghubungkan laptop dan kedua HP. |
