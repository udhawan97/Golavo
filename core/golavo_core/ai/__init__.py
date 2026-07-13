"""Optional, local-first AI safety machinery (deterministic, no network).

Nothing in this package talks to an LLM. It contains the pure guards that make
an AI layer safe: the numeric-whitelist matcher, the untrusted-text sanitizer,
the fixed versioned prompt, and the narration validator. The only module that
reaches an LLM is golavo_server.ai_gateway, which composes these guards around a
provider call and always fails closed to a local-only fallback.

Invariant: the deterministic engine owns every probability. The AI may cite and
explain numbers from a MatchEvidenceBundle's allowed_numbers list; it can never
introduce, change, or override one.
"""

from golavo_core.ai.narration import (
    NARRATION_SCHEMA_VERSION,
    NarrationReview,
    review_narration,
)
from golavo_core.ai.prompts import (
    BACKGROUND_ADDENDUM,
    DEEP_ANALYSIS_ADDENDUM,
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    build_user_prompt,
)
from golavo_core.ai.sanitize import sanitize_untrusted
from golavo_core.ai.whitelist import (
    contains_betting_lexicon,
    contains_secret_pattern,
    extract_numbers,
    number_matches,
    unsupported_numbers,
)

__all__ = [
    "BACKGROUND_ADDENDUM",
    "DEEP_ANALYSIS_ADDENDUM",
    "NARRATION_SCHEMA_VERSION",
    "PROMPT_VERSION",
    "SYSTEM_PROMPT",
    "NarrationReview",
    "build_user_prompt",
    "contains_betting_lexicon",
    "contains_secret_pattern",
    "extract_numbers",
    "number_matches",
    "review_narration",
    "sanitize_untrusted",
    "unsupported_numbers",
]
