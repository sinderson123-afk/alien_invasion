const quotes = [
  "哪怕魔法与时间都会消逝，但此刻吹过耳畔的风，依然温柔。",
  "时间流转，有些风景与心意，永远在此停驻。",
  "将今天的阳光折叠，寄给明天的自己。",
  "在平淡的日子里，也要寻找闪闪发光的瞬间。",
  "世界偶尔冷酷，但总有不期而遇的温暖。",
  "生活收集起细碎的喜悦，织成我们温柔的日常。",
  "去吹吹风吧，如果能清醒的话，感冒也无所谓。",
  "我们都在奔赴各自不同的人生，愿你在漫长的岁月里终能得偿所愿。",
  "前路浩浩荡荡，万物皆可期待。",
  "慢品人间烟火色，闲观万事岁月长。",
  "生活明朗，万物可爱，人间值得，未来可期。"
];

export function initQuotes() {
  const quoteBox = document.getElementById("quote-box");
  const refreshQuoteBtn = document.getElementById("refresh-quote-btn");

  function changeQuote() {
    refreshQuoteBtn.classList.add("spinning");
    quoteBox.classList.add("transitioning");

    setTimeout(() => {
      const randomIndex = Math.floor(Math.random() * quotes.length);
      quoteBox.innerText = "“" + quotes[randomIndex] + "”";
      quoteBox.classList.remove("transitioning");
    }, 300);

    setTimeout(() => {
      refreshQuoteBtn.classList.remove("spinning");
    }, 600);
  }

  refreshQuoteBtn.addEventListener("click", changeQuote);

  const randomIndex = Math.floor(Math.random() * quotes.length);
  quoteBox.innerText = "“" + quotes[randomIndex] + "”";
}
