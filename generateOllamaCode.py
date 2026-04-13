"""
Reads batch_input.jsonl and generates responses using Ollama's
OpenAI-compatible API, saving results to MongoDB.

Usage:
  python generateOllamaCode.py
"""

from config import config
import pymongo
import json
import os

from openai import OpenAI
from tqdm import tqdm

client = OpenAI(
  api_key='ollama',
  base_url=config['OLLAMA']['BASE_URL'] + '/v1'
)

MODEL = config['OLLAMA']['MODEL']
INPUT_FILE = 'batch_input.jsonl'

mongoClient = pymongo.MongoClient(config['DATABASE']['CONNECTION_STRING'])
db = mongoClient[config['DATABASE']['NAME']]


def main():
    if not os.path.exists(INPUT_FILE):
        print(f'{INPUT_FILE} not found. Run generateGPTCode.py submit first.')
        return

    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    print(f'Loaded {len(lines)} requests from {INPUT_FILE}')

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
            response = client.chat.completions.create(
                model=MODEL,
                seed=42,
                temperature=0,
                reasoning_effort='high',
                messages=messages
            )

            ai_response = response.choices[0].message.content

            aiResultsCollection.update_one({
                'number': number,
                'model': MODEL,
                'few_shot': few_shot,
                'tecnica': tecnica,
                'topk': topk,
                'days_before': days_before
            }, {'$set': {
                'number': number,
                'model': MODEL,
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
