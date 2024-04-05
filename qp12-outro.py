from config import config
import pymongo

mongoClient = pymongo.MongoClient(config['DATABASE']['CONNECTION_STRING'])
db = mongoClient[config['DATABASE']['NAME']]

queryTarefasValidas = {
  'closed_at': {
    '$gte': '2020-07-01',
    '$lte': '2024-01-31',
  },
  'files.0': {'$exists': True},
}

def getLowerEnd(collection):
  lower = collection.find_one({'created_at': {
    '$gte': '2020-07-01'
  }}, sort=[('number', pymongo.ASCENDING)])
  return lower['number']

tarefas = 0
t1 = 0
t3 = 0

for projeto in db.list_collection_names():
    if projeto.endswith('_results') or projeto.endswith('_diff') or projeto.startswith('facebook/react'):
        continue
    lower = getLowerEnd(db[projeto])
    filtro = {
       'number': {'$gte': lower},
       'filtros.daysBefore': 180,
       'tecnica': 'sbert'
    }

    resultsCollection = db[f'{projeto}_results']
    print(projeto, filtro)

    issues = resultsCollection.find(filtro)
    for issue in issues:
        acerto = issue['acertos']
        erros = issue['erros']
        total = acerto + erros
        if issue['topk'] == 1:
            tarefas += 1
            t1 += total
        elif issue['topk'] == 3:
            t3 += total

print(t3, t1, tarefas, t3/tarefas, t1/tarefas, t3/tarefas - t1/tarefas)