from fhr3.agents.base import Agent, AgentSpec


def build_agent(spec: AgentSpec) -> Agent:
    """Agent registry. Add new agent kinds here (see docs/extending.md)."""
    params = dict(spec.params)
    if spec.kind == "heuristic":
        from fhr3.agents.heuristic import HeuristicAgent

        style = params.pop("style", "neutral")
        return HeuristicAgent(spec.agent_id, style=style, **params.pop("overrides", {}), **params)
    if spec.kind == "plo_heuristic":
        from fhr3.agents.plo import PLOHeuristicAgent

        style = params.pop("style", "neutral")
        return PLOHeuristicAgent(spec.agent_id, style=style, **params.pop("overrides", {}), **params)
    if spec.kind == "cp_heuristic":
        from fhr3.agents.pineapple import CrazyPineappleAgent

        style = params.pop("style", "neutral")
        return CrazyPineappleAgent(spec.agent_id, style=style, **params.pop("overrides", {}), **params)
    if spec.kind == "checkcall":
        from fhr3.agents.simple import CheckCallAgent

        return CheckCallAgent(spec.agent_id)
    if spec.kind == "random":
        from fhr3.agents.simple import RandomLegalAgent

        return RandomLegalAgent(spec.agent_id)
    raise ValueError(f"unknown agent kind: {spec.kind!r}")


__all__ = ["Agent", "AgentSpec", "build_agent"]
