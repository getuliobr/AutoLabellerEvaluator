import pymongo, re
from config import config

mongoClient = pymongo.MongoClient(config['DATABASE']['CONNECTION_STRING'])
db = mongoClient[config['DATABASE']['NAME']]


total = 0
totalgfi = 0
totalTests = 0

for result in db.list_collection_names():
  if not result.endswith('_results'):
    continue
  
  collection = db[result]
  
  totalTests += collection.count_documents({})
  
  total += collection.count_documents({
    'topk': 1, 
    'filtros.daysBefore': 180,
    'tecnica': 'tfidf'
  })
  
  gfi = collection.count_documents({
    'topk': 1, 
    'filtros.daysBefore': 180,
    'tecnica': 'tfidf',
    'filtros.goodFirstIssue': 1
  })
  
  if gfi == 0:
    print(result)
  
  totalgfi += gfi

print('_results: ', totalTests, total, totalgfi)

total = 0
totalgfi = 0

regx = re.compile("good first issue", re.IGNORECASE)

for repo in db.list_collection_names():
  if repo.endswith('_results'):
    continue
  collection = db[repo]
  total += collection.count_documents({
    'created_at': {
      '$gte': '2020-01-01'
    }
  })
  totalgfi += collection.count_documents({
    'created_at': {
      '$gte': '2020-01-01'
    },
    'labels':{'$regex': regx}
  })
  
print('2020-01-01: ', total, totalgfi)

prs = 0
files = 0

for repo in db.list_collection_names():
  if repo.endswith('_results'):
    continue
  
  collection = db[repo]
  
  prsCurr = []
  filesCurr = []
  issues = collection.find({
    'created_at': {
      '$gte': '2020-01-01'
    }
  })
  
  for issue in issues:
    prsCurr.extend(issue['prs'])
    filesCurr.extend(issue['files'])
    
  prs += len(set(prsCurr))
  files += len(set(filesCurr))
  
print('prs files:', prs, files)
