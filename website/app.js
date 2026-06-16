const profiles = {
  AAPL: {
    company: "Apple Inc.",
    sector: "Consumer platforms",
    score: 82,
    confidence: 76,
    timing: "Wait",
    action: "Wait",
    actionLabel: "Entry trigger missing",
    gaps: 2,
    evidence: [
      ["Growth quality", 72, "green"],
      ["Moat durability", 88, "blue"],
      ["Valuation discipline", 52, "amber"],
      ["Timing setup", 48, "amber"]
    ],
    thesis: "Research quality remains strong, but the cockpit waits for a cleaner entry trigger.",
    risk: "Multiple expansion depends on services growth and device replacement cycle evidence."
  },
  NVDA: {
    company: "NVIDIA Corporation",
    sector: "AI infrastructure",
    score: 86,
    confidence: 72,
    timing: "Watch",
    action: "Watch",
    actionLabel: "High quality, stretched setup",
    gaps: 3,
    evidence: [
      ["Growth quality", 94, "green"],
      ["Moat durability", 84, "blue"],
      ["Valuation discipline", 34, "red"],
      ["Timing setup", 43, "amber"]
    ],
    thesis: "Business quality is exceptional, while valuation and setup quality need stricter triggers.",
    risk: "Consensus revision risk rises if capacity signals or hyperscaler demand decelerate."
  },
  TSLA: {
    company: "Tesla Inc.",
    sector: "Autos and energy",
    score: 61,
    confidence: 64,
    timing: "Watch",
    action: "Watch",
    actionLabel: "Thesis needs confirmation",
    gaps: 4,
    evidence: [
      ["Growth quality", 55, "amber"],
      ["Moat durability", 66, "blue"],
      ["Valuation discipline", 39, "red"],
      ["Timing setup", 58, "amber"]
    ],
    thesis: "The cockpit keeps research and timing separate because the story is catalyst-heavy.",
    risk: "Margin pressure and delivery mix can overwhelm product-cycle optimism."
  },
  "00700": {
    company: "Tencent Holdings",
    sector: "China internet",
    score: 78,
    confidence: 69,
    timing: "Ready",
    action: "Ready",
    actionLabel: "Sizing still controls risk",
    gaps: 2,
    evidence: [
      ["Growth quality", 74, "green"],
      ["Moat durability", 82, "blue"],
      ["Valuation discipline", 69, "green"],
      ["Timing setup", 73, "green"]
    ],
    thesis: "Research quality and timing are both constructive when source coverage is complete.",
    risk: "Regulatory tone and China risk premium must stay visible in the conclusion."
  }
};

const modeAdjustments = {
  skill: {
    label: "Skill only",
    confidence: -8,
    gaps: 2,
    note: "Uses the public instruction set and user-provided evidence."
  },
  local: {
    label: "Local companion",
    confidence: 4,
    gaps: -1,
    note: "Adds pipeline data, Obsidian context, dashboard write-back, and report quality checks."
  },
  finance: {
    label: "Finance plugin",
    confidence: 9,
    gaps: -2,
    note: "Adds Baseline skills (funda-data, company-valuation, estimate-analysis, stock-correlation, finance-sentiment, sepa-strategy), Conditional skills (yfinance-data, stock-liquidity, earnings-preview, earnings-recap, options-payoff, etf-premium, tradingview-reader, hormuz-strait, twitter-reader, telegram-reader, discord-reader, linkedin-reader, yc-reader, opencli-reader), and Explicit-only skills (startup-analysis, generative-ui, saas-valuation-compression, skill-creator) while keeping source readers read-only and trade execution out of scope."
  }
};

const installCommands = {
  codex: {
    label: "Codex local skill",
    command: "mkdir -p ~/.codex/skills\ncp -R skills/stock-research-cockpit ~/.codex/skills/"
  },
  agents: {
    label: "Agents local skill",
    command: "mkdir -p ~/.agents/skills\ncp -R skills/stock-research-cockpit ~/.agents/skills/"
  },
  repo: {
    label: "Repo local skill",
    command: "git clone https://github.com/oliwill/Insight.git\ncd Insight\n# Keep skills/stock-research-cockpit/ in place and let your agent index repo-local skills."
  },
  finance: {
    label: "Finance companion plugin",
    command: "npx plugins add himself65/finance-skills\n# Provides six groups: market-analysis, data-providers, social-readers, startup-tools, ui-tools, skill-creator.\n# Policy: Baseline for full public-equity analysis, Conditional when triggered, Explicit-only when requested.\n# Keep source readers read-only; do not post, write externally, or execute trades."
  }
};

const form = document.querySelector("#research-form");
const tickerInput = document.querySelector("#ticker-input");
const companyName = document.querySelector("#company-name");
const timingPill = document.querySelector("#timing-pill");
const scoreValue = document.querySelector("#score-value");
const scoreLabel = document.querySelector("#score-label");
const confidenceValue = document.querySelector("#confidence-value");
const confidenceLabel = document.querySelector("#confidence-label");
const actionValue = document.querySelector("#action-value");
const actionLabel = document.querySelector("#action-label");
const gapValue = document.querySelector("#gap-value");
const gapLabel = document.querySelector("#gap-label");
const evidenceList = document.querySelector("#evidence-list");
const modeCaption = document.querySelector("#mode-caption");
const chartCaption = document.querySelector("#chart-caption");
const reportOutput = document.querySelector("#report-output");
const updatedAt = document.querySelector("#updated-at");
const installCommand = document.querySelector("#install-command");
const activeInstallLabel = document.querySelector("#active-install-label");
const copyInstall = document.querySelector("#copy-install");
const canvas = document.querySelector("#price-canvas");
const ctx = canvas.getContext("2d");

let activeInstall = "codex";

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function normalizeTicker(value) {
  return value.trim().toUpperCase().replace(/[^A-Z0-9.]/g, "").slice(0, 16) || "AAPL";
}

function fallbackProfile(ticker) {
  const seed = Array.from(ticker).reduce((sum, char) => sum + char.charCodeAt(0), 0);
  const score = 48 + (seed % 38);
  const confidence = 54 + (seed % 24);
  const timing = score > 76 ? "Wait" : score > 58 ? "Watch" : "Avoid";
  return {
    company: `${ticker} Research Target`,
    sector: "Unclassified watchlist",
    score,
    confidence,
    timing,
    action: timing,
    actionLabel: timing === "Avoid" ? "Data gap too large" : "Needs source confirmation",
    gaps: 4,
    evidence: [
      ["Growth quality", clamp(score - 8, 20, 90), "amber"],
      ["Moat durability", clamp(score + 2, 20, 90), "blue"],
      ["Valuation discipline", clamp(score - 14, 20, 88), score > 72 ? "green" : "amber"],
      ["Timing setup", clamp(score - 20, 18, 82), timing === "Avoid" ? "red" : "amber"]
    ],
    thesis: "The cockpit can structure the question, but it should not overstate conclusions until sources are attached.",
    risk: "Unknown source coverage can turn a clean-looking summary into false precision."
  };
}

function getMode() {
  return new FormData(form).get("mode") || "skill";
}

function getSources() {
  return Array.from(form.querySelectorAll('input[name="source"]:checked')).map((input) => input.value);
}

function scoreBand(score) {
  if (score >= 75) return "High conviction";
  if (score >= 60) return "Standard candidate";
  if (score >= 45) return "Watchlist";
  return "Pass";
}

function sourcePenalty(sources) {
  const missing = 4 - sources.length;
  return {
    confidence: missing * -5,
    gaps: missing
  };
}

function currentProfile() {
  const ticker = normalizeTicker(tickerInput.value);
  const base = profiles[ticker] || fallbackProfile(ticker);
  const mode = getMode();
  const sources = getSources();
  const modeAdjustment = modeAdjustments[mode];
  const sourceAdjustment = sourcePenalty(sources);
  const confidence = clamp(base.confidence + modeAdjustment.confidence + sourceAdjustment.confidence, 28, 96);
  const gaps = clamp(base.gaps + modeAdjustment.gaps + sourceAdjustment.gaps, 0, 8);
  const score = clamp(base.score + (mode === "finance" ? 2 : 0), 0, 100);

  return {
    ...base,
    ticker,
    mode,
    modeLabel: modeAdjustment.label,
    modeNote: modeAdjustment.note,
    sources,
    confidence,
    gaps,
    score
  };
}

function updateStatePill(timing) {
  timingPill.className = "state-pill";
  const key = timing.toLowerCase();
  if (["ready", "watch", "avoid"].includes(key)) {
    timingPill.classList.add(key);
  }
  timingPill.textContent = `Timing: ${timing}`;
}

function renderEvidence(profile) {
  evidenceList.innerHTML = "";
  profile.evidence.forEach(([label, value, tone]) => {
    const item = document.createElement("div");
    item.className = "evidence-item";
    item.innerHTML = `
      <div class="evidence-row">
        <span>${label}</span>
        <span>${value}%</span>
      </div>
      <div class="bar-track" aria-hidden="true">
        <div class="bar-fill ${tone}" style="width: ${value}%"></div>
      </div>
    `;
    evidenceList.appendChild(item);
  });
}

function renderReport(profile) {
  const missingSources = ["fundamentals", "price", "news", "sentiment"].filter(
    (source) => !profile.sources.includes(source)
  );
  const dataGapLine = missingSources.length
    ? `Missing or thin coverage: ${missingSources.join(", ")}.`
    : "Core source coverage is present; still disclose stale or unavailable feeds.";

  reportOutput.textContent = `# ${profile.ticker} ${profile.company}

Mode: ${profile.modeLabel}
Research Score: ${profile.score} (${scoreBand(profile.score)})
Timing State: ${profile.timing}
Primary action: ${profile.action} - ${profile.actionLabel}

Question:
${document.querySelector("#question-input").value.trim()}

Main read:
${profile.thesis}

Evidence discipline:
- ${profile.modeNote}
- Finance plugin taxonomy: Baseline / Conditional / Explicit-only; source readers are read-only and never execute trades.
- Data gaps: ${profile.gaps}. ${dataGapLine}
- Research Score and Timing State are intentionally separate.

Risk to monitor:
${profile.risk}

Next move:
Attach current evidence, rerun the cockpit, then only write back to Obsidian when persistence is explicitly wanted.`;
}

function chartSeries(profile) {
  const seed = Array.from(profile.ticker).reduce((sum, char) => sum + char.charCodeAt(0), 0);
  const points = [];
  let value = 48 + (seed % 24);
  for (let index = 0; index < 44; index += 1) {
    const drift = (profile.score - 62) / 55;
    const wave = Math.sin((index + seed) / 3.2) * 3.8 + Math.cos((index + seed) / 5.1) * 2.1;
    value = clamp(value + drift + wave * 0.18, 20, 92);
    points.push(value);
  }
  return points;
}

function drawChart(profile) {
  const rect = canvas.getBoundingClientRect();
  const ratio = window.devicePixelRatio || 1;
  canvas.width = Math.max(320, Math.floor(rect.width * ratio));
  canvas.height = Math.max(240, Math.floor(rect.height * ratio));
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);

  const width = rect.width;
  const height = rect.height;
  const padding = 28;
  const points = chartSeries(profile);
  const usableWidth = width - padding * 2;
  const usableHeight = height - padding * 2;

  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = "#fbfcf7";
  ctx.fillRect(0, 0, width, height);

  ctx.strokeStyle = "#d8ded4";
  ctx.lineWidth = 1;
  for (let i = 0; i < 5; i += 1) {
    const y = padding + (usableHeight / 4) * i;
    ctx.beginPath();
    ctx.moveTo(padding, y);
    ctx.lineTo(width - padding, y);
    ctx.stroke();
  }

  const readyY = padding + usableHeight * 0.32;
  const avoidY = padding + usableHeight * 0.72;
  ctx.fillStyle = "rgba(11, 122, 89, 0.08)";
  ctx.fillRect(padding, padding, usableWidth, readyY - padding);
  ctx.fillStyle = "rgba(179, 58, 50, 0.08)";
  ctx.fillRect(padding, avoidY, usableWidth, height - avoidY - padding);

  ctx.beginPath();
  points.forEach((point, index) => {
    const x = padding + (usableWidth / (points.length - 1)) * index;
    const y = padding + usableHeight - (point / 100) * usableHeight;
    if (index === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.strokeStyle = profile.timing === "Ready" ? "#0b7a59" : profile.timing === "Avoid" ? "#b33a32" : "#245ea8";
  ctx.lineWidth = 3;
  ctx.stroke();

  const last = points[points.length - 1];
  const lastX = width - padding;
  const lastY = padding + usableHeight - (last / 100) * usableHeight;
  ctx.fillStyle = "#171b1f";
  ctx.beginPath();
  ctx.arc(lastX, lastY, 5, 0, Math.PI * 2);
  ctx.fill();

  ctx.fillStyle = "#5e6872";
  ctx.font = "12px JetBrains Mono, IBM Plex Mono, monospace";
  ctx.fillText("Ready zone", padding + 8, padding + 18);
  ctx.fillText("Risk zone", padding + 8, height - padding - 8);
}

function render() {
  const profile = currentProfile();
  tickerInput.value = profile.ticker;
  companyName.textContent = profile.company;
  scoreValue.textContent = profile.score;
  scoreLabel.textContent = scoreBand(profile.score);
  confidenceValue.textContent = `${profile.confidence}%`;
  confidenceLabel.textContent = profile.confidence > 78 ? "Source coverage strong" : "Source coverage medium";
  actionValue.textContent = profile.action;
  actionLabel.textContent = profile.actionLabel;
  gapValue.textContent = profile.gaps;
  gapLabel.textContent = profile.gaps > 3 ? "Needs disclosure" : "Disclosed before conclusion";
  modeCaption.textContent = profile.modeLabel;
  chartCaption.textContent = `${profile.ticker} sample path`;
  updatedAt.textContent = `Updated ${new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`;
  updateStatePill(profile.timing);
  renderEvidence(profile);
  renderReport(profile);
  drawChart(profile);
}

function setTab(tabName) {
  document.querySelectorAll(".tab").forEach((tab) => {
    const active = tab.dataset.tab === tabName;
    tab.classList.toggle("is-active", active);
    tab.setAttribute("aria-selected", String(active));
  });
  document.querySelectorAll(".tab-panel").forEach((panel) => {
    panel.classList.toggle("is-active", panel.dataset.panel === tabName);
  });
}

function setInstall(type) {
  activeInstall = type;
  document.querySelectorAll(".install-option").forEach((option) => {
    option.classList.toggle("is-active", option.dataset.install === type);
  });
  installCommand.textContent = installCommands[type].command;
  activeInstallLabel.textContent = installCommands[type].label;
}

async function copyText(text) {
  if (navigator.clipboard && window.isSecureContext) {
    await navigator.clipboard.writeText(text);
    return;
  }
  const area = document.createElement("textarea");
  area.value = text;
  area.setAttribute("readonly", "");
  area.style.position = "fixed";
  area.style.opacity = "0";
  document.body.appendChild(area);
  area.select();
  document.execCommand("copy");
  document.body.removeChild(area);
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  render();
});

form.addEventListener("input", () => {
  render();
});

document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => setTab(tab.dataset.tab));
});

document.querySelectorAll(".install-option").forEach((option) => {
  option.addEventListener("click", () => setInstall(option.dataset.install));
});

copyInstall.addEventListener("click", async () => {
  await copyText(installCommands[activeInstall].command);
  copyInstall.textContent = "Copied";
  window.setTimeout(() => {
    copyInstall.textContent = "Copy command";
  }, 1400);
});

window.addEventListener("resize", () => drawChart(currentProfile()));

setInstall(activeInstall);
render();
