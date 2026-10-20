from django.urls import path
from django.views.generic import RedirectView

from routes import docs, views

urlpatterns = [
    path("", views.index),
    path("nodes", views.nodes),
    path("edges", views.edges),
    path("routes/shortest", views.shortest_route),
    path("routes/history", views.history),
    path("swagger/", docs.swagger_ui, name="swagger-ui"),
    path("docs/", RedirectView.as_view(pattern_name="swagger-ui", permanent=False)),
    path("openapi.json", docs.openapi_schema, name="openapi-schema"),
]
