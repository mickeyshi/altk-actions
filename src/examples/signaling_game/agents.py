from ultk.effcomm.agent import CommunicativeAgent, Speaker, Listener
from ultk.language.semantics import Meaning
from languages import Signal, SignalMeaning, SignalingLanguage
from typing import Any


class Sender(Speaker):
    """A Sender agent in a signaling game chooses a signal given an observed state of nature, according to P(signal | state)."""

    def __init__(self, language: SignalingLanguage, weights=None, name: str = None):
        super().__init__(language, name=name)
        self.shape = (len(self.language.universe), len(self.language))
        self.initialize_weights(weights)

    def encode(self, state: Meaning) -> Signal:
        """Choose a signal given the state of nature observed, e.g. encode a discrete input as a discrete symbol."""
        index = self.sample_strategy(index=self.referent_to_index(state))
        return self.index_to_expression(index)

    def strategy_to_indices(self, strategy: dict[str, Any]) -> tuple[int]:
        """Map a state -> signal strategy to `(referent, expression)` indices."""
        return (
            self.referent_to_index(strategy["referent"]),
            self.expression_to_index(strategy["expression"]),
        )


class Receiver(Listener):
    """A Receiver agent in a signaling game chooses an action=state given a signal they received, according to P(state | signal)."""

    def __init__(self, language: SignalingLanguage, weights=None, name: str = None):
        super().__init__(language, name=name)
        self.shape = (len(self.language), len(self.language.universe))
        self.initialize_weights(weights=weights)

    def decode(self, signal: Signal) -> SignalMeaning:
        """Choose an action given the signal received, e.g. decode a target state given its discrete encoding."""
        index = self.sample_strategy(index=self.expression_to_index(signal))
        return self.index_to_referent(index)

    def strategy_to_indices(self, strategy: dict[str, Any]) -> tuple[int]:
        """Map a signal -> state strategy to `(expression, referent)` indices."""
        return (
            self.expression_to_index(strategy["expression"]),
            self.referent_to_index(strategy["referent"]),
        )
