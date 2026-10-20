from django.contrib.staticfiles import finders
from django.test import SimpleTestCase, TestCase
from django.urls import resolve, reverse
from openapi_schema_validator import OAS30Validator
from openapi_spec_validator import OpenAPIV30SpecValidator


def validate_payload(document, schema, payload):
    OAS30Validator(
        {**schema, "components": document["components"]},
        format_checker=OAS30Validator.FORMAT_CHECKER,
    ).validate(payload)


class DocumentationTests(SimpleTestCase):
    def test_swagger_page_loads_with_local_assets(self):
        response = self.client.get(reverse("swagger-ui"))
        self.assertContains(response, "SwaggerUIBundle")
        self.assertContains(response, 'url: "/openapi.json"')
        self.assertContains(response, "validatorUrl: null")
        for filename in ("swagger-ui.css", "swagger-ui-bundle.js", "favicon-32x32.png"):
            asset = f"drf_spectacular_sidecar/swagger-ui-dist/{filename}"
            self.assertContains(response, f"/static/{asset}")
            self.assertIsNotNone(finders.find(asset))
        self.assertRedirects(self.client.get("/docs/"), "/swagger/")

    def test_schema_is_valid_and_documents_existing_routes(self):
        response = self.client.get(reverse("openapi-schema"))
        self.assertEqual(response.status_code, 200)
        document = response.json()
        OpenAPIV30SpecValidator(document).validate()
        for path in document["paths"]:
            with self.subTest(path=path):
                self.assertIsNotNone(resolve(path).func)

    def test_documented_examples_match_their_schemas(self):
        document = self.client.get(reverse("openapi-schema")).json()
        for path, operations in document["paths"].items():
            for method, operation in operations.items():
                bodies = list(operation["responses"].values())
                if "requestBody" in operation:
                    bodies.append(operation["requestBody"])
                for body in bodies:
                    media = body.get("content", {}).get("application/json")
                    if media:
                        for name, example in media["examples"].items():
                            with self.subTest(path=path, method=method, example=name):
                                validate_payload(document, media["schema"], example["value"])
                for parameter in operation.get("parameters", []):
                    examples = parameter.get("examples", {}).values()
                    if "example" in parameter:
                        examples = [{"value": parameter["example"]}]
                    for example in examples:
                        validate_payload(document, parameter["schema"], example["value"])

    def test_documentation_is_read_only(self):
        for name in ("swagger-ui", "openapi-schema"):
            self.assertEqual(self.client.post(reverse(name)).status_code, 405)


class DocumentationContractTests(TestCase):
    def setUp(self):
        self.document = self.client.get(reverse("openapi-schema")).json()

    def request_and_validate(self, method, path, expected_status, data=None):
        if method == "post":
            response = self.client.post(path, data=data, content_type="application/json")
        else:
            response = self.client.get(path, data=data or {})
        self.assertEqual(response.status_code, expected_status, response.content)
        operation = self.document["paths"][path][method]
        schema = operation["responses"][str(expected_status)]["content"]["application/json"]["schema"]
        validate_payload(self.document, schema, response.json())
        return response.json()

    def test_swagger_walkthrough_matches_live_responses(self):
        paths = self.document["paths"]
        for path in ("/nodes", "/edges"):
            examples = paths[path]["post"]["requestBody"]["content"]["application/json"]["examples"]
            for example in examples.values():
                self.request_and_validate("post", path, 201, example["value"])
            self.request_and_validate("get", path, 200)
        route_examples = paths["/routes/shortest"]["post"]["requestBody"]["content"]["application/json"]["examples"]
        route = self.request_and_validate("post", "/routes/shortest", 200, route_examples["Cheapest route"]["value"])
        self.assertEqual(route, {"total_latency": 23.4, "path": ["ServerA", "ServerB", "ServerD"]})
        self.request_and_validate("post", "/routes/shortest", 200, route_examples["Same node"]["value"])
        self.request_and_validate("post", "/routes/shortest", 404, route_examples["No reverse path"]["value"])
        history = self.request_and_validate("get", "/routes/history", 200)
        self.assertEqual(len(history), 3)
        self.assertIsNone(history[0]["total_latency"])
        self.assertEqual(history[0]["path"], [])
        filtered = self.request_and_validate("get", "/routes/history", 200, {"source": "ServerA", "destination": "ServerD", "limit": 1})
        self.assertEqual(filtered[0]["path"], route["path"])
        service = self.request_and_validate("get", "/", 200)
        self.assertEqual(service["documentation"], reverse("swagger-ui"))

    def test_documented_error_messages_match_live_responses(self):
        cases = [
            ("post", "/nodes", {}, "Missing or blank name"),
            ("post", "/routes/shortest", {"source": "Missing", "destination": "Missing"}, "Unknown node"),
            ("get", "/routes/history", {"limit": "no"}, "Invalid limit"),
            ("get", "/routes/history", {"date_from": "bad"}, "Invalid date"),
            ("get", "/routes/history", {"date_from": "2026-03-01", "date_to": "2026-02-01"}, "Reversed range"),
        ]
        for method, path, data, example_name in cases:
            with self.subTest(path=path, example=example_name):
                payload = self.request_and_validate(method, path, 400, data)
                media = self.document["paths"][path][method]["responses"]["400"]["content"]["application/json"]
                self.assertEqual(payload, media["examples"][example_name]["value"])
