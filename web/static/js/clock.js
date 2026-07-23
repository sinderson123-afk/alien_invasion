export function initClock() {
  const liveClock = document.getElementById("live-clock");
  const fullDateElement = document.getElementById("full-date");
  const timeGreeting = document.getElementById("time-greeting");

  function updateClock() {
    const now = new Date();
    const hrs = String(now.getHours()).padStart(2, '0');
    const mins = String(now.getMinutes()).padStart(2, '0');
    const secs = String(now.getSeconds()).padStart(2, '0');
    liveClock.innerText = `${hrs}:${mins}:${secs}`;

    const year = now.getFullYear();
    const month = now.getMonth() + 1;
    const date = now.getDate();
    const days = ["星期日", "星期一", "星期二", "星期三", "星期四", "星期五", "星期六"];
    const dayOfWeek = days[now.getDay()];
    fullDateElement.innerText = `${year}年${month}月${date}日 ${dayOfWeek}`;

    const hour = now.getHours();
    let greetingStr = "";
    let greetingIcon = "";
    if (hour >= 5 && hour < 11) {
      greetingStr = "早上好，愿新的一天充满阳光！";
      greetingIcon = "☀️";
    } else if (hour >= 11 && hour < 13) {
      greetingStr = "中午好，别忘了按时吃饭、休息一下。";
      greetingIcon = "🍲";
    } else if (hour >= 13 && hour < 17) {
      greetingStr = "下午好，喝杯热茶继续前行吧。";
      greetingIcon = "☕";
    } else if (hour >= 17 && hour < 23) {
      greetingStr = "晚上好，享受轻松惬意的夜晚吧。";
      greetingIcon = "🌙";
    } else {
      greetingStr = "深夜了，早点休息，祝你好梦。";
      greetingIcon = "✨";
    }
    timeGreeting.innerHTML = `<span>${greetingIcon} ${greetingStr}</span>`;
  }

  updateClock();
  setInterval(updateClock, 1000);
}
