from ortools.constraint_solver import pywrapcp, routing_enums_pb2

from .provider import Matrix, PlanningError


def validate_matrix(matrix: Matrix, size: int) -> None:
    if len(matrix) != size or any(len(row) != size for row in matrix):
        raise PlanningError("invalid_provider_response", "Distance matrix has an invalid shape.", 502)
    for row in matrix:
        for value in row:
            if value is not None and (type(value) is not int or value < 0 or value > 10**12):
                raise PlanningError("invalid_provider_response", "Distance matrix contains invalid distances.", 502)


def optimize(matrix: Matrix, budget_ms: int = 1000) -> list[int]:
    size = len(matrix)
    if size < 2:
        raise ValueError("At least two endpoint nodes are required")
    validate_matrix(matrix, size)
    manager = pywrapcp.RoutingIndexManager(size, 1, [0], [size - 1])
    routing = pywrapcp.RoutingModel(manager)

    def distance(source, target):
        value = matrix[manager.IndexToNode(source)][manager.IndexToNode(target)]
        return value if value is not None else 10**15

    callback = routing.RegisterTransitCallback(distance)
    routing.SetArcCostEvaluatorOfAllVehicles(callback)
    # Remove forbidden arcs explicitly; a large penalty alone could permit them.
    for source in range(routing.Size()):
        for target in range(routing.Size() + 1):
            if matrix[manager.IndexToNode(source)][manager.IndexToNode(target)] is None:
                routing.NextVar(source).RemoveValue(target)
    parameters = pywrapcp.DefaultRoutingSearchParameters()
    parameters.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    parameters.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    parameters.time_limit.FromMilliseconds(budget_ms)
    solution = routing.SolveWithParameters(parameters)
    if solution is None:
        raise PlanningError("no_route_found", "No complete route was found within the calculation budget. Check locations or retry.")
    result = []
    index = routing.Start(0)
    while not routing.IsEnd(index):
        result.append(manager.IndexToNode(index))
        index = solution.Value(routing.NextVar(index))
    result.append(manager.IndexToNode(index))
    return result
