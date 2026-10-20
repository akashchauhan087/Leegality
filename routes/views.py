import json
import math
from datetime import datetime, time, timezone

from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.urls import reverse
from django.utils.dateparse import parse_date, parse_datetime
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .models import Edge, Node, RouteQuery
from .services import find_shortest_route


def read_body(request):
    try:
        data = json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        raise ValueError("Request body must be valid JSON")
    if not isinstance(data, dict):
        raise ValueError("Request body must be a JSON object")
    return data


def read_name(data, field):
    value = data.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required")
    value = value.strip()
    if len(value) > 100:
        raise ValueError(f"{field} must be at most 100 characters")
    return value


def read_endpoints(data):
    source = read_name(data, "source")
    destination = read_name(data, "destination")
    existing = set(Node.objects.filter(name__in=[source, destination]).values_list("name", flat=True))
    if source not in existing or destination not in existing:
        raise ValueError("Source and destination nodes must exist")
    return source, destination


@require_GET
def index(request):
    return JsonResponse({
        "service": "Network route optimization",
        "endpoints": ["/nodes", "/edges", "/routes/shortest", "/routes/history"],
        "documentation": reverse("swagger-ui"),
        "schema": reverse("openapi-schema"),
    })


@require_http_methods(["GET", "POST"])
def nodes(request):
    if request.method == "GET":
        return JsonResponse(list(Node.objects.order_by("id").values("id", "name")), safe=False)
    try:
        name = read_name(read_body(request), "name")
        with transaction.atomic():
            node = Node.objects.create(name=name)
    except ValueError as error:
        return JsonResponse({"error": str(error)}, status=400)
    except IntegrityError:
        return JsonResponse({"error": "A node with this name already exists"}, status=400)
    return JsonResponse({"id": node.id, "name": node.name}, status=201)


@require_http_methods(["GET", "POST"])
def edges(request):
    if request.method == "GET":
        records = Edge.objects.select_related("source", "destination").order_by("id")
        return JsonResponse([{"id": edge.id, "source": edge.source.name, "destination": edge.destination.name, "latency": edge.latency} for edge in records], safe=False)
    try:
        data = read_body(request)
        source, destination = read_endpoints(data)
        latency = data.get("latency")
        if isinstance(latency, bool) or not isinstance(latency, (int, float)):
            raise ValueError("latency must be a positive finite number")
        try:
            latency = float(latency)
        except OverflowError:
            raise ValueError("latency must be a positive finite number")
        if not math.isfinite(latency) or latency <= 0:
            raise ValueError("latency must be a positive finite number")
        with transaction.atomic():
            edge = Edge.objects.create(source=Node.objects.get(name=source), destination=Node.objects.get(name=destination), latency=latency)
    except ValueError as error:
        return JsonResponse({"error": str(error)}, status=400)
    except IntegrityError:
        return JsonResponse({"error": "This directed edge already exists"}, status=400)
    return JsonResponse({"id": edge.id, "source": source, "destination": destination, "latency": latency}, status=201)


@require_POST
def shortest_route(request):
    try:
        source, destination = read_endpoints(read_body(request))
    except ValueError as error:
        return JsonResponse({"error": str(error)}, status=400)
    total_latency, path = find_shortest_route(source, destination)
    if total_latency is not None and not math.isfinite(total_latency):
        return JsonResponse({"error": "Total latency exceeds the supported numeric range"}, status=400)
    RouteQuery.objects.create(source=source, destination=destination, total_latency=total_latency, path=path)
    if total_latency is None:
        return JsonResponse({"error": f"No path exists between {source} and {destination}"}, status=404)
    return JsonResponse({"total_latency": total_latency, "path": path})


def read_timestamp(value, end_of_day=False):
    try:
        date = parse_date(value)
        timestamp = datetime.combine(date, time.max if end_of_day else time.min) if date else parse_datetime(value)
    except ValueError:
        timestamp = None
    if timestamp is None:
        raise ValueError("Dates must use ISO 8601, for example 2026-02-20 or 2026-02-20T14:32:00Z")
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return timestamp


@require_GET
def history(request):
    queries = RouteQuery.objects.order_by("-created_at", "-id")
    for field in ("source", "destination"):
        if field in request.GET:
            queries = queries.filter(**{field: request.GET[field]})
    try:
        start = read_timestamp(request.GET["date_from"]) if "date_from" in request.GET else None
        end = read_timestamp(request.GET["date_to"], end_of_day=True) if "date_to" in request.GET else None
        if start and end and start > end:
            raise ValueError("date_from must be before date_to")
        if start:
            queries = queries.filter(created_at__gte=start)
        if end:
            queries = queries.filter(created_at__lte=end)
        if "limit" in request.GET:
            try:
                limit = int(request.GET["limit"])
            except ValueError:
                raise ValueError("limit must be a positive integer")
            if limit <= 0:
                raise ValueError("limit must be a positive integer")
            queries = queries[:limit]
    except ValueError as error:
        return JsonResponse({"error": str(error)}, status=400)
    return JsonResponse(list(queries.values("id", "source", "destination", "total_latency", "path", "created_at")), safe=False)
