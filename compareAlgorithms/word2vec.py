# Python program to generate word vectors using Word2Vec
# pip install nltk
# pip install gensim

# importing all necessary modules
from gensim.models import Word2Vec
import gensim
import nltk
from nltk.tokenize import sent_tokenize, word_tokenize
import warnings

warnings.filterwarnings(action='ignore')

def word2vec(issuesTitles: list, currentTitle: str):  
  numberOfSimilarissueTitles = 5

  mostSimilarIssueTitles = []
  
  data = []

  # tokenize the sentence into words
  for issue in issuesTitles:
    data.append(word_tokenize(issue.lower()))

  CBOWModel = gensim.models.Word2Vec(
    data, min_count=1, vector_size=100, window=5)

  temp = []
  for similarTitle in issuesTitles:
    if currentTitle == similarTitle:
      continue
    similarity = CBOWModel.wv.n_similarity(word_tokenize(currentTitle), word_tokenize(similarTitle))
    mostSimilarIssueTitles.append((similarTitle, similarity))
  return mostSimilarIssueTitles