import numpy as np
from config import config
from scipy import stats
import pymongo

from statistics import mean, stdev
from math import sqrt

mongoClient = pymongo.MongoClient(config['DATABASE']['CONNECTION_STRING'])
db = mongoClient[config['DATABASE']['NAME']]
  
tecnicas = ['tfidf', 'sbert', 'word2vec', 'w2vGithub']
diasAnteriores = [30, 90, 180]
topks = [1, 3]

cacheTarefasValidas = {}

queryTarefasValidas = {
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
  return "{:.2f}%-{} {:.2f}% {:.2f}%-{}".format(minimo, minimoRepo, media, maximo, maximoRepo)
  # return "{:.2f}% {:.2f}% {:.2f}%".format(minimo, media, maximo)

def rejeitar_hip_nula(amostra1, amostra2, alpha=0.05):
  _, pvalor = stats.kruskal(amostra1, amostra2)
  return (pvalor <= alpha, pvalor)

def print_t_tests(resultados, cols=None, alpha=0.05):
    '''
    Esta função imprime o resultado do teste de hipótese nula em uma matriz entre todos os pares de experimentos.
    
    resultados : dict
        Dicionário onde as chaves são strings que representam um experimento e os valores
        são listas com os resultados por fold.
        
    cols : list, optional
        Lista de colunas que serão mostradas. Por padrão, usar todas as chaves do dicionário
        resultados como colunas.
        
    alpha: float, optional
        Limiar para rejeitar a hipótese nula. 
        A hipótese nula será rejeitada se p_valor <= alpha.
    
    Caso a hipótese não possa ser rejeitada (p_valor>alpha), o p_valor é simplesmente impresso. 
    Caso a hipótese seja rejeitada, o p_valor é impresso, justamente com um (*c), onde s é
    um caractere que representa a relação entre as médias da linha e da coluna. Por exemplo, 
    se a média do experimento     da linha for maior que a média do experimento da coluna, 
    c será >. Caso contrário, c será <.
    '''    
    if cols is None:
        cols = sorted(resultados)    
    
    largura = max(max(map(len,cols))+2,12)
    
    print(" " * largura , end="")
    
    for t in cols:
        print(t.center(largura), end='')
    print()
    
    for t in sorted(resultados):
        print(t.center(largura), end='')
        for t2 in cols:
            d, p = rejeitar_hip_nula(resultados[t], resultados[t2], alpha=alpha)
            dif = '<' if np.mean(resultados[t]) - np.mean(resultados[t2]) < 0 else '>'
            print(("%.02f%s" % (p, (' (*%c)' % dif) if d else '')).center(largura), end='')
        print()

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
  
def getLowerEnd(collection):
  lower = collection.find_one({'created_at': {
    '$gte': '2020-07-01'
  }}, sort=[('number', pymongo.ASCENDING)])
  return lower['number']

acuraciasTeste = {}
likelihoodTeste = {}

for tecnica in tecnicas:    
  for diaAnterior in diasAnteriores:
    for topk in topks:
      acuracias = []
      likelihoods = []
      feedbacks = []
      projetos = []
      # Caso queira só good first issue colocar filtro aqui
      filtro = {'tecnica': tecnica, 'topk': topk, 'filtros.daysBefore': diaAnterior,
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


def cohens_d(c0, c1):
  return (mean(c0) - mean(c1)) / (sqrt((stdev(c0) ** 2 + stdev(c1) ** 2) / 2))

key = f'{tecnica}_{topk}_{diaAnterior}'  

chosenCohen = ['sbert_1_180', 'sbert_1_90', 'tfidf_1_180', 'tfidf_1_90']
print('.', ' '.join(chosenCohen))
for y in chosenCohen:
  print(y, end=' ')
  for x in chosenCohen:
    print(cohens_d(acuraciasTeste[x], acuraciasTeste[y]), end=' ')
  print('')

# print('ACURACIAS')
# print_t_tests(acuraciasTeste)

# print('LIKELIHOODS')
# print_t_tests(acuraciasTeste)