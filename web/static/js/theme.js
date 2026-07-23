import { storage } from './storage.js';

export function initTheme() {
  const themeToggleBtn = document.getElementById("theme-toggle");

  const cachedTheme = storage.get("calendar_theme", "dark");
  if (cachedTheme === "light") {
    document.body.classList.add("light-mode");
  }

  themeToggleBtn.addEventListener("click", () => {
    document.body.classList.toggle("light-mode");
    const isLight = document.body.classList.contains("light-mode");
    storage.set("calendar_theme", isLight ? "light" : "dark");
  });
}
