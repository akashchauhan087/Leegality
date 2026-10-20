# Network routes

A small Django API for the Leegality Python exercise. Uses SQLite and Dijkstra's algorithm. No extra API framework is needed.

## Run locally

Requires Python 3.10 or newer.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Open http://127.0.0.1:8000/ for the endpoint list. Run commands from this project folder.

## Swagger documentation

Open **http://127.0.0.1:8000/swagger/** for interactive API documentation. `/docs/` redirects there.
The OpenAPI 3.0 JSON schema is available at **http://127.0.0.1:8000/openapi.json** and can be imported into Postman or other OpenAPI tools.

The docs include request and response schemas, selectable examples, validation errors, status codes, and all history filters. Expand an endpoint and click **Try it out**, then **Execute** to send a request to your running server. These requests use your real local database.

For a complete example, create `ServerA`, `ServerB`, and `ServerD` using the node examples. Create all three edge examples, then run the shortest-route example. The cheaper route goes through `ServerB` with total latency `23.4`. Query history to see the saved result. Leave date filters empty when looking for queries you just ran; the documentation uses fixed example dates.

Swagger UI assets are supplied locally by [drf-spectacular-sidecar](https://github.com/tfranzel/drf-spectacular-sidecar). Once dependencies are installed, the docs do not need a CDN or an external validator. Django's development server serves the assets automatically.

The schema is maintained in `routes/openapi.py`, alongside the plain Django views. Update it when changing API behavior. The documentation tests validate the OpenAPI document, its examples, and representative live responses.

## Try it

```bash
curl -X POST http://127.0.0.1:8000/nodes -H 'Content-Type: application/json' -d '{"name":"ServerA"}'
curl -X POST http://127.0.0.1:8000/nodes -H 'Content-Type: application/json' -d '{"name":"ServerB"}'
curl -X POST http://127.0.0.1:8000/edges -H 'Content-Type: application/json' -d '{"source":"ServerA","destination":"ServerB","latency":12.5}'
curl -X POST http://127.0.0.1:8000/routes/shortest -H 'Content-Type: application/json' -d '{"source":"ServerA","destination":"ServerB"}'
curl 'http://127.0.0.1:8000/routes/history?source=ServerA&limit=10'
```

## API

| Method | Endpoint | Purpose |
| --- | --- | --- |
| POST | `/nodes` | Create a uniquely named node |
| GET | `/nodes` | List nodes |
| POST | `/edges` | Create a directed edge with positive latency |
| GET | `/edges` | List edges |
| POST | `/routes/shortest` | Find the route with the lowest total latency |
| GET | `/routes/history` | List route queries, newest first |

History accepts `source`, `destination`, `limit`, `date_from`, and `date_to`. Dates use ISO 8601; date-only filters include the whole day. Timestamps without an offset are interpreted as UTC.

Edges are directed: A → B does not imply B → A. Names are trimmed and case-sensitive. A route from a node to itself has zero latency. Queries with no path are saved with `total_latency: null` and `path: []`; invalid requests are not saved. The optional delete APIs are not implemented.

This is a local development project with no authentication. Development settings are in `config/settings.py`; configure secrets, hosts and deployment security before hosting it publicly.

## Tests

```bash
pip install -r requirements-dev.txt
python manage.py test
```
