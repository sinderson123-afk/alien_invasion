import { initTheme } from './theme.js';
import { initClock } from './clock.js';
import { initWeather } from './weather.js';
import { initCalendar } from './calendar.js';
import { initQuotes } from './quotes.js';
import { initCalculator } from './calculator.js';
import { initTimer, cleanupTimer } from './timer.js';
import { initAnalytics } from './analytics.js';
import { initGame } from './game.js';
import { initLeaderboard, cleanupLeaderboard } from './leaderboard.js';

initTheme();
initClock();
initWeather();
initCalendar();
initQuotes();
initCalculator();
initTimer();
initAnalytics();
initGame();
initLeaderboard();

window.addEventListener('beforeunload', () => {
  cleanupTimer();
  cleanupLeaderboard();
});
