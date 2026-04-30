"""
Reads batch_input_*.jsonl and generates responses using Ollama's
OpenAI-compatible API, appending results to a JSONL output file.

Usage:
  python generateOllamaCode.py
"""

from config import config
import glob
import logging
import json
import os
import sys

from datetime import datetime

from ollama import Client
from openai import OpenAI

from tqdm import tqdm

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    stream=sys.stdout,
)
log = logging.getLogger('generateOllamaCode')

'''
client = OpenAI(
  api_key='ollama',
  base_url=config['OLLAMA']['BASE_URL'] + '/v1'
)
'''
client = Client(host=config['OLLAMA']['BASE_URL'])

GEN_COUNT = 1
MODEL = config['OLLAMA']['MODEL']
INPUT_FILE_PREFIX = 'batch_input_'
OUTPUT_FILE = 'ollama_output.jsonl'
LOG_EVERY = 25  # log progress every N requests when stdout isn't a tty (nohup)


def load_processed_keys(path):
    """Return set of (custom_id, generation) tuples already in OUTPUT_FILE."""
    keys = set()
    if not os.path.exists(path):
        return keys
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                keys.add((rec['custom_id'], rec['generation']))
            except (json.JSONDecodeError, KeyError):
                continue
    return keys


def main():
    input_files = sorted(glob.glob(f'{INPUT_FILE_PREFIX}*.jsonl'))
    if not input_files:
        log.error('No %s*.jsonl files found. Run generateGPTCode.py submit first.', INPUT_FILE_PREFIX)
        return

    lines = []
    for fname in input_files:
        with open(fname, 'r', encoding='utf-8') as f:
            file_lines = f.readlines()
        log.info('Loaded %d requests from %s', len(file_lines), fname)
        lines.extend(file_lines)

    total = len(lines)
    log.info('Total: %d requests across %d file(s)', total, len(input_files))

    processed = load_processed_keys(OUTPUT_FILE)
    if processed:
        log.info('Found %d existing records in %s; will skip those', len(processed), OUTPUT_FILE)

    saved = 0
    errors = 0
    skipped = 0

    is_tty = sys.stdout.isatty()
    iterator = tqdm(lines, desc='Processing with Ollama') if is_tty else lines

    out_f = open(OUTPUT_FILE, 'a', encoding='utf-8')
    log.info('Appending responses to %s', OUTPUT_FILE)

    for idx, line in enumerate(iterator, start=1):
        req = json.loads(line)
        custom_id = req['custom_id']

        # parse "{repo}_{number}_{few_shot}_{tecnica}_{topk}_{days_before}"
        # repo name may contain slashes/underscores
        repo, number, few_shot, tecnica, topk, days_before = custom_id.rsplit('_', 5)
        number = int(number)
        few_shot = few_shot == 'True'
        topk = int(topk)
        days_before = int(days_before)

        if custom_id.startswith('aws/aws-cdk_26615'):
            skipped += 1
            continue

        # skip if all generations already in output file
        if all((custom_id, i) in processed for i in range(GEN_COUNT)):
            skipped += 1
            if not is_tty and idx % LOG_EVERY == 0:
                log.info('Progress %d/%d saved=%d skipped=%d errors=%d', idx, total, saved, skipped, errors)
            continue

        messages = req['body']['messages']

        try:
            for i in range(GEN_COUNT):
                if (custom_id, i) in processed:
                    continue
                '''
                response = client.chat.completions.create(
                    model=MODEL,
                    temperature=0.7,
                    messages=messages,
                    extra_body={'think': False}
                }

                ai_response = response.choices[0].message.content
                '''

                response = client.chat(
                    model=MODEL,
                    think=True,
                    options={'temperature': 0.7},
                    messages=messages,
                )
              
                print(json.dumps(response.model_dump(), ensure_ascii=False))

                ai_response = response.message.content

                record = {
                    'custom_id': custom_id,
                    'repo': repo,
                    'number': number,
                    'model': MODEL,
                    'generation': i,
                    'response': ai_response,
                    'few_shot': few_shot,
                    'tecnica': tecnica,
                    'topk': topk,
                    'days_before': days_before,
                    'metadata': json.dumps(response.model_dump(),ensure_ascii=False)
                }

                out_f.write(json.dumps(record, ensure_ascii=False) + '\n')
                out_f.flush()
                processed.add((custom_id, i))
                saved += 1

        except Exception as e:
            log.exception('Error for %s: %s', custom_id, e)
            errors += 1
            continue

        if not is_tty and idx % LOG_EVERY == 0:
            log.info('Progress %d/%d saved=%d skipped=%d errors=%d', idx, total, saved, skipped, errors)

    out_f.close()
    log.info('Done! saved=%d skipped=%d errors=%d', saved, skipped, errors)


if __name__ == '__main__':
    main()
