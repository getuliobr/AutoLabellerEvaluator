import re
from bs4 import BeautifulSoup
import pymongo
from config import config
import requests

projetos = [
  #'jabref/jabref',
  'microsoft/TypeScript',
  'prestodb/presto',
  'facebook/react',
  'vuejs/vue',
  'tensorflow/tensorflow',
  'neovim/neovim',
  'internetarchive/openlibrary',
  'scikit-learn/scikit-learn'
]

mongoClient = pymongo.MongoClient(config['DATABASE']['CONNECTION_STRING'])
db = mongoClient[config['DATABASE']['NAME']]


for projeto in projetos:
  collection = db[projeto]
  
  totais = collection.count_documents({})
  
  pos20200601 = collection.count_documents({
    'files.0': {'$exists': True},
    'closed_at': {
      '$gte': '2020-06-01'
    }
  })
  
  issues = collection.find({
    'files.0': {'$exists': True},
    'closed_at': {
      '$gte': '2020-06-01'
    }
  }, sort=[('closed_at', -1)])
  
  prs = []
  arquivos = 0
  for issue in issues:
    arquivos += len(issue['files'])
    r = requests.get(f'https://github.com/{projeto}/pull/{issue["number"]}')
    soup = BeautifulSoup(r.text, 'html.parser')
    issueForm = soup.find("form", { "aria-label": re.compile('Link issues')})
    if not issueForm:
      continue
    linkedMergedPR = [f"https://github.com{i.parent['href']}" for i in issueForm.find_all('svg', attrs={ "aria-label": re.compile('Merged Pull Request')})]
    prs.extend(linkedMergedPR)

  print(f'{projeto} & {totais} & {pos20200601} & {len(set(prs))} & {arquivos} & ARRUMAR \\\\')