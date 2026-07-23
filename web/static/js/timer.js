let pomodoroTimerId = null;
let swTimerId = null;

const Pomodoro = {
  mode: "FOCUS",
  focusDuration: 25 * 60,
  breakDuration: 5 * 60,
  timeLeft: 25 * 60,
  totalTime: 25 * 60,
  isRunning: false,

  init() {
    const pTimeEl = document.getElementById("p-time");
    const pStateLabel = document.getElementById("p-state-label");
    const pProgressBar = document.getElementById("p-progress-bar");
    const pStartBtn = document.getElementById("p-start-btn");
    const pStartIcon = document.getElementById("p-start-icon");
    const pResetBtn = document.getElementById("p-reset-btn");
    const pFocusInput = document.getElementById("p-focus-input");
    const pFocusVal = document.getElementById("p-focus-val");
    const circleStrokeLength = 326.72;

    this.timeLeft = this.focusDuration;
    this.totalTime = this.focusDuration;

    const self = this;

    function updateUI() {
      const mins = String(Math.floor(self.timeLeft / 60)).padStart(2, '0');
      const secs = String(self.timeLeft % 60).padStart(2, '0');
      pTimeEl.innerText = `${mins}:${secs}`;
      pStateLabel.innerText = self.mode;

      const percent = self.timeLeft / self.totalTime;
      const offset = circleStrokeLength * (1 - percent);
      pProgressBar.style.strokeDashoffset = offset;
    }

    function playTimerDoneSound() {
      try {
        const AudioContext = window.AudioContext || window.webkitAudioContext;
        if (!AudioContext) return;
        const audioCtx = new AudioContext();

        const osc1 = audioCtx.createOscillator();
        const gain1 = audioCtx.createGain();
        osc1.connect(gain1);
        gain1.connect(audioCtx.destination);
        osc1.type = "sine";
        osc1.frequency.setValueAtTime(659.25, audioCtx.currentTime);
        gain1.gain.setValueAtTime(0.12, audioCtx.currentTime);
        gain1.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.3);
        osc1.start();
        osc1.stop(audioCtx.currentTime + 0.32);

        setTimeout(() => {
          const osc2 = audioCtx.createOscillator();
          const gain2 = audioCtx.createGain();
          osc2.connect(gain2);
          gain2.connect(audioCtx.destination);
          osc2.type = "sine";
          osc2.frequency.setValueAtTime(880.00, audioCtx.currentTime);
          gain2.gain.setValueAtTime(0.12, audioCtx.currentTime);
          gain2.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.4);
          osc2.start();
          osc2.stop(audioCtx.currentTime + 0.42);
        }, 180);
      } catch (e) {
        console.error("Audio Playback Error:", e);
      }
    }

    pStartBtn.addEventListener("click", () => {
      if (self.isRunning) {
        clearInterval(pomodoroTimerId);
        self.isRunning = false;
        pStartIcon.setAttribute("d", "M8 5v14l11-7z");
      } else {
        self.isRunning = true;
        pStartIcon.setAttribute("d", "M6 19h4V5H6v14zm8-14v14h4V5h-4z");

        pomodoroTimerId = setInterval(() => {
          self.timeLeft--;
          if (self.timeLeft <= 0) {
            playTimerDoneSound();
            if (self.mode === "FOCUS") {
              self.mode = "BREAK";
              self.timeLeft = self.breakDuration;
              self.totalTime = self.breakDuration;
              alert("☀️ 专注时间结束，休息一下吧！");
            } else {
              self.mode = "FOCUS";
              self.timeLeft = self.focusDuration;
              self.totalTime = self.focusDuration;
              alert("📖 休息结束，重新开始专注吧！");
            }
          }
          updateUI();
        }, 1000);
      }
    });

    pResetBtn.addEventListener("click", () => {
      clearInterval(pomodoroTimerId);
      self.isRunning = false;
      self.mode = "FOCUS";
      self.timeLeft = self.focusDuration;
      self.totalTime = self.focusDuration;
      pStartIcon.setAttribute("d", "M8 5v14l11-7z");
      updateUI();
    });

    pFocusInput.addEventListener("input", (e) => {
      const val = parseInt(e.target.value);
      pFocusVal.innerText = val;
      self.focusDuration = val * 60;
      if (!self.isRunning && self.mode === "FOCUS") {
        self.timeLeft = self.focusDuration;
        self.totalTime = self.focusDuration;
        updateUI();
      }
    });

    updateUI();
  }
};

const Stopwatch = {
  isRunning: false,
  startTime: 0,
  accumulatedTime: 0,
  lapCount: 0,

  init() {
    const swTimeEl = document.getElementById("sw-time");
    const swStartBtn = document.getElementById("sw-start-btn");
    const swStartIcon = document.getElementById("sw-start-icon");
    const swLapBtn = document.getElementById("sw-lap-btn");
    const swResetBtn = document.getElementById("sw-reset-btn");
    const swLapsList = document.getElementById("sw-laps-list");
    const swLapsWrapper = document.getElementById("sw-laps-wrapper");

    const self = this;

    function formatStopwatchTime(ms) {
      let totalSecs = Math.floor(ms / 1000);
      let centis = Math.floor((ms % 1000) / 10);
      let secs = totalSecs % 60;
      let mins = Math.floor(totalSecs / 60);
      return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}.${String(centis).padStart(2, '0')}`;
    }

    function updateStopwatch() {
      const elapsed = Date.now() - self.startTime + self.accumulatedTime;
      swTimeEl.innerText = formatStopwatchTime(elapsed);
    }

    swStartBtn.addEventListener("click", () => {
      if (self.isRunning) {
        clearInterval(swTimerId);
        self.accumulatedTime += Date.now() - self.startTime;
        self.isRunning = false;
        swStartIcon.setAttribute("d", "M8 5v14l11-7z");
      } else {
        self.startTime = Date.now();
        self.isRunning = true;
        swStartIcon.setAttribute("d", "M6 19h4V5H6v14zm8-14v14h4V5h-4z");
        swTimerId = setInterval(updateStopwatch, 10);
      }
    });

    swLapBtn.addEventListener("click", () => {
      if (!self.isRunning && self.accumulatedTime === 0) return;

      self.lapCount++;
      const currentMs = self.isRunning ? (Date.now() - self.startTime + self.accumulatedTime) : self.accumulatedTime;
      const lapTimeFormatted = formatStopwatchTime(currentMs);

      const li = document.createElement("li");
      li.classList.add("sw-lap-item");
      li.innerHTML = `
        <span class="lap-index">计次 ${self.lapCount}</span>
        <span class="lap-time">${lapTimeFormatted}</span>
      `;
      swLapsList.appendChild(li);
      swLapsWrapper.scrollTop = swLapsWrapper.scrollHeight;
    });

    swResetBtn.addEventListener("click", () => {
      clearInterval(swTimerId);
      self.isRunning = false;
      self.startTime = 0;
      self.accumulatedTime = 0;
      self.lapCount = 0;
      swTimeEl.innerText = "00:00.00";
      swStartIcon.setAttribute("d", "M8 5v14l11-7z");
      swLapsList.innerHTML = "";
    });
  }
};

export function initTimer() {
  const tabBtns = document.querySelectorAll(".timer-tab-btn");
  const timerPanels = document.querySelectorAll(".timer-panel");

  tabBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      tabBtns.forEach(b => b.classList.remove("active"));
      timerPanels.forEach(p => p.classList.remove("active"));

      btn.classList.add("active");
      const targetTab = btn.getAttribute("data-tab");
      document.getElementById(`panel-${targetTab}`).classList.add("active");
    });
  });

  Pomodoro.init();
  Stopwatch.init();
}

export function cleanupTimer() {
  if (pomodoroTimerId) clearInterval(pomodoroTimerId);
  if (swTimerId) clearInterval(swTimerId);
}
