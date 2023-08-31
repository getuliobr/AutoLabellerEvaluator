import pymongo
from config import config
from nltk.tokenize import word_tokenize

from gensim.models import Word2Vec
import gensim

mongoClient = pymongo.MongoClient(config['DATABASE']['CONNECTION_STRING'])
db = mongoClient[config['DATABASE']['NAME']]
modelData = []
for col in db.list_collections():
  if col['name'].endswith('_results'):
    continue
  
  print(f'Getting tokens from {col["name"]}')
  
  issues = db[col['name']].find({})
  
  for issue in issues:
    issueData = f"{issue['title']}{' ' if issue['body'] else ''}{issue['body'] if issue['body'] else ''}"
    modelData.append(word_tokenize(issueData))
    
  print(f'Got tokens from {col["name"]}')
  
CBOWModel = gensim.models.Word2Vec(
    modelData, min_count=1, vector_size=100, window=5, workers=8)

CBOWModel.save('word2vec.model')