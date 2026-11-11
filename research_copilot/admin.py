"""Explicit setup commands: schema upgrades, key provisioning, and the SQLite ledger import."""
import argparse
import asyncio
import sys
from pathlib import Path


def _db_upgrade(args):
    from research_copilot.db.engine import database_url
    from research_copilot.db.migrate import upgrade
    upgrade(database_url())
    print('Database schema is up to date.')


def _keys_init(args):
    from research_copilot.storage.credential_keys import init_key_file, key_file_path
    path = init_key_file(Path(args.path).expanduser() if args.path else key_file_path())
    print(f'Created credential key file at {path}.')
    print('Back it up somewhere protected (for example an encrypted password manager). '
          'Without it, saved Notion credentials cannot be decrypted and you must reconnect.')


def _import_exports(args):
    from research_copilot.db.engine import Database
    from research_copilot.storage.export_store import import_sqlite_ledger

    async def run():
        db = Database.from_env()
        try:
            return await import_sqlite_ledger(Path(args.sqlite).expanduser(), db)
        finally:
            await db.close()

    imported, skipped = asyncio.run(run())
    print(f'Imported {imported} export record(s); {skipped} were already present.')


def build_parser():
    parser = argparse.ArgumentParser(prog='research-copilot-admin')
    commands = parser.add_subparsers(dest='command', required=True)

    db = commands.add_parser('db', help='Database schema').add_subparsers(dest='action', required=True)
    db.add_parser('upgrade', help='Apply application and checkpoint migrations').set_defaults(func=_db_upgrade)

    keys = commands.add_parser('keys', help='Credential encryption key').add_subparsers(dest='action', required=True)
    init = keys.add_parser('init', help='Create a new key file (never overwrites)')
    init.add_argument('--path', help='Key file location (default: MCP_CREDENTIAL_KEY_FILE or '
                                     '~/.config/research-copilot/credential-keys.json)')
    init.set_defaults(func=_keys_init)

    imports = commands.add_parser('import-exports', help='Import the legacy SQLite export ledger')
    default = Path.home() / '.local/share/research-copilot/exports.sqlite3'
    imports.add_argument('--sqlite', default=str(default), help=f'Ledger path (default: {default})')
    imports.set_defaults(func=_import_exports)

    evals = commands.add_parser('eval', help='Offline evaluation suites').add_subparsers(dest='suite', required=True)
    routing = evals.add_parser('routing', help='Score intent routing against a labelled query set')
    routing.add_argument('--router', choices=['llm', 'keyword'], default='llm',
                         help='llm runs the real classify_intent node; keyword is the baseline (no API calls)')
    routing.add_argument('--dataset', default='evals/datasets/routing.jsonl')
    routing.add_argument('--out', default='evals/results', help='Directory for the JSON report')
    routing.add_argument('--label', help='Suffix for the report filename, e.g. a prompt version')
    routing.add_argument('--model', help='Override LLM_MODEL for this run, e.g. gemini-3.5-flash-lite')
    routing.add_argument('--limit', type=int, help='Only evaluate the first N cases')
    routing.add_argument('--max-api-calls', type=int, default=200,
                         help='Stop once this many uncached LLM requests were made (default: 200)')
    routing.add_argument('--rpm', type=float, default=8,
                         help='Client-side request rate limit per minute; 0 disables (default: 8)')
    routing.add_argument('--cache', default='evals/.cache/llm_cache.sqlite',
                         help='SQLite LLM response cache; reruns of unchanged prompts are free')
    routing.add_argument('--no-cache', action='store_true', help='Always call the API')
    routing.add_argument('--verbose', action='store_true', help='Print each case as it runs')
    routing.set_defaults(func=_eval_routing)

    retrieval = evals.add_parser('retrieval', help='Score local retrieval on a BEIR-format dataset (no API calls)')
    retrieval.add_argument('--data-dir', default='evals/.cache/beir/scifact-download/scifact',
                           help='Folder with corpus.jsonl, queries.jsonl and qrels/<split>.tsv')
    retrieval.add_argument('--split', default='test')
    retrieval.add_argument('--index-dir', default='evals/.cache/qdrant', help='Local Qdrant folder for eval indexes')
    retrieval.add_argument('--chunk-size', type=int, default=500, help='Child chunk size (production: 500)')
    retrieval.add_argument('--chunk-overlap', type=int, default=100, help='Child chunk overlap (production: 100)')
    retrieval.add_argument('--configs', help='Comma-separated config names (default: all)')
    retrieval.add_argument('--off-topic', default='evals/datasets/routing.jsonl',
                           help='JSONL whose non-paper queries probe off-topic score separation; "" to skip')
    retrieval.add_argument('--limit', type=int, help='Only evaluate the first N queries')
    retrieval.add_argument('--out', default='evals/results')
    retrieval.add_argument('--label')
    retrieval.add_argument('--verbose', action='store_true')
    retrieval.set_defaults(func=_eval_retrieval)
    return parser


def _eval_retrieval(args):
    from research_copilot.evals.retrieval import run_cli
    return run_cli(args)


def _eval_routing(args):
    from research_copilot.evals.routing import run_cli
    return run_cli(args)


def main(argv=None):
    from dotenv import load_dotenv
    load_dotenv()
    args = build_parser().parse_args(argv)
    try:
        code = args.func(args)
    except Exception as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 1
    return code if isinstance(code, int) else 0


if __name__ == '__main__':
    sys.exit(main())
