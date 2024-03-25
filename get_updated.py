import re
import pymongo
from config import config
from graphql import get_project_data

mongoClient = pymongo.MongoClient(config['DATABASE']['CONNECTION_STRING'])
db = mongoClient[config['DATABASE']['NAME']]

totalTarefa = 0
totalGFI = 0
totalPR = 0
totalFiles = 0

ooo = {}

for result in db.list_collection_names():
  if result.endswith('_results') or result.startswith('facebook/react'):
    continue
  
  collection = db[result]
   
  totais = collection.count_documents({})
  
  query = {
    'created_at': {
      '$gte': '2020-01-01'
    }
  }
  
  total = collection.count_documents(query)
      
  prs = []
  files = []
  
  issues = collection.find(query, sort=[('closed_at', -1)])
  for issue in issues:
    prs.extend(issue['prs'])
    files.extend(issue['files'])
    
  prs = len(set(prs))
  files = len(set(files))
  
  query['labels'] = {'$regex': re.compile("good first issue", re.IGNORECASE)}
  gfi = collection.count_documents(query)

  totalTarefa += totais
  totalGFI += gfi
  totalPR += prs
  totalFiles += files
  
  contributors, stars, forks, language = get_project_data(result)
  ooo[f'{language} {result}'] = f'{result} & {language} & {stars} & {forks} & {contributors} & {totais} & {gfi} & {prs} & {files} \\\\'

repos = sorted(ooo.keys(), key=lambda x:x.lower())
for repo in repos:
  print(ooo[repo])