export interface TruncatedText {
  text: string;
  truncated: boolean;
}

const SENTENCE_ENDINGS = new Set([".", "!", "?", ";", "\n"]);

/**
 * Truncate `input` to at most `max` characters, preferring a sentence
 * boundary within the second half of the window; otherwise a clean
 * word-boundary fallback at `max` with an ellipsis. Used to keep
 * guided-view evidence quotes scannable. Sentence-boundary cuts read
 * as complete sentences (no ellipsis); hard cuts get a trailing "…".
 */
export function truncateText(input: string, max = 240): TruncatedText {
  const text = input.trim();
  if (text.length <= max) return { text, truncated: false };

  const window = text.slice(0, max);
  const floor = Math.floor(max / 2); // don't cut too short

  let boundary = -1;
  for (let i = window.length - 1; i >= floor; i--) {
    if (SENTENCE_ENDINGS.has(window[i])) {
      boundary = i;
      break;
    }
  }
  if (boundary >= floor) {
    return { text: text.slice(0, boundary + 1).trim(), truncated: true };
  }

  const lastSpace = window.lastIndexOf(" ");
  const cut = lastSpace >= floor ? lastSpace : max;
  return { text: text.slice(0, cut).trim() + "…", truncated: true };
}
