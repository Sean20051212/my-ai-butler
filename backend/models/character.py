from dataclasses import dataclass, field


@dataclass
class CharacterState:
    """Mutable runtime state for the Hiyori character.

    Shared between the vision background thread and the chat endpoint.
    Simple dict-level assignments are GIL-safe in CPython for this use case.
    """
    trust_level:   int  = 45
    stress_level:  int  = 20
    energy_level:  int  = 80
    current_mood:  str  = "neutral"
    latest_vision: str  = "目前沒看到什麼特別的"
    is_chatting:   bool = False
    chat_history:  list = field(default_factory=list)
    MAX_HISTORY:   int  = 6

    # ------------------------------------------------------------------
    # History management
    # ------------------------------------------------------------------

    def add_to_history(self, user_msg: str, assistant_msg: str) -> None:
        self.chat_history.append({"role": "user",      "content": user_msg})
        self.chat_history.append({"role": "assistant", "content": assistant_msg})
        while len(self.chat_history) > self.MAX_HISTORY:
            self.chat_history.pop(0)

    # ------------------------------------------------------------------
    # Emotion-driven state updates
    # ------------------------------------------------------------------

    def apply_emotion(self, emotion: str) -> None:
        self.current_mood = emotion
        if emotion in ("happy", "excited"):
            self.trust_level  = min(100, self.trust_level  + 2)
            self.stress_level = max(0,   self.stress_level - 3)
            self.energy_level = max(0,   self.energy_level - 1)
        elif emotion in ("angry", "sad"):
            self.stress_level = min(100, self.stress_level + 5)
            self.trust_level  = max(0,   self.trust_level  - 1)
            self.energy_level = max(0,   self.energy_level - 2)
        elif emotion == "shy":
            self.trust_level  = min(100, self.trust_level  + 1)
        else:
            # neutral / surprised: gradual energy drain
            self.energy_level = max(0, self.energy_level - 1)
