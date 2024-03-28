from config import config
import pymongo, requests

mongoClient = pymongo.MongoClient(config['DATABASE']['CONNECTION_STRING'])
db = mongoClient[config['DATABASE']['NAME']]
  
tecnicas = ['tfidf', 'sbert', 'word2vec', 'w2vGithub']
diasAnteriores = [30, 90, 180]
topks = [1, 3]

cacheTarefasValidas = {}

queryTarefasValidas = {
  'closed_at': {
      '$gte': '2020-06-01'
  },
  'files.0': {'$exists': True},
}

for diaAnterior in diasAnteriores:
  for topk in topks:
    for tecnica in tecnicas:    
      filtro = {'tecnica': tecnica, 'topk': topk, 'filtros.daysBefore': diaAnterior}
      
      tarefas = 0
      tarefasSugeridas = 0
      arqSugestoesInterArqResolveram = 0
      arqSugestoes = 0
      likelihood = 0
      
      for result in db.list_collection_names():
        if result.endswith('_results') or result.startswith('facebook/react'):
          continue
        
        issueDataCollection = db[result]
        if result not in cacheTarefasValidas:
          with issueDataCollection.find(queryTarefasValidas, no_cursor_timeout=True) as issues:
            tarefasFetching = 0
            for issue in issues:
              FILES_FORMAT = ('.txt', '.md')
              currSolvedBy = issue['files']
              currSolvedBy = list(filter(lambda x: not x.lower().endswith(FILES_FORMAT), currSolvedBy))
              if len(currSolvedBy):
                tarefasFetching += 1
          cacheTarefasValidas[result] = tarefasFetching
        
        tarefas += cacheTarefasValidas[result]
        resultsCollection = db[f'{result}_results']
      
        tarefasSugeridas += resultsCollection.count_documents(filtro)
        with resultsCollection.find(filtro, no_cursor_timeout=True) as issues:
          for issue in issues:
            acerto = issue['acertos']
            erros = issue['erros']
            totalSugerido = acerto + erros
            
            arqSugestoesInterArqResolveram += acerto
            arqSugestoes += totalSugerido
            likelihood += 1 if acerto else 0
      
      print()
      print(diaAnterior, 'dias, topk=', topk, 'tecnica=',  tecnica)    
      print('acuracia', arqSugestoesInterArqResolveram/arqSugestoes)
      print('likelihood', likelihood/tarefasSugeridas)
      print('feedback', tarefasSugeridas/tarefas)