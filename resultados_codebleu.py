from codebleu import calc_codebleu
from config import config
import pymongo, requests

mongoClient = pymongo.MongoClient(config['DATABASE']['CONNECTION_STRING'])
db = mongoClient[config['DATABASE']['NAME']]

issueDataCollection = db['jabref/jabref']
resultsCollection = db['jabref/jabref_results']

resultado = resultsCollection.find_one({'topk': 1, 'tecnica': 'tfidf', 'filtros.goodFirstIssue': 1})
issueSugerida = resultado['issues_sugeridas'][0][0]

resultadoData = issueDataCollection.find_one({'number': resultado['number']})
prResultado = resultadoData['prs'][0]

sugestao = issueDataCollection.find_one({'number': issueSugerida})
prSugestao = sugestao['prs'][0]

print(prResultado, prSugestao)

reference = [requests.get(f'https://patch-diff.githubusercontent.com/raw/JabRef/jabref/pull/{prResultado}.patch').text]
sugestao = [requests.get(f'https://patch-diff.githubusercontent.com/raw/JabRef/jabref/pull/{prSugestao}.patch').text]

# # sugestão gpt
# with open('gpt.java') as f:
#   chatgpt = f.read()

# # sugestão tfidf topk 1 para 30 dias anteriores
# with open('8817.patch') as f:
#   sugestao = f.read()
  
# with open('8838.patch') as f:
#   reference = f.read()

# result = calc_codebleu([reference], [chatgpt], lang="java")
# print('ChatGPT:', result)

result = calc_codebleu(reference, sugestao, lang="java")
print('tfidf topk 1 para 30 dias:', result)

# # ChatGPT: {'codebleu': 0.07428629502186776, 'ngram_match_score': 0.0024633647129697882, 'weighted_ngram_match_score': 0.00435467767798658, 'syntax_match_score': 0.12449799196787148, 'dataflow_match_score': 0.1658291457286432}
# # tfidf topk 1 para 30 dias: {'codebleu': 0.31203043408173964, 'ngram_match_score': 0.24731039613206682, 'weighted_ngram_match_score': 0.24865699416756634, 'syntax_match_score': 0.606425702811245, 'dataflow_match_score': 0.1457286432160804}