from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
import re
from string import digits


def toLowercase(data):
    return data.lower()

def filterLinks(data):
    return re.sub(r'http\S+', '', data)

def filterDigits(data):
    remove_digits = str.maketrans('', '', digits)
    return data.translate(remove_digits)

def filterStopWords(data):
    stop_words = set(stopwords.words('english'))
    word_tokens = word_tokenize(data)
    data = [w for w in word_tokens if not w in stop_words]
    return ' '.join(data)