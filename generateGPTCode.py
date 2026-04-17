"""
OpenAI Batch API version of the GPT evaluation script.

Usage:
  python generateGPTCode.py submit             - Build JSONL for all 3 scenarios, upload, create batch
  python generateGPTCode.py submit --dry-run   - Build JSONL only; do not upload or create a batch
  python generateGPTCode.py status             - Check the status of the running batch
  python generateGPTCode.py retrieve           - Download results, upsert each scenario into MongoDB

Each sampled issue gets three requests in the same batch: zeroshot, sbert top-1 @180d, tfidf top-1 @180d.
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

from openai import OpenAI
from tqdm import tqdm

from github_diff import get_diff

client = OpenAI(
  api_key=config['OPENAI']['API_KEY'],
  base_url=config['OPENAI']['BASE_URL']
)

MODEL = config['OPENAI']['MODEL']
STATE_FILE = 'batch_state.json'
INPUT_FILE_PREFIX = 'batch_input_'
# Org-wide enqueued-token cap is 900k. Stay under with margin so a single
# slightly-larger-than-estimated request can't push us over.
MAX_BATCH_TOKENS = 800_000

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

def get_suggestion(repo, number, tecnica='sbert', topk=1, days_before=180):
    """Get code snippets and issue metadata from the recommender's top suggested issues.

    Returns (suggestions, error_reason).
      - suggestions: list of dicts {'title', 'body', 'code'}.
      - error_reason: None unless the recommender produced suggestions but every
        one of them had a diff-fetch failure. In that case the caller should
        skip the request entirely rather than send a useless few-shot prompt.
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
        return [], None

    suggestions = []
    failure_reasons = []
    for suggestion_number, _similarity in issue['issues_sugeridas']:
        diff_list, errors = get_diff(repo, suggestion_number, db)
        if errors:
            err_msg = '; '.join(f'PR#{p}: {r}' for p, r in errors)
            failure_reasons.append(f'#{suggestion_number}: {err_msg}')
            continue
        if not diff_list:
            failure_reasons.append(f'#{suggestion_number}: no PRs linked')
            continue
        suggestion_issue = issueCollection.find_one({'number': suggestion_number})
        suggestions.append({
            'title': suggestion_issue['title'] if suggestion_issue else f'Issue #{suggestion_number}',
            'body': suggestion_issue.get('body', '') if suggestion_issue else '',
            'code': '\n'.join(diff_list)
        })
    if not suggestions and failure_reasons:
        return [], '; '.join(failure_reasons)
    return suggestions, None


SCENARIOS = [
    {'few_shot': False, 'tecnica': 'zeroshot', 'topk': 1, 'days_before': 180},
    {'few_shot': True,  'tecnica': 'sbert',    'topk': 1, 'days_before': 180},
    {'few_shot': True,  'tecnica': 'tfidf',    'topk': 1, 'days_before': 180},
]


def build_message(repo, title, body, number, scenario):
    """Returns (message, error_reason). message is None if the request should be skipped."""
    message = (
        f"You are a knowledgeable developer for the {repo} GitHub project\n\n"
        f"Please give me just and only the git diff you think would solve the "
        f"following issue:\n\n"
        f"# {title}\n\n"
        f"{body}"
    )
    if scenario['few_shot']:
        suggestions, error = get_suggestion(
            repo, number,
            tecnica=scenario['tecnica'],
            topk=scenario['topk'],
            days_before=scenario['days_before'],
        )
        if error:
            return None, error
        if suggestions:
            examples = []
            for s in suggestions[:5]:
                examples.append(
                    f"The following issue was solved like this:\n\n"
                    f"# {s['title']}\n\n"
                    f"{s['body']}\n\n"
                    f"Solution:\n{s['code']}"
                )
            message += '\n\n---\n\n'.join(examples)
    return message, None


def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)


def load_state():
    if not os.path.exists(STATE_FILE):
        print(f'No {STATE_FILE} found. Run "python generateGPTCode.py submit" first.')
        sys.exit(1)
    with open(STATE_FILE, 'r') as f:
        state = json.load(f)
    # Backward-compat: old single-batch state -> wrap as one chunk.
    if 'chunks' not in state and 'batch_id' in state:
        state = {
            'chunks': [{
                'file': 'batch_input.jsonl',
                'input_file_id': state.get('input_file_id'),
                'batch_id': state['batch_id'],
                'request_count': state.get('total_requests', 0),
                'estimated_tokens': None,
            }],
            'current': 0,
        }
    return state


def estimate_tokens(text):
    """Rough char->token approximation. Overestimates slightly for code, which is safe."""
    return len(text) // 4


def chunk_requests(requests, max_tokens):
    """Greedy split into chunks whose summed estimated tokens stay <= max_tokens.
    A single request larger than max_tokens still gets its own chunk (the API may reject it).
    """
    chunks = []
    current = []
    current_tokens = 0
    for req in requests:
        msg = req['body']['messages'][0]['content']
        tokens = estimate_tokens(msg)
        if current and current_tokens + tokens > max_tokens:
            chunks.append(current)
            current = []
            current_tokens = 0
        current.append(req)
        current_tokens += tokens
    if current:
        chunks.append(current)
    return chunks


def _submit_chunk(chunk_meta):
    """Upload chunk_meta['file'] and create a batch; mutate chunk_meta in place."""
    print(f"Uploading {chunk_meta['file']}...")
    batch_input = client.files.create(file=open(chunk_meta['file'], 'rb'), purpose='batch')
    chunk_meta['input_file_id'] = batch_input.id
    print(f'  uploaded as {batch_input.id}')
    batch = client.batches.create(
        input_file_id=batch_input.id,
        endpoint='/v1/chat/completions',
        completion_window='24h',
    )
    chunk_meta['batch_id'] = batch.id
    print(f'  batch {batch.id} created (status: {batch.status})')
    return batch


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


def submit(dry_run=False):
    """Build the JSONL input file for all three scenarios, upload it, and create a batch.
    Uses stratified random sampling (proportional allocation) to select a statistically
    representative subset of issues at 95% confidence / 5% margin, then emits one request
    per scenario (zeroshot, sbert, tfidf) for each sampled issue.
    """
    # Phase 1: collect eligible issues per repo
    issues_by_repo = {}  # repo -> list of issue dicts {number, title, body}

    for repo in REPOS:
        issueCollection = db[repo]
        resultsCollection = db[f'{repo}_results']

        filtro = {
            "filtros.goodFirstIssue": 1,
            "topk": 1,
            "filtros.daysBefore": 30,
            "tecnica": "sbert"
        }

        repo_issues = []

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

                repo_issues.append({
                    'number': number,
                    'title': issue['title'],
                    'body': issue['body'],
                })

        if repo_issues:
            issues_by_repo[repo] = repo_issues

    # Phase 2: stratified random sampling over issues
    total_population = sum(len(v) for v in issues_by_repo.values())

    if total_population == 0:
        print("No eligible issues to submit.")
        return

    sample_size = compute_sample_size(total_population)  # 95% CI, 5% margin

    print(f'\nPopulation: {total_population} issues across {len(issues_by_repo)} projects')
    print(f'Sample size (95% confidence, 5% margin): {sample_size}')
    print(f'Scenarios per issue: {len(SCENARIOS)}')
    print(f'\n{"Project":<50} {"Population":>10} {"Sample":>8}')
    print('-' * 70)

    sampled_issues = []  # list of (repo, issue) tuples

    for repo, repo_issues in issues_by_repo.items():
        stratum_size = len(repo_issues)
        # proportional allocation: nh = n * (Nh / N), at least 1
        nh = max(1, round(sample_size * stratum_size / total_population))
        nh = min(nh, stratum_size)
        random.seed(42)  # reproducible sampling per stratum
        sample_idx = random.sample(range(stratum_size), nh)
        sampled_issues.extend((repo, repo_issues[i]) for i in sample_idx)
        print(f'{repo:<50} {stratum_size:>10} {nh:>8}')

    print('-' * 70)
    sampled_count = len(sampled_issues)
    print(f'{"TOTAL":<50} {total_population:>10} {sampled_count:>8}')

    # Phase 3: expand sampled issues across scenarios
    sampled_requests = []
    missing_log_path = 'missing_diffs.txt'
    skipped = 0
    missing_log = open(missing_log_path, 'w', encoding='utf-8')
    for repo, issue in tqdm(sampled_issues, desc='Building requests'):
        current_scenario_requests = []
        for scenario in SCENARIOS:
            message, error = build_message(repo, issue['title'], issue['body'], issue['number'], scenario)
            if error:
                missing_log.write(f"{repo} {issue['number']} ({scenario['tecnica']}): {error}\n")
                missing_log.flush()
                skipped += 1
                break
            custom_id = (
                f"{repo}_{issue['number']}_{scenario['few_shot']}"
                f"_{scenario['tecnica']}_{scenario['topk']}_{scenario['days_before']}"
            )
            current_scenario_requests.append({
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
        if len(current_scenario_requests) == len(SCENARIOS):
            sampled_requests.extend(current_scenario_requests)

    missing_log.close()
    total = len(sampled_requests)

    if total == 0:
        print('No requests built; nothing to submit.')
        return

    # Phase 4: chunk by token budget and write one JSONL per chunk
    chunks = chunk_requests(sampled_requests, MAX_BATCH_TOKENS)
    print(f'\nBuilt {total} requests; split into {len(chunks)} chunk(s) under {MAX_BATCH_TOKENS:,} tokens each')
    if skipped:
        print(f'Skipped {skipped} requests with unfetchable suggestion diffs; see {missing_log_path}')

    chunk_meta = []
    for i, chunk in enumerate(chunks):
        fname = f'{INPUT_FILE_PREFIX}{i:03d}.jsonl'
        with open(fname, 'w', encoding='utf-8') as f:
            for req in chunk:
                f.write(json.dumps(req, ensure_ascii=False) + '\n')
        size_mb = os.path.getsize(fname) / 1e6
        tokens = sum(estimate_tokens(r['body']['messages'][0]['content']) for r in chunk)
        print(f'  chunk {i}: {len(chunk):>4} requests, ~{tokens:>9,} tokens, {size_mb:>5.2f} MB -> {fname}')
        chunk_meta.append({
            'file': fname,
            'input_file_id': None,
            'batch_id': None,
            'request_count': len(chunk),
            'estimated_tokens': tokens,
        })

    if dry_run:
        print('\n--dry-run set: skipping upload and batch creation.')
        return

    # Submit only the first chunk; the rest wait until retrieve advances.
    print(f'\nSubmitting chunk 0 ({chunk_meta[0]["request_count"]} requests, ~{chunk_meta[0]["estimated_tokens"]:,} tokens)...')
    _submit_chunk(chunk_meta[0])

    save_state({'chunks': chunk_meta, 'current': 0})
    print(f'\nState saved to {STATE_FILE}.')
    print(f'Run "python generateGPTCode.py status" to check progress.')
    if len(chunk_meta) > 1:
        print(f'When chunk 0 completes, "python generateGPTCode.py retrieve" will save its results AND auto-submit chunk 1.')

def status(batch_id=None):
    """Show progress for every chunk; flag the one currently in flight."""
    if batch_id:
        batch = client.batches.retrieve(batch_id)
        print(f'Batch {batch.id}: {batch.status} '
              f'({batch.request_counts.completed}/{batch.request_counts.total}, '
              f'{batch.request_counts.failed} failed)')
        return

    state = load_state()
    chunks = state['chunks']
    current = state['current']

    for i, c in enumerate(chunks):
        marker = '>>' if i == current else '  '
        if not c['batch_id']:
            print(f'{marker} chunk {i}: pending submission ({c["request_count"]} requests, ~{c.get("estimated_tokens") or 0:,} tokens)')
            continue
        batch = client.batches.retrieve(c['batch_id'])
        rc = batch.request_counts
        print(f'{marker} chunk {i}: {batch.status:<12} {rc.completed:>4}/{rc.total:<4} '
              f'({rc.failed} failed)  batch={c["batch_id"]}')
        if batch.status == 'failed' and batch.errors:
            for err in batch.errors.data:
                print(f'      error: {err.message}')


def _save_results_to_mongo(content):
    """Parse a batch output JSONL and upsert each response into {repo}_ai_results."""
    saved = 0
    errors = 0
    for line in tqdm(content.strip().split('\n'), desc='Saving results to MongoDB'):
        result = json.loads(line)
        custom_id = result['custom_id']
        if custom_id.startswith('aws/aws-cdk_26615'):
            # Known oversized issue (~579k input tokens, model cap is lower).
            continue

        repo, number, few_shot, tecnica, topk, days_before = custom_id.rsplit('_', 5)
        number = int(number)
        few_shot = few_shot == 'True'
        topk = int(topk)
        days_before = int(days_before)

        if result['response']['status_code'] != 200:
            print(f'  Error for {custom_id}: {result["response"]["body"]}')
            errors += 1
            continue

        ai_response = result['response']['body']['choices'][0]['message']['content']
        db[f'{repo}_ai_results'].update_one({
            'number': number, 'model': MODEL, 'few_shot': few_shot,
            'tecnica': tecnica, 'topk': topk, 'days_before': days_before,
        }, {'$set': {
            'number': number, 'model': MODEL, 'response': ai_response,
            'few_shot': few_shot, 'tecnica': tecnica, 'topk': topk, 'days_before': days_before,
        }}, upsert=True)
        saved += 1
    return saved, errors


def retrieve(batch_id=None):
    """Download the current chunk's results, save them, then auto-submit the next chunk."""
    if batch_id:
        # One-off: download a specific batch ID without touching state.
        batch = client.batches.retrieve(batch_id)
        if batch.status != 'completed':
            print(f'Batch status is "{batch.status}", not "completed".')
            return
        content = client.files.content(batch.output_file_id).text
        saved, errors = _save_results_to_mongo(content)
        print(f'\nDone! Saved {saved} results, {errors} errors.')
        return

    state = load_state()
    chunks = state['chunks']
    idx = state['current']
    chunk = chunks[idx]

    if not chunk['batch_id']:
        print(f'Chunk {idx} has not been submitted yet.')
        return

    batch = client.batches.retrieve(chunk['batch_id'])
    if batch.status != 'completed':
        print(f'Chunk {idx} status is "{batch.status}", not "completed". Cannot retrieve yet.')
        if batch.status in ('in_progress', 'validating', 'finalizing'):
            print('Run "python generateGPTCode.py status" to check progress.')
        return

    if not batch.output_file_id:
        print('No output file found on the batch.')
        return

    print(f'Chunk {idx}: downloading output file {batch.output_file_id}...')
    content = client.files.content(batch.output_file_id).text
    saved, errors = _save_results_to_mongo(content)
    print(f'Chunk {idx}: saved {saved} results, {errors} errors.')

    next_idx = idx + 1
    if next_idx < len(chunks):
        next_chunk = chunks[next_idx]
        print(f'\nSubmitting chunk {next_idx} ({next_chunk["request_count"]} requests, '
              f'~{next_chunk["estimated_tokens"]:,} tokens)...')
        try:
            _submit_chunk(next_chunk)
        except Exception as e:
            print(f'  failed to submit chunk {next_idx}: {e}')
            print(f'  state preserved; re-run "python generateGPTCode.py retrieve" to retry.')
            save_state(state)
            return
        state['current'] = next_idx
        save_state(state)
        print(f'\nChunk {next_idx} submitted. Run "python generateGPTCode.py status" to monitor.')
        return

    # All chunks done: cleanup files.
    save_state(state)
    for c in chunks:
        if os.path.exists(c['file']):
            os.remove(c['file'])
    if os.path.exists(STATE_FILE):
        os.remove(STATE_FILE)
    print('\nAll chunks complete. Cleaned up temporary files.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='OpenAI Batch API for GPT code evaluation')
    parser.add_argument('command', choices=['submit', 'status', 'retrieve'])
    parser.add_argument('--dry-run', action='store_true', help='Write JSONL only; skip upload and batch creation (submit only)')
    parser.add_argument('--batch-id', type=str, required=False, help='Batch ID for status/retrieve')
    args = parser.parse_args()

    if args.command == 'submit':
        submit(dry_run=args.dry_run)
    elif args.command == 'status':
        status(batch_id=args.batch_id)
    elif args.command == 'retrieve':
        retrieve(batch_id=args.batch_id)