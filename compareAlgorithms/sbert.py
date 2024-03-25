import pickle
from sentence_transformers import SentenceTransformer, util
from bson.binary import Binary
from compareAlgorithms.cache import Cache

sbertModel = SentenceTransformer('all-MiniLM-L6-v2')
sbertCache = Cache()

def sbert(issuesTitles: list, currentTitle: str):
  mostSimilarIssueTitles = []

  model = SentenceTransformer('all-MiniLM-L6-v2')

  currentTitleEmbedding = model.encode(currentTitle)

  for similarTitle in issuesTitles:
    if currentTitle == similarTitle:
      continue
    similarTitleEmbedding = model.encode(similarTitle)
    similarity = util.pytorch_cos_sim(currentTitleEmbedding, similarTitleEmbedding).numpy()[0]
    mostSimilarIssueTitles.append((similarTitle, float(similarity[0])))

  return mostSimilarIssueTitles

def get_sbert_embeddings(issue):
  title = issue["tfidf"]["title"]
  body = issue["tfidf"]["body"]
  title_body = issue["tfidf"]["title_body"]
  
  encode = lambda x: Binary(pickle.dumps(sbertModel.encode(x)))
  
  return {
    'title': encode(title),
    'body': encode(body),
    'title_body': encode(title_body)
  }

def sbert_new(issuesTitles: list, currentTitle: str, currNumber):
  mostSimilarIssueTitles = []

  currentTitleEmbedding = pickle.loads(currentTitle)

  for number, similarTitle in issuesTitles:
    if currentTitle == similarTitle:
      continue
    
    cacheVal = sbertCache.get(currNumber, number)
    if cacheVal:
      mostSimilarIssueTitles.append((number, cacheVal))
      continue
    
    
    
    similarTitleEmbedding = pickle.loads(similarTitle)
    similarity = util.pytorch_cos_sim(currentTitleEmbedding, similarTitleEmbedding).numpy()[0]
    similarity = float(similarity[0])
    
    sbertCache.set(currNumber, number, similarity)
    mostSimilarIssueTitles.append((number, similarity))

  return mostSimilarIssueTitles