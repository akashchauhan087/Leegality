from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from .openapi import SCHEMA


@require_GET
def swagger_ui(request):
    return render(request, "routes/swagger.html")


@require_GET
def openapi_schema(request):
    return JsonResponse(SCHEMA, json_dumps_params={"indent": 2})
