"""
OpenAI Batch API version of the GPT evaluation script.

Usage:
  python generateGPTCode.py submit              - Build JSONL, upload, and create a batch job
  python generateGPTCode.py submit --few-shot    - Same, but with few-shot examples from recommender
  python generateGPTCode.py status               - Check the status of the running batch
  python generateGPTCode.py retrieve             - Download results and save them to MongoDB

The batch ID is persisted in batch_state.json between steps.
"""

from config import config
import pymongo
import json
import math
import random
import sys
import argparse
import os
import requests as http_requests
from unidiff import PatchSet

from openai import OpenAI
from tqdm import tqdm

client = OpenAI(
  api_key=config['OPENAI']['API_KEY'],
  base_url=config['OPENAI']['BASE_URL']
)

MODEL = config['OPENAI']['MODEL']
STATE_FILE = 'batch_state.json'
INPUT_FILE = 'batch_input.jsonl'

REPOS = {
  'dotnet/aspnetcore': 'c_sharp',
  'dotnet/efcore': 'c_sharp',
  'dotnet/runtime': 'c_sharp',
  'files-community/Files': 'c_sharp',
  'apple/swift': 'cpp',
  'azerothcore/azerothcore-wotlk': 'cpp',
  'CleverRaven/Cataclysm-DDA': 'cpp',
  'godotengine/godot': 'cpp',
  'rizinorg/cutter': 'cpp',
  'cosmos/cosmos-sdk': 'go',
  'hashicorp/terraform-provider-aws': 'go',
  'hashicorp/terraform-provider-azurerm': 'go',
  'kubernetes/minikube': 'go',
  'pingcap/tidb': 'go',
  'apache/shardingsphere': 'java',
  'elastic/elasticsearch': 'java',
  'jabref/jabref': 'java',
  'provectus/kafka-ui': 'java',
  'trinodb/trino': 'java',
  'PipedreamHQ/pipedream': 'javascript',
  'ToolJet/ToolJet': 'javascript',
  'vercel/next.js': 'javascript',
  'WordPress/gutenberg': 'javascript',
  'nextcloud/server': 'php',
  'phpmyadmin/phpmyadmin': 'php',
  'apache/airflow': 'python',
  'pandas-dev/pandas': 'python',
  'Qiskit/qiskit': 'python',
  'scipy/scipy': 'python',
  'zulip/zulip': 'python',
  'appwrite/appwrite': 'typescript',
  'aws/aws-cdk': 'typescript',
  'elastic/kibana': 'typescript',
  'mattermost/mattermost': 'typescript',
  'microsoft/vscode': 'typescript',
}

mongoClient = pymongo.MongoClient(config['DATABASE']['CONNECTION_STRING'])
db = mongoClient[config['DATABASE']['NAME']]

def get_diff(repo, number):
    """Fetch the diff for an issue from MongoDB or GitHub."""
    diffCollection = db[f'{repo}_diff']
    issueCollection = db[repo]

    result = diffCollection.find_one({'number': number})
    if result:
        return result['diff']

    issue = issueCollection.find_one({'number': number})
    diff = []
    for pr in issue['prs']:
        diffURL = f'https://patch-diff.githubusercontent.com/raw/{repo}/pull/{pr}.diff'
        diff.append(http_requests.get(diffURL).text)
    doc = {'number': number, 'diff': diff}
    doc_size = len(json.dumps(doc, default=str).encode('utf-8'))
    if doc_size > 15_000_000:  # stay under 16 MB BSON limit
        print(f'  WARNING: diff for {repo}#{number} is ~{doc_size/1e6:.1f}MB, skipping MongoDB cache.')
    else:
        diffCollection.insert_one(doc)
    return diff


def get_code(repo, number):
    """Extract code changes from diffs, caching in MongoDB."""
    diffCodeCollection = db[f'{repo}_diff_code_results']

    dbSearch = diffCodeCollection.find_one({'number': number})
    if dbSearch:
        return dbSearch['codes']

    codes = []
    diffs = get_diff(repo, number)

    for diff in diffs:
        patch_set = PatchSet(diff)
        for patched_file in patch_set:
            FILES_FORMAT = ('.txt', '.md')
            if patched_file.path.lower().endswith(FILES_FORMAT):
                continue
            code = ''.join([line.value for hunk in patched_file for line in hunk])
            if len(code):
                codes.append(code)
    doc = {'number': number, 'codes': codes}
    doc_size = len(json.dumps(doc, default=str).encode('utf-8'))
    if doc_size > 15_000_000:  # stay under 16 MB BSON limit
        print(f'  WARNING: code for {repo}#{number} is ~{doc_size/1e6:.1f}MB, skipping MongoDB cache.')
    else:
        diffCodeCollection.insert_one(doc)
    return codes


def get_suggestion(repo, number, tecnica='sbert', topk=1, days_before=180):
    """Get code snippets and issue metadata from the recommender's top suggested issues.
    Returns a list of dicts: {'title': ..., 'body': ..., 'code': ...}
    """
    resultsCollection = db[f'{repo}_results']
    issueCollection = db[repo]
    issue = resultsCollection.find_one({
        'filtros.goodFirstIssue': 1,
        'number': number,
        'topk': topk,
        'filtros.daysBefore': days_before,
        'tecnica': tecnica
    })
    if not issue or 'issues_sugeridas' not in issue:
        return []

    suggestions = []
    for suggestion_number, _similarity in issue['issues_sugeridas']:
        codes = get_code(repo, suggestion_number)
        if not codes:
            continue
        suggestion_issue = issueCollection.find_one({'number': suggestion_number})
        suggestions.append({
            'title': suggestion_issue['title'] if suggestion_issue else f'Issue #{suggestion_number}',
            'body': suggestion_issue.get('body', '') if suggestion_issue else '',
            'code': '\n'.join(codes)
        })
    return suggestions


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


def submit(few_shot=False, tecnica='sbert', topk=1, days_before=180):
    """Build the JSONL input file, upload it, and create a batch.
    Uses stratified random sampling (proportional allocation) to select
    a statistically representative subset at 95% confidence / 5% margin.
    """
    # Phase 1: collect all eligible requests grouped by repo
    requests_by_repo = {}  # repo -> list of request dicts

    for repo in REPOS:
        issueCollection = db[repo]
        resultsCollection = db[f'{repo}_results']

        filtro = {
            "filtros.goodFirstIssue": 1,
            "topk": 1,
            "filtros.daysBefore": 30,
            "tecnica": "sbert"
        }

        repo_requests = []

        with resultsCollection.find(filtro).sort([('data', 1), ('number', 1)]) as results:
            for result in tqdm(results,
                               total=resultsCollection.count_documents(filtro),
                               desc=f'Preparing {repo}'):
                number = result['number']

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

                # Append few-shot examples from recommender suggestions
                if few_shot:
                    suggestions = get_suggestion(repo, number, tecnica=tecnica, topk=topk, days_before=days_before)
                    if suggestions:
                        examples = []
                        for s in suggestions[:5]:  # limit to 5 examples
                            examples.append(
                                f"The following issue was solved like this:\n\n"
                                f"# {s['title']}\n\n"
                                f"{s['body']}\n\n"
                                f"Solution:\n{s['code']}"
                            )
                        message += '\n\n---\n\n'.join(examples)

                tecnica = tecnica if few_shot else 'zeroshot'
                custom_id = f"{repo}_{number}_{few_shot}_{tecnica}_{topk}_{days_before}"

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
    total_population = sum(len(v) for v in requests_by_repo.values())  # total population

    if total_population == 0:
        print("No new requests to submit - all issues already have AI results.")
        return

    sample_size = compute_sample_size(total_population)  # required sample size (95% CI, 5% margin)

    print(f'\nPopulation: {total_population} issues across {len(requests_by_repo)} projects')
    print(f'Sample size (95% confidence, 5% margin): {sample_size}')
    print(f'\n{"Project":<50} {"Population":>10} {"Sample":>8}')
    print('-' * 70)

    sampled_requests = []

    for repo, repo_reqs in requests_by_repo.items():
        stratum_size = len(repo_reqs)  # stratum size
        # proportional allocation: nh = n * (Nh / N), at least 1
        nh = max(1, round(sample_size * stratum_size / total_population))
        nh = min(nh, stratum_size)    # can't sample more than available
        random.seed(42)     # reproducible sampling
        sample = random.sample([i for i in range(len(repo_reqs))], nh)
        sampled_requests.extend([repo_reqs[i] for i in sample])
        print(f'{repo:<50} {stratum_size:>10} {nh:>8}')
    
    print('-' * 70)
    total = len(sampled_requests)
    print(f'{"TOTAL":<50} {total_population:>10} {total:>8}')

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
        'total_requests': total,
        'few_shot': few_shot,
        'tecnica': tecnica,
        'topk': topk,
        'days_before': days_before
    })
    print(f'State saved to {STATE_FILE}. Run "python gptCode.py status" to check progress.')

def status(batch_id=None):
    """Check the status of the current batch."""
    state = load_state()
    batch_id = batch_id or state['batch_id']
    batch = client.batches.retrieve(batch_id)

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


def retrieve(batch_id=None, few_shot=None, tecnica=None, topk=None, days_before=None):
    """Download batch results and save them to MongoDB."""
    if not batch_id:
        state = load_state()
        batch_id = state['batch_id']
    batch = client.batches.retrieve(batch_id)

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
        if custom_id.startswith('aws/aws-cdk_26615'):
            "Input tokens exceed the configured limit of 272000 tokens. Your messages resulted in 579340 tokens. Please reduce the length of the messages."
            continue

        # parse "{repo}_{number}_{tecnica}_{topk}_{days_before}" - repo name may contain underscores,
        repo, number, few_shot, tecnica, topk, days_before = custom_id.rsplit('_', 5)
        number = int(number)
        few_shot = few_shot == 'True'
        topk = topk or int(topk)
        days_before = days_before or int(days_before)

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

    print(f'\nDone! Saved {saved} results, {errors} errors.')

    # Cleanup
    os.remove(INPUT_FILE) if os.path.exists(INPUT_FILE) else None
    os.remove(STATE_FILE) if os.path.exists(STATE_FILE) else None
    print('Cleaned up temporary files.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='OpenAI Batch API for GPT code evaluation')
    parser.add_argument('command', choices=['submit', 'status', 'retrieve'])
    parser.add_argument('--few-shot', action='store_true', help='Include few-shot examples from recommender')
    parser.add_argument('--tecnica', default='sbert', help='Recommender technique (default: sbert)')
    parser.add_argument('--topk', type=int, default=1, help='Top-k value for recommender (default: 1)')
    parser.add_argument('--days-before', type=int, default=180, help='Days before filter (default: 180)')
    parser.add_argument('--batch-id', type=str, required=False, help='Batch ID to retrieve (only for "retrieve" command)')
    args = parser.parse_args()

    if args.command == 'submit':
        submit(few_shot=args.few_shot, tecnica=args.tecnica, topk=args.topk, days_before=args.days_before)
    elif args.command == 'status':
        status(batch_id=args.batch_id)
    elif args.command == 'retrieve':
        # python .\generateGPTCode.py retrieve --batch-id batch_69b8aa9652e48190976f0910f2bd51e0 --few-shot --tecnica tfidf --topk 1 --days-before 180
        retrieve(batch_id=args.batch_id, few_shot=args.few_shot, tecnica=args.tecnica, topk=args.topk, days_before=args.days_before)