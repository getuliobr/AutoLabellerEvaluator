from codebleu import calc_codebleu
from config import config
import numpy as np
import pymongo, requests

mongoClient = pymongo.MongoClient(config['DATABASE']['CONNECTION_STRING'])
db = mongoClient[config['DATABASE']['NAME']]

issueCollection = db['jabref/jabref']
diffCollection = db['jabref/jabref_diff']
resultsCollection = db['jabref/jabref_results']
cacheCollection = db['jabref/jabref_cache_results']
gptResultsCollection = db['jabref/jabref_gpt_results']
codebleuResultsCollection = db['jabref/jabref_code_results']

tecnicas = ['tfidf', 'sbert', 'word2vec', 'w2vGithub']
diasAnteriores = [30, 90, 180]
topks = [1, 3]


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

def codebleu(reference, diff):
  cacheKey = hash(f'{reference} {diff}')
  result = cacheCollection.find_one({'key': cacheKey})
  
  if result:
    print('hit')
    return result['codebleu']
  
  result = calc_codebleu([reference], [diff], lang="java")['codebleu']
  cacheCollection.insert_one({'key': cacheKey, 'codebleu': result})
  return result

def run(tecnica, diaAnterior, topk):
  # 6678 numero da primeira gfi criada >= 2020-07-01
  filtro = {"filtros.goodFirstIssue": 1, "number": {"$gte": 6678}, "topk": topk, "filtros.daysBefore": diaAnterior, "tecnica": tecnica}
  recomendador = []
  with resultsCollection.find(filtro) as results:
    for i, issue in enumerate(results):
      testNumber = issue['number']
      # essa issue n roda por algum motivo
      if testNumber == 9092:
        continue
      testDiff = get_diff(testNumber)
      print(i, testNumber)
      
      suggestionDiff = []
      for suggestionNumber, textSimilarity in issue['issues_sugeridas']:
        suggestionDiff.extend(get_diff(suggestionNumber))
      
      avgCodeBLEU = []
      for reference in testDiff:
        for diff in suggestionDiff:
          avgCodeBLEU.append(codebleu(reference, diff))
      
      recomendador.append(np.mean(avgCodeBLEU))
      
      # avgCodeBLEUGPT3 = []
      # for reference in testDiff:
      #   chatGPT3 = gptResultsCollection.find_one({'number': testNumber, 'model': 'gpt-3.5-turbo-0125'})['response']
      #   avgCodeBLEUGPT3.append(calc_codebleu([reference], [chatGPT3], lang="java")['codebleu'])
        
      # gpt3.append(np.mean(avgCodeBLEUGPT3))
      
      # avgCodeBLEUGPT4= []
      # for reference in testDiff:
      #   chatGPT4 = gptResultsCollection.find_one({'number': testNumber, 'model': 'gpt-4-turbo-preview'})['response']
      #   avgCodeBLEUGPT4.append(calc_codebleu([reference], [chatGPT4], lang="java")['codebleu'])
        
      # gpt4.append(np.mean(avgCodeBLEUGPT4))

  print(f'{tecnica}_{topk}_{diaAnterior}', np.mean(recomendador), '+-', np.std(recomendador))

tecnicas = ['tfidf', 'sbert', 'word2vec', 'w2vGithub']
diasAnteriores = [30, 90, 180]
topks = [1, 3]
for tecnica in tecnicas:    
  for diaAnterior in diasAnteriores:
    for topk in topks:
      filtro = {"filtros.goodFirstIssue": 1, "number": {"$gte": 6678}, "topk": topk, "filtros.daysBefore": diaAnterior, "tecnica": tecnica}
      recomendador = []
      if codebleuResultsCollection.find_one({
        'tecnica': tecnica,
        'topk': topk,
        'daysBefore': diaAnterior,
      }):
        print('this one is done')
        continue
      with resultsCollection.find(filtro) as results:
        for i, issue in enumerate(results):
          testNumber = issue['number']
          # essa issue n roda por algum motivo
          if testNumber == 9092:
            continue
          testDiff = get_diff(testNumber)
          print(i, testNumber)
          
          suggestionDiff = []
          for suggestionNumber, textSimilarity in issue['issues_sugeridas']:
            if suggestionNumber in [9092, 8540]:
              continue
            suggestionDiff.extend(get_diff(suggestionNumber))
          
          if not len(suggestionDiff):
            continue
          
          avgCodeBLEU = []
          for reference in testDiff:
            for diff in suggestionDiff:
              avgCodeBLEU.append(codebleu(reference, diff))
          
          recomendador.append(np.mean(avgCodeBLEU))

      codebleuResultsCollection.insert_one({
        'tecnica': tecnica,
        'topk': topk,
        'daysBefore': diaAnterior,
        'mean': np.mean(recomendador),
        'std': np.std(recomendador)
      })
      print(f'{tecnica}_{topk}_{diaAnterior}', np.mean(recomendador), '+-', np.std(recomendador))
      

filtro = {"filtros.goodFirstIssue": 1, "number": {"$gte": 6678}, "topk": 1, "filtros.daysBefore": 180, "tecnica": "sbert"}

with resultsCollection.find(filtro) as results:
  for i, issue in enumerate(results):
    testNumber = issue['number']
    # essa issue n roda por algum motivo
    if testNumber == 9092:
      continue
    testDiff = get_diff(testNumber)
    print(i, testNumber)
    
    avgCodeBLEUGPT3 = []
    for reference in testDiff:
      chatGPT3 = gptResultsCollection.find_one({'number': testNumber, 'model': 'gpt-3.5-turbo-0125'})['response']
      avgCodeBLEUGPT3.append(calc_codebleu([reference], [chatGPT3], lang="java")['codebleu'])
      
    gpt3.append(np.mean(avgCodeBLEUGPT3))

    avgCodeBLEUGPT4= []
    for reference in testDiff:
      chatGPT4 = gptResultsCollection.find_one({'number': testNumber, 'model': 'gpt-4-turbo-preview'})['response']
      avgCodeBLEUGPT4.append(calc_codebleu([reference], [chatGPT4], lang="java")['codebleu'])
      
    gpt4.append(np.mean(avgCodeBLEUGPT4))
    
    codebleuResultsCollection.update_one({
      'tecnica': "gpt-3.5-turbo-0125"
    }, {"$set": {
      'tecnica': "gpt-3.5-turbo-0125",
      'mean': np.mean(gpt3),
      'std': np.std(gpt3)
    }}, upsert=True)
    
    codebleuResultsCollection.update_one({
      'tecnica': "gpt-4-turbo-preview"
    }, {"$set": {
      'tecnica': "gpt-4-turbo-preview",
      'mean': np.mean(gpt4),
      'std': np.std(gpt4)
    }}, upsert=True)