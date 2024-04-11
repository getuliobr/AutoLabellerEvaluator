import numpy as np
from config import config
from scipy import stats
import pymongo

from statistics import mean, stdev
from math import sqrt

mongoClient = pymongo.MongoClient(config['DATABASE']['CONNECTION_STRING'])
db = mongoClient[config['DATABASE']['NAME']]
  
tecnicas = [
  'tfidf',
  'sbert',
  'word2vec',
  'w2vGithub'
]
diasAnteriores = [
  30,
  90,
  180
]
topks = [
  1,
  3
]

cacheTarefasValidas = {}

queryTarefasValidas = {
  'created_at': {
    '$gte': '2020-07-01'
  },
  'closed_at': {
    '$gte': '2020-07-01',
    '$lte': '2024-01-31',
  },
  'files.0': {'$exists': True},
}

def avg(list):
  return sum(list)/len(list)

def stat(list: list, repos):
  minimo = min(list)*100
  minimoRepo = repos[list.index(min(list))]
  maximo = max(list)*100
  maximoRepo = repos[list.index(max(list))]
  media = avg(list)*100
  # return "{:.2f}%-{} {:.2f}% {:.2f}%-{}".format(minimo, minimoRepo, media, maximo, maximoRepo)
  return "{:.2f}% {:.2f}% {:.2f}%".format(minimo, media, maximo)

def getLowerEnd(collection):
  lower = collection.find_one({'created_at': {
    '$gte': '2020-07-01'
  }}, sort=[('number', pymongo.ASCENDING)])
  return lower['number']

def setCache(issueDataCollection, projeto):
  with issueDataCollection.find(queryTarefasValidas, no_cursor_timeout=True) as issues:
    tarefasFetching = 0
    for issue in issues:
      FILES_FORMAT = ('.txt', '.md')
      currSolvedBy = issue['files']
      currSolvedBy = list(filter(lambda x: not x.lower().endswith(FILES_FORMAT), currSolvedBy))
      if len(currSolvedBy):
        tarefasFetching += 1
  cacheTarefasValidas[projeto] = tarefasFetching

acuraciasTeste = {}
likelihoodTeste = {}

TOTAL = 0
ACERTO = 0
ERRO = 0

for tecnica in tecnicas:    
  for diaAnterior in diasAnteriores:
    for topk in topks:
      acuracias = []
      likelihoods = []
      feedbacks = []
      projetos = []
      # Caso queira só good first issue colocar filtro aqui
      filtro = {'tecnica': tecnica, 'topk': topk, 'filtros.daysBefore': diaAnterior,
        # 'filtros.goodFirstIssue': 1,
        'data': {'$lte': '2024-01-31'},
      }
      key = f'{tecnica}_{topk}_{diaAnterior}'      
      for projeto in db.list_collection_names():
        tarefas = 0
        tarefasSugeridas = 0
        arqSugestoesInterArqResolveram = 0
        arqSugestoes = 0
        likelihood = 0
        
        if projeto.endswith('_results') or projeto.endswith('_diff') or projeto.startswith('facebook/react'):
          continue
        
        resultsCollection = db[f'{projeto}_results']
        
        if projeto not in cacheTarefasValidas:
          setCache(db[projeto], projeto)
        
        filtro['number'] = {'$gte': getLowerEnd(db[projeto])}
        
        tarefas = cacheTarefasValidas[projeto]
        tarefasSugeridas = resultsCollection.count_documents(filtro)
        
        with resultsCollection.find(filtro, no_cursor_timeout=True) as issues:
          for issue in issues:
            acerto = issue['acertos']
            erros = issue['erros']
            totalSugerido = acerto + erros
            TOTAL += totalSugerido
            ERRO += erros
            ACERTO += acerto
            
            arqSugestoesInterArqResolveram += acerto
            arqSugestoes += totalSugerido
            likelihood += 1 if acerto else 0      
        
        acuracias.append(arqSugestoesInterArqResolveram/arqSugestoes)
        likelihoods.append(likelihood/tarefasSugeridas)
        feedbacks.append(tarefasSugeridas/tarefas)
        projetos.append(projeto)
      
      acuraciasTeste[key] = acuracias
      likelihoodTeste[key] = likelihoods
              
      print(tecnica, diaAnterior, topk, stat(acuracias, projetos), stat(likelihoods, projetos), stat(feedbacks, projetos) )

print(TOTAL, ACERTO, ERRO)

def cohens_d(c0, c1):
  return (mean(c0) - mean(c1)) / (sqrt((stdev(c0) ** 2 + stdev(c1) ** 2) / 2))

key = f'{tecnica}_{topk}_{diaAnterior}'  

chosenCohen = ['sbert_1_180', 'sbert_1_90', 'tfidf_1_180', 'tfidf_1_90']
for x in chosenCohen:
  for y in chosenCohen:
    print(x, y)
    print('M1:', np.mean(acuraciasTeste[x]), np.std(acuraciasTeste[x]), len(acuraciasTeste[x]))
    print('M2:', np.mean(acuraciasTeste[y]), np.std(acuraciasTeste[y]), len(acuraciasTeste[y]))
    print(cohens_d(acuraciasTeste[x], acuraciasTeste[y]))