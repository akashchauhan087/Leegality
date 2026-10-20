import json

from django.test import TestCase

from .models import Edge, Node, RouteQuery


class RouteApiTests(TestCase):
    def post(self, url, data):
        return self.client.post(url, json.dumps(data), content_type="application/json")

    def setUp(self):
        self.server_a = Node.objects.create(name="ServerA")
        self.server_b = Node.objects.create(name="ServerB")
        self.server_c = Node.objects.create(name="ServerC")

    def test_create_node_and_reject_duplicate(self):
        response = self.post("/nodes", {"name": " ServerD "})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["name"], "ServerD")
        self.assertEqual(self.post("/nodes", {"name": "ServerD"}).status_code, 400)
        self.assertEqual(self.post("/nodes", {"name": " "}).status_code, 400)

    def test_bad_json_and_non_object_body(self):
        for body in ("{", "[]", "null"):
            response = self.client.post("/nodes", body, content_type="application/json")
            self.assertEqual(response.status_code, 400)

    def test_create_edge_and_validate_inputs(self):
        data = {"source": "ServerA", "destination": "ServerB", "latency": 12.5}
        self.assertEqual(self.post("/edges", data).status_code, 201)
        self.assertEqual(self.post("/edges", data).status_code, 400)
        for latency in (0, -1, True, "12", None, float("inf"), float("nan"), 10**400):
            data["latency"] = latency
            self.assertEqual(self.post("/edges", data).status_code, 400)
        data.update(latency=1, destination="Missing")
        self.assertEqual(self.post("/edges", data).status_code, 400)

    def test_shortest_route_uses_cheaper_indirect_path(self):
        Edge.objects.create(source=self.server_a, destination=self.server_c, latency=50)
        Edge.objects.create(source=self.server_a, destination=self.server_b, latency=12.5)
        Edge.objects.create(source=self.server_b, destination=self.server_c, latency=10.9)
        response = self.post("/routes/shortest", {"source": "ServerA", "destination": "ServerC"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"total_latency": 23.4, "path": ["ServerA", "ServerB", "ServerC"]})
        self.assertEqual(RouteQuery.objects.count(), 1)

    def test_directed_edges_and_unreachable_history(self):
        Edge.objects.create(source=self.server_a, destination=self.server_b, latency=1)
        response = self.post("/routes/shortest", {"source": "ServerB", "destination": "ServerA"})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"error": "No path exists between ServerB and ServerA"})
        self.assertIsNone(RouteQuery.objects.get().total_latency)

    def test_cycles_do_not_prevent_finding_a_route(self):
        Edge.objects.create(source=self.server_a, destination=self.server_b, latency=2)
        Edge.objects.create(source=self.server_b, destination=self.server_a, latency=1)
        Edge.objects.create(source=self.server_b, destination=self.server_c, latency=3)
        response = self.post("/routes/shortest", {"source": "ServerA", "destination": "ServerC"})
        self.assertEqual(response.json(), {"total_latency": 5, "path": ["ServerA", "ServerB", "ServerC"]})

    def test_same_node_and_invalid_endpoint(self):
        response = self.post("/routes/shortest", {"source": "ServerA", "destination": "ServerA"})
        self.assertEqual(response.json(), {"total_latency": 0, "path": ["ServerA"]})
        self.assertEqual(self.post("/routes/shortest", {"source": "Missing", "destination": "ServerA"}).status_code, 400)
        self.assertEqual(RouteQuery.objects.count(), 1)

    def test_history_filters_and_limit(self):
        first = RouteQuery.objects.create(source="ServerA", destination="ServerB", total_latency=1, path=["ServerA", "ServerB"])
        RouteQuery.objects.filter(pk=first.pk).update(created_at="2026-02-20T14:32:00Z")
        RouteQuery.objects.create(source="ServerB", destination="ServerC", total_latency=2, path=["ServerB", "ServerC"])
        response = self.client.get("/routes/history", {"source": "ServerA", "destination": "ServerB", "date_from": "2026-02-20", "date_to": "2026-02-20", "limit": 1})
        self.assertEqual(response.status_code, 200)
        self.assertEqual([record["id"] for record in response.json()], [first.id])
        response = self.client.get("/routes/history", {"limit": 1})
        self.assertEqual(response.json()[0]["source"], "ServerB")

    def test_invalid_history_filters(self):
        for params in ({"limit": "abc"}, {"limit": 0}, {"limit": -1}, {"date_from": "bad"}, {"date_to": "2026-02-30"}, {"date_from": "2026-03-01", "date_to": "2026-02-01"}):
            self.assertEqual(self.client.get("/routes/history", params).status_code, 400)

    def test_list_endpoints_and_method_restrictions(self):
        self.assertEqual(len(self.client.get("/nodes").json()), 3)
        self.assertEqual(self.client.get("/edges").json(), [])
        self.assertEqual(self.client.get("/routes/shortest").status_code, 405)
