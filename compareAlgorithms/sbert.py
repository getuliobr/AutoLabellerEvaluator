import pickle
from sentence_transformers import SentenceTransformer, util

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

def sbert_new(issuesTitles: list, currentTitle: str):
  mostSimilarIssueTitles = []

  currentTitleEmbedding = pickle.loads(currentTitle)

  for similarTitle in issuesTitles:
    if currentTitle == similarTitle:
      continue
    similarTitleEmbedding = pickle.loads(similarTitle)
    similarity = util.pytorch_cos_sim(currentTitleEmbedding, similarTitleEmbedding).numpy()[0]
    mostSimilarIssueTitles.append((similarTitle, float(similarity[0])))

  return mostSimilarIssueTitles