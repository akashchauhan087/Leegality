import heapq
from collections import defaultdict
from decimal import Decimal

from .models import Edge


def find_shortest_route(source, destination):
    graph = defaultdict(list)
    for start, end, latency in Edge.objects.values_list("source__name", "destination__name", "latency"):
        graph[start].append((end, Decimal(str(latency))))

    distances = {source: Decimal(0)}
    previous = {}
    queue = [(Decimal(0), source)]
    while queue:
        distance, current = heapq.heappop(queue)
        if distance != distances[current]:
            continue
        if current == destination:
            path = [current]
            while current in previous:
                current = previous[current]
                path.append(current)
            return float(distance), list(reversed(path))
        for neighbor, latency in graph[current]:
            candidate = distance + latency
            if neighbor not in distances or candidate < distances[neighbor]:
                distances[neighbor] = candidate
                previous[neighbor] = current
                heapq.heappush(queue, (candidate, neighbor))
    return None, []
