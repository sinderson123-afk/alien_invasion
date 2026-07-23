import { storage } from './storage.js';

export function initAnalytics() {
  const totalCountEl = document.getElementById("visit-total-count");
  const todayCountEl = document.getElementById("visit-today-count");
  const chartContainer = document.getElementById("visit-chart-container");

  const d = new Date();
  const todayKey = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;

  let history = storage.get("calendar_visit_history", {});

  let total = storage.get("calendar_visit_total", 0);

  history[todayKey] = (history[todayKey] || 0) + 1;
  total += 1;

  const thirtyDaysAgoTime = Date.now() - 30 * 24 * 60 * 60 * 1000;
  for (let key in history) {
    const keyTime = new Date(key).getTime();
    if (isNaN(keyTime) || keyTime < thirtyDaysAgoTime) {
      delete history[key];
    }
  }

  storage.set("calendar_visit_history", history);
  storage.set("calendar_visit_total", total);

  todayCountEl.innerText = history[todayKey];
  totalCountEl.innerText = `总量: ${total}`;

  const past7Days = [];
  for (let i = 6; i >= 0; i--) {
    const tempDate = new Date();
    tempDate.setDate(tempDate.getDate() - i);
    const dateStr = `${tempDate.getFullYear()}-${String(tempDate.getMonth() + 1).padStart(2, '0')}-${String(tempDate.getDate()).padStart(2, '0')}`;
    const labelStr = `${String(tempDate.getMonth() + 1).padStart(2, '0')}-${String(tempDate.getDate()).padStart(2, '0')}`;
    past7Days.push({ key: dateStr, label: labelStr });
  }

  const counts = past7Days.map(day => history[day.key] || 0);
  const maxCount = Math.max(...counts, 1);

  chartContainer.innerHTML = "";
  past7Days.forEach((day, index) => {
    const count = history[day.key] || 0;
    const heightPercent = Math.max((count / maxCount) * 100, 6);

    const wrapper = document.createElement("div");
    wrapper.classList.add("chart-bar-wrapper");

    const bar = document.createElement("div");
    bar.classList.add("chart-bar");
    bar.setAttribute("data-count", count);

    setTimeout(() => {
      bar.style.height = `${heightPercent}%`;
    }, 80 + index * 40);

    const label = document.createElement("div");
    label.classList.add("chart-label");
    label.innerText = day.label;

    wrapper.appendChild(bar);
    wrapper.appendChild(label);
    chartContainer.appendChild(wrapper);
  });
}
