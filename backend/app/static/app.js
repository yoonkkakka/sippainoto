const SUPABASE_URL = "https://zvxggmvwrqbntywpbcso.supabase.co";
const SUPABASE_ANON_KEY = "sb_publishable_nLN5GjNJ5MEPY83o46UQVA_hm_pHsAV";

const authView = document.getElementById("authView");
const mainView = document.getElementById("mainView");
const authError = document.getElementById("authError");
const entryError = document.getElementById("entryError");
const crisisModal = document.getElementById("crisisModal");

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

function renderMainView() {
  authView.classList.add("hidden");
  mainView.classList.remove("hidden");
  loadToday();
  loadEntries();
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
      </div>`
      )
      .join("");
  } catch (e) {
    list.innerHTML = `<div class="error">${e.message}</div>`;
  }
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
  } catch (e) {
    showError(entryError, e.message);
  }
});

if (getToken()) {
  renderMainView();
} else {
  renderAuthView();
}
