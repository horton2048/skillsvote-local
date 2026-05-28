from __future__ import annotations

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ScoreWeights(BaseModel):
    """Unified weighting of the value dimensions. Must sum to 1.0."""

    model_config = ConfigDict(extra="forbid")

    relevance: float = Field(default=0.35, ge=0.0, le=1.0)
    demand: float = Field(default=0.25, ge=0.0, le=1.0)
    recency: float = Field(default=0.15, ge=0.0, le=1.0)
    gap: float = Field(default=0.15, ge=0.0, le=1.0)
    fit: float = Field(default=0.10, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _check_sum(self) -> Self:
        total = self.relevance + self.demand + self.recency + self.gap + self.fit
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"score weights must sum to 1.0, got {total:.4f}")
        return self


class ScoreConfig(BaseModel):
    """Tunable knobs for the deterministic scorer."""

    model_config = ConfigDict(extra="forbid")

    weights: ScoreWeights = Field(default_factory=ScoreWeights)
    # Prompt count at which `demand` saturates to 1.0 (log scale).
    demand_saturation: int = Field(default=25, ge=1)
    # Half-life in days for the recency time-decay.
    recency_half_life_days: float = Field(default=30.0, gt=0.0)
    # A skill token only counts toward demand matching when its IDF is at least
    # this fraction of the corpus's max IDF (filters out ubiquitous filler).
    distinctive_idf_ratio: float = Field(default=0.35, ge=0.0, le=1.0)
    # Value retained on the gap dimension for skills the user already uses.
    already_have_gap: float = Field(default=0.2, ge=0.0, le=1.0)


class UserProfile(BaseModel):
    """A lexical fingerprint of how the user actually drives Claude Code.

    Built from local usage (``~/.claude/history.jsonl`` and session transcripts),
    never from the network.
    """

    model_config = ConfigDict(extra="forbid")

    prompt_count: int = Field(ge=0)
    # token -> sorted list of prompt indices that contain it (inverted index).
    postings: dict[str, list[int]] = Field(default_factory=dict)
    # epoch-ms timestamp per prompt index.
    prompt_timestamps: list[int] = Field(default_factory=list)
    # slash-command slug -> invocation count, plus skill slugs seen in usage.
    used_slugs: dict[str, int] = Field(default_factory=dict)
    now_ms: int = Field(ge=0)
    sample_prompts: list[str] = Field(default_factory=list)

    def doc_freq(self, token: str) -> int:
        return len(self.postings.get(token, ()))


class SkillDescriptor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    description: str = ""
    path: str | None = None
    source: Literal["frontmatter", "dirname", "name-only"] = "name-only"


class ScoreDimensions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    relevance: float = Field(ge=0.0, le=1.0)
    demand: float = Field(ge=0.0, le=1.0)
    recency: float = Field(ge=0.0, le=1.0)
    gap: float = Field(ge=0.0, le=1.0)
    fit: float = Field(ge=0.0, le=1.0)


class SkillScore(BaseModel):
    """Personalized value of one skill for one user."""

    model_config = ConfigDict(extra="forbid")

    skill_name: str = Field(min_length=1)
    value: float = Field(ge=0.0, le=100.0)
    dimensions: ScoreDimensions
    matched_prompt_count: int = Field(ge=0)
    matched_terms: list[str] = Field(default_factory=list)
    last_used_days_ago: float | None = None
    already_have: bool = False
    reason: str = ""
