"""Mixed Chinese/English tokenizer for prompts and SKILL.md content.

ASCII words are matched whole; CJK runs are bigrammed so "公众号" contributes
"公众" and "众号" — coarse but works without jieba dependency.

Ported from packaging/skillsvote/tokenize.py; the original lived inside a pip
package, this one is dependency-free so it can live in a skill.
"""
from __future__ import annotations

import re

_CJK = r"一-鿿㐀-䶿豈-﫿"
_ASCII_RE = re.compile(r"[a-z0-9][a-z0-9+_.#/-]*")
_CJK_RUN_RE = re.compile(rf"[{_CJK}]+")

_STOPWORDS = frozenset({
    # articles / conjunctions / prepositions
    "the", "and", "for", "with", "this", "that", "from", "into", "out", "off",
    "over", "under", "about", "above", "below", "between", "through", "during",
    "before", "after", "again", "to", "of", "in", "on", "at", "by", "as", "or",
    "an", "if", "so", "no", "up", "via", "per", "than", "then", "else", "not",
    "but", "nor", "yet", "too", "very", "just", "only", "also", "more", "most",
    "such", "own", "same", "each", "few", "other", "any", "all", "some", "both",
    # pronouns
    "you", "your", "yours", "my", "me", "mine", "we", "us", "our", "ours",
    "he", "him", "his", "she", "her", "they", "them", "their", "its", "it",
    # verbs / aux / common command words
    "are", "is", "be", "been", "being", "was", "were", "am", "do", "does",
    "did", "done", "can", "could", "will", "would", "should", "shall", "may",
    "might", "must", "use", "using", "used", "get", "got", "let", "want",
    "need", "please", "help", "make", "made", "give", "set", "run", "see",
    "add", "have", "has", "had", "go", "going",
    # interrogatives / misc
    "how", "what", "why", "when", "where", "which", "who", "whom", "one",
    "two", "now", "yes", "ok", "okay", "first", "next", "last",
    # urls
    "http", "https", "www", "com", "org", "net",
})


def tokenize(text: str) -> list[str]:
    """Tokenize mixed Chinese/English into lexical features.

    Returns ASCII word tokens (length >= 2, non-numeric, non-stopword) and CJK
    character bigrams. Order preserved; callers usually consume as a set.
    """
    tokens: list[str] = []
    for match in _ASCII_RE.finditer(text.lower()):
        word = match.group(0).strip("._-#/+")
        if len(word) < 2 or word.isdigit() or word in _STOPWORDS:
            continue
        tokens.append(word)
    for run in _CJK_RUN_RE.findall(text):
        if len(run) == 1:
            tokens.append(run)
            continue
        for i in range(len(run) - 1):
            tokens.append(run[i: i + 2])
    return tokens


def extract_slash_commands(text: str) -> list[str]:
    """Pull leading slash-commands like '/browse' from a prompt."""
    return [
        m.group(1).lower()
        for m in re.finditer(r"(?:^|\s)/([a-z][a-z0-9-]{1,40})", text.lower())
    ]
