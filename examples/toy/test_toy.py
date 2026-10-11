"""Toy project for the reproledger demo: two tests, one metric.

Run the demo:
    repro verify examples/toy/recipe.json --no-clone --workdir examples/toy/demo
"""
import json


def test_addition():
    assert 1 + 1 == 2


def test_metrics_file_exists():
    # the recipe command writes this; the test just documents the contract
    assert True


if __name__ == "__main__":
    # `repro pytest` writes metrics; this is the manual equivalent:
    json.dump({"tests_passed": 2, "answer": 42},
              open("repro_metrics.json", "w"))
