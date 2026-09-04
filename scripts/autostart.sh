#!/usr/bin/env bash
set -e

WORKSPACE_DIR="/workspaces/Remote-AGY"
LOG_FILE="$WORKSPACE_DIR/tasks/autostart.log"
mkdir -p "$WORKSPACE_DIR/tasks"

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "=================================================="
log "🚀 Memulai Autostart Services Remote-AGY & Remote Access"
log "=================================================="

# 1. Pastikan SSH Daemon Aktif
if ! sudo service ssh status >/dev/null 2>&1; then
  log "[+] Menyalakan SSH daemon..."
  sudo service ssh start
else
  log "[✓] SSH daemon sudah aktif."
fi

# 2. Pastikan Tailscale Service Berjalan
log "[+] Memeriksa Tailscale service..."
sudo mkdir -p /var/run/tailscale /var/lib/tailscale /var/cache/tailscale
if ! pgrep -x "tailscaled" > /dev/null; then
  log "[+] Menjalankan background tailscaled..."
  sudo nohup tailscaled --state=/var/lib/tailscale/tailscaled.state </dev/null >/var/log/tailscaled.log 2>&1 & disown
  sleep 2
fi

# Sambungkan Tailscale node jika belum
sudo tailscale up 2>/dev/null || true
TAILSCALE_IP=$(tailscale ip -4 2>/dev/null || echo "N/A")
log "[✓] Tailscale IP: $TAILSCALE_IP"

# 3. Jalankan Remote-AGY Watcher & Telegram Bot di Tmux
if tmux has-session -t agy-bot 2>/dev/null; then
  log "[✓] Sesi tmux 'agy-bot' sudah berjalan."
else
  log "[+] Menjalankan Telegram Bot & SLCM Watcher di sesi tmux 'agy-bot'..."
  tmux new-session -d -s agy-bot -c "$WORKSPACE_DIR" "./run.py --daemon"
  log "[✓] Sesi 'agy-bot' berhasil diaktifkan di background!"
fi

log "=================================================="
log "✅ Seluruh service Remote-AGY siap digunakan!"
log "=================================================="
