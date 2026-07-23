const Game = {
  isRunning: true,
  gameTime: 0,
  collectedCount: 0,
  gameTotalCount: 0,
  currentFullQuote: "",
  currentQuoteCharacters: [],
  letters: [],
  particles: [],
  letterSpawnTimer: 0,
  SEASON_DURATION: 1500,
  userInteracted: false,

  traveler: {
    x: 80,
    y: 130,
    vy: 0,
    gravity: 0.45,
    isJumping: false,
    width: 20,
    height: 30
  },

  gameQuotes: [
    "愿你在漫长的四季流转中，活成自己喜欢的模样。",
    "今天的阳光很温柔，愿你也能被温柔以待。",
    "慢品人间烟火色，闲观万事岁月长。",
    "愿所有美好，都如期而至，温暖如初。",
    "无论晴雨，愿你的心里始终有一片晴空。",
    "时间很长，风景很美，慢慢走，别着急。",
    "生活明朗，万物可爱，愿你今天顺心如意。"
  ],

  seasonColors: [
    {
      skyTop: "#eef2ff", skyBottom: "#fce7f3",
      hillFar: "#c7d2fe", hillNear: "#fbcfe8",
      foliage: "#f472b6", ground: "#d9f99d",
      particleColor: "#f472b6", particleType: "blossom"
    },
    {
      skyTop: "#e0f2fe", skyBottom: "#bae6fd",
      hillFar: "#7dd3fc", hillNear: "#38bdf8",
      foliage: "#10b981", ground: "#a7f3d0",
      particleColor: "#34d399", particleType: "leaf"
    },
    {
      skyTop: "#fef3c7", skyBottom: "#ffedd5",
      hillFar: "#fcd34d", hillNear: "#fdba74",
      foliage: "#f97316", ground: "#fef08a",
      particleColor: "#f97316", particleType: "maple"
    },
    {
      skyTop: "#ecfeff", skyBottom: "#e2e8f0",
      hillFar: "#cbd5e1", hillNear: "#94a3b8",
      foliage: "#e2e8f0", ground: "#ffffff",
      particleColor: "#ffffff", particleType: "snowflake"
    }
  ],

  internalWidth: 800,
  internalHeight: 180,
  canvas: null,
  ctx: null,

  /* Season color interpolation */
  hexToRgb(hex) {
    const bigint = parseInt(hex.slice(1), 16);
    return { r: (bigint >> 16) & 255, g: (bigint >> 8) & 255, b: bigint & 255 };
  },

  lerpColor(hex1, hex2, factor) {
    const r1 = this.hexToRgb(hex1);
    const r2 = this.hexToRgb(hex2);
    const r = r1.r + (r2.r - r1.r) * factor;
    const g = r1.g + (r2.g - r1.g) * factor;
    const b = r1.b + (r2.b - r1.b) * factor;
    return `rgb(${Math.round(r)}, ${Math.round(g)}, ${Math.round(b)})`;
  },

  getSeasonState() {
    const cycle = this.gameTime % (this.SEASON_DURATION * 4);
    const seasonId = Math.floor(cycle / this.SEASON_DURATION);
    const seasonProgress = (cycle % this.SEASON_DURATION) / this.SEASON_DURATION;
    const current = this.seasonColors[seasonId];
    const next = this.seasonColors[(seasonId + 1) % 4];

    let factor = 0;
    if (seasonProgress > 0.85) {
      factor = (seasonProgress - 0.85) / 0.15;
    }

    return {
      skyTop: this.lerpColor(current.skyTop, next.skyTop, factor),
      skyBottom: this.lerpColor(current.skyBottom, next.skyBottom, factor),
      hillFar: this.lerpColor(current.hillFar, next.hillFar, factor),
      hillNear: this.lerpColor(current.hillNear, next.hillNear, factor),
      foliage: this.lerpColor(current.foliage, next.foliage, factor),
      ground: this.lerpColor(current.ground, next.ground, factor),
      particleColor: current.particleColor,
      particleType: current.particleType
    };
  },

  /* Audio */
  playCollectSound() {
    try {
      const AudioContext = window.AudioContext || window.webkitAudioContext;
      if (!AudioContext) return;
      const audioCtx = new AudioContext();
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();
      osc.connect(gain);
      gain.connect(audioCtx.destination);
      osc.type = "sine";
      osc.frequency.setValueAtTime(987.77, audioCtx.currentTime);
      osc.frequency.exponentialRampToValueAtTime(1975.53, audioCtx.currentTime + 0.12);
      gain.gain.setValueAtTime(0.18, audioCtx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.2);
      osc.start();
      osc.stop(audioCtx.currentTime + 0.22);
    } catch (e) {
      console.error("Audio Context Error:", e);
    }
  },

  /* Particle system */
  spawnSparkles(x, y) {
    for (let i = 0; i < 12; i++) {
      const angle = Math.random() * Math.PI * 2;
      const speed = Math.random() * 2.8 + 1.2;
      this.particles.push({
        x: x, y: y,
        vx: Math.cos(angle) * speed,
        vy: Math.sin(angle) * speed - 1.0,
        size: Math.random() * 3 + 2,
        alpha: 1.0,
        rotation: Math.random() * Math.PI * 2,
        spin: Math.random() * 0.1 - 0.05,
        type: "sparkle",
        color: "#fbbf24"
      });
    }
  },

  drawParticles(state) {
    if (this.particles.length < 28 && Math.random() < 0.15) {
      this.particles.push({
        x: this.internalWidth + 20,
        y: Math.random() * (this.internalHeight - 65) + 10,
        vx: -(Math.random() * 1.5 + 1.2),
        vy: Math.random() * 0.5 - 0.15,
        size: Math.random() * 4 + 3,
        alpha: Math.random() * 0.48 + 0.35,
        rotation: Math.random() * Math.PI * 2,
        spin: Math.random() * 0.04 - 0.02,
        type: state.particleType,
        color: state.particleColor
      });
    }

    for (let i = this.particles.length - 1; i >= 0; i--) {
      const p = this.particles[i];
      p.x += p.vx;
      p.y += p.vy;
      p.rotation += p.spin;

      if (p.type === "snowflake") {
        p.x += Math.sin(this.gameTime * 0.03 + p.y) * 0.25;
      }

      if (p.type === "sparkle") {
        p.alpha -= 0.038;
        p.vy += 0.08;
        if (p.alpha <= 0) {
          this.particles.splice(i, 1);
          continue;
        }
      }

      if (p.x < -20 || p.y > this.internalHeight + 20) {
        this.particles.splice(i, 1);
        continue;
      }

      this.ctx.save();
      this.ctx.globalAlpha = p.alpha;
      this.ctx.fillStyle = p.color;
      this.ctx.translate(p.x, p.y);
      this.ctx.rotate(p.rotation);

      if (p.type === "blossom" || p.type === "leaf" || p.type === "maple") {
        this.ctx.beginPath();
        this.ctx.ellipse(0, 0, p.size, p.size / 2, 0, 0, Math.PI * 2);
        this.ctx.fill();
      } else if (p.type === "snowflake") {
        this.ctx.strokeStyle = "#ffffff";
        this.ctx.lineWidth = 1.0;
        this.ctx.beginPath();
        for (let j = 0; j < 4; j++) {
          this.ctx.moveTo(-p.size / 2, 0);
          this.ctx.lineTo(p.size / 2, 0);
          this.ctx.rotate(Math.PI / 4);
        }
        this.ctx.stroke();
      } else if (p.type === "sparkle") {
        this.ctx.fillStyle = p.color;
        this.ctx.beginPath();
        for (let j = 0; j < 4; j++) {
          this.ctx.lineTo(0, -p.size);
          this.ctx.lineTo(p.size / 3, -p.size / 3);
          this.ctx.rotate(Math.PI / 2);
        }
        this.ctx.closePath();
        this.ctx.fill();
      }
      this.ctx.restore();
    }
  },

  /* Letter spawner & collision */
  startNewGame() {
    const randIndex = Math.floor(Math.random() * this.gameQuotes.length);
    this.currentFullQuote = this.gameQuotes[randIndex];

    this.currentQuoteCharacters = [];
    for (let char of this.currentFullQuote) {
      this.currentQuoteCharacters.push({
        char: char,
        revealed: (char === "，" || char === "。" || char === "？" || char === "！" || char === "、")
      });
    }

    this.gameTotalCount = this.currentQuoteCharacters.filter(c => !c.revealed).length;
    this.collectedCount = 0;

    this.letters = [];
    this.particles = [];
    this.letterSpawnTimer = 0;
    this.traveler.y = 130;
    this.traveler.vy = 0;
    this.traveler.isJumping = false;

    document.getElementById("game-collected-count").innerText = "0";
    document.getElementById("game-total-count").innerText = this.gameTotalCount;

    this.updateRevealBoard();
  },

  updateRevealBoard() {
    const board = document.getElementById("quote-reveal-board");
    board.innerHTML = "";
    this.currentQuoteCharacters.forEach(item => {
      const box = document.createElement("div");
      box.classList.add("char-box");
      if (item.revealed) {
        box.classList.add("revealed");
        box.innerText = item.char;
      } else {
        box.innerText = "?";
      }
      board.appendChild(box);
    });
  },

  drawLetters() {
    const gameModalActive = document.getElementById("game-modal").classList.contains("active");
    if (this.collectedCount < this.gameTotalCount && !gameModalActive) {
      this.letterSpawnTimer++;
      if (this.letterSpawnTimer >= 150) {
        this.letterSpawnTimer = 0;
        const nextIndex = this.currentQuoteCharacters.findIndex(c => !c.revealed);
        if (nextIndex !== -1) {
          this.letters.push({
            x: this.internalWidth + 30,
            baseY: Math.random() * 60 + 35,
            phase: Math.random() * Math.PI * 2,
            width: 24,
            height: 16,
            collected: false,
            charIndex: nextIndex,
            char: this.currentQuoteCharacters[nextIndex].char
          });
        }
      }
    }

    for (let i = this.letters.length - 1; i >= 0; i--) {
      const L = this.letters[i];
      L.x -= 2.2;
      L.y = L.baseY + Math.sin(L.x * 0.025 + L.phase) * 12;

      if (L.x < -30) {
        this.letters.splice(i, 1);
        continue;
      }

      const txCenter = 85;
      const tyCenter = this.traveler.y - 15;
      const dist = Math.hypot(L.x - txCenter, L.y - tyCenter);

      if (dist < 24 && !L.collected) {
        L.collected = true;
        this.collectedCount++;

        this.currentQuoteCharacters[L.charIndex].revealed = true;

        this.playCollectSound();
        this.spawnSparkles(L.x, L.y);

        document.getElementById("game-collected-count").innerText = this.collectedCount;
        this.updateRevealBoard();

        if (this.collectedCount === this.gameTotalCount) {
          setTimeout(() => this.showGameCompleteModal(), 800);
        }

        this.letters.splice(i, 1);
        continue;
      }

      this.ctx.save();
      this.ctx.shadowColor = "rgba(168, 85, 247, 0.4)";
      this.ctx.shadowBlur = 8;

      this.ctx.fillStyle = "#ffffff";
      this.ctx.strokeStyle = "#818cf8";
      this.ctx.lineWidth = 1.2;

      this.ctx.beginPath();
      this.ctx.roundRect(L.x - L.width / 2, L.y - L.height / 2, L.width, L.height, 3);
      this.ctx.fill();
      this.ctx.stroke();

      this.ctx.beginPath();
      this.ctx.moveTo(L.x - L.width / 2, L.y - L.height / 2);
      this.ctx.lineTo(L.x, L.y + 1);
      this.ctx.lineTo(L.x + L.width / 2, L.y - L.height / 2);
      this.ctx.stroke();

      this.ctx.restore();
    }
  },

  showGameCompleteModal() {
    document.getElementById("final-quote-text").innerText = `"${this.currentFullQuote}"`;
    document.getElementById("game-modal").classList.add("active");
  },

  triggerJump() {
    if (!this.userInteracted) {
      this.userInteracted = true;
      document.getElementById("game-instruction-overlay").classList.add("fade-out");
    }
    if (!this.traveler.isJumping) {
      this.traveler.vy = -8.2;
      this.traveler.isJumping = true;
    }
  },

  gameLoop() {
    if (!this.isRunning) return;
    this.gameTime++;

    const state = this.getSeasonState();

    this.ctx.clearRect(0, 0, this.internalWidth, this.internalHeight);
    const skyGrad = this.ctx.createLinearGradient(0, 0, 0, this.internalHeight);
    skyGrad.addColorStop(0, state.skyTop);
    skyGrad.addColorStop(1, state.skyBottom);
    this.ctx.fillStyle = skyGrad;
    this.ctx.fillRect(0, 0, this.internalWidth, this.internalHeight);

    this.ctx.fillStyle = state.hillFar;
    this.ctx.beginPath();
    const offsetFar = (this.gameTime * 0.2) % 800;
    this.ctx.moveTo(-offsetFar, this.internalHeight);
    for (let x = 0; x <= this.internalWidth + 800; x += 40) {
      const y = 92 + Math.sin(x * 0.005) * 18;
      this.ctx.lineTo(x - offsetFar, y);
    }
    this.ctx.lineTo(this.internalWidth + 800 - offsetFar, this.internalHeight);
    this.ctx.closePath();
    this.ctx.fill();

    const offsetMid = (this.gameTime * 0.5) % 900;
    for (let i = 0; i < 8; i++) {
      const treeX = i * 150 - offsetMid + 80;
      this.ctx.fillStyle = "rgba(120, 80, 50, 0.4)";
      this.ctx.fillRect(treeX - 2.5, 112, 5, 20);

      this.ctx.fillStyle = state.foliage;
      this.ctx.beginPath();
      this.ctx.arc(treeX, 105, 15, 0, Math.PI * 2);
      this.ctx.arc(treeX - 8, 97, 11, 0, Math.PI * 2);
      this.ctx.arc(treeX + 8, 97, 11, 0, Math.PI * 2);
      this.ctx.fill();
    }

    this.drawParticles(state);

    this.ctx.fillStyle = state.ground;
    this.ctx.fillRect(0, 130, this.internalWidth, 50);

    this.ctx.strokeStyle = getComputedStyle(document.body).getPropertyValue('--card-border').trim() || "rgba(255,255,255,0.08)";
    this.ctx.lineWidth = 1.0;
    this.ctx.beginPath();
    this.ctx.moveTo(0, 130);
    this.ctx.lineTo(this.internalWidth, 130);
    this.ctx.stroke();

    this.ctx.strokeStyle = state.foliage;
    this.ctx.lineWidth = 1.2;
    const offsetGround = (this.gameTime * 1.0) % 300;
    for (let i = 0; i < 7; i++) {
      const gx = i * 140 - offsetGround + 40;
      this.ctx.beginPath();
      this.ctx.moveTo(gx, 130);
      this.ctx.lineTo(gx - 2, 123);
      this.ctx.moveTo(gx, 130);
      this.ctx.lineTo(gx + 2, 121);
      this.ctx.stroke();
    }

    if (this.traveler.isJumping) {
      this.traveler.vy += this.traveler.gravity;
      this.traveler.y += this.traveler.vy;
      if (this.traveler.y >= 130) {
        this.traveler.y = 130;
        this.traveler.vy = 0;
        this.traveler.isJumping = false;
      }
    }

    let bob = 0;
    let stickAngle = 0;
    if (!this.traveler.isJumping) {
      bob = Math.sin(this.gameTime * 0.15) * 2.5;
      stickAngle = Math.sin(this.gameTime * 0.15) * 0.22;
    } else {
      stickAngle = 0.22;
    }

    const ty = this.traveler.y + bob;
    const primaryTextColor = getComputedStyle(document.body).getPropertyValue('--text-primary').trim() || "#f8fafc";
    const secondaryTextColor = getComputedStyle(document.body).getPropertyValue('--text-secondary').trim() || "#94a3b8";

    this.ctx.fillStyle = "rgba(99, 102, 241, 0.75)";
    this.ctx.beginPath();
    this.ctx.roundRect(this.traveler.x - 7, ty - 22, 5, 11, 2);
    this.ctx.fill();

    this.ctx.fillStyle = primaryTextColor;
    this.ctx.beginPath();
    this.ctx.moveTo(this.traveler.x - 4, ty);
    this.ctx.lineTo(this.traveler.x - 1, ty - 24);
    this.ctx.lineTo(this.traveler.x + 9, ty - 24);
    this.ctx.lineTo(this.traveler.x + 12, ty);
    this.ctx.closePath();
    this.ctx.fill();

    this.ctx.fillStyle = secondaryTextColor;
    this.ctx.fillRect(this.traveler.x + 2, ty - 18, 4, 18);

    this.ctx.fillStyle = "#fed7aa";
    this.ctx.beginPath();
    this.ctx.arc(this.traveler.x + 4, ty - 28, 4, 0, Math.PI * 2);
    this.ctx.fill();

    this.ctx.fillStyle = "#eab308";
    this.ctx.beginPath();
    this.ctx.ellipse(this.traveler.x + 4, ty - 31, 10, 2.5, 0, 0, Math.PI * 2);
    this.ctx.fill();
    this.ctx.beginPath();
    this.ctx.arc(this.traveler.x + 4, ty - 32, 4.5, Math.PI, 0);
    this.ctx.fill();

    this.ctx.strokeStyle = "#78350f";
    this.ctx.lineWidth = 1.8;
    this.ctx.beginPath();
    this.ctx.moveTo(this.traveler.x + 10, ty - 4);
    const sx = this.traveler.x + 10 + Math.sin(stickAngle) * 6;
    const sy = ty - 20 + Math.cos(stickAngle) * 2;
    this.ctx.lineTo(sx, sy);
    this.ctx.stroke();

    this.drawLetters();

    requestAnimationFrame(() => this.gameLoop());
  },

  init() {
    this.canvas = document.getElementById("game-canvas");
    this.ctx = this.canvas.getContext("2d");
    this.canvas.width = this.internalWidth;
    this.canvas.height = this.internalHeight;

    const self = this;

    document.getElementById("modal-write-memo-btn").addEventListener("click", () => {
      const memoArea = document.getElementById("memo-textarea");
      const nowContent = memoArea.value.trim();
      const quoteText = `【旅人的信笺寄语】\n"${self.currentFullQuote}"`;

      if (nowContent.includes(self.currentFullQuote)) {
        alert("这段寄语已经在您今日的便签中了哦 ✍️");
        return;
      }

      if (nowContent === "") {
        memoArea.value = quoteText;
      } else {
        memoArea.value = nowContent + "\n\n" + quoteText;
      }

      document.getElementById("save-memo-btn").click();

      const writeBtn = document.getElementById("modal-write-memo-btn");
      const originalText = writeBtn.innerHTML;
      writeBtn.innerHTML = "✓ 已写入日历";
      writeBtn.style.opacity = "0.75";

      setTimeout(() => {
        writeBtn.innerHTML = originalText;
        writeBtn.style.opacity = "1";
        document.getElementById("game-modal").classList.remove("active");
        self.startNewGame();
      }, 1300);
    });

    document.getElementById("modal-replay-btn").addEventListener("click", () => {
      document.getElementById("game-modal").classList.remove("active");
      self.startNewGame();
    });

    this.canvas.addEventListener("mousedown", (e) => {
      e.preventDefault();
      self.triggerJump();
    });

    this.canvas.addEventListener("touchstart", (e) => {
      e.preventDefault();
      self.triggerJump();
    });

    window.addEventListener("keydown", (e) => {
      if (e.code === "Space") {
        const activeEl = document.activeElement;
        if (activeEl !== document.getElementById("memo-textarea") &&
          activeEl !== document.getElementById("city-input")) {
          e.preventDefault();
          self.triggerJump();
        }
      }
    });

    self.startNewGame();
    self.gameLoop();
  }
};

export function initGame() {
  Game.init();
}
