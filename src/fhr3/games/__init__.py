from fhr3.games.base import GameAdapter, GameConfig


def make_adapter(config: GameConfig) -> GameAdapter:
    """Variant registry. Add new variants here (see docs/extending.md)."""
    if config.variant == "nlhe":
        from fhr3.games.pokerkit_holdem import PokerKitHoldemAdapter

        return PokerKitHoldemAdapter(config)
    raise ValueError(f"unknown/unimplemented variant: {config.variant!r}")


__all__ = ["GameAdapter", "GameConfig", "make_adapter"]
