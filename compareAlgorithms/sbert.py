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
