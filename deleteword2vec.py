import pymongo
from config import config

# REPO = 'jabref/jabref'


mongoClient = pymongo.MongoClient(config['DATABASE']['CONNECTION_STRING'])
db = mongoClient[config['DATABASE']['NAME']]


db[f'{REPO}_results'].delete_many({ 'tecnica': 'word2vec' })