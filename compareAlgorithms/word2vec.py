# Python program to generate word vectors using Word2Vec
# pip install nltk
# pip install gensim

# importing all necessary modules
from gensim.models import Word2Vec
import gensim
import nltk
from nltk.tokenize import sent_tokenize, word_tokenize
import warnings
import gensim.downloader as api

warnings.filterwarnings(action='ignore')

print("Loading word2vec model")
CBOWModel = api.load('word2vec-google-news-300')  # download the corpus and return it opened as an iterable
print("Loaded google news model")
CBOWModelGH = gensim.models.Word2Vec.load('w2vGithub.model')
print("Loaded github issues model")
print("Done loading word2vec model")

def word2vec(issuesTitles: list, currentTitle: str):  
  mostSimilarIssueTitles = []
  for similarTitle in issuesTitles:
    if currentTitle == similarTitle:
      continue
    # similarity = CBOWModel.wv.n_similarity(word_tokenize(currentTitle), word_tokenize(similarTitle))
    similarity = CBOWModel.n_similarity(word_tokenize(currentTitle), word_tokenize(similarTitle))
    mostSimilarIssueTitles.append((similarTitle, float(similarity)))
  return mostSimilarIssueTitles

def word2vecGithub(issuesTitles: list, currentTitle: str):
  mostSimilarIssueTitles = []
  for similarTitle in issuesTitles:
    if currentTitle == similarTitle:
      continue
    similarity = CBOWModelGH.wv.n_similarity(word_tokenize(currentTitle), word_tokenize(similarTitle))
    mostSimilarIssueTitles.append((similarTitle, float(similarity)))
  return mostSimilarIssueTitles