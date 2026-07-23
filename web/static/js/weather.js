import { storage } from './storage.js';

const apiKey = "Sm3B_GbXZNk3C3D65";

export function initWeather() {
  let currentCity = storage.get("calendar_city", "ip");

  const weatherCityEl = document.getElementById("weather-city");
  const weatherTempEl = document.getElementById("weather-temp");
  const weatherTextEl = document.getElementById("weather-text");
  const weatherIconContainer = document.getElementById("weather-icon-container");

  const citySearchOverlay = document.getElementById("city-search-overlay");
  const weatherCityBtn = document.getElementById("weather-city-btn");
  const cityInput = document.getElementById("city-input");
  const citySubmitBtn = document.getElementById("city-submit-btn");
  const cityCloseBtn = document.getElementById("city-close-btn");

  function getWeatherSVG(text) {
    let svgContent = `
      <svg class="weather-svg sensor-pulse" viewBox="0 0 64 64">
        <circle cx="32" cy="32" r="16" fill="none" stroke="var(--text-muted)" stroke-width="4" stroke-dasharray="10 6"/>
        <circle cx="32" cy="32" r="4" fill="var(--text-secondary)"/>
      </svg>
    `;

    if (text.includes("晴")) {
      svgContent = `
        <svg class="weather-svg sunny" viewBox="0 0 64 64">
          <circle cx="32" cy="32" r="14" fill="#f59e0b"/>
          <path class="sun-rays" d="M32 8v4M32 52v4M8 32h4M52 32h4M15 15l3 3M46 46l3 3M15 49l3-3M46 18l3-3" stroke="#f59e0b" stroke-width="4" stroke-linecap="round"/>
        </svg>
      `;
    } else if (text.includes("多云") || text.includes("阴")) {
      svgContent = `
        <svg class="weather-svg cloudy" viewBox="0 0 64 64">
          <circle cx="24" cy="24" r="8" fill="#f59e0b" opacity="0.8"/>
          <path d="M46 38a9 9 0 0 0-3.6-17.1A12.5 12.5 0 0 0 18 24a9 9 0 0 0 0 18h26a7 7 0 0 0 2-14z" fill="#cbd5e1"/>
          <path d="M44 42a9 9 0 0 0-3.6-17.1A12.5 12.5 0 0 0 16 28a9 9 0 0 0 0 18h26a7 7 0 0 0 2-14z" fill="#94a3b8" opacity="0.85"/>
        </svg>
      `;
    } else if (text.includes("雨") || text.includes("雷") || text.includes("雹")) {
      svgContent = `
        <svg class="weather-svg rainy" viewBox="0 0 64 64">
          <path d="M44 32a9 9 0 0 0-3.6-17.1A12.5 12.5 0 0 0 16 18a9 9 0 0 0 0 18h26a7 7 0 0 0 2-14z" fill="#64748b"/>
          <path class="rain-drop drop-1" d="M22 40v8" stroke="#3b82f6" stroke-width="3" stroke-linecap="round"/>
          <path class="rain-drop drop-2" d="M32 42v8" stroke="#3b82f6" stroke-width="3" stroke-linecap="round"/>
          <path class="rain-drop drop-3" d="M42 40v8" stroke="#3b82f6" stroke-width="3" stroke-linecap="round"/>
        </svg>
      `;
    } else if (text.includes("雪") || text.includes("霜") || text.includes("冰")) {
      svgContent = `
        <svg class="weather-svg snowy" viewBox="0 0 64 64">
          <path d="M44 32a9 9 0 0 0-3.6-17.1A12.5 12.5 0 0 0 16 18a9 9 0 0 0 0 18h26a7 7 0 0 0 2-14z" fill="#cbd5e1"/>
          <circle class="snowflake snow-1" cx="22" cy="42" r="2.5" fill="#fff"/>
          <circle class="snowflake snow-2" cx="32" cy="44" r="2.5" fill="#fff"/>
          <circle class="snowflake snow-3" cx="42" cy="42" r="2.5" fill="#fff"/>
        </svg>
      `;
    }
    return svgContent;
  }

  function fetchWeather(city) {
    weatherTextEl.innerText = "天气感知中...";
    weatherTempEl.innerText = "--°C";
    if (city === "ip") {
      weatherCityEl.innerText = "定位中...";
    } else {
      weatherCityEl.innerText = city.charAt(0).toUpperCase() + city.slice(1);
    }

    const weatherUrl = `https://api.seniverse.com/v3/weather/now.json?key=${apiKey}&location=${encodeURIComponent(city)}&language=zh-Hans&unit=c`;

    fetch(weatherUrl)
      .then(response => {
        if (!response.ok) throw new Error("API 请求失败");
        return response.json();
      })
      .then(data => {
        const temp = data.results[0].now.temperature;
        const text = data.results[0].now.text;
        const resolvedCity = data.results[0].location.name;

        weatherCityEl.innerText = resolvedCity;
        weatherTempEl.innerText = `${temp}°C`;
        weatherTextEl.innerText = text;

        weatherIconContainer.innerHTML = getWeatherSVG(text);

        storage.set("calendar_city", city);
        currentCity = city;
      })
      .catch(error => {
        console.error("天气数据获取失败: ", error);
        weatherCityEl.innerText = city;
        weatherTextEl.innerText = "暂无天气数据";
        weatherTempEl.innerText = "--°C";

        weatherIconContainer.innerHTML = `
          <svg class="weather-svg" viewBox="0 0 64 64" style="opacity: 0.5;">
            <circle cx="32" cy="32" r="14" fill="none" stroke="var(--text-muted)" stroke-width="4" stroke-dasharray="5 5"/>
            <path d="M22 22 L42 42 M42 22 L22 42" stroke="var(--text-muted)" stroke-width="4" stroke-linecap="round"/>
          </svg>
        `;
      });
  }

  weatherCityBtn.addEventListener("click", () => {
    citySearchOverlay.classList.add("active");
    cityInput.value = "";
    cityInput.focus();
  });

  cityCloseBtn.addEventListener("click", () => {
    citySearchOverlay.classList.remove("active");
  });

  function handleCitySearch() {
    const inputVal = cityInput.value.trim();
    if (inputVal) {
      fetchWeather(inputVal);
    }
    citySearchOverlay.classList.remove("active");
  }

  citySubmitBtn.addEventListener("click", handleCitySearch);
  cityInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") handleCitySearch();
  });

  fetchWeather(currentCity);
}
