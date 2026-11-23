const SUPABASE_URL = "https://zvxggmvwrqbntywpbcso.supabase.co";
const SUPABASE_ANON_KEY = "sb_publishable_nLN5GjNJ5MEPY83o46UQVA_hm_pHsAV";

const authView = document.getElementById("authView");
const mainView = document.getElementById("mainView");
const authError = document.getElementById("authError");
const entryError = document.getElementById("entryError");
const crisisModal = document.getElementById("crisisModal");
const confirmModal = document.getElementById("confirmModal");

let confirmDialogBusy = false;

function confirmDialog(message) {
  if (confirmDialogBusy) return Promise.resolve(false);
  confirmDialogBusy = true;
  document.getElementById("confirmMessage").textContent = message;
  confirmModal.classList.remove("hidden");
  return new Promise((resolve) => {
    const cleanup = (result) => {
      confirmModal.classList.add("hidden");
      okBtn.removeEventListener("click", onOk);
      cancelBtn.removeEventListener("click", onCancel);
      confirmDialogBusy = false;
      resolve(result);
    };
    const okBtn = document.getElementById("confirmOkBtn");
    const cancelBtn = document.getElementById("confirmCancelBtn");
    const onOk = () => cleanup(true);
    const onCancel = () => cleanup(false);
    okBtn.addEventListener("click", onOk);
    cancelBtn.addEventListener("click", onCancel);
  });
}

function getToken() {
  return localStorage.getItem("access_token");
}

function setToken(token) {
  if (token) localStorage.setItem("access_token", token);
  else localStorage.removeItem("access_token");
}

function showError(el, message) {
  el.textContent = message;
  el.classList.remove("hidden");
}

function hideError(el) {
  el.classList.add("hidden");
}

async function supabaseAuth(path, body) {
  const res = await fetch(`${SUPABASE_URL}/auth/v1${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      apikey: SUPABASE_ANON_KEY,
    },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.msg || data.error_description || data.message || "인증에 실패했습니다.");
  }
  return data;
}

async function api(path, options = {}) {
  const res = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${getToken()}`,
      ...(options.headers || {}),
    },
  });
  if (res.status === 401) {
    setToken(null);
    renderAuthView();
    throw new Error("세션이 만료됐어요. 다시 로그인해주세요.");
  }
  let data = null;
  try {
    data = await res.json();
  } catch {
    // 서버가 JSON이 아닌 오류(예: 500 플레인 텍스트)를 보낸 경우
  }
  if (!res.ok) {
    throw new Error((data && data.detail) || `요청에 실패했습니다. (${res.status})`);
  }
  return data;
}

function renderAuthView() {
  authView.classList.remove("hidden");
  mainView.classList.add("hidden");
}

const viewLoaders = {
  today: () => {
    loadToday();
    loadEntries();
  },
  notebooks: loadNotebooks,
  pet: loadPetView,
  stats: loadStats,
  exports: loadExportsView,
  settings: loadSettings,
};

function switchView(name) {
  document.querySelectorAll(".tabBtn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.view === name);
  });
  document.querySelectorAll(".view").forEach((section) => {
    section.classList.toggle("hidden", section.id !== `view-${name}`);
  });
  viewLoaders[name]();
}

document.querySelectorAll(".tabBtn").forEach((btn) => {
  btn.addEventListener("click", () => switchView(btn.dataset.view));
});

function renderMainView() {
  authView.classList.add("hidden");
  mainView.classList.remove("hidden");
  switchView("today");
}

document.getElementById("loginBtn").addEventListener("click", async () => {
  hideError(authError);
  const email = document.getElementById("authEmail").value.trim();
  const password = document.getElementById("authPassword").value;
  try {
    const data = await supabaseAuth("/token?grant_type=password", { email, password });
    setToken(data.access_token);
    renderMainView();
  } catch (e) {
    showError(authError, e.message);
  }
});

document.getElementById("signupBtn").addEventListener("click", async () => {
  hideError(authError);
  const email = document.getElementById("authEmail").value.trim();
  const password = document.getElementById("authPassword").value;
  try {
    const data = await supabaseAuth("/signup", { email, password });
    if (data.access_token) {
      setToken(data.access_token);
      renderMainView();
    } else {
      showError(authError, "가입 완료! 이메일 확인 후 로그인해주세요.");
    }
  } catch (e) {
    showError(authError, e.message);
  }
});

document.getElementById("logoutBtn").addEventListener("click", () => {
  setToken(null);
  renderAuthView();
});

document.getElementById("crisisCloseBtn").addEventListener("click", () => {
  crisisModal.classList.add("hidden");
});

async function loadToday() {
  try {
    const status = await api("/entries/today");
    document.getElementById("todayCount").textContent = `${status.today_count}/${status.daily_limit}`;
    const submitBtn = document.getElementById("submitEntryBtn");
    submitBtn.disabled = status.today_count >= status.daily_limit;
  } catch (e) {
    console.error(e);
  }
}

async function loadEntries() {
  const list = document.getElementById("entryList");
  try {
    const entries = await api("/entries");
    if (entries.length === 0) {
      list.innerHTML = '<div style="color:#a79f8f;font-size:13px;">아직 쓴 글이 없어요.</div>';
      return;
    }
    list.innerHTML = entries
      .map(
        (e) => `
      <div class="entry">
        <div class="entry-date">${e.entry_date}</div>
        <div class="entry-title">${e.title || "(제목 없음)"}
          <span class="tag ${e.is_manual_emotion_tag ? "emotion" : "failure"}">
            ${e.is_manual_emotion_tag ? "감정" : "실패"}
          </span>
        </div>
        <div class="entry-content">${escapeHtml(e.content)}</div>
        <button class="secondary delete-btn" data-entry-id="${e.id}" style="margin-top:6px;">삭제</button>
      </div>`
      )
      .join("");
    bindDeleteButtons(loadEntries);
  } catch (e) {
    list.innerHTML = `<div class="error">${e.message}</div>`;
  }
}

function bindDeleteButtons(onDeleted) {
  document.querySelectorAll(".delete-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const ok = await confirmDialog("이 글을 삭제할까요? 삭제하면 되돌릴 수 없어요.");
      if (!ok) return;
      btn.disabled = true;
      try {
        await api(`/entries/${btn.dataset.entryId}`, { method: "DELETE" });
        onDeleted();
      } catch (e) {
        alert(e.message);
        btn.disabled = false;
      }
    });
  });
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

document.getElementById("submitEntryBtn").addEventListener("click", async () => {
  hideError(entryError);
  const title = document.getElementById("entryTitle").value.trim();
  const content = document.getElementById("entryContent").value.trim();
  const isManualEmotionTag = document.getElementById("emotionTag").checked;
  if (!content) {
    showError(entryError, "내용을 입력해주세요.");
    return;
  }
  try {
    const result = await api("/entries", {
      method: "POST",
      body: JSON.stringify({ title, content, is_manual_emotion_tag: isManualEmotionTag }),
    });
    document.getElementById("entryTitle").value = "";
    document.getElementById("entryContent").value = "";
    document.getElementById("emotionTag").checked = false;
    if (result.crisis && result.crisis.is_crisis) {
      crisisModal.classList.remove("hidden");
    }
    loadToday();
    loadEntries();
    checkMilestone();
  } catch (e) {
    showError(entryError, e.message);
  }
});

const MILESTONE_MESSAGES = {
  1: "🎉 첫 기록을 남겼어요. 여기까지 온 것만으로도 잘한 거예요.",
  10: "🎉 벌써 10장째예요. 꾸준히 쓰고 있네요.",
  30: "🎉 30장 달성! 한 달치 실패가 쌓였어요.",
  50: "🎉 50장이에요. 절반을 향해 가고 있어요.",
  100: "🎉 100장 돌파! 이 정도면 책 한 권이에요.",
  155: "🎉 155장, 한 권을 가득 채웠어요. 수고했어요.",
};

async function checkMilestone() {
  try {
    const stats = await api("/stats/overview");
    const message = MILESTONE_MESSAGES[stats.total_entries];
    if (message) showMilestoneToast(message);
  } catch (e) {
    console.error(e);
  }
}

function showMilestoneToast(message) {
  const toast = document.createElement("div");
  toast.className = "milestone-toast";
  toast.textContent = message;
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 3200);
}

const NOTEBOOK_TYPE_LABEL = { failure: "실패작 노트", emotion: "감정 노트" };
const NOTEBOOK_STATUS_LABEL = { in_progress: "작성 중", completed: "완결" };

async function loadNotebooks() {
  const containers = {
    failure: document.getElementById("notebookList-failure"),
    emotion: document.getElementById("notebookList-emotion"),
  };
  try {
    const [notebooks, failureEntries, emotionEntries] = await Promise.all([
      api("/notebooks"),
      api("/entries?notebook_type=failure"),
      api("/entries?notebook_type=emotion"),
    ]);
    const entriesByType = { failure: failureEntries, emotion: emotionEntries };

    for (const type of ["failure", "emotion"]) {
      const list = notebooks.filter((n) => n.type === type).sort((a, b) => a.volume_no - b.volume_no);
      const container = containers[type];
      if (list.length === 0) {
        container.innerHTML = '<div style="color:var(--muted);font-size:13px;">아직 시작된 노트북이 없어요.</div>';
        continue;
      }
      container.innerHTML = list
        .map((nb) => {
          const pct = Math.min(100, Math.round((nb.entry_count / nb.page_limit) * 100));
          const entries = entriesByType[type].filter((e) => e.notebook_id === nb.id);
          const entriesHtml = entries
            .map(
              (e) => `
            <div class="entry">
              <div class="entry-date">${e.entry_date}</div>
              <div class="entry-title">${e.title || "(제목 없음)"}</div>
              <div class="entry-content">${escapeHtml(e.content)}</div>
              <div class="row" style="margin-top:6px;">
                <button class="secondary move-btn" data-entry-id="${e.id}">
                  ${type === "failure" ? "감정 노트로 이동" : "실패작 노트로 이동"}
                </button>
                <button class="secondary delete-btn" data-entry-id="${e.id}">삭제</button>
              </div>
            </div>`
            )
            .join("");
          return `
          <div class="notebook-block">
            <div class="notebook-head">
              <strong>${nb.volume_no}권</strong>
              <span class="tag ${type}">${NOTEBOOK_STATUS_LABEL[nb.status] || nb.status}</span>
              <span style="margin-left:auto;font-size:12px;color:var(--muted);">${nb.entry_count}/${nb.page_limit}</span>
            </div>
            <div class="progress-bar"><div class="progress-fill" style="width:${pct}%;"></div></div>
            ${entriesHtml}
          </div>`;
        })
        .join("");
    }

    document.querySelectorAll(".move-btn").forEach((btn) => {
      btn.addEventListener("click", async () => {
        btn.disabled = true;
        try {
          await api(`/entries/${btn.dataset.entryId}/move`, { method: "POST" });
          loadNotebooks();
        } catch (e) {
          alert(e.message);
          btn.disabled = false;
        }
      });
    });
    bindDeleteButtons(loadNotebooks);
  } catch (e) {
    containers.failure.innerHTML = `<div class="error">${e.message}</div>`;
  }
}

async function loadStats() {
  const body = document.getElementById("statsBody");
  try {
    const stats = await api("/stats/overview");
    const completedRows = Object.entries(stats.completed_notebooks)
      .map(([type, count]) => `<div class="stat-row"><span>${NOTEBOOK_TYPE_LABEL[type] || type} 완결</span><strong>${count}권</strong></div>`)
      .join("");

    const progressRows = Object.entries(stats.current_progress)
      .map(([type, progress]) => {
        if (!progress) {
          return `<div class="stat-row"><span>${NOTEBOOK_TYPE_LABEL[type] || type}</span><span style="color:var(--muted);">진행 중인 노트북 없음</span></div>`;
        }
        const pct = Math.min(100, Math.round((progress.entry_count / progress.page_limit) * 100));
        return `
        <div class="stat-row-block">
          <div class="stat-row"><span>${NOTEBOOK_TYPE_LABEL[type] || type} ${progress.volume_no}권</span><strong>${progress.entry_count}/${progress.page_limit}</strong></div>
          <div class="progress-bar"><div class="progress-fill" style="width:${pct}%;"></div></div>
        </div>`;
      })
      .join("");

    const maxTone = Math.max(1, ...Object.values(stats.tone_category_totals));
    const toneRows = Object.entries(stats.tone_category_totals)
      .map(([category, value]) => {
        const pct = Math.round((value / maxTone) * 100);
        return `
        <div class="stat-row-block">
          <div class="stat-row"><span>${escapeHtml(category)}</span><strong>${value}</strong></div>
          <div class="progress-bar"><div class="progress-fill" style="width:${pct}%;"></div></div>
        </div>`;
      })
      .join("") || '<div style="color:var(--muted);font-size:13px;">아직 분석된 감정 톤이 없어요.</div>';

    body.innerHTML = `
      <div class="stat-row" style="margin-bottom:10px;"><span>총 기록 수</span><strong>${stats.total_entries}장</strong></div>
      <h3 class="card-subtitle">완결한 노트북</h3>
      ${completedRows}
      <h3 class="card-subtitle">진행 중인 노트북</h3>
      ${progressRows}
      <h3 class="card-subtitle">감정 톤 분포</h3>
      ${toneRows}
    `;
  } catch (e) {
    body.innerHTML = `<div class="error">${e.message}</div>`;
  }
}

async function loadExportsView() {
  const select = document.getElementById("exportNotebookSelect");
  const list = document.getElementById("exportList");
  try {
    const notebooks = await api("/notebooks");
    const completed = notebooks.filter((n) => n.status === "completed");
    select.innerHTML = completed.length
      ? completed
          .map((n) => `<option value="${n.id}">${NOTEBOOK_TYPE_LABEL[n.type] || n.type} ${n.volume_no}권</option>`)
          .join("")
      : '<option value="">완결된 노트북이 없어요</option>';
  } catch (e) {
    select.innerHTML = `<option value="">${e.message}</option>`;
  }

  try {
    const exports = await api("/exports");
    list.innerHTML = exports.length
      ? exports
          .map(
            (ex) => `
        <div class="entry">
          <div class="entry-date">${new Date(ex.created_at).toLocaleString()}</div>
          <div class="entry-title">📎 ${ex.binding_style === "kr" ? "가로쓰기" : "세로쓰기"} · ${escapeHtml(ex.cover_theme)}</div>
          <a href="${ex.download_url}" target="_blank" rel="noopener">다운로드해서 스테이플 찍기</a>
        </div>`
          )
          .join("")
      : '<div style="color:var(--muted);font-size:13px;">아직 내보낸 파일이 없어요.</div>';
  } catch (e) {
    list.innerHTML = `<div class="error">${e.message}</div>`;
  }
}

document.getElementById("exportCreateBtn").addEventListener("click", async () => {
  const errorEl = document.getElementById("exportError");
  hideError(errorEl);
  const notebookId = document.getElementById("exportNotebookSelect").value;
  if (!notebookId) {
    showError(errorEl, "출력할 수 있는 완결된 노트북이 없어요.");
    return;
  }
  const bindingStyle = document.getElementById("exportBindingSelect").value;
  const coverTheme = document.getElementById("exportCoverTheme").value.trim() || "mono";
  try {
    await api(`/notebooks/${notebookId}/export`, {
      method: "POST",
      body: JSON.stringify({ binding_style: bindingStyle, cover_theme: coverTheme }),
    });
    loadExportsView();
  } catch (e) {
    showError(errorEl, e.message);
  }
});

async function loadSettings() {
  const errorEl = document.getElementById("settingsError");
  hideError(errorEl);
  try {
    const profile = await api("/account/profile");
    document.getElementById("settingsNickname").value = profile.nickname || "";
    document.getElementById("settingsTimezone").value = profile.timezone || "";
    document.getElementById("settingsAppLock").checked = !!profile.app_lock_enabled;
  } catch (e) {
    showError(errorEl, e.message);
  }
}

document.getElementById("settingsSaveBtn").addEventListener("click", async () => {
  const errorEl = document.getElementById("settingsError");
  hideError(errorEl);
  try {
    await api("/account/profile", {
      method: "PATCH",
      body: JSON.stringify({
        nickname: document.getElementById("settingsNickname").value.trim(),
        timezone: document.getElementById("settingsTimezone").value.trim(),
        app_lock_enabled: document.getElementById("settingsAppLock").checked,
      }),
    });
  } catch (e) {
    showError(errorEl, e.message);
  }
});

document.getElementById("dataExportBtn").addEventListener("click", async () => {
  try {
    const data = await api("/account/data-export");
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `실패작노트_백업_${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  } catch (e) {
    alert(e.message);
  }
});

const PET_MOOD_IMAGES = {
  happy: "/static/mascot_happy.png",
  normal: "/static/mascot_neutral.png",
  sad: "/static/mascot_sad.png",
  angry: "/static/mascot_angry.png",
};
const PET_MOOD_LABELS = {
  happy: "기분이 좋아 보여요",
  normal: "평온해 보여요",
  sad: "조금 외로워 보여요",
  angry: "삐진 것 같아요",
};
const PET_SPEECH_LINES = {
  happy: [
    "루나: 오늘도 당신 덕분에 행복해요!",
    "루나: 꼬리가 멈추질 않아요!",
    "루나: 같이 있어서 좋아요.",
  ],
  normal: [
    "루나: 오늘 하루는 어땠어요?",
    "루나: 곁에 있을게요, 천천히 적어봐요.",
    "루나: 당신의 하루가 궁금해요.",
  ],
  sad: [
    "루나: 요즘 좀 심심했어요...",
    "루나: 보고 싶었어요, 글 좀 써줄래요?",
    "루나: 조금 외로웠어요.",
  ],
  angry: [
    "루나: 흥, 한참 기다렸단 말이에요!",
    "루나: 삐졌어요. 쓰다듬어주세요.",
    "루나: 너무 오랜만이잖아요!",
  ],
};

function renderPetState(pet) {
  document.getElementById("petMascotImg").src = PET_MOOD_IMAGES[pet.mood];
  document.getElementById("petStageLabel").textContent = pet.stage;
  document.getElementById("petLevelLabel").textContent = `Lv.${pet.level} · 루나와 만난 지 ${pet.days_together}일째`;
  document.getElementById("petExpBar").style.width = `${pet.exp}%`;
  document.getElementById("petExpText").textContent = `${pet.exp}/100`;
  document.getElementById("petAffectionBar").style.width = `${pet.affection}%`;
  document.getElementById("petAffectionText").textContent = `${pet.affection}`;
  document.getElementById("petMoodLabel").textContent = PET_MOOD_LABELS[pet.mood] || "";
  const lines = PET_SPEECH_LINES[pet.mood] || [];
  document.getElementById("petSpeechLabel").textContent = lines[Math.floor(Math.random() * lines.length)] || "";
  document.getElementById("petPatCountLabel").textContent = `지금까지 ${pet.total_pats}번 쓰다듬었어요`;
}

async function loadPetView() {
  const errorEl = document.getElementById("petError");
  hideError(errorEl);
  try {
    const pet = await api("/pet");
    renderPetState(pet);
  } catch (e) {
    showError(errorEl, e.message);
  }
}

document.getElementById("petPatBtn").addEventListener("click", async () => {
  const errorEl = document.getElementById("petError");
  hideError(errorEl);
  try {
    const pet = await api("/pet/pat", { method: "POST" });
    renderPetState(pet);
  } catch (e) {
    showError(errorEl, e.message);
  }
});

const MASCOT_WHISPERS = [
  "오늘도 수고했어요.",
  "실패해도 괜찮아요, 다시 쓰면 되니까.",
  "생각보다 잘하고 있어요.",
  "가끔은 그냥 울어도 돼요.",
  "내일은 오늘보다 나을 거예요.",
  "쓰담쓰담...",
  "이 노트는 당신 편이에요.",
];

function setupMascotWhisper(el) {
  if (!el) return;
  let clicks = [];
  el.style.cursor = "pointer";
  el.addEventListener("click", () => {
    const now = Date.now();
    clicks = clicks.filter((t) => now - t < 4000);
    clicks.push(now);
    if (clicks.length >= 5) {
      clicks = [];
      const wrap = el.closest(".mascot-wrap");
      if (!wrap) return;
      wrap.querySelectorAll(".mascot-whisper").forEach((n) => n.remove());
      const bubble = document.createElement("div");
      bubble.className = "mascot-whisper";
      bubble.textContent = MASCOT_WHISPERS[Math.floor(Math.random() * MASCOT_WHISPERS.length)];
      wrap.appendChild(bubble);
      setTimeout(() => bubble.remove(), 2800);
    }
  });
}

setupMascotWhisper(document.getElementById("mascotAvatar"));
setupMascotWhisper(document.getElementById("mascotSplash"));

function showEasterOverlay({ icon, title, body, emojis }) {
  const overlay = document.createElement("div");
  overlay.className = "konami-overlay";
  overlay.innerHTML = `
    <div class="box">
      <div style="font-size:32px;margin-bottom:10px;">${icon}</div>
      <div style="font-weight:700;margin-bottom:6px;">${title}</div>
      <div style="font-size:13px;color:var(--muted);">${body}</div>
    </div>
  `;
  for (let i = 0; i < 18; i++) {
    const sparkle = document.createElement("div");
    sparkle.className = "konami-sparkle";
    sparkle.textContent = emojis[i % emojis.length];
    sparkle.style.left = `${Math.random() * 100}%`;
    sparkle.style.bottom = "0";
    sparkle.style.animationDelay = `${Math.random() * 1.5}s`;
    overlay.appendChild(sparkle);
  }
  overlay.addEventListener("click", () => overlay.remove());
  document.body.appendChild(overlay);
  setTimeout(() => overlay.remove(), 6000);
}

function showKonamiEasterEgg() {
  showEasterOverlay({
    icon: "✨",
    title: "숨겨진 위로를 찾았어요",
    body: "오늘 하루도, 실패해도 괜찮았어요.<br />당신은 이미 충분히 애쓰고 있어요.",
    emojis: ["✨", "💜", "⭐", "🩹"],
  });
}

function showSadEasterEgg() {
  showEasterOverlay({
    icon: "🩹",
    title: "많이 힘들었죠",
    body: "지금은 그냥 쉬어가도 돼요.<br />혼자 견디기 힘들면 109, 자살예방상담전화가 곁에 있어요.",
    emojis: ["💧", "🩹", "🤍", "🫂"],
  });
}

function showLoveEasterEgg() {
  showEasterOverlay({
    icon: "💜",
    title: "토닥토닥",
    body: "오늘 하루도 애쓴 당신, 꼭 안아주고 싶어요.",
    emojis: ["💜", "🩷", "💞", "✨"],
  });
}

function showReverseEasterEgg() {
  document.body.style.transition = "transform 0.4s ease";
  document.body.style.transform = "rotate(180deg)";
  setTimeout(() => {
    document.body.style.transform = "";
  }, 1500);
}

const EASTER_SEQUENCES = [
  {
    keys: ["arrowup", "arrowup", "arrowdown", "arrowdown", "arrowleft", "arrowright", "arrowleft", "arrowright", "b", "a"],
    action: showKonamiEasterEgg,
  },
  { keys: ["s", "a", "d"], action: showSadEasterEgg },
  { keys: ["l", "o", "v", "e"], action: showLoveEasterEgg },
  {
    keys: ["arrowdown", "arrowdown", "arrowup", "arrowup", "arrowright", "arrowleft", "arrowright", "arrowleft", "a", "b"],
    action: showReverseEasterEgg,
  },
];
let easterKeyBuffer = [];

document.addEventListener("keydown", (e) => {
  easterKeyBuffer.push(e.key.toLowerCase());
  if (easterKeyBuffer.length > 20) easterKeyBuffer.shift();

  for (const seq of EASTER_SEQUENCES) {
    const tail = easterKeyBuffer.slice(-seq.keys.length);
    if (tail.length === seq.keys.length && tail.every((k, i) => k === seq.keys[i])) {
      easterKeyBuffer = [];
      seq.action();
      break;
    }
  }
});

if (getToken()) {
  renderMainView();
} else {
  renderAuthView();
}
