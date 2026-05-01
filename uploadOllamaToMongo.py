"""
Streams ollama_output.jsonl line-by-line and upserts each record into
{repo}_ai_results in MongoDB, mirroring generateGPTCode.py:_save_results_to_mongo.

The file is never fully loaded into memory; records are flushed in bulk batches.

Usage:
  python uploadOllamaToMongo.py
"""

from config import config
import json
import logging
import os
import sys

import pymongo
from pymongo import UpdateOne

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    stream=sys.stdout,
)
log = logging.getLogger('uploadOllamaToMongo')

INPUT_FILE = 'ollama_output.jsonl'
BATCH_SIZE = 500
LOG_EVERY = 1000

IS_2026_RUN = True

mongoClient = pymongo.MongoClient(config['DATABASE']['CONNECTION_STRING'])
db = mongoClient[config['DATABASE']['NAME']]


def flush(ops_by_repo):
    written = 0
    for repo, ops in ops_by_repo.items():
        if not ops:
            continue
        db[f'{repo}_ai_results'].bulk_write(ops, ordered=False)
        written += len(ops)
        ops.clear()
    return written


def main():
    if not os.path.exists(INPUT_FILE):
        log.error('%s not found', INPUT_FILE)
        return

    saved = 0
    skipped = 0
    errors = 0
    pending = 0
    ops_by_repo = {}

    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        for idx, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                errors += 1
                continue

            custom_id = rec.get('custom_id', '')
            if custom_id.startswith('aws/aws-cdk_26615'):
                skipped += 1
                continue

            repo = rec['repo']
            # rec['model'] = f'{rec["model"]}_off'
            doc = {
                'number': rec['number'],
                'model': rec['model'],
                'response': rec['response'],
                'few_shot': rec['few_shot'],
                'tecnica': rec['tecnica'],
                'topk': rec['topk'],
                'is_2026_run': IS_2026_RUN,
                'days_before': rec['days_before'],
                'metadata': rec.get('metadata', {}),
            }
            key = {
                'number': rec['number'],
                'model': rec['model'],
                'few_shot': rec['few_shot'],
                'tecnica': rec['tecnica'],
                'topk': rec['topk'],
                'days_before': rec['days_before'],
            }
            if 'generation' in rec:
                doc['generation'] = rec['generation']
                key['generation'] = rec['generation']

            ops_by_repo.setdefault(repo, []).append(
                UpdateOne(key, {'$set': doc}, upsert=True)
            )
            pending += 1

            if pending >= BATCH_SIZE:
                saved += flush(ops_by_repo)
                pending = 0

            if idx % LOG_EVERY == 0:
                log.info('Read %d lines | saved=%d skipped=%d errors=%d', idx, saved, skipped, errors)

    saved += flush(ops_by_repo)
    log.info('Done! saved=%d skipped=%d errors=%d', saved, skipped, errors)


if __name__ == '__main__':
    main()
