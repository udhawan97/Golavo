"""Sanitize untrusted text before it is shown to the model.

Any text Golavo did not generate itself — a fetched web snippet used for the
optional research/candidate-fact path — is untrusted DATA, never instructions.
The defenses are layered:

  1. This module strips control characters and known chat-template control
     tokens, removes our own fence sentinels so the payload cannot "close" the
     untrusted block, and caps length.
  2. ``build_user_prompt`` wraps the result in explicit, unique delimiters and
     tells the model everything inside is data.
  3. The fixed system prompt instructs the model to never follow instructions
     found in bundle or research text, and it is given no tools.
  4. Whatever the model emits still passes the numeric-whitelist and citation
     guards, so a successful injection cannot put an unsupported number or an
     uncited claim in front of the user — it can only cause a local-only
     fallback.

Sanitizing is not a substitute for (2)–(4); it is the first, cheapest layer.
"""

from __future__ import annotations

import re

# Fence sentinels used by build_user_prompt. Kept here so the sanitizer can
# strip any copy an attacker embeds to try to break out of the data block.
UNTRUSTED_OPEN = "<<<GOLAVO_UNTRUSTED_DATA>>>"
UNTRUSTED_CLOSE = "<<<END_GOLAVO_UNTRUSTED_DATA>>>"

MAX_UNTRUSTED_CHARS = 4000

# Chat-template / role control tokens across common local model families. These
# are the real injection vector for llama.cpp/Ollama models: neutralized to a
# space so they cannot re-open a system or assistant turn.
_CONTROL_TOKENS = (
    "<|im_start|>", "<|im_end|>", "<|system|>", "<|user|>", "<|assistant|>",
    "<|endoftext|>", "<|eot_id|>", "<|start_header_id|>", "<|end_header_id|>",
    "<s>", "</s>", "[INST]", "[/INST]", "<<SYS>>", "<</SYS>>",
    "<think>", "</think>", "```",
)

_CONTROL_RE = re.compile("|".join(re.escape(token) for token in _CONTROL_TOKENS), re.IGNORECASE)
# Control characters except tab and newline.
_CTRL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_MANY_NEWLINES_RE = re.compile(r"\n{3,}")
_MANY_SPACES_RE = re.compile(r"[ \t]{2,}")


def sanitize_untrusted(text: str, *, max_chars: int = MAX_UNTRUSTED_CHARS) -> str:
    """Return a defanged, length-capped copy of untrusted ``text``.

    Removes control characters and chat-template control tokens, strips any of
    our own fence sentinels, and collapses runaway whitespace. Never raises; an
    empty or non-string input yields an empty string.
    """
    if not isinstance(text, str) or not text:
        return ""
    cleaned = _CTRL_CHARS_RE.sub(" ", text)
    cleaned = cleaned.replace(UNTRUSTED_OPEN, " ").replace(UNTRUSTED_CLOSE, " ")
    cleaned = _CONTROL_RE.sub(" ", cleaned)
    cleaned = _MANY_SPACES_RE.sub(" ", cleaned)
    cleaned = _MANY_NEWLINES_RE.sub("\n\n", cleaned)
    cleaned = cleaned.strip()
    if len(cleaned) > max_chars:
        cleaned = cleaned[:max_chars].rstrip() + " …[truncated]"
    return cleaned
