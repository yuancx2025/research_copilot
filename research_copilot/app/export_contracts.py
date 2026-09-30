"""Export contracts without app startup, database connections, or engine creation.

Usage: python -m research_copilot.app.export_contracts --output openapi.json
"""
import argparse
from contextlib import redirect_stdout
import json
from pathlib import Path
import sys

from fastapi import FastAPI

from .contracts import install_contracts


def contract_document():
    # Some legacy imports print diagnostics. Never mix those with JSON output.
    with redirect_stdout(sys.stderr):
        from .api import api_router
        from .oauth_routes import oauth_router
        app = FastAPI(title='Research Copilot')
        app.include_router(api_router())
        # Route registration does not invoke the service. Include every mode's API.
        app.include_router(oauth_router(None))
        install_contracts(app)
        return app.openapi()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    document = contract_document()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(document, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
