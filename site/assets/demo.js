const STORAGE_KEY = "pelumas-demo-lang";
const LANGS = ["id", "en"];

const state = {
  data: null,
  i18n: null,
  lang: "id",
  scenario: null,
  index: 0,
  timer: null,
  playing: false,
  lastTrace: null,
};

const el = (id) => document.getElementById(id);

function t(key, replacements = {}) {
  const table = (state.i18n && state.i18n[state.lang]) || {};
  const fallback = (state.i18n && state.i18n.id) || {};
  let text = table[key] ?? fallback[key] ?? key;
  for (const [name, value] of Object.entries(replacements)) {
    text = text.replaceAll(`{${name}}`, String(value));
  }
  return text;
}

function resolveLang() {
  const fromQuery = new URLSearchParams(window.location.search).get("lang");
  if (fromQuery && LANGS.includes(fromQuery)) return fromQuery;
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored && LANGS.includes(stored)) return stored;
  const browser = (navigator.language || "").slice(0, 2).toLowerCase();
  if (LANGS.includes(browser)) return browser;
  return "id";
}

async function init() {
  const [transcripts, i18n] = await Promise.all([
    fetch("assets/transcripts.json", { cache: "no-store" }).then((r) => r.json()),
    fetch("assets/i18n.json", { cache: "no-store" }).then((r) => r.json()),
  ]);
  state.data = transcripts;
  state.i18n = i18n;
  state.lang = resolveLang();

  bindLangSwitch();
  applyLang(state.lang);
  selectScenario(state.data.scenarios[0].id);
  bindControls();
}

function bindLangSwitch() {
  document.querySelectorAll(".lang-btn").forEach((button) => {
    button.addEventListener("click", () => setLang(button.dataset.lang));
  });
}

function setLang(lang) {
  if (!LANGS.includes(lang) || lang === state.lang) return;
  state.lang = lang;
  localStorage.setItem(STORAGE_KEY, lang);
  const url = new URL(window.location.href);
  url.searchParams.set("lang", lang);
  window.history.replaceState({}, "", url);
  applyLang(lang);
  rerender();
}

function applyLang(lang) {
  document.documentElement.lang = lang;
  document.querySelectorAll("[data-i18n]").forEach((node) => {
    node.textContent = t(node.dataset.i18n);
  });
  document.querySelectorAll("[data-i18n-attr]").forEach((node) => {
    const [attr, key] = node.dataset.i18nAttr.split(":");
    node.setAttribute(attr, t(key));
  });
  document.querySelectorAll(".lang-btn").forEach((button) => {
    button.setAttribute("aria-pressed", String(button.dataset.lang === lang));
  });
  document.title = t("meta.title");
}

function scenarioTitle(scenario) {
  return state.lang === "en" ? scenario.title_en || scenario.title : scenario.title;
}

function scenarioSubtitle(scenario) {
  return state.lang === "en" ? scenario.subtitle_en || scenario.subtitle : scenario.subtitle;
}

function messageText(message) {
  return state.lang === "en" ? message.text_en || message.text : message.text;
}

function buyerCount(scenario) {
  return scenario.messages.filter((m) => m.role === "buyer").length;
}

function renderScenarioList() {
  const list = el("scenario-list");
  list.innerHTML = "";
  for (const scenario of state.data.scenarios) {
    const button = document.createElement("button");
    button.className = "scenario-btn";
    button.type = "button";
    button.setAttribute("aria-pressed", String(state.scenario && scenario.id === state.scenario.id));
    button.dataset.id = scenario.id;
    button.innerHTML = `<b>${scenario.order}. ${escapeHtml(scenarioTitle(scenario))}</b><span>${escapeHtml(scenarioSubtitle(scenario))}</span>`;
    button.addEventListener("click", () => selectScenario(scenario.id));
    list.appendChild(button);
  }
}

function renderGuardTable() {
  const body = el("guard-table").querySelector("tbody");
  body.innerHTML = "";
  for (const proof of state.data.guard_proofs || []) {
    const english = state.lang === "en";
    const attempt = english ? proof.attempt_en || proof.attempt : proof.attempt;
    const replacement = english
      ? proof.replacement_en ?? proof.replacement
      : proof.replacement;
    const row = document.createElement("tr");
    const status = proof.blocked
      ? `<span class="strike">${escapeHtml(attempt)}</span>`
      : `<span class="repl">${escapeHtml(attempt)}</span>`;
    const outcome = proof.blocked
      ? `<span class="repl">${escapeHtml(replacement || "")}</span>`
      : `<span class="ok">${escapeHtml(t("guard.allowedAdmin"))}</span>`;
    row.innerHTML = `<td class="mono">${escapeHtml(proof.rule)}</td><td>${status}</td><td>${outcome}</td>`;
    body.appendChild(row);
  }
}

function selectScenario(id) {
  stopTimer();
  state.scenario = state.data.scenarios.find((item) => item.id === id);
  state.index = 0;
  state.lastTrace = null;
  el("chat-body").innerHTML = "";
  renderScenarioList();
  updateChatSub();
  resetInspector();
  updateProgress();
}

function updateChatSub() {
  if (!state.scenario) {
    el("chat-sub").textContent = t("chat.subEmpty");
    return;
  }
  el("chat-sub").textContent = t("chat.sub", { n: buyerCount(state.scenario) });
}

function bindControls() {
  el("btn-play").addEventListener("click", () => (state.playing ? stopTimer() : startPlaying()));
  el("btn-step").addEventListener("click", () => {
    stopTimer();
    step();
  });
  el("btn-replay").addEventListener("click", () => selectScenario(state.scenario.id));
  el("speed").addEventListener("change", () => {
    if (state.playing) {
      stopTimer();
      startPlaying();
    }
  });
}

function startPlaying() {
  if (state.index >= state.scenario.messages.length) {
    state.index = 0;
    state.lastTrace = null;
    el("chat-body").innerHTML = "";
    resetInspector();
    updateProgress();
  }
  state.playing = true;
  el("btn-play").textContent = t("btn.pause");
  scheduleNext();
}

function scheduleNext() {
  const delay = Number(el("speed").value);
  state.timer = setTimeout(() => {
    step();
    if (state.playing) {
      if (state.index >= state.scenario.messages.length) {
        stopTimer();
      } else {
        scheduleNext();
      }
    }
  }, delay);
}

function stopTimer() {
  state.playing = false;
  if (state.timer) {
    clearTimeout(state.timer);
    state.timer = null;
  }
  const playButton = el("btn-play");
  if (playButton) playButton.textContent = t("btn.play");
}

function step() {
  if (!state.scenario) return;
  if (state.index >= state.scenario.messages.length) return;
  const message = state.scenario.messages[state.index];
  state.index += 1;
  if (message.role === "trace") {
    state.lastTrace = message;
    renderTrace(message);
  } else {
    appendBubble(message);
  }
  updateProgress();
}

function rerender() {
  renderScenarioList();
  renderGuardTable();
  updateChatSub();
  const body = el("chat-body");
  body.innerHTML = "";
  for (let i = 0; i < state.index; i += 1) {
    const message = state.scenario.messages[i];
    if (message.role !== "trace") appendBubble(message);
  }
  if (state.lastTrace) renderTrace(state.lastTrace);
  else resetInspector();
  updateProgress();
  el("btn-play").textContent = state.playing ? t("btn.pause") : t("btn.play");
}

function bubbleLabel(message) {
  if (message.role === "buyer") return t("who.buyer");
  if (message.role === "admin") {
    return message.origin ? t("who.admin") : t("who.adminHandoff");
  }
  return message.origin === "eta-follow-up" ? t("who.etaFollowUp") : t("who.agent");
}

function appendBubble(message) {
  const body = el("chat-body");
  const english = state.lang === "en";
  const primary = messageText(message);

  if (message.role === "clock") {
    const marker = document.createElement("div");
    marker.className = "clock-marker";
    marker.textContent = primary;
    body.appendChild(marker);
    body.scrollTop = body.scrollHeight;
    return;
  }

  const bubble = document.createElement("div");
  bubble.className = `bubble ${message.role}`;
  const original =
    english && message.text && message.text_en && message.text_en !== message.text
      ? `<span class="original-text">${escapeHtml(t("original.label"))}: ${escapeHtml(message.text)}</span>`
      : "";
  bubble.innerHTML = `<span class="who">${escapeHtml(bubbleLabel(message))}</span>${escapeHtml(primary)}${original}`;

  if (message.guard && message.role === "agent") {
    const badge = document.createElement("span");
    badge.className = `guard-badge ${message.guard.passed ? "pass" : "fail"}`;
    badge.textContent = message.guard.passed
      ? message.origin === "admin-relay"
        ? t("badge.passAdmin")
        : t("badge.pass")
      : t("badge.blocked", { rule: message.guard.rule });
    bubble.appendChild(badge);
  }

  body.appendChild(bubble);
  body.scrollTop = body.scrollHeight;
}

function renderTrace(trace) {
  el("stage-pill").textContent = trace.stage;

  const toolList = el("tool-list");
  if (trace.tools.length === 0) {
    toolList.innerHTML = `<span class="empty">${escapeHtml(t("empty.toolsStep"))}</span>`;
  } else {
    toolList.innerHTML = "";
    for (const tool of trace.tools) {
      const card = document.createElement("div");
      card.className = "tool-card";
      card.innerHTML = `
        <span class="name">${escapeHtml(tool.name)}()</span>
        <details>
          <summary>${escapeHtml(t("tool.argsAndResult"))}</summary>
          <pre>${escapeHtml(JSON.stringify(tool.arguments, null, 2))}\n\n→ ${escapeHtml(JSON.stringify(tool.result, null, 2))}</pre>
        </details>`;
      toolList.appendChild(card);
    }
  }

  const guardList = el("guard-list");
  const scenarioGuards = state.scenario.guard_blocks || [];
  if (scenarioGuards.length === 0) {
    guardList.innerHTML = `<span class="empty">${escapeHtml(t("empty.guardStep"))}</span>`;
  } else {
    guardList.innerHTML = "";
    for (const guard of scenarioGuards) {
      const card = document.createElement("div");
      card.className = "guard-card";
      const rules = (guard.rules || []).join(", ") || "guard";
      card.innerHTML = `
        <span class="label">${escapeHtml(t("guard.labelBlocked", { rules }))}</span>
        <span class="attempt">${escapeHtml(guard.blocked)}</span>`;
      guardList.appendChild(card);
    }
  }

  const rfqCard = el("rfq-card");
  if (state.scenario.rfq) {
    const rfq = state.scenario.rfq;
    const items = (rfq.items || [])
      .map((item) => `${escapeHtml(item.part_no || item.name || "?")} × ${escapeHtml(String(item.qty ?? "?"))}`)
      .join("<br>");
    const statusKey = `status.${rfq.status}`;
    const statusText = t(statusKey);
    const buyerKey = `buyerType.${rfq.buyer_type}`;
    rfqCard.innerHTML = `
      <dl class="rfq-card">
        <dt>${escapeHtml(t("rfq.id"))}</dt><dd class="mono">${escapeHtml(rfq.id)}</dd>
        <dt>${escapeHtml(t("rfq.status"))}</dt><dd>${escapeHtml(statusText === statusKey ? rfq.status : statusText)}</dd>
        <dt>${escapeHtml(t("rfq.buyerType"))}</dt><dd>${escapeHtml(t(buyerKey) === buyerKey ? rfq.buyer_type : t(buyerKey))}</dd>
        <dt>${escapeHtml(t("rfq.items"))}</dt><dd>${items || "—"}</dd>
        <dt>${escapeHtml(t("rfq.city"))}</dt><dd>${escapeHtml(rfq.delivery_city || "—")}</dd>
        <dt>${escapeHtml(t("rfq.price"))}</dt><dd>${rfq.quoted_total ? escapeHtml(rfq.quoted_total) : escapeHtml(t("rfq.notYet"))}</dd>
      </dl>`;
  } else if (state.index >= state.scenario.messages.length) {
    rfqCard.innerHTML = `<span class="empty">${escapeHtml(t("empty.rfqNone"))}</span>`;
  }
}

function resetInspector() {
  el("stage-pill").textContent = "—";
  el("tool-list").innerHTML = `<span class="empty">${escapeHtml(t("empty.tools"))}</span>`;
  el("guard-list").innerHTML = `<span class="empty">${escapeHtml(t("empty.guard"))}</span>`;
  el("rfq-card").innerHTML = `<span class="empty">${escapeHtml(t("empty.rfq"))}</span>`;
}

function updateProgress() {
  const total = state.scenario ? state.scenario.messages.length : 0;
  el("progress-chip").textContent = `${state.index} / ${total}`;
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

init().catch((error) => {
  el("chat-body").innerHTML = `<div class="bubble agent">${escapeHtml(t("error.load", { message: error.message }))}</div>`;
});
