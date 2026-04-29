"""
qp4.py - SBERT semantic similarity between AI-generated code and actual PR diffs.

For each issue in {repo}_ai_results, computes cosine similarity (all-MiniLM-L6-v2)
between the LLM response and the actual code that fixed the issue (from {repo}_diff),
for all 3 techniques: zeroshot, sbert, tfidf.

Results are cached in {repo}_sbert_sim_results and plotted as a boxplot.
"""

from config import config
import pymongo
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
import scikit_posthocs as sp
from sentence_transformers import SentenceTransformer, util
from tqdm import tqdm
from statistics import mean, stdev
from math import sqrt, isnan

from github_diff import get_diff

IS_2026_RUN = False  # Set to True to only include issues created in 2026 or later (for the 2026 run)

mongoClient = pymongo.MongoClient(config['DATABASE']['CONNECTION_STRING'])
db = mongoClient[config['DATABASE']['NAME']]

REPOS = {
  'dotnet/aspnetcore': 'c_sharp',
  'dotnet/efcore': 'c_sharp',
  'dotnet/runtime': 'c_sharp',
  'files-community/Files': 'c_sharp',
  'swiftlang/swift': 'cpp',
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

TECNICAS = ['zeroshot', 'sbert', 'tfidf']

# If an issue is in this set, drop it for ALL tecnicas (zeroshot, sbert, tfidf) and all models.
# Covers both reference-PR-diff failures and few-shot-suggestion-diff failures.
SKIP_ISSUES = {
    ('dotnet/runtime', 42838),          # err when running qp3
    ('appwrite/appwrite', 5150),        # err when running qp3
    ('mattermost/mattermost', 16149),   # err when running qp3
    ('aws/aws-cdk', 26616),             # err when generating on gpt5.2 (too many tokens)
    ('aws/aws-cdk', 13403),             # err couldnt find pr
    ('aws/aws-cdk', 26615),             # err couldnt find pr
    ('nextcloud/server', 24549),        # err couldnt find pr
    ('mattermost/mattermost', 17293),   # err couldnt find pr
    ('mattermost/mattermost', 24290),   # err couldnt find pr
    ('mattermost/mattermost', 21162),   # err couldnt find pr
    ('mattermost/mattermost', 15455),   # err couldnt find pr
    ('mattermost/mattermost', 23427),   # err couldnt find pr
    # Those errors bellow happened on the 2026 run
    ('apache/airflow', 62088),          # err when generating on gpt5.2 (too many tokens)
    ('apache/airflow', 61920),          # err when generating on gpt5.2 (too many tokens)
}

print('Loading all-MiniLM-L6-v2...')
sbert_model = SentenceTransformer('all-MiniLM-L6-v2')


def sbert_similarity(text_a, text_b):
    emb_a = sbert_model.encode(text_a, convert_to_tensor=True)
    emb_b = sbert_model.encode(text_b, convert_to_tensor=True)
    return float(util.pytorch_cos_sim(emb_a, emb_b)[0][0])

# --- Phase 1: Compute and cache SBERT similarity ---
for repo in REPOS:
    print(f'\n=== Processing {repo} ===')
    aiResultsCollection = db[f'{repo}_ai_results']
    simResultsCollection = db[f'{repo}_sbert_sim_results']

    for tecnica in TECNICAS:
        docs = list(aiResultsCollection.find({
            'tecnica': tecnica,
            'is_2026_run': IS_2026_RUN
        }))
        if not docs:
            continue

        for doc in tqdm(docs, desc=f'{repo} / {tecnica}'):
            number = doc['number']
            model = doc.get('model', '')

            if (repo, number) in SKIP_ISSUES:
                continue

            if simResultsCollection.find_one({'number': number, 'tecnica': tecnica, 'model': model}):
                continue

            diff_list, _ = get_diff(repo, number, db)
            reference_code = '\n'.join(diff_list)
            sim = sbert_similarity(doc['response'], reference_code)

            simResultsCollection.update_one({
                'number': number,
                'tecnica': tecnica,
                'model': model,
            }, {
                '$set': {
                    'similarity': sim,
                }
            }, upsert=True)

# --- Phase 2: Aggregate all results into a DataFrame ---
all_dfs = []
for repo in REPOS:
    simResultsCollection = db[f'{repo}_sbert_sim_results']
    docs = list(simResultsCollection.find({}, {'_id': 0}))
    if docs:
        repo_df = pd.DataFrame(docs)
        repo_df['repo'] = repo
        all_dfs.append(repo_df)

if not all_dfs:
    print('No results found. Run Phase 1 first.')
    exit(1)

df = pd.concat(all_dfs, ignore_index=True)

# Defensive: drop any stale cached rows that now fall under the skip list.
df = df[~df.apply(lambda r: (r['repo'], r['number']) in SKIP_ISSUES, axis=1)]

df['tecnica'] = df['tecnica'].replace({
    'zeroshot': 'Zero-shot',
    'sbert': 'SBERT-180-1',
    'tfidf': 'TFIDF-180-1',
})

df['model'] = df['model'].replace({
    'gpt-oss:120b': 'gpt-oss:120b_high',
    'qwen3.6:35b': 'qwen3.6:35b_on',
})

# df['similarity'] *= 100  # Convert to percentage

# --- Phase 3: Plot ---
# fig, ax = plt.subplots(figsize=(10, 6))
ax = sns.boxplot(
    data=df,
    x='tecnica',
    y='similarity',
    hue='model',
    order=['Zero-shot', 'SBERT-180-1', 'TFIDF-180-1'],
    # ax=ax,
    flierprops=dict(marker='o', markersize=3, alpha=0.5, markeredgewidth=0.5),
)
ax.set_xlabel('Technique')
ax.set_ylabel('Cosine Similarity') 
plt.tight_layout()
plt.savefig('artigo/boxplot_sbert.pdf')
print('\nSaved artigo/boxplot_sbert.pdf')
plt.show()

# --- Phase 4: Statistics ---
print('\n=== Descriptive Statistics (tecnica x model) ===')
print(df.groupby(['tecnica', 'model']).describe()['similarity'])

rows = [('Technique', 'LLM', 'Min', 'Mean', 'Max')]

for tecnica in df['tecnica'].unique():
    tec_df = df[df['tecnica'] == tecnica]
    agg = tec_df.groupby('model')['similarity'].agg(['min', 'mean', 'max']).reset_index()
    for _, row in agg.iterrows():
        rows.append((tecnica, row['model'], f"'{row['min']:.4f}", f"'{row['mean']:.4f}", f"'{row['max']:.4f}"))

import csv, io
buf = io.StringIO()
csv.writer(buf).writerows(rows)
print(buf.getvalue())


def cohens_d(c0, c1):
    return (mean(c0) - mean(c1)) / (sqrt((stdev(c0) ** 2 + stdev(c1) ** 2) / 2))


def run_dunn(groups: dict, p_adjust='bonferroni'):
    labels = list(groups.keys())
    result = sp.posthoc_dunn(list(groups.values()), p_adjust=p_adjust)
    result.index = labels
    result.columns = labels
    print(f'  --- Dunn post-hoc (p_adjust={p_adjust}) ---')
    for i, a in enumerate(labels):
        for b in labels[i + 1:]:
            p = result.loc[a, b]
            sig = '***' if p < 0.001 else ('**' if p < 0.01 else ('*' if p < 0.05 else 'ns'))
            if sig != 'ns':
                print(f'  {a} vs {b}: p = {p:.4f} {sig}')


for model in sorted(df['model'].unique()):
    print(f'\n===== Model: {model} =====')
    model_df = df[df['model'] == model]
    tecnica_groups = model_df.groupby('tecnica')

    testes = {
        label: [v for v in group['similarity'].tolist() if not isnan(v)]
        for label, group in tecnica_groups
    }
    if len(testes) < 2:
        print('  not enough tecnica groups for tests')
        continue

    print('  --- Kruskal-Wallis (across tecnicas) ---')
    kw = stats.kruskal(*testes.values())
    print(f'  {kw}')
    if kw.pvalue < 0.05:
        run_dunn(testes)

    print("  --- Cohen's d (pairwise across tecnicas) ---")
    labels = list(testes.keys())
    for i, x_ in enumerate(labels):
        for y_ in labels[i + 1:]:
            x, y = testes[x_], testes[y_]
            print(f'  {x_} vs {y_}: d = {cohens_d(x, y):.4f}  '
                  f'(M1={mean(x):.2f}±{stdev(x):.2f} n={len(x)}, '
                  f'M2={mean(y):.2f}±{stdev(y):.2f} n={len(y)})')

print('\n===== Per-tecnica: model comparison =====')
for tecnica in sorted(df['tecnica'].unique()):
    tec_df = df[df['tecnica'] == tecnica]
    model_groups = {
        m: [v for v in g['similarity'].tolist() if not isnan(v)]
        for m, g in tec_df.groupby('model')
    }
    if len(model_groups) < 2:
        continue
    print(f'\n  --- {tecnica} ---')
    kw = stats.kruskal(*model_groups.values())
    print(f'  Kruskal-Wallis: {kw}')
    if kw.pvalue < 0.05:
        run_dunn(model_groups)
    ms = list(model_groups.keys())
    for i, a in enumerate(ms):
        for b in ms[i + 1:]:
            x, y = model_groups[a], model_groups[b]
            print(f'  {a} vs {b}: d = {cohens_d(x, y):.4f}  '
                  f'(M1={mean(x):.2f}±{stdev(x):.2f} n={len(x)}, '
                  f'M2={mean(y):.2f}±{stdev(y):.2f} n={len(y)})')

print('\n===== Cross (tecnica, model) pairwise Cohen\'s d =====')
combo_groups = {
    (tec, mdl): [v for v in g['similarity'].tolist() if not isnan(v)]
    for (tec, mdl), g in df.groupby(['tecnica', 'model'])
}
combos = sorted(combo_groups.keys())
for i, a in enumerate(combos):
    for b in combos[i + 1:]:
        x, y = combo_groups[a], combo_groups[b]
        if len(x) < 2 or len(y) < 2:
            continue

        print(f'  {a[0]}/{a[1]} vs {b[0]}/{b[1]}: d = {cohens_d(x, y):.4f}  '
            f'(M1={mean(x):.2f}±{stdev(x):.2f} n={len(x)}, '
            f'M2={mean(y):.2f}±{stdev(y):.2f} n={len(y)}) {"<- check EFFECT SIZE" if abs(cohens_d(x, y)) >= 0.2 else ""}')
