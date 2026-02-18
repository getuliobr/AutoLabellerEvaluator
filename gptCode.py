"""
OpenAI Batch API version of the GPT evaluation script.

Usage:
  python gptCode.py submit   - Build JSONL, upload, and create a batch job
  python gptCode.py status   - Check the status of the running batch
  python gptCode.py retrieve - Download results and save them to MongoDB

The batch ID is persisted in batch_state.json between steps.
"""

from config import config
import pymongo
import json
import math
import random
import sys
import time
import os

from openai import OpenAI
from tqdm import tqdm

client = OpenAI(
  api_key=config['OPENAI']['API_KEY'],
  base_url=config['OPENAI']['BASE_URL']
)

MODEL = config['OPENAI']['MODEL']
STATE_FILE = 'batch_state.json'
INPUT_FILE = 'batch_input.jsonl'

mongoClient = pymongo.MongoClient(config['DATABASE']['CONNECTION_STRING'])
db = mongoClient[config['DATABASE']['NAME']]

# get repos names (collection that doesnt have _ in the name)
repos = [col for col in db.list_collection_names() if '_' not in col]


def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)


def load_state():
    if not os.path.exists(STATE_FILE):
        print(f'No {STATE_FILE} found. Run "python gptCode.py submit" first.')
        sys.exit(1)
    with open(STATE_FILE, 'r') as f:
        return json.load(f)


def compute_sample_size(N, confidence=0.95, margin=0.05, p=0.5):
    """Cochran's formula with finite population correction.
    Returns the required sample size for a given population N.
    """
    z_scores = {0.90: 1.645, 0.95: 1.96, 0.99: 2.576}
    z = z_scores.get(confidence, 1.96)
    # Cochran's formula (infinite population)
    n0 = (z ** 2 * p * (1 - p)) / (margin ** 2)
    # Finite population correction
    n = n0 / (1 + (n0 - 1) / N)
    return math.ceil(n)


def submit():
    """Build the JSONL input file, upload it, and create a batch.
    Uses stratified random sampling (proportional allocation) to select
    a statistically representative subset at 95% confidence / 5% margin.
    """
    # Phase 1: collect all eligible requests grouped by repo
    requests_by_repo = {}  # repo -> list of request dicts

    for repo in repos:
        issueCollection = db[repo]
        resultsCollection = db[f'{repo}_results']
        aiResultsCollection = db[f'{repo}_ai_results']

        filtro = {
            "filtros.goodFirstIssue": 1,
            "topk": 1,
            "filtros.daysBefore": 30,
            "tecnica": "sbert"
        }

        repo_requests = []

        with resultsCollection.find(filtro).sort('data', 1) as results:
            for result in tqdm(results,
                               total=resultsCollection.count_documents(filtro),
                               desc=f'Preparing {repo}'):
                number = result['number']

                # skip if already processed
                if aiResultsCollection.find_one({
                    'number': number,
                    'model': MODEL
                }):
                    continue

                issue = issueCollection.find_one({
                  'number': number,
                  'created_at': {'$gte': '2020-07-01'},
                  'closed_at': {'$lte': '2024-01-31'},
                })

                if not issue:
                    continue

                body = issue['body']
                title = issue['title']
                message = (
                    f"You are a knowledgeable developer for the {repo} GitHub project\n\n"
                    f"Please give me just and only the code or code snippet you think "
                    f"would solve the following issue:\n\n"
                    f"# {title}\n\n"
                    f"{body}"
                )

                custom_id = f"{repo}_{number}"

                repo_requests.append({
                    "custom_id": custom_id,
                    "method": "POST",
                    "url": "/v1/chat/completions",
                    "body": {
                        "model": MODEL,
                        "seed": 42,
                        "temperature": 0,
                        "messages": [
                            {"role": "user", "content": message}
                        ]
                    }
                })

        if repo_requests:
            requests_by_repo[repo] = repo_requests

    # Phase 2: stratified random sampling
    N = sum(len(v) for v in requests_by_repo.values())  # total population

    if N == 0:
        print("No new requests to submit - all issues already have AI results.")
        return

    n = compute_sample_size(N)  # required sample size (95% CI, 5% margin)

    print(f'\nPopulation: {N} issues across {len(requests_by_repo)} projects')
    print(f'Sample size (95% confidence, 5% margin): {n}')
    print(f'\n{"Project":<50} {"Population":>10} {"Sample":>8}')
    print('-' * 70)

    sampled_requests = []
    random.seed(42)  # reproducible sampling

    for repo, repo_reqs in requests_by_repo.items():
        Nh = len(repo_reqs)  # stratum size
        # proportional allocation: nh = n * (Nh / N), at least 1
        nh = max(1, round(n * Nh / N))
        nh = min(nh, Nh)  # can't sample more than available

        sample = random.sample(repo_reqs, nh)
        sampled_requests.extend(sample)
        print(f'{repo:<50} {Nh:>10} {nh:>8}')

    print('-' * 70)
    total = len(sampled_requests)
    print(f'{"TOTAL":<50} {N:>10} {total:>8}')

    # Write JSONL file
    with open(INPUT_FILE, 'w', encoding='utf-8') as f:
        for req in sampled_requests:
            f.write(json.dumps(req, ensure_ascii=False) + '\n')

    print(f'\nWrote {total} requests to {INPUT_FILE}')

    # Upload the file
    print('Uploading input file...')
    batch_input = client.files.create(
        file=open(INPUT_FILE, 'rb'),
        purpose='batch'
    )
    print(f'Uploaded file: {batch_input.id}')

    # Create the batch
    print('Creating batch...')
    batch = client.batches.create(
        input_file_id=batch_input.id,
        endpoint="/v1/chat/completions",
        completion_window="24h"
    )
    print(f'Batch created: {batch.id}')
    print(f'Status: {batch.status}')

    save_state({
        'batch_id': batch.id,
        'input_file_id': batch_input.id,
        'total_requests': total
    })
    print(f'State saved to {STATE_FILE}. Run "python gptCode.py status" to check progress.')


def status():
    """Check the status of the current batch."""
    state = load_state()
    batch = client.batches.retrieve(state['batch_id'])

    print(f'Batch ID:    {batch.id}')
    print(f'Status:      {batch.status}')
    print(f'Total:       {batch.request_counts.total}')
    print(f'Completed:   {batch.request_counts.completed}')
    print(f'Failed:      {batch.request_counts.failed}')

    if batch.status == 'completed':
        print(f'\nBatch is done! Run "python gptCode.py retrieve" to download results.')
    elif batch.status == 'failed':
        print(f'\nBatch failed.')
        if batch.errors:
            for err in batch.errors.data:
                print(f'  Error: {err.message}')
    elif batch.status in ('in_progress', 'validating', 'finalizing'):
        print(f'\nBatch is still running. Check again later.')


def retrieve():
    """Download batch results and save them to MongoDB."""
    state = load_state()
    batch = client.batches.retrieve(state['batch_id'])

    if batch.status != 'completed':
        print(f'Batch status is "{batch.status}", not "completed". Cannot retrieve yet.')
        if batch.status in ('in_progress', 'validating', 'finalizing'):
            print('Run "python gptCode.py status" to check progress.')
        return

    output_file_id = batch.output_file_id
    if not output_file_id:
        print('No output file found on the batch.')
        return

    print(f'Downloading output file {output_file_id}...')
    content = client.files.content(output_file_id).text

    results = content.strip().split('\n')
    saved = 0
    errors = 0

    for line in tqdm(results, desc='Saving results to MongoDB'):
        result = json.loads(line)
        custom_id = result['custom_id']

        # parse "repo_number" - repo name may contain underscores,
        # but number is always the last segment
        parts = custom_id.rsplit('_', 1)
        repo = parts[0]
        number = int(parts[1])

        if result['response']['status_code'] != 200:
            print(f'  Error for {custom_id}: {result["response"]["body"]}')
            errors += 1
            continue

        response_body = result['response']['body']
        ai_response = response_body['choices'][0]['message']['content']

        aiResultsCollection = db[f'{repo}_ai_results']
        aiResultsCollection.update_one({
            'number': number,
            'model': MODEL,
        }, {'$set': {
            'number': number,
            'model': MODEL,
            'response': ai_response
        }}, upsert=True)
        saved += 1

    print(f'\nDone! Saved {saved} results, {errors} errors.')

    # Cleanup
    os.remove(INPUT_FILE) if os.path.exists(INPUT_FILE) else None
    os.remove(STATE_FILE) if os.path.exists(STATE_FILE) else None
    print('Cleaned up temporary files.')


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: python gptCode.py <submit|status|retrieve>')
        sys.exit(1)

    command = sys.argv[1].lower()

    if command == 'submit':
        submit()
    elif command == 'status':
        status()
    elif command == 'retrieve':
        retrieve()
    else:
        print(f'Unknown command: {command}')
        print('Usage: python gptCode.py <submit|status|retrieve>')
        sys.exit(1)