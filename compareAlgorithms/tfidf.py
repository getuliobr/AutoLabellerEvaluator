from sklearn.feature_extraction.text import TfidfVectorizer
import numpy as np  
import nltk
from filters import *

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

def get_tfidf_filtered(issue):
    title = issue['title'] if issue['title'] != None else ''
    body = issue['body'] if issue['body'] != None else ''
        
    if issue["lowercase"]:
        title = toLowercase(title)
        body = toLowercase(body)
    
    if issue["lowercase"]:
        title = filterLinks(title)
        body = filterLinks(body)
    
    if issue["removeDigits"]:
        title = filterDigits(title)
        body = filterDigits(body)
    
    if issue["removeStopWords"]:
        title = filterStopWords(title)
        body = filterStopWords(body)
    
    title_body = f"{title} {body}"
        
    return {
        'title': title,
        'body': body,
        'title_body': title_body
    }