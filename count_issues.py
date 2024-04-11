from config import config
import pymongo



mongoClient = pymongo.MongoClient(config['DATABASE']['CONNECTION_STRING'])
db = mongoClient[config['DATABASE']['NAME']]

tarefas = 0
prs = 0
arquivos = 0
testes = 0

def getLowerEnd(collection):
  lower = collection.find_one({'created_at': {
    '$gte': '2020-07-01'
  }}, sort=[('number', pymongo.ASCENDING)])
  return lower['number']

for projeto in db.list_collection_names():
  if projeto.endswith('_results') or projeto.endswith('_diff') or projeto.startswith('facebook/react'):
    continue
  
  issues = db[f'{projeto}'].find({})
  
  for issue in issues:
    tarefas += 1
    try:
      prs += len(issue['prs'])
      arquivos += len(issue['files'])
    except Exception:
      print(projeto)
  try:
    testes += db[f'{projeto}_results'].count_documents({'number':{'$gte': getLowerEnd(db[f'{projeto}'])}, 'data': {'$lte': '2024-01-31'}})
  except Exception as e:
    print(projeto, e)
print(tarefas, prs, arquivos, testes)