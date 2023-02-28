from sklearn.feature_extraction.text import TfidfVectorizer
import numpy as np  
import nltk

def tfidf(issuesTitles: list, currentTitle: str):
  corpus = issuesTitles

  last = len(corpus)
  corpus.append(currentTitle)

  tfidf = TfidfVectorizer().fit_transform(corpus)
  pairwise_similarity = tfidf * tfidf.T

  arr = pairwise_similarity.toarray()
  np.fill_diagonal(arr, -1)
  result = []
  for i in range(len(arr[last])):
    if issuesTitles[i] == currentTitle:
      continue
    result.append((issuesTitles[i], arr[last][i]))
  return result

def lemmatizatizeCorpus(corpus):
  lemma = nltk.wordnet.WordNetLemmatizer()

  for i in range(len(corpus)):
    words = nltk.word_tokenize(corpus[i])
    words = [lemma.lemmatize(word) for word in words]
    corpus[i] = ' '.join(words)

  return corpus