"""
Reads batch_input.jsonl and generates responses using Ollama's
OpenAI-compatible API, saving results to MongoDB.

Usage:
  python generateOllamaCode.py
"""

from config import config
import glob
import pymongo
import json
import os

from openai import OpenAI
from tqdm import tqdm

client = OpenAI(
  api_key='ollama',
  base_url=config['OLLAMA']['BASE_URL'] + '/v1'
)

GEN_COUNT = 10
MODEL = config['OLLAMA']['MODEL']
INPUT_FILE_PREFIX = 'batch_input_'

mongoClient = pymongo.MongoClient(config['DATABASE']['CONNECTION_STRING'])
db = mongoClient[config['DATABASE']['NAME']]


def main():
    input_files = sorted(glob.glob(f'{INPUT_FILE_PREFIX}*.jsonl'))
    if not input_files:
        print(f'No {INPUT_FILE_PREFIX}*.jsonl files found. Run generateGPTCode.py submit first.')
        return

    lines = []
    for fname in input_files:
        with open(fname, 'r', encoding='utf-8') as f:
            file_lines = f.readlines()
        print(f'Loaded {len(file_lines)} requests from {fname}')
        lines.extend(file_lines)

    print(f'Total: {len(lines)} requests across {len(input_files)} file(s)')

    saved = 0
    errors = 0

    for line in tqdm(lines, desc='Processing with Ollama'):
        req = json.loads(line)
        custom_id = req['custom_id']

        # parse "{repo}_{number}_{few_shot}_{tecnica}_{topk}_{days_before}"
        # repo name may contain slashes/underscores
        repo, number, few_shot, tecnica, topk, days_before = custom_id.rsplit('_', 5)
        number = int(number)
        few_shot = few_shot == 'True'
        topk = int(topk)
        days_before = int(days_before)

        aiResultsCollection = db[f'{repo}_ai_results']

        # skip if already processed
        if aiResultsCollection.find_one({
            'number': number,
            'model': MODEL,
            'few_shot': few_shot,
            'tecnica': tecnica,
            'topk': topk,
            'days_before': days_before
        }):
            continue

        if custom_id.startswith('aws/aws-cdk_26615'):
            continue

        messages = req['body']['messages']

        try:
            for i in range(GEN_COUNT):
                response = client.chat.completions.create(
                    model=MODEL,
                    temperature=0.7,
                    messages=messages,
                    extra_body={'think': True}
                )

                ai_response = response.choices[0].message.content

                aiResultsCollection.update_one({
                    'number': number,
                    'model': MODEL,
                    'generation': i,
                    'few_shot': few_shot,
                    'tecnica': tecnica,
                    'topk': topk,
                    'days_before': days_before
                }, {'$set': {
                    'number': number,
                    'model': MODEL,
                    'generation': i,
                    'response': ai_response,
                    'few_shot': few_shot,
                    'tecnica': tecnica,
                    'topk': topk,
                    'days_before': days_before
                }}, upsert=True)
                saved += 1

        except Exception as e:
            print(f'\n  Error for {custom_id}: {e}')
            errors += 1
            continue

    print(f'\nDone! Saved {saved} results, {errors} errors.')


if __name__ == '__main__':
    main()
