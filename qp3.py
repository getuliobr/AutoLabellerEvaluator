from collections import defaultdict
from codebleu import calc_codebleu
from config import config
import numpy as np
import pymongo, requests
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
from unidiff import PatchSet
from statistics import mean, stdev
from math import sqrt

mongoClient = pymongo.MongoClient(config['DATABASE']['CONNECTION_STRING'])
db = mongoClient[config['DATABASE']['NAME']]

def read_mongo(db, query={}, no_id=True):
  cursor = db.find(query)
  df =  pd.DataFrame(list(cursor))
  if no_id:
    del df['_id']
  return df

issueCollection = db['jabref/jabref']
resultsCollection = db['jabref/jabref_results']

diffCollection = db['jabref/jabref_diff']
diffCodeCollection = db['jabref/jabref_diff_code_results']
cacheCollection = db['jabref/jabref_cache_results']
gptResultsCollection = db['jabref/jabref_gpt_results']
codebleuResultsCollection = db['jabref/jabref_code_results']

tecnicas = ['tfidf', 'sbert']
diasAnteriores = [180]
topks = [1]


gpt3 = []
gpt4 = []

'''
number: issue number NOT PR number
'''
def get_diff(number):
  result = diffCollection.find_one({'number': number})
  if result:
    return result['diff']
  
  issue = issueCollection.find_one({'number': number})
  diff = []
  for pr in issue['prs']:
    diffURL = f'https://patch-diff.githubusercontent.com/raw/jabref/jabref/pull/{pr}.diff'
    diff.append(requests.get(diffURL).text)
  
  diffCollection.insert_one({'number': number, 'diff': diff})
  return diff

def get_code(number):
  dbSearch = diffCodeCollection.find_one({'number': number})
  if dbSearch:
    return dbSearch['codes']
  
  codes = []
  
  diffs = get_diff(number)

  for diff in diffs:
    patch_set = PatchSet(diff)

    for patched_file in patch_set:
      FILES_FORMAT = ('.txt', '.md')
      if patched_file.path.lower().endswith(FILES_FORMAT):
        continue
      code = ''.join([ line.value for hunk in patched_file for line in hunk ])
      if len(code):
        codes.append(code)
  
  diffCodeCollection.insert_one({'number': number, 'codes': codes})
  return codes

def codebleu(reference, diff):
  cacheKey = f'{reference} {diff}'
  result = cacheCollection.find_one({'key': cacheKey})
  
  if result:
    return result['codebleu']
  
  result = calc_codebleu([reference], [diff], lang="java")['codebleu']
  cacheCollection.insert_one({'key': cacheKey, 'codebleu': result})
  return result

for tecnica in tecnicas:    
  for diaAnterior in diasAnteriores:
    for topk in topks:
      filtro = {"filtros.goodFirstIssue": 1, "number": {"$gte": 6678}, "topk": topk, "filtros.daysBefore": diaAnterior, "tecnica": tecnica}
      recomendador = []
      with resultsCollection.find(filtro) as results:
        for i, issue in enumerate(results):
          testNumber = issue['number']
          if codebleuResultsCollection.find_one({
            'tecnica': tecnica,
            'number': testNumber,
          }):
            print(testNumber, 'this one is done')
            continue

          testCode = get_code(testNumber)
          print(i, testNumber)
          
          suggestionCodes = []
          for suggestionNumber, textSimilarity in issue['issues_sugeridas']:
            suggestionCodes.extend(get_code(suggestionNumber))
          
          if not len(suggestionCodes):
            continue
                    
          avgCodeBLEU = []
          for reference in testCode:
            for suggestion in suggestionCodes:
              avgCodeBLEU.append(codebleu(reference, suggestion))

          codebleuResultsCollection.insert_one({
            'tecnica': tecnica,
            'number': testNumber,
            'mean': np.mean(avgCodeBLEU),
          })
      

filtro = {"filtros.goodFirstIssue": 1, "number": {"$gte": 6678}, "topk": 1, "filtros.daysBefore": 180, "tecnica": "sbert"}

def runGPT(testNumber, tecnica):
  testCode = get_code(testNumber)
  if codebleuResultsCollection.find_one({
    'tecnica': tecnica,
    'number': testNumber
  }):
    print(testNumber, 'this one is done')
    return
  
  avgCodeBLEUGPT = []
  for reference in testCode:
    chatGPT = gptResultsCollection.find_one({'number': testNumber, 'model': tecnica})['response']
    avgCodeBLEUGPT.append(codebleu(reference, chatGPT))
  
  codebleuResultsCollection.insert_one({
    'tecnica': tecnica,
    'number': testNumber,
    'mean': np.mean(avgCodeBLEUGPT)
  })

with resultsCollection.find(filtro) as results:
  for i, issue in enumerate(results):
    testNumber = issue['number']
    print(i, testNumber)
    
    runGPT(testNumber, 'gpt-3.5-turbo-0125')
    runGPT(testNumber, 'gpt-4-turbo-preview')
    
df = read_mongo(codebleuResultsCollection)

df['tecnica'].replace({
  'tfidf': 'TF-IDF-180-1',
  'sbert': 'SBERT-180-1',
  'gpt-3.5-turbo-0125': 'GPT 3.5',
  'gpt-4-turbo-preview': 'GPT 4',
}, inplace=True)

df['mean'] *= 100

box = sns.boxplot(data=df, x="tecnica", y="mean")
box.set_xlabel('Técnica')
box.set_ylabel('CodeBLEU (%)')
plt.savefig('artigo/boxplot.png')


tecnica = df.groupby('tecnica')
media = tecnica.describe()['mean']

sbert = 1
gpt35 = 1
gpt4 = 1
print(df['mean'].median())
print(media)
testes = {
  'tfidf': df[df['tecnica'] == 'TF-IDF-180-1']['mean'].tolist(),
  'sbert': df[df['tecnica'] == 'SBERT-180-1']['mean'].tolist(),
  'gpt3': df[df['tecnica'] == 'GPT 3.5']['mean'].tolist(),
  'gpt4': df[df['tecnica'] == 'GPT 4']['mean'].tolist()
}

print('sbert 180 1 median', df[df['tecnica'] == 'SBERT-180-1']['mean'].median())
print(stats.kruskal(testes['tfidf'], testes['sbert'], testes['gpt3'], testes['gpt4']))

def cohens_d(c0, c1):
  return (mean(c0) - mean(c1)) / (sqrt((stdev(c0) ** 2 + stdev(c1) ** 2) / 2))

for x_ in testes:
  for y_ in testes:
    print(x_, y_)
    x = testes[x_]
    y = testes[y_]
    print('M1:', mean(x), stdev(x), len(x))
    print('M2:', mean(y), stdev(y), len(y))
    print(cohens_d(x, y))