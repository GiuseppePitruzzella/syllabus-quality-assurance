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

/**
 * Clean small scraper artefacts before rendering syllabus prose.
 *
 * Some SmartEdu fields contain lines made only of punctuation (most
 * commonly a single ".") before the actual paragraph. Those markers
 * are not meaningful content, so the UI drops only standalone
 * punctuation lines while preserving normal punctuation inside text.
 */
export function cleanSyllabusDisplayText(input: string | null | undefined): string {
  if (!input) return "";
  return input
    .split(/\r?\n/)
    .map((line) => line.trimEnd())
    .filter((line) => {
      const compact = line.trim();
      return compact === "" || !/^[.:;·•-]+$/.test(compact);
    })
    .join("\n")
    .trim();
}

const STANDALONE_NUMBER_MARKER = /^\d+[.)]$/;
const STANDALONE_BULLET_MARKER = /^[·•]$/;
const SENTENCE_BOUNDARY = /[.!?;:…]["'»”’)]?$/;
const OPENING_PUNCTUATION = new Set(["(", "[", "{", '"', "'", "«", "“", "‘"]);
const ITALIAN_ONE_LETTER_WORDS = new Set(["a", "e", "i", "o"]);
const SPLIT_A_WORD_CONTINUATION = /^nalis/i;

/**
 * Reconstruct readable syllabus paragraphs from scraper text.
 *
 * SmartEdu may serialize DOM boundaries as newlines even when the official
 * page renders continuous prose. The same data can also contain standalone
 * list markers and occasional one-letter word fragments. This formatter is
 * deliberately presentation-only: persisted values and evaluation inputs stay
 * untouched.
 */
export function syllabusProseParagraphs(
  input: string | null | undefined,
): string[] {
  if (!input) return [];

  const lines = input
    .replace(/\r\n?/g, "\n")
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line !== "" && !/^[.:;-]+$/.test(line));

  const paragraphs: string[] = [];
  let current = "";
  let pendingMarker = "";

  const flush = () => {
    const text = current.trim();
    if (text) paragraphs.push(text);
    current = "";
  };

  for (const line of lines) {
    if (STANDALONE_NUMBER_MARKER.test(line)) {
      flush();
      pendingMarker = line;
      continue;
    }
    if (STANDALONE_BULLET_MARKER.test(line)) {
      flush();
      pendingMarker = "•";
      continue;
    }

    if (pendingMarker) {
      current = `${pendingMarker} ${line}`;
      pendingMarker = "";
      continue;
    }

    if (!current) {
      current = line;
      continue;
    }

    if (shouldJoinSyllabusLines(current, line)) {
      current = joinSyllabusLines(current, line);
    } else {
      flush();
      current = line;
    }
  }

  // A terminal marker such as "2." commonly leaks from the next Dublin
  // descriptor during parsing. Without following content it is not a list
  // item and must not be rendered.
  flush();
  return paragraphs;
}

function shouldJoinSyllabusLines(previous: string, next: string): boolean {
  if (!SENTENCE_BOUNDARY.test(previous)) return true;
  return /^[a-zà-öø-ÿ),]/.test(next);
}

function joinSyllabusLines(previous: string, next: string): string {
  const lastToken =
    previous.match(/([A-Za-zÀ-ÖØ-öø-ÿ]+)$/)?.[1] ?? "";
  const firstCharacter = next.match(/^([a-zà-öø-ÿ])/)?.[1] ?? "";
  const touchesParenthesis =
    OPENING_PUNCTUATION.has(previous.charAt(previous.length - 1)) ||
    /^[)\]}.,;:!?»”’]/.test(next);
  const isWordFragment =
    lastToken.length === 1 &&
    firstCharacter !== "" &&
    (!ITALIAN_ONE_LETTER_WORDS.has(lastToken.toLowerCase()) ||
      (lastToken.toLowerCase() === "a" && SPLIT_A_WORD_CONTINUATION.test(next)));
  const separator =
    touchesParenthesis || isWordFragment ? "" : " ";
  return `${previous}${separator}${next}`;
}
