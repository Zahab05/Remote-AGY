/**
 * Remote-AGY Cloudflare Worker 24/7 Webhook Relay
 * 
 * Fungsi:
 * 1. Menerima interaksi tombol Telegram secara instan 24/7 saat Codespace mati.
 * 2. Menjawab callback query di Telegram agar tombol tidak loading (<50ms).
 * 3. Membangunkan GitHub Codespace otomatis via GitHub REST API.
 * 4. Memicu GitHub Repository Dispatch untuk mencatat antrean tugas yang disetujui.
 */

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    // Health check endpoint
    if (request.method === "GET") {
      return new Response(JSON.stringify({
        status: "online",
        service: "Remote-AGY Cloudflare Webhook Relay",
        timestamp: new Date().toISOString()
      }, null, 2), {
        headers: { "Content-Type": "application/json" }
      });
    }

    if (request.method !== "POST") {
      return new Response("Method Not Allowed", { status: 405 });
    }

    try {
      const update = await request.json();

      // 1. Tangani Klik Tombol (Inline Keyboard Callback Query)
      if (update.callback_query) {
        return await handleCallbackQuery(update.callback_query, env);
      }

      // 2. Tangani Perintah Chat Teks (/start, /status, /wake, /approve)
      if (update.message && update.message.text) {
        return await handleTextMessage(update.message, env);
      }

      return new Response("OK", { status: 200 });
    } catch (err) {
      console.error("Error processing update:", err);
      return new Response(JSON.stringify({ error: err.message }), {
        status: 500,
        headers: { "Content-Type": "application/json" }
      });
    }
  }
};

/**
 * Menangani klik tombol [Setujui / Abaikan / Tunda] di Telegram
 */
async function handleCallbackQuery(query, env) {
  const queryId = query.id;
  const data = query.data || "";
  const chatId = query.message.chat.id;
  const messageId = query.message.message_id;

  const [action, taskId] = data.split(":");

  if (action === "approve") {
    // 1. Segera jawab callback ke Telegram agar tombol tidak muter-muter
    await answerTelegramCallback(env.TELEGRAM_BOT_TOKEN, queryId, "✅ Persetujuan diterima! Membangunkan Codespace & AGY...");

    // 2. Perbarui tampilan pesan di Telegram
    const editMsg = 
      `✅ *Persetujuan Diterima!*\n\n` +
      `🆔 *ID Tugas*: \`${taskId}\`\n\n` +
      `⚙️ _Cloudflare Worker sedang membangunkan GitHub Codespace..._\n` +
      `AGY di terminal akan otomatis mulai mengerjakan tugas begitu Codespace aktif. Berkas hasil akan dikirim ke sini.`;
    
    await editTelegramMessage(env.TELEGRAM_BOT_TOKEN, chatId, messageId, editMsg);

    // 3. Bangunkan Codespace via GitHub API
    const wakeResult = await wakeUpCodespace(env);

    // 4. Catat antrean via GitHub Repository Dispatch
    await triggerGitHubDispatch(env, "task_approved", { task_id: taskId });

    return new Response(JSON.stringify({
      success: true,
      action: "approved",
      task_id: taskId,
      codespace_wake: wakeResult
    }), { headers: { "Content-Type": "application/json" } });
  } 
  else if (action === "ignore") {
    await answerTelegramCallback(env.TELEGRAM_BOT_TOKEN, queryId, "❌ Tugas diabaikan");
    await editTelegramMessage(env.TELEGRAM_BOT_TOKEN, chatId, messageId, `❌ *Tugas (\`${taskId}\`) telah diabaikan.*`);
    return new Response("Ignored", { status: 200 });
  } 
  else if (action === "snooze") {
    await answerTelegramCallback(env.TELEGRAM_BOT_TOKEN, queryId, "⏳ Tugas ditunda");
    await editTelegramMessage(env.TELEGRAM_BOT_TOKEN, chatId, messageId, `⏳ *Tugas (\`${taskId}\`) ditunda. Akan diingatkan pada jadwal berikutnya.*`);
    return new Response("Snoozed", { status: 200 });
  }

  return new Response("OK", { status: 200 });
}

/**
 * Menangani pesan teks seperti /status, /wake, /start
 */
async function handleTextMessage(msg, env) {
  const chatId = msg.chat.id;
  const text = msg.text.trim();

  if (text.startsWith("/start")) {
    const welcome = 
      `🤖 *Remote-AGY Cloud Relay 24/7 Aktif!*\n\n` +
      `Worker ini selalu terjaga di cloud untuk menerima tombol persetujuan dan membangunkan Codespace otomatis.\n\n` +
      `Perintah:\n` +
      `• /status - Cek status koneksi Codespace\n` +
      `• /wake - Bangunkan Codespace secara manual\n` +
      `• /approve <id> - Setujui tugas via perintah teks`;
    await sendTelegramMessage(env.TELEGRAM_BOT_TOKEN, chatId, welcome);
  }
  else if (text.startsWith("/status")) {
    const statusInfo = await getCodespaceStatus(env);
    await sendTelegramMessage(env.TELEGRAM_BOT_TOKEN, chatId, `📊 *Status Codespace di Cloud:*\n${statusInfo}`);
  }
  else if (text.startsWith("/wake")) {
    await sendTelegramMessage(env.TELEGRAM_BOT_TOKEN, chatId, "🚀 Mengirim sinyal bangun ke GitHub Codespace...");
    const res = await wakeUpCodespace(env);
    await sendTelegramMessage(env.TELEGRAM_BOT_TOKEN, chatId, `[✓] Sinyal terkirim! Status: ${res}`);
  }
  else if (text.startsWith("/approve")) {
    const parts = text.split(" ");
    if (parts.length > 1) {
      const taskId = parts[1];
      await sendTelegramMessage(env.TELEGRAM_BOT_TOKEN, chatId, `✅ Tugas \`${taskId}\` disetujui! Membangunkan Codespace...`);
      await wakeUpCodespace(env);
      await triggerGitHubDispatch(env, "task_approved", { task_id: taskId });
    }
  }

  return new Response("OK", { status: 200 });
}

/**
 * Memanggil GitHub API untuk membangunkan Codespace
 */
async function wakeUpCodespace(env) {
  const endpoint = `https://api.github.com/user/codespaces/${env.CODESPACE_NAME}/start`;
  const res = await fetch(endpoint, {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${env.GITHUB_PAT}`,
      "Accept": "application/vnd.github+json",
      "User-Agent": "Remote-AGY-Cloudflare-Worker"
    }
  });

  if (res.status === 200 || res.status === 202) {
    return "Codespace is booting / already running";
  } else {
    const errText = await res.text();
    console.error("Gagal start codespace:", res.status, errText);
    return `Error ${res.status}: ${errText}`;
  }
}

/**
 * Cek status terkini Codespace
 */
async function getCodespaceStatus(env) {
  const endpoint = `https://api.github.com/user/codespaces/${env.CODESPACE_NAME}`;
  const res = await fetch(endpoint, {
    headers: {
      "Authorization": `Bearer ${env.GITHUB_PAT}`,
      "Accept": "application/vnd.github+json",
      "User-Agent": "Remote-AGY-Cloudflare-Worker"
    }
  });

  if (res.status === 200) {
    const data = await res.json();
    return `• Nama: \`${data.name}\`\n• Kondisi: *${data.state}*\n• Terakhir Aktif: ${data.last_used_at}`;
  } else {
    return "Gagal mendapatkan status dari GitHub API.";
  }
}

/**
 * Memicu GitHub Repository Dispatch Event
 */
async function triggerGitHubDispatch(env, eventType, payload) {
  const endpoint = `https://api.github.com/repos/${env.GITHUB_REPO}/dispatches`;
  return await fetch(endpoint, {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${env.GITHUB_PAT}`,
      "Accept": "application/vnd.github+json",
      "User-Agent": "Remote-AGY-Cloudflare-Worker",
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      event_type: eventType,
      client_payload: payload
    })
  });
}

/**
 * Helper Telegram Bot API
 */
async function answerTelegramCallback(token, callbackQueryId, text) {
  const url = `https://api.telegram.org/bot${token}/answerCallbackQuery`;
  return await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      callback_query_id: callbackQueryId,
      text: text,
      show_alert: false
    })
  });
}

async function editTelegramMessage(token, chatId, messageId, text) {
  const url = `https://api.telegram.org/bot${token}/editMessageText`;
  return await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      chat_id: chatId,
      message_id: messageId,
      text: text,
      parse_mode: "Markdown"
    })
  });
}

async function sendTelegramMessage(token, chatId, text) {
  const url = `https://api.telegram.org/bot${token}/sendMessage`;
  return await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      chat_id: chatId,
      text: text,
      parse_mode: "Markdown"
    })
  });
}
