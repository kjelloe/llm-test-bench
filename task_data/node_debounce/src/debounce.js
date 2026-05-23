export function debounce(fn, delay) {
  return function (...args) {
    let timer;
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delay);
  };
}
