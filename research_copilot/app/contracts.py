"""OpenAPI metadata shared by the running app and the offline contract exporter."""
from fastapi.openapi.utils import get_openapi

from .schemas import ResearchEventOut, UploadEventOut


def stream_responses(model_name: str):
    return {200: {
        'description': 'SSE stream. Each data field contains one JSON event.',
        'content': {'text/event-stream': {'schema': {'type': 'string'}}},
        'x-event-schema': {'$ref': f'#/components/schemas/{model_name}'},
    }}


def install_contracts(app):
    def openapi():
        if app.openapi_schema is None:
            schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
            components = schema.setdefault('components', {}).setdefault('schemas', {})
            for model in (ResearchEventOut, UploadEventOut):
                event = model.model_json_schema(mode='serialization', ref_template='#/components/schemas/{model}')
                components.update(event.pop('$defs', {}))
                components[model.__name__] = event
            app.openapi_schema = schema
        return app.openapi_schema
    app.openapi = openapi
