export const storage = {
  get(key, fallback) {
    try {
      const value = localStorage.getItem(key);
      if (value === null) return fallback;
      return JSON.parse(value);
    } catch {
      return fallback;
    }
  },
  set(key, value) {
    localStorage.setItem(key, JSON.stringify(value));
  },
  remove(key) {
    localStorage.removeItem(key);
  }
};
