# Remote-AGY

Workspace bersama antara **Laptop Lokal** (`C:\Users\zahir\projects\remote-AGY`) dan **GitHub Codespaces** untuk pengerjaan project menggunakan agent Antigravity (`agy`).

## Alur Kerja Sinkronisasi
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