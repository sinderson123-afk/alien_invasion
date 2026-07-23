import { storage } from './storage.js';

const Calendar = {
  state: {
    selectedDate: new Date(),
    currentYear: new Date().getFullYear(),
    currentMonth: new Date().getMonth()
  },

  formatDateKey(year, month, day) {
    return `calendar_memo_${year}_${String(month + 1).padStart(2, '0')}_${String(day).padStart(2, '0')}`;
  },

  render() {
    const { currentYear, currentMonth } = this.state;
    const calendarDaysGrid = document.getElementById("calendar-days-grid");
    const calendarMonthYear = document.getElementById("calendar-month-year");

    calendarDaysGrid.innerHTML = "";

    calendarMonthYear.innerText = `${currentYear}年${currentMonth + 1}月`;

    const firstDayIndex = new Date(currentYear, currentMonth, 1).getDay();
    const totalDays = new Date(currentYear, currentMonth + 1, 0).getDate();

    for (let i = 0; i < firstDayIndex; i++) {
      const emptyCell = document.createElement("div");
      emptyCell.classList.add("day-cell", "empty");
      calendarDaysGrid.appendChild(emptyCell);
    }

    const today = new Date();
    const { selectedDate } = this.state;

    for (let day = 1; day <= totalDays; day++) {
      const dayCell = document.createElement("div");
      dayCell.classList.add("day-cell");
      dayCell.innerText = day;

      if (day === today.getDate() && currentMonth === today.getMonth() && currentYear === today.getFullYear()) {
        dayCell.classList.add("today");
      }

      if (day === selectedDate.getDate() && currentMonth === selectedDate.getMonth() && currentYear === selectedDate.getFullYear()) {
        dayCell.classList.add("selected");
      }

      const memoKey = this.formatDateKey(currentYear, currentMonth, day);
      const hasMemo = storage.get(memoKey, "");
      if (hasMemo && hasMemo.trim().length > 0) {
        const dot = document.createElement("span");
        dot.classList.add("memo-dot");
        dayCell.appendChild(dot);
      }

      dayCell.addEventListener("click", () => {
        document.querySelectorAll(".day-cell.selected").forEach(el => el.classList.remove("selected"));
        dayCell.classList.add("selected");
        this.state.selectedDate = new Date(currentYear, currentMonth, day);
        this.loadMemo();
      });

      calendarDaysGrid.appendChild(dayCell);
    }
  },

  loadMemo() {
    const { selectedDate } = this.state;
    const y = selectedDate.getFullYear();
    const m = selectedDate.getMonth();
    const d = selectedDate.getDate();

    const memoTitle = document.getElementById("memo-title");
    const memoTextarea = document.getElementById("memo-textarea");

    memoTitle.innerText = `✍️ ${m + 1}月${d}日 便签`;

    const memoKey = this.formatDateKey(y, m, d);
    const savedText = storage.get(memoKey, "");
    memoTextarea.value = savedText;
  },

  init() {
    const prevMonthBtn = document.getElementById("prev-month-btn");
    const nextMonthBtn = document.getElementById("next-month-btn");
    const saveMemoBtn = document.getElementById("save-memo-btn");
    const self = this;

    prevMonthBtn.addEventListener("click", () => {
      self.state.currentMonth--;
      if (self.state.currentMonth < 0) {
        self.state.currentMonth = 11;
        self.state.currentYear--;
      }
      self.render();
    });

    nextMonthBtn.addEventListener("click", () => {
      self.state.currentMonth++;
      if (self.state.currentMonth > 11) {
        self.state.currentMonth = 0;
        self.state.currentYear++;
      }
      self.render();
    });

    saveMemoBtn.addEventListener("click", () => {
      const { selectedDate } = self.state;
      const y = selectedDate.getFullYear();
      const m = selectedDate.getMonth();
      const d = selectedDate.getDate();
      const memoKey = self.formatDateKey(y, m, d);
      const memoTextarea = document.getElementById("memo-textarea");
      const textVal = memoTextarea.value.trim();

      if (textVal === "") {
        storage.remove(memoKey);
      } else {
        storage.set(memoKey, textVal);
      }

      const originalText = saveMemoBtn.innerHTML;
      saveMemoBtn.innerHTML = "✓ 已保存";
      saveMemoBtn.style.opacity = "0.8";

      setTimeout(() => {
        saveMemoBtn.innerHTML = originalText;
        saveMemoBtn.style.opacity = "1";
      }, 1200);

      self.render();
    });
  }
};

export function initCalendar() {
  Calendar.init();
  Calendar.render();
  Calendar.loadMemo();
}
