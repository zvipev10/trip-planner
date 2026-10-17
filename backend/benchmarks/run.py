"""Deterministic synthetic benchmark; no Israel road-data claims."""
import json
import random
from itertools import permutations
from time import perf_counter

from app.solver import optimize


def run():
    for stops in (0, 2, 5, 10, 20):
        rng = random.Random(42 + stops)
        size = stops + 2
        matrix = [[0 if i == j else rng.randint(100, 50000) for j in range(size)] for i in range(size)]
        started = perf_counter()
        order = optimize(matrix, 250)
        elapsed = perf_counter() - started
        distance = sum(matrix[a][b] for a, b in zip(order, order[1:]))
        result = {"source": "synthetic_directed_matrix", "stops": stops, "solverSeconds": round(elapsed, 4), "syntheticCostMeters": distance, "allStopsOnce": sorted(order) == list(range(size))}
        if stops <= 5:
            best = min(sum(matrix[a][b] for a, b in zip(path, path[1:])) for p in permutations(range(1, size - 1)) for path in [[0, *p, size - 1]])
            result["matchesExhaustiveOptimum"] = distance == best
        print(json.dumps(result))


if __name__ == "__main__":
    run()
