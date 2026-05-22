// Baseline: timer is declared inside the returned function — resets on every call.
export function debounce(fn, delay) {
  return function (...args) {
    let timer;                         // BUG: new variable each call; never cancels previous
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delay);
  };
}
