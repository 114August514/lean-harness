"""Tracer Bullet test verification."""

from src.app import add, load_seeds


def test_tracer_add():
    assert add(1, 2) == 3


def test_tracer_load_seeds():
    seeds = load_seeds()
    assert isinstance(seeds, list)
