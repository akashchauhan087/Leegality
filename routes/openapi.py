def schema_ref(name):
    return {"$ref": f"#/components/schemas/{name}"}


def json_content(schema, examples):
    return {
        "application/json": {
            "schema": schema,
            "examples": {name: {"value": value} for name, value in examples.items()},
        }
    }


def error_response(description, examples):
    return {
        "description": description,
        "content": json_content(
            schema_ref("Error"),
            {name: {"error": message} for name, message in examples.items()},
        ),
    }


NAME = {
    "type": "string",
    "minLength": 1,
    "maxLength": 100,
    "description": "Case-sensitive node name. Surrounding whitespace is trimmed before validation.",
    "example": "ServerA",
}
ENDPOINTS = {
    "source": {**NAME, "description": "Name of an existing source node; trimmed and case-sensitive."},
    "destination": {
        **NAME,
        "description": "Name of an existing destination node; trimmed and case-sensitive.",
        "example": "ServerB",
    },
}
LATENCY = {
    "type": "number",
    "format": "double",
    "minimum": 0,
    "exclusiveMinimum": True,
    "description": (
        "Finite number strictly greater than zero. Strings, booleans, NaN and infinity are rejected. "
        "Use the same latency unit for every edge; the API does not convert units."
    ),
    "example": 12.5,
}
PATH = {
    "type": "array",
    "items": {"type": "string"},
    "description": "Node names in traversal order, including the source and destination.",
    "example": ["ServerA", "ServerB", "ServerD"],
}
TOTAL_LATENCY = {
    "type": "number",
    "format": "double",
    "minimum": 0,
    "description": "Sum of edge latencies along the returned path, in the same unit as the edges.",
    "example": 23.4,
}
BODY_ERRORS = {
    "Malformed JSON": "Request body must be valid JSON",
    "Non-object JSON": "Request body must be a JSON object",
}
ENDPOINT_ERRORS = {
    **BODY_ERRORS,
    "Missing source": "source is required",
    "Missing destination": "destination is required",
    "Source too long": "source must be at most 100 characters",
    "Destination too long": "destination must be at most 100 characters",
    "Unknown node": "Source and destination nodes must exist",
}
EDGE_EXAMPLES = {
    "First hop": {"source": "ServerA", "destination": "ServerB", "latency": 12.5},
    "Second hop": {"source": "ServerB", "destination": "ServerD", "latency": 10.9},
    "Slower direct edge": {"source": "ServerA", "destination": "ServerD", "latency": 50},
}
ROUTE_EXAMPLES = {
    "Cheapest route": {"source": "ServerA", "destination": "ServerD"},
    "Same node": {"source": "ServerA", "destination": "ServerA"},
    "No reverse path": {"source": "ServerD", "destination": "ServerA"},
}
HISTORY_EXAMPLE = [
    {
        "id": 2,
        "source": "ServerD",
        "destination": "ServerA",
        "total_latency": None,
        "path": [],
        "created_at": "2026-02-20T15:10:00Z",
    },
    {
        "id": 1,
        "source": "ServerA",
        "destination": "ServerD",
        "total_latency": 23.4,
        "path": ["ServerA", "ServerB", "ServerD"],
        "created_at": "2026-02-20T14:32:00Z",
    },
]
SERVICE_EXAMPLE = {
    "service": "Network route optimization",
    "endpoints": ["/nodes", "/edges", "/routes/shortest", "/routes/history"],
    "documentation": "/swagger/",
    "schema": "/openapi.json",
}
METHOD_NOT_ALLOWED = {
    "description": (
        "This HTTP method is not supported. The Allow header lists supported methods. "
        "Django returns an empty body, not a JSON error."
    ),
    "headers": {"Allow": {"description": "Allowed HTTP methods.", "schema": {"type": "string"}}},
}

SCHEMA = {
    "openapi": "3.0.3",
    "info": {
        "title": "Network Routes API",
        "version": "1.0.0",
        "description": (),
    },
    "security": [],
    "tags": [
        {"name": "Nodes", "description": "Create and list the servers in the network."},
        {"name": "Edges", "description": "Create and list directed connections with positive latency."},
        {"name": "Routes", "description": "Find the cheapest route and inspect saved query history."},
        {"name": "Service", "description": "Discover API and documentation URLs."},
    ],
    "paths": {
        "/": {
            "get": {
                "tags": ["Service"],
                "operationId": "getServiceInfo",
                "summary": "Get service information",
                "description": "Returns the API endpoint list and links to Swagger UI and this OpenAPI schema.",
                "responses": {
                    "200": {
                        "description": "Service information.",
                        "content": json_content(schema_ref("ServiceInfo"), {"Service": SERVICE_EXAMPLE}),
                    },
                    "405": METHOD_NOT_ALLOWED,
                },
            }
        },
        "/nodes": {
            "get": {
                "tags": ["Nodes"],
                "operationId": "listNodes",
                "summary": "List all nodes",
                "description": "Returns all nodes ordered by ID ascending. An empty network returns `[]`.",
                "responses": {
                    "200": {
                        "description": "Nodes in creation order.",
                        "content": json_content(
                            {"type": "array", "items": schema_ref("Node")},
                            {"Nodes": [{"id": 1, "name": "ServerA"}, {"id": 2, "name": "ServerB"}], "Empty": []},
                        ),
                    },
                    "405": METHOD_NOT_ALLOWED,
                },
            },
            "post": {
                "tags": ["Nodes"],
                "operationId": "createNode",
                "summary": "Add a node",
                "description": (
                    "Creates one uniquely named node. Missing, non-string or whitespace-only names return 400. "
                    "The 100-character limit and uniqueness check apply after trimming. `ServerA` and `servera` "
                    "are different nodes."
                ),
                "requestBody": {
                    "required": True,
                    "content": json_content(schema_ref("NodeInput"), {
                        "Server A": {"name": "ServerA"},
                        "Server B": {"name": "ServerB"},
                        "Server D": {"name": "ServerD"},
                    }),
                },
                "responses": {
                    "201": {
                        "description": "Node created; the response includes its generated ID and trimmed name.",
                        "content": json_content(schema_ref("Node"), {"Created": {"id": 1, "name": "ServerA"}}),
                    },
                    "400": error_response("Invalid request or duplicate name.", {
                        **BODY_ERRORS,
                        "Missing or blank name": "name is required",
                        "Name too long": "name must be at most 100 characters",
                        "Duplicate node": "A node with this name already exists",
                    }),
                    "405": METHOD_NOT_ALLOWED,
                },
            },
        },
        "/edges": {
            "get": {
                "tags": ["Edges"],
                "operationId": "listEdges",
                "summary": "List all directed edges",
                "description": "Returns all edges ordered by ID ascending, using node names instead of node IDs.",
                "responses": {
                    "200": {
                        "description": "Directed edges in creation order; an empty network returns `[]`.",
                        "content": json_content(
                            {"type": "array", "items": schema_ref("Edge")},
                            {"Edges": [{"id": 1, **EDGE_EXAMPLES["First hop"]}], "Empty": []},
                        ),
                    },
                    "405": METHOD_NOT_ALLOWED,
                },
            },
            "post": {
                "tags": ["Edges"],
                "operationId": "createEdge",
                "summary": "Add a directed edge",
                "description": (
                    "Both nodes must already exist. Latency must be a finite JSON number strictly greater than zero. "
                    "An existing source/destination pair returns 400 even if the new latency is different. "
                    "The reverse edge is a separate connection and must be created explicitly. Self-loops are allowed."
                ),
                "requestBody": {
                    "required": True,
                    "content": json_content(schema_ref("EdgeInput"), EDGE_EXAMPLES),
                },
                "responses": {
                    "201": {
                        "description": "Directed edge created.",
                        "content": json_content(schema_ref("Edge"), {"Created": {"id": 1, **EDGE_EXAMPLES["First hop"]}}),
                    },
                    "400": error_response("Invalid request, missing nodes, invalid latency or duplicate edge.", {
                        **ENDPOINT_ERRORS,
                        "Invalid latency": "latency must be a positive finite number",
                        "Duplicate edge": "This directed edge already exists",
                    }),
                    "405": METHOD_NOT_ALLOWED,
                },
            },
        },
        "/routes/shortest": {
            "post": {
                "tags": ["Routes"],
                "operationId": "findShortestRoute",
                "summary": "Find the route with the lowest total latency",
                "description": (
                    "Uses Dijkstra's algorithm on directed edges. Both endpoint nodes must exist. "
                    "The response includes the source and destination in the path. If several routes have the same "
                    "lowest latency, one is returned.\n\n"
                    "A successful result is saved to history. If both nodes exist but no directed path connects them, "
                    "the response is 404 and history stores `total_latency: null` with `path: []`. "
                    "Missing or unknown nodes return 400 and are not recorded. Routing from a node to itself "
                    "returns 200 with latency 0, even if the node has no edges."
                ),
                "requestBody": {
                    "required": True,
                    "content": json_content(schema_ref("RouteInput"), ROUTE_EXAMPLES),
                },
                "responses": {
                    "200": {
                        "description": "The cheapest route was found and saved to history.",
                        "content": json_content(schema_ref("RouteResult"), {
                            "Cheapest route": {"total_latency": 23.4, "path": ["ServerA", "ServerB", "ServerD"]},
                            "Same node": {"total_latency": 0, "path": ["ServerA"]},
                        }),
                    },
                    "400": error_response("Invalid request or total latency outside the supported numeric range.", {
                        **ENDPOINT_ERRORS,
                        "Numeric overflow": "Total latency exceeds the supported numeric range",
                    }),
                    "404": error_response("Both nodes exist, but no directed path connects them.", {
                        "No path": "No path exists between ServerD and ServerA",
                    }),
                    "405": METHOD_NOT_ALLOWED,
                },
            }
        },
        "/routes/history": {
            "get": {
                "tags": ["Routes"],
                "operationId": "listRouteHistory",
                "summary": "Get route query history",
                "description": (
                    "Returns saved queries ordered by creation time descending, then ID descending. "
                    "All supplied filters are combined with AND. The limit is applied after filtering and sorting; "
                    "omitting it returns all matches. Empty results return 200 with `[]`.\n\n"
                    "Source and destination filters are exact and case-sensitive; unlike POST input, these filters "
                    "are not trimmed. An unknown name simply produces no matches. Date bounds are inclusive. "
                    "A date-only lower bound starts at midnight, and a date-only upper bound includes the entire day. "
                    "Timestamps without a timezone are interpreted as UTC. An explicit offset is respected. "
                    "URL-encode a plus sign in timezone offsets as `%2B` when constructing query strings manually. "
                    "Equal date bounds are allowed; a lower bound after the upper bound returns 400."
                ),
                "parameters": [
                    {
                        "name": "source", "in": "query", "required": False,
                        "description": "Exact source node name. Omit to include all sources.",
                        "schema": {"type": "string"}, "example": "ServerA",
                    },
                    {
                        "name": "destination", "in": "query", "required": False,
                        "description": "Exact destination node name. Omit to include all destinations.",
                        "schema": {"type": "string"}, "example": "ServerD",
                    },
                    {
                        "name": "limit", "in": "query", "required": False,
                        "description": "Maximum number of results. Must be a positive integer; no default limit.",
                        "schema": {"type": "integer", "minimum": 1}, "example": 10,
                    },
                    {
                        "name": "date_from", "in": "query", "required": False,
                        "description": "Inclusive lower bound: ISO 8601 date or timestamp. Date-only values start at 00:00:00 UTC.",
                        "schema": {"type": "string"},
                        "examples": {
                            "Date": {"value": "2026-02-20"},
                            "UTC timestamp": {"value": "2026-02-20T14:32:00Z"},
                            "Offset timestamp": {"value": "2026-02-20T20:02:00+05:30"},
                        },
                    },
                    {
                        "name": "date_to", "in": "query", "required": False,
                        "description": "Inclusive upper bound: ISO 8601 date or timestamp. Date-only values end at 23:59:59.999999 UTC.",
                        "schema": {"type": "string"},
                        "examples": {
                            "Date": {"value": "2026-02-20"},
                            "UTC timestamp": {"value": "2026-02-20T23:59:59Z"},
                        },
                    },
                ],
                "responses": {
                    "200": {
                        "description": "Matching saved queries, newest first. Unreachable queries have null latency and an empty path.",
                        "content": json_content(
                            {"type": "array", "items": schema_ref("RouteHistory")},
                            {"Query history": HISTORY_EXAMPLE, "No matches": []},
                        ),
                    },
                    "400": error_response("Invalid limit, malformed date or reversed date range.", {
                        "Invalid limit": "limit must be a positive integer",
                        "Invalid date": "Dates must use ISO 8601, for example 2026-02-20 or 2026-02-20T14:32:00Z",
                        "Reversed range": "date_from must be before date_to",
                    }),
                    "405": METHOD_NOT_ALLOWED,
                },
            }
        },
    },
    "components": {
        "schemas": {
            "NodeInput": {
                "type": "object", "required": ["name"],
                "properties": {"name": NAME},
            },
            "Node": {
                "type": "object", "required": ["id", "name"],
                "properties": {"id": {"type": "integer", "format": "int64", "example": 1}, "name": NAME},
            },
            "EdgeInput": {
                "type": "object", "required": ["source", "destination", "latency"],
                "properties": {**ENDPOINTS, "latency": LATENCY},
            },
            "Edge": {
                "type": "object", "required": ["id", "source", "destination", "latency"],
                "properties": {
                    "id": {"type": "integer", "format": "int64", "example": 1},
                    **ENDPOINTS,
                    "latency": LATENCY,
                },
            },
            "RouteInput": {
                "type": "object", "required": ["source", "destination"],
                "properties": ENDPOINTS,
            },
            "RouteResult": {
                "type": "object", "required": ["total_latency", "path"],
                "properties": {"total_latency": TOTAL_LATENCY, "path": {**PATH, "minItems": 1}},
            },
            "RouteHistory": {
                "type": "object",
                "required": ["id", "source", "destination", "total_latency", "path", "created_at"],
                "properties": {
                    "id": {"type": "integer", "format": "int64", "example": 1},
                    **ENDPOINTS,
                    "total_latency": {
                        **TOTAL_LATENCY,
                        "nullable": True,
                        "description": "Total latency of a found route, or null when no path existed at query time.",
                    },
                    "path": {**PATH, "description": "Saved node sequence, or [] when no path existed."},
                    "created_at": {
                        "type": "string", "format": "date-time",
                        "description": "UTC time when the query was saved.",
                        "example": "2026-02-20T14:32:00Z",
                    },
                },
            },
            "Error": {
                "type": "object", "required": ["error"],
                "properties": {"error": {"type": "string", "description": "A readable description of the error."}},
            },
            "ServiceInfo": {
                "type": "object", "required": ["service", "endpoints", "documentation", "schema"],
                "properties": {
                    "service": {"type": "string"},
                    "endpoints": {"type": "array", "items": {"type": "string"}},
                    "documentation": {"type": "string", "description": "Relative Swagger UI URL."},
                    "schema": {"type": "string", "description": "Relative OpenAPI JSON URL."},
                },
            },
        }
    },
}
