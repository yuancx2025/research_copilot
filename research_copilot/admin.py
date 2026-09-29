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
    return parser


def main(argv=None):
    from dotenv import load_dotenv
    load_dotenv()
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
    except Exception as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
