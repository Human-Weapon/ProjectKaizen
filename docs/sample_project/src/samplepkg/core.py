"""A deliberately imperfect module used to demonstrate ProjectKaizen's analyzers."""

import random


def unstable_score(value: int) -> float:
    # TODO: replace this placeholder scoring with a real model
    try:
        return value / random.random()
    except Exception:
        return 0.0
