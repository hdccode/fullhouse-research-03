from fhr3.games.base import GameAdapter, GameConfig

VARIANTS = ("nlhe", "plo", "aof", "bomb_pot", "crazy_pineapple", "nit_game")


def make_adapter(config: GameConfig) -> GameAdapter:
    """Variant registry. Add new variants here (see docs/extending.md)."""
    if config.variant == "nit_game":
        from fhr3.games.nit import NitGameAdapter

        return NitGameAdapter(config)
    from fhr3.games.pokerkit_board import ADAPTERS

    if config.variant not in ADAPTERS:
        raise ValueError(f"unknown/unimplemented variant: {config.variant!r}; have {VARIANTS}")
    return ADAPTERS[config.variant](config)


__all__ = ["VARIANTS", "GameAdapter", "GameConfig", "make_adapter"]
