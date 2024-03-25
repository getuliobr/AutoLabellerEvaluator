# Python program to generate word vectors using Word2Vec
# pip install nltk
# pip install gensim

# importing all necessary modules
import pickle
from gensim.models import Word2Vec
from gensim import matutils
import nltk
from nltk.tokenize import word_tokenize
import warnings
import gensim.downloader as api
from bson.binary import Binary
from numpy import dot
from compareAlgorithms.cache import Cache

warnings.filterwarnings(action='ignore')

loaded = False
CBOWModel = None
CBOWModelGH = None

def load_w2v_models():
  global CBOWModel
  global CBOWModelGH
  global loaded
  if not loaded:
    print("Loading word2vec model")
    CBOWModel = api.load('word2vec-google-news-300')  # download the corpus and return it opened as an iterable
    print("Loaded google news model")
    CBOWModelGH = Word2Vec.load('w2vGithub.model')
    print("Loaded github issues model")
    loaded = True
    print("Done loading word2vec model")

w2vCache = Cache()
w2vGHCache = Cache()

def word2vec_old(issuesTitles: list, currentTitle: str):  
  mostSimilarIssueTitles = []
  for similarTitle in issuesTitles:
    if currentTitle == similarTitle:
      continue
    # similarity = CBOWModel.wv.n_similarity(word_tokenize(currentTitle), word_tokenize(similarTitle))
    similarity = CBOWModel.n_similarity(word_tokenize(currentTitle), word_tokenize(similarTitle))
    mostSimilarIssueTitles.append((similarTitle, float(similarity)))
  return mostSimilarIssueTitles

def word2vecGithub_old(issuesTitles: list, currentTitle: str):
  mostSimilarIssueTitles = []
  for similarTitle in issuesTitles:
    if currentTitle == similarTitle:
      continue
    similarity = CBOWModelGH.wv.n_similarity(word_tokenize(currentTitle), word_tokenize(similarTitle))
    mostSimilarIssueTitles.append((similarTitle, float(similarity)))
  return mostSimilarIssueTitles

def get_word2vec_embeddings(issue):
  title = issue["tfidf"]["title"]
  body = issue["tfidf"]["body"]
  title_body = issue["tfidf"]["title_body"]
  
  encode = lambda x: Binary(pickle.dumps(matutils.unitvec(CBOWModel.get_mean_vector(word_tokenize(x), pre_normalize=False))))
  
  return {
    'title': encode(title if len(title) else '-'),
    'body': encode(body if len(body) else '-'),
    'title_body': encode(title_body if len(title_body) else '-')
  }

def get_w2vGithub_embeddings(issue):
  title = issue["tfidf"]["title"]
  body = issue["tfidf"]["body"]
  title_body = issue["tfidf"]["title_body"]
  
  # got this from gensim keyedvectors implementation
  encode = lambda x: Binary(pickle.dumps(matutils.unitvec(CBOWModelGH.wv.get_mean_vector(word_tokenize(x), pre_normalize=False))))
  
  return {
    'title': encode(title if len(title) else '-'),
    'body': encode(body if len(body) else '-'),
    'title_body': encode(title_body if len(title_body) else '-')
  }

def word2vec_new(issuesTitles: list, currentTitle: str, currNumber):  
  mostSimilarIssueTitles = []

  currentTitleEmbedding = pickle.loads(currentTitle)

  for number, similarTitle in issuesTitles:
    if currentTitle == similarTitle:
      continue
    similarTitleEmbedding = pickle.loads(similarTitle)
    # got this from gensim keyedvectors implementation
    similarity = dot(currentTitleEmbedding, similarTitleEmbedding)
    mostSimilarIssueTitles.append((number, float(similarity)))

  return mostSimilarIssueTitles

def word2vec_wrapper(isGithubDataset):
  cache = w2vGHCache if isGithubDataset else w2vCache
  
  def w2v(issuesTitles: list, currentTitle: str, currNumber):
    mostSimilarIssueTitles = []

    currentTitleEmbedding = pickle.loads(currentTitle)

    for number, similarTitle in issuesTitles:
      if currentTitle == similarTitle:
        continue
      
      cacheVal = cache.get(currNumber, number)
      if cacheVal:
        mostSimilarIssueTitles.append((number, cacheVal))
        continue
      
      similarTitleEmbedding = pickle.loads(similarTitle)
      # got this from gensim keyedvectors implementation
      similarity = dot(currentTitleEmbedding, similarTitleEmbedding)
      similarity = float(similarity)
      
      cache.set(currNumber, number, similarity)
      mostSimilarIssueTitles.append((number, similarity))

    return mostSimilarIssueTitles
  return w2v