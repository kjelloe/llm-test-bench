// Baseline: splits on comma — does not handle quoted fields.
export function parseCSV(text) {
  return text.trim().split('\n').map(line => line.split(','));
}
