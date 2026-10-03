"""Word error rate with an explicit, Spanish-preserving normalization policy."""

import unicodedata


def normalize(text: str) -> list[str]:
    """Lowercase and remove punctuation, preserving accents, ñ and numbers."""
    text = unicodedata.normalize("NFC", text).lower()
    text = "".join(" " if unicodedata.category(c).startswith("P") else c for c in text)
    return text.split()


def word_errors(reference: str, hypothesis: str) -> dict[str, int | float | None]:
    """Compute Levenshtein word edits; empty references have undefined WER."""
    expected, actual = normalize(reference), normalize(hypothesis)
    previous = list(range(len(actual) + 1))
    for i, word in enumerate(expected, 1):
        current = [i]
        for j, other in enumerate(actual, 1):
            current.append(min(current[-1] + 1, previous[j] + 1, previous[j - 1] + (word != other)))
        previous = current
    edits = previous[-1]
    return {
        "reference_words": len(expected),
        "hypothesis_words": len(actual),
        "word_edits": edits,
        "wer": edits / len(expected) if expected else None,
    }
