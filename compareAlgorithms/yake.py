import yake as _yake


def yake(corpus):
  language = "en"
  max_ngram_size = 3
  deduplication_threshold = 0.9
  deduplication_algo = 'seqm'
  windowSize = 1
  numOfKeywords = 20

  custom_kw_extractor = _yake.KeywordExtractor(lan=language, n=max_ngram_size, dedupLim=deduplication_threshold, dedupFunc=deduplication_algo, windowsSize=windowSize, top=numOfKeywords, features=None)
  return custom_kw_extractor.extract_keywords(corpus)

  