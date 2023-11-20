def exemplo_sbert():
  # Importar biblioteca e utilidades
  from sentence_transformers import SentenceTransformer, util
  # Carregar modelo  
  model = SentenceTransformer('all-MiniLM-L6-v2')

  # Calcula os embeddings
  embedding1 = model.encode('Esse texto descreve uma tarefa')
  embedding2 = model.encode('Outro texto de uma outra tarefa')
  embedding3 = model.encode('Texto completamente diferente')
  # Exibe a similaridade textual do texto 1 para os textos 2 e 3
  print(util.pytorch_cos_sim(embedding1, embedding1))
  print(util.pytorch_cos_sim(embedding1, embedding2))
  print(util.pytorch_cos_sim(embedding1, embedding3))

def exemplo_tfidf():
  # Importar biblioteca e utilidades
  from sklearn.feature_extraction.text import TfidfVectorizer
  import numpy as np  
  
  # Carrega os textos
  corpus = [
    'Esse texto descreve uma tarefa',
    'Outro texto de uma outra tarefa',
    'Texto completamente diferente'
  ]
  
  # Calcula o tfidf
  tfidf = TfidfVectorizer().fit_transform(corpus)
  # Calcula a similaridade de par a par
  pairwise_similarity = tfidf * tfidf.T
  
  # Imprime a similaridade do primeiro exemplo do corpus entre todos, inclusive ele mesmo
  print(pairwise_similarity[0])
  
def exemplo_word2vec():
  # Importar biblioteca necessárias
  from gensim.models import Word2Vec
  import gensim
  from nltk.tokenize import word_tokenize
  import gensim.downloader as api

  # Carrega o modelo de noticias
  word2vecModel = api.load('word2vec-google-news-300')

  # Separa o texto em tokens
  tokens1 = word_tokenize('Esse texto descreve uma tarefa')
  tokens2 = word_tokenize('Outro texto de uma outra tarefa')
  tokens3 = word_tokenize('Texto completamente diferente')

  # Calcula as similaridades
  print(word2vecModel.n_similarity(tokens1, tokens1))
  print(word2vecModel.n_similarity(tokens1, tokens2))
  print(word2vecModel.n_similarity(tokens1, tokens3))