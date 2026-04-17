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
from sentence_transformers import SentenceTransformer, util
from unidiff import PatchSet
from tqdm import tqdm
from statistics import mean, stdev
from math import sqrt, isnan

from github_diff import get_diff
import github_diff

mongoClient = pymongo.MongoClient(config['DATABASE']['CONNECTION_STRING'])
db = mongoClient[config['DATABASE']['NAME']]

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

TECNICAS = ['zeroshot', 'sbert', 'tfidf']

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
        docs = list(aiResultsCollection.find({'tecnica': tecnica}))
        if not docs:
            continue

        for doc in tqdm(docs, desc=f'{repo} / {tecnica}'):
            number = doc['number']
            '''        
            [github_diff] dotnet/runtime#4938: 404 (PR missing/transferred)
            [github_diff] appwrite/appwrite#319: 404 (PR missing/transferred)
            [github_diff] mattermost/mattermost#7786: 404 (PR missing/transferred)
            '''
            if repo == 'dotnet/runtime' and number == 4938:
                continue
            if repo == 'appwrite/appwrite' and number == 319:
                continue
            if repo == 'mattermost/mattermost' and number == 7786:
                continue

            if simResultsCollection.find_one({'number': number, 'tecnica': tecnica}):
                continue

            diff_list, _ = get_diff(repo, number, db)
            reference_code = '\n'.join(diff_list)
            sim = sbert_similarity(doc['response'], reference_code)

            simResultsCollection.update_one({
                'number': number,
                'tecnica': tecnica
            }, {
                '$set': {
                    'model': doc.get('model', ''),
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

df['tecnica'] = df['tecnica'].replace({
    'zeroshot': 'Zero-shot',
    'sbert': 'SBERT-180-1',
    'tfidf': 'TFIDF-180-1',
})

df['similarity'] *= 100  # Convert to percentage

# --- Phase 3: Plot ---
fig, ax = plt.subplots(figsize=(10, 6))
sns.boxplot(
    data=df,
    x='tecnica',
    y='similarity',
    order=['Zero-shot', 'SBERT-180-1', 'TFIDF-180-1'],
    ax=ax,
    flierprops=dict(marker='o', markersize=3, alpha=0.5, markeredgewidth=0.5),
)
ax.set_xlabel('Technique')
ax.set_ylabel('Cosine Similarity (%) (all-MiniLM-L6-v2)') 
plt.tight_layout()
plt.savefig('artigo/boxplot_sbert.pdf')
print('\nSaved artigo/boxplot_sbert.pdf')
plt.show()

# --- Phase 4: Statistics ---
tecnica_groups = df.groupby('tecnica')
print('\n=== Descriptive Statistics ===')
print(tecnica_groups.describe()['similarity'])

testes = {
    label: [v for v in group['similarity'].tolist() if not isnan(v)]
    for label, group in tecnica_groups
}

print('\n=== Kruskal-Wallis Test ===')
print(stats.kruskal(*testes.values()))


def cohens_d(c0, c1):
    return (mean(c0) - mean(c1)) / (sqrt((stdev(c0) ** 2 + stdev(c1) ** 2) / 2))


print('\n=== Cohen\'s d (pairwise) ===')
labels = list(testes.keys())
for i, x_ in enumerate(labels):
    for y_ in labels[i + 1:]:
        x, y = testes[x_], testes[y_]
        print(f'{x_} vs {y_}: d = {cohens_d(x, y):.4f}  '
              f'(M1={mean(x):.2f}±{stdev(x):.2f} n={len(x)}, '
              f'M2={mean(y):.2f}±{stdev(y):.2f} n={len(y)})')
