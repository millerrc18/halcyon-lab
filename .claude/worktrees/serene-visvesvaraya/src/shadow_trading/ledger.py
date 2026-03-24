"""Shadow trading placeholder.

Future implementation should map qualified recommendations to simulated entries/exits
through Alpaca paper or an internal execution model.
"""


def open_shadow_trade(recommendation_id: str) -> None:
    print(f"Opening shadow trade for recommendation {recommendation_id}")
