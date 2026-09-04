# 🌐 Panduan Setup Cloudflare Worker: 24/7 Telegram Approval Relay & Codespace Auto-Wake

Worker ini berfungsi sebagai **jembatan 24/7 di cloud**. Saat Codespace Anda mati, tombol persetujuan di Telegram akan langsung dijawab oleh Cloudflare Worker ini, dan Worker secara otomatis membangunkan Codespace melalui GitHub API agar AGY langsung bekerja!

---

## 📋 Prasyarat (Hanya Perlu Dilakukan Sekali)

1. **Akun Cloudflare Gratis**: Daftar di [dash.cloudflare.com](https://dash.cloudflare.com/) jika belum punya (100% gratis).
2. **GitHub Personal Access Token (PAT)**:
   - Buka GitHub ➔ Klik foto profil pojok kanan atas ➔ **Settings**.
   - Di menu sebelah kiri paling bawah, klik **Developer settings** ➔ **Personal access tokens** ➔ **Tokens (classic)**.
   - Klik tombol **Generate new token (classic)**.
   - Beri nama: `Remote-AGY-Worker`.
   - Centang izin berikut:
     - [x] **`repo`** (Full control of private repositories)
     - [x] **`codespace`** (Full control of codespaces)
   - Klik **Generate token** dan salin token tersebut (contoh: `ghp_xxxxxxxxxxxx`).

---

## 🚀 Langkah 1: Buat Worker di Cloudflare Dashboard

1. Buka [dash.cloudflare.com](https://dash.cloudflare.com/) dan login.
2. Di menu sebelah kiri, pilih **Workers & Pages**.
3. Klik tombol **Create Application** ➔ pilih tab **Workers** ➔ klik **Create Worker**.
4. Beri nama worker Anda (misal: `remote-agy-relay`), lalu klik tombol **Deploy**.
5. Setelah deploy berhasil, klik tombol **Edit code**.
6. Hapus seluruh isi kode bawaan, lalu salin dan tempelkan seluruh isi file [`worker.js`](worker.js) ke editor tersebut.
7. Klik tombol **Deploy** di pojok kanan atas.

---

## 🔑 Langkah 2: Masukkan Variabel & Secrets di Cloudflare

1. Kembali ke halaman overview Worker Anda di Cloudflare.
2. Klik tab **Settings** ➔ pilih **Variables and Secrets**.
3. Klik **Add** pada bagian **Environment Variables** / **Secrets** dan tambahkan variabel berikut:

| Nama Variabel | Jenis | Nilai / Value |
| :--- | :--- | :--- |
| `TELEGRAM_BOT_TOKEN` | Secret | `8830895042:AAEtFffDubFkL7n2PoewGdagTbDRL4y5uxU` |
| `TELEGRAM_CHAT_ID` | Variable | `1063145210` |
| `CODESPACE_NAME` | Variable | `symmetrical-space-couscous-7vp47x55p954frqxg` |
| `GITHUB_REPO` | Variable | `Zahab05/Remote-AGY` |
| `GITHUB_PAT` | Secret | *Token GitHub PAT yang Anda buat di Prasyarat (`ghp_...`)* |

4. Klik **Deploy** / **Save**.

---

## 🔗 Langkah 3: Sambungkan Bot Telegram ke Worker (Set Webhook)

Salin URL worker Anda (misal: `https://remote-agy-relay.nama-akun.workers.dev`).

Buka tab baru di browser Anda dan buka URL berikut (ganti `<URL_WORKER_ANDA>` dengan URL worker Anda):

```text
https://api.telegram.org/bot8830895042:AAEtFffDubFkL7n2PoewGdagTbDRL4y5uxU/setWebhook?url=<URL_WORKER_ANDA>
```

Browser akan menampilkan respons JSON:
```json
{
  "ok": true,
  "result": true,
  "description": "Webhook was set"
}
```

---

## 🎉 Selesai! Bagaimana Cara Kerjanya Sekarang?

1. Codespace dan laptop Anda boleh **mati total**.
2. GitHub Actions memantau tugas kampus tiap 3 jam.
3. Begitu ada tugas baru, kartu tugas masuk ke Telegram Anda.
4. Anda cukup klik **`[ ✅ Setujui & Kerjakan ]`** di Telegram:
   - Tombol langsung tercentang hijau (<50ms).
   - Cloudflare Worker otomatis membangunkan Codespace di cloud.
   - Codespace bangun (~15 detik) ➔ Autostart menyala ➔ AGY langsung mengeksekusi tugas.
   - File hasil `.zip` dikirimkan ke chat Telegram Anda!
