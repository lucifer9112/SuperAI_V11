"""
SuperAI V11 — backend/personality/personality_engine.py

FEATURE 11: Personality & Identity Layer

Components:
  1. PersonalityProfile  — stable trait scores (curiosity, empathy, etc.)
  2. EmotionalState      — dynamic, session-aware emotional context
  3. UserAdapter         — learns communication style per user/session
  4. ResponsePersonalizer — adjusts tone, depth, formality before output

The personality stays consistent across sessions while adapting
communication style to individual users.
"""
from __future__ import annotations

import math
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from loguru import logger


# ── Personality traits ────────────────────────────────────────────

@dataclass
class PersonalityProfile:
    name:       str
    curiosity:  float = 0.8   # drives asking clarifying questions
    empathy:    float = 0.7   # drives acknowledging user emotion
    directness: float = 0.6   # drives concise vs. explanatory responses
    creativity: float = 0.75  # drives novel examples and analogies
    caution:    float = 0.5   # drives hedging and caveats

    def trait_modifier(self, trait: str) -> float:
        return max(0.0, min(getattr(self, trait, 0.5), 1.0))


# ── Emotional state ───────────────────────────────────────────────

EMOTION_VOCABULARY = {
    "positive":   ["Great question!", "I'd love to help!", "That's an interesting point."],
    "negative":   ["I understand your frustration.", "Let me help fix this."],
    "curious":    ["That's a fascinating question.", "Let me think through this carefully."],
    "frustrated": ["I apologize for the confusion.", "Let me clarify this properly."],
    "urgent":     ["Addressing this immediately.", "Here's a quick answer:"],
    "neutral":    ["", "", ""],
}


@dataclass
class EmotionalState:
    current_emotion: str   = "neutral"
    confidence:      float = 0.5
    last_updated:    float = field(default_factory=time.time)
    history:         List[str] = field(default_factory=list)

    def update(self, emotion: str, confidence: float = 0.7) -> None:
        self.history.append(self.current_emotion)
        if len(self.history) > 10:
            self.history.pop(0)
        self.current_emotion = emotion
        self.confidence      = confidence
        self.last_updated    = time.time()

    def get_opener(self) -> str:
        import random
        options = EMOTION_VOCABULARY.get(self.current_emotion, [""])
        return random.choice(options)


# ── User style adapter ────────────────────────────────────────────

@dataclass
class UserProfile:
    session_id:        str
    message_count:     int   = 0
    avg_msg_length:    float = 0.0
    technical_score:   float = 0.5    # 0=layman, 1=expert
    formality_score:   float = 0.5    # 0=casual, 1=formal
    preferred_depth:   str   = "medium"  # brief | medium | detailed
    last_updated:      float = field(default_factory=time.time)


TECH_KEYWORDS = [
    "function", "class", "api", "server", "database", "algorithm",
    "async", "docker", "gpu", "tensor", "neural", "embedding", "layer",
]
CASUAL_INDICATORS = ["hey", "lol", "btw", "pls", "thx", "ok", "gonna"]
FORMAL_INDICATORS = ["please", "could you", "kindly", "I would like", "regarding"]


class UserStyleAdapter:
    """Learns user communication style from messages."""

    def __init__(self) -> None:
        self._profiles: Dict[str, UserProfile] = {}

    def update(self, session_id: str, message: str) -> UserProfile:
        if session_id not in self._profiles:
            self._profiles[session_id] = UserProfile(session_id=session_id)

        p = self._profiles[session_id]
        words = message.lower().split()

        # Update avg length
        p.avg_msg_length = (p.avg_msg_length * p.message_count + len(words)) / (p.message_count + 1)
        p.message_count += 1

        # Technical score
        tech_hits = sum(1 for w in words if w in TECH_KEYWORDS)
        if tech_hits > 0:
            p.technical_score = min(p.technical_score + 0.1 * tech_hits, 1.0)
        else:
            p.technical_score = max(p.technical_score - 0.02, 0.1)

        # Formality
        casual_hits = sum(1 for w in words if w in CASUAL_INDICATORS)
        formal_hits = sum(1 for phrase in FORMAL_INDICATORS if phrase in message.lower())
        if casual_hits > formal_hits:
            p.formality_score = max(p.formality_score - 0.05, 0.0)
        elif formal_hits > casual_hits:
            p.formality_score = min(p.formality_score + 0.05, 1.0)

        # Preferred depth from message length
        if p.avg_msg_length < 8:
            p.preferred_depth = "brief"
        elif p.avg_msg_length > 30:
            p.preferred_depth = "detailed"
        else:
            p.preferred_depth = "medium"

        p.last_updated = time.time()
        return p

    def get_profile(self, session_id: str) -> Optional[UserProfile]:
        return self._profiles.get(session_id)


# ── Response personalizer ─────────────────────────────────────────

class ResponsePersonalizer:
    """
    Adjusts the final response based on personality, emotion, and user style.
    """

    def personalize(
        self,
        response: str,
        personality: PersonalityProfile,
        emotion: EmotionalState,
        user_profile: Optional[UserProfile],
    ) -> str:
        """Apply personality modifiers to the response."""
        modified = response

        # 1. Emotional opener
        if personality.empathy > 0.6:
            opener = emotion.get_opener()
            if opener and not modified.startswith(opener):
                modified = f"{opener} {modified}" if opener else modified

        # 2. Depth adjustment based on user style
        if user_profile:
            if user_profile.preferred_depth == "brief" and len(modified.split()) > 80:
                # Truncate at natural sentence boundary
                sentences = re.split(r'(?<=[.!?])\s+', modified)
                if len(sentences) > 2:
                    modified = " ".join(sentences[:3]) + "..."

            elif user_profile.preferred_depth == "detailed" and len(modified.split()) < 30:
                # Add elaboration hint
                if personality.curiosity > 0.7:
                    modified += "\n\nWould you like me to elaborate further on any aspect of this?"

        # 3. Technical level adjustment
        if user_profile and user_profile.technical_score < 0.3:
            # Simplify technical jargon (basic replacement)
            simplified = modified.replace("instantiate", "create")
            simplified = simplified.replace("asynchronous", "non-blocking")
            simplified = simplified.replace("iterate over", "go through each")
            modified = simplified

        return modified


# ── Main Personality Engine ───────────────────────────────────────

class PersonalityEngine:
    """
    Top-level personality coordinator.
    Manages profile, emotion state, user adaptation, and response personalization.
    """

    def __init__(self, cfg) -> None:
        self.cfg        = cfg
        self._enabled   = getattr(cfg, "enabled", True)
        traits          = getattr(cfg, "traits", {})

        self._profile   = PersonalityProfile(
            name       = getattr(cfg, "name", "SuperAI"),
            curiosity  = traits.get("curiosity",  0.8),
            empathy    = traits.get("empathy",    0.7),
            directness = traits.get("directness", 0.6),
            creativity = traits.get("creativity", 0.75),
            caution    = traits.get("caution",    0.5),
        )
        self._emotions: Dict[str, EmotionalState] = {}
        self._adapter   = UserStyleAdapter()
        self._personalizer = ResponsePersonalizer()

        logger.info("PersonalityEngine ready",
                    name=self._profile.name, enabled=self._enabled)

    def update_session(self, session_id: str, user_message: str, emotion: str) -> None:
        """Called on every user message."""
        self._adapter.update(session_id, user_message)
        if session_id not in self._emotions:
            self._emotions[session_id] = EmotionalState()
        self._emotions[session_id].update(emotion)

    def personalize_response(
        self, response: str, session_id: str
    ) -> str:
        if not self._enabled:
            return response

        emotion      = self._emotions.get(session_id, EmotionalState())
        user_profile = self._adapter.get_profile(session_id)

        return self._personalizer.personalize(
            response, self._profile, emotion, user_profile
        )

    def get_system_prompt_addon(self, session_id: str) -> str:
        """Generate personality-aware system prompt suffix."""
        user_profile = self._adapter.get_profile(session_id)
        if not user_profile:
            return ""

        parts = []
        if user_profile.technical_score > 0.7:
            parts.append("The user is technically proficient — use precise terminology.")
        elif user_profile.technical_score < 0.3:
            parts.append("Explain concepts in simple, everyday language.")

        if user_profile.preferred_depth == "brief":
            parts.append("Be concise — the user prefers short answers.")
        elif user_profile.preferred_depth == "detailed":
            parts.append("Provide thorough, detailed explanations.")

        return " ".join(parts)

    def session_emotion(self, session_id: str) -> str:
        state = self._emotions.get(session_id)
        return state.current_emotion if state else "neutral"

    def get_profile(self) -> Dict:
        return {
            "name":       self._profile.name,
            "curiosity":  self._profile.curiosity,
            "empathy":    self._profile.empathy,
            "directness": self._profile.directness,
            "creativity": self._profile.creativity,
            "caution":    self._profile.caution,
        }
