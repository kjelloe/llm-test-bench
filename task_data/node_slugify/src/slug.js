// Baseline: only lowercases and replaces whitespace — does not handle punctuation.
export function slugify(str) {
  return str.toLowerCase().replace(/\s+/g, '-');
}
