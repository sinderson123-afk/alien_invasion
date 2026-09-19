"""Run export with Google ADC; import on the VPS with no Google dependency.

Stop writes to the old service before the final export. The export contains
password hashes and login tokens: transfer over SSH and keep permissions 0600.
"""
import argparse
import json
import os
from datetime import datetime
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['export', 'import'])
    parser.add_argument('file')
    parser.add_argument('--project')
    args = parser.parse_args()
    if args.action == 'export':
        from google.cloud import firestore
        db = firestore.Client(project=args.project)
        collections = list(db.collections())
        names = {collection.id for collection in collections}
        if names - {'users', 'codes', 'leaderboard'}:
            raise RuntimeError(f'Unexpected collections; inspect before migration: {names}')
        result = {'version': 1, 'collections': {}}
        for collection in collections:
            docs = list(collection.stream())
            if any(list(doc.reference.collections()) for doc in docs):
                raise RuntimeError('Nested collections found; inspect before migration')
            result['collections'][collection.id] = {doc.id: doc.to_dict() for doc in docs}
        def encode(value):
            if isinstance(value, datetime):
                return value.isoformat()
            raise TypeError(type(value).__name__)
        descriptor = os.open(args.file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, 'w', encoding='utf-8') as output:
            json.dump(result, output, default=encode)
    else:
        import storage
        result = json.loads(Path(args.file).read_text(encoding='utf-8'))
        if result.get('version') != 1:
            raise ValueError('Unsupported export format')
        if set(result['collections']) - {'users', 'codes', 'leaderboard'}:
            raise ValueError('Unexpected collection')
        db = storage.Client()
        with db.transaction():
            with db.connection() as conn:
                if conn.execute('SELECT COUNT(*) FROM documents').fetchone()[0]:
                    raise RuntimeError('Import requires an empty database; preserve existing data')
            for name, docs in result['collections'].items():
                for identifier, data in docs.items():
                    db.collection(name).document(identifier).set(data)
    print(json.dumps({name: len(docs) for name, docs in result['collections'].items()}))


if __name__ == '__main__':
    main()
