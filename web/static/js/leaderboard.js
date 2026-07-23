const SERVER_URL = "https://alien-invasion-1018096304579.asia-east1.run.app";
let pollInterval = null;

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
    if (!data || !data.leaderboard || data.leaderboard.length === 0) {
      lbContent.innerHTML = '<div class="leaderboard-empty">还没有人留下足迹，快去下载游戏打个榜首吧！</div>';
      lbStats.style.display = "none";
      return;
    }

    const rankClasses = { 1: "top1", 2: "top2", 3: "top3" };
    let html = `<table class="leaderboard-table">
      <thead><tr><th>#</th><th>玩家</th><th>分数</th><th>关卡</th></tr></thead><tbody>`;
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
      lbHighestScore.innerText = Number(data.data.highest_score).toLocaleString();
      lbStats.style.display = "flex";
    } else if (data && data.total_players !== undefined) {
      lbPlayerCount.innerText = data.total_players.toLocaleString();
      lbHighestScore.innerText = Number(data.highest_score).toLocaleString();
      lbStats.style.display = "flex";
    }
  }

  async function fetchLeaderboard() {
    try {
      const resp = await fetch(`${SERVER_URL}/api/leaderboard?limit=10`);
      const data = await resp.json();
      if (data.status === "success") {
        renderLeaderboard(data);
        renderStats(data);
      }
    } catch (e) {
      console.error("云端通信失败:", e);
      lbContent.innerHTML = '<div class="leaderboard-empty" style="color: #ef4444;">连接云端服务器失败，请稍后再试。</div>';
    }

    try {
      const resp = await fetch(`${SERVER_URL}/api/stats`);
      const data = await resp.json();
      renderStats(data);
    } catch (e) {}
  }

  if (lbRefreshBtn) {
    lbRefreshBtn.addEventListener("click", () => {
      lbContent.innerHTML = '<div class="leaderboard-empty">正在向云端拉取最新数据...</div>';
      fetchLeaderboard();
    });
  }

  fetchLeaderboard();
  pollInterval = setInterval(fetchLeaderboard, 30000);

  window.addEventListener('beforeunload', () => {
    if (pollInterval) clearInterval(pollInterval);
  });
}

export function cleanupLeaderboard() {
  if (pollInterval) clearInterval(pollInterval);
}

async function updateDownloadLink() {
  try {
    const resp = await fetch('https://api.github.com/repos/sinderson123-afk/alien_invasion/releases/latest');
    const data = await resp.json();
    const exeAsset = data.assets.find(a => a.name.endsWith('.exe'));
    if (exeAsset) {
      const link = document.querySelector('.download-btn');
      if (link) link.href = exeAsset.browser_download_url;
      const verSpan = document.querySelector('.game-card-container span[style*="版本"]');
      if (!verSpan) {
        const spans = document.querySelectorAll('.game-card-container span');
        for (const s of spans) {
          if (s.textContent && s.textContent.includes('版本')) {
            s.textContent = `版本: ${data.tag_name} | 大小: 约 104MB`;
            break;
          }
        }
      } else {
        verSpan.textContent = `版本: ${data.tag_name} | 大小: 约 104MB`;
      }
    }
  } catch (e) {
    /* keep default link */
  }
}

updateDownloadLink();
