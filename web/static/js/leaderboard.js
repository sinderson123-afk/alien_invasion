const SERVER_URL = "https://alien-invasion-1018096304579.asia-east1.run.app";
let pollInterval = null;

const MIRROR_BASES = [
  "https://gh.llkk.cc/",
  "https://github.akams.cn/",
  "https://gh-proxy.com/",
];

const GITHUB_RELEASE_BASE =
  "https://github.com/sinderson123-afk/alien_invasion/releases/download";

// ─── Speed test ──────────────────────────────────────────────

async function probeURL(url, timeout = 7000) {
  return new Promise((resolve) => {
    const start = performance.now();
    const xhr = new XMLHttpRequest();
    const timer = setTimeout(() => resolve(Infinity), timeout);
    xhr.onreadystatechange = () => {
      if (xhr.readyState >= 3) {
        clearTimeout(timer);
        resolve(performance.now() - start);
        xhr.abort();
      }
    };
    xhr.onerror = xhr.ontimeout = xhr.onabort = () => {
      clearTimeout(timer);
      resolve(Infinity);
    };
    xhr.open("GET", url, true);
    xhr.timeout = timeout;
    xhr.send();
  });
}

async function pickFastestDownload(tag) {
  const basename = `/AlienInvasion.exe`;
  const directUrl = `${GITHUB_RELEASE_BASE}/${tag}${basename}`;
  const fullPath = `${GITHUB_RELEASE_BASE}/${tag}${basename}`;

  const sources = [
    { name: "GitHub Direct", build: () => directUrl },
    ...MIRROR_BASES.map((base) => ({
      name: new URL(base).hostname,
      build: () => base + fullPath,
    })),
  ];

  const probes = sources.map(async (src) => {
    const url = src.build();
    const ms = await probeURL(url);
    return { name: src.name, url, ms };
  });

  const results = await Promise.all(probes);
  results.sort((a, b) => a.ms - b.ms);

  const winner = results[0];
  if (winner.ms === Infinity) {
    return { url: directUrl, results: [] };
  }
  return { url: winner.url, results };
}

// ─── Download button ─────────────────────────────────────────

async function updateDownloadLink() {
  const btn = document.querySelector(".download-btn");
  if (!btn) return;

  const originalHTML = btn.innerHTML;

  try {
    const vResp = await fetch("/version.json");
    const verData = await vResp.json();
    const tag = verData.latest;

    btn.innerHTML =
      '<span style="font-size:13px;">⏳ Testing mirrors...</span>';
    btn.style.pointerEvents = "none";
    btn.style.opacity = "0.7";

    const { url, results } = await pickFastestDownload(tag);

    btn.href = url;
    btn.innerHTML = originalHTML;
    btn.style.pointerEvents = "";
    btn.style.opacity = "";
    btn.title =
      "Fastest: " +
      results
        .slice(0, 3)
        .map((r) => `${r.name} (${r.ms.toFixed(0)}ms)`)
        .join(" | ");

    const verSpan = document.querySelector(
      '.game-card-container span[style*="版本"]'
    );
    const text = `版本: ${tag} | 大小: 约 104MB`;
    if (verSpan) {
      verSpan.textContent = text;
    } else {
      const spans = document.querySelectorAll(".game-card-container span");
      for (const s of spans) {
        if (s.textContent && s.textContent.startsWith("版本")) {
          s.textContent = text;
          break;
        }
      }
    }
  } catch (e) {
    btn.innerHTML = originalHTML;
    btn.style.pointerEvents = "";
    btn.style.opacity = "";
  }
}

// ─── Leaderboard ─────────────────────────────────────────────

export function initLeaderboard() {
  const lbContent = document.getElementById("leaderboard-content");
  const lbStats = document.getElementById("leaderboard-stats");
  const lbPlayerCount = document.getElementById("lb-player-count");
  const lbHighestScore = document.getElementById("lb-highest-score");
  const lbRefreshBtn = document.getElementById("leaderboard-refresh-btn");

  function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  }

  function renderLeaderboard(data) {
    if (
      !data ||
      !data.leaderboard ||
      data.leaderboard.length === 0
    ) {
      lbContent.innerHTML =
        '<div class="leaderboard-empty">No records yet. Download and claim the top spot!</div>';
      lbStats.style.display = "none";
      return;
    }

    const rankClasses = { 1: "top1", 2: "top2", 3: "top3" };
    let html = `<table class="leaderboard-table">
      <thead><tr><th>#</th><th>Player</th><th>Score</th><th>Level</th></tr></thead><tbody>`;
    data.leaderboard.forEach((entry, idx) => {
      const rank = idx + 1;
      const rankCls = rankClasses[rank] || "";
      const name = escapeHtml(entry.player_name || entry.username);
      const score = Number(entry.score).toLocaleString();
      html += `<tr>
        <td class="lb-rank ${rankCls}">${rank}</td>
        <td class="lb-name">${name}</td>
        <td class="lb-score">${score}</td>
        <td class="lb-level">Lv.${entry.level}</td>
      </tr>`;
    });
    html += "</tbody></table>";
    lbContent.innerHTML = html;
  }

  function renderStats(data) {
    if (data && data.status === "success" && data.data) {
      lbPlayerCount.innerText = data.data.player_count.toLocaleString();
      lbHighestScore.innerText = Number(
        data.data.highest_score
      ).toLocaleString();
      lbStats.style.display = "flex";
    } else if (data && data.total_players !== undefined) {
      lbPlayerCount.innerText = data.total_players.toLocaleString();
      lbHighestScore.innerText = Number(
        data.highest_score
      ).toLocaleString();
      lbStats.style.display = "flex";
    }
  }

  async function fetchLeaderboard() {
    try {
      const resp = await fetch(
        `${SERVER_URL}/api/leaderboard?limit=10`
      );
      const data = await resp.json();
      if (data.status === "success") {
        renderLeaderboard(data);
        renderStats(data);
      }
    } catch (e) {
      console.error("Leaderboard fetch failed:", e);
      lbContent.innerHTML =
        '<div class="leaderboard-empty" style="color: #ef4444;">Could not connect to server. Please try again later.</div>';
    }

    try {
      const resp = await fetch(`${SERVER_URL}/api/stats`);
      const data = await resp.json();
      renderStats(data);
    } catch (e) {}
  }

  if (lbRefreshBtn) {
    lbRefreshBtn.addEventListener("click", () => {
      lbContent.innerHTML =
        '<div class="leaderboard-empty">Fetching latest data...</div>';
      fetchLeaderboard();
    });
  }

  fetchLeaderboard();
  pollInterval = setInterval(fetchLeaderboard, 30000);

  window.addEventListener("beforeunload", () => {
    if (pollInterval) clearInterval(pollInterval);
  });
}

export function cleanupLeaderboard() {
  if (pollInterval) clearInterval(pollInterval);
}

// ─── Init on load ────────────────────────────────────────────

updateDownloadLink();
