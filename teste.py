import pymongo
from config import config

REPO = 'jabref/jabref'


mongoClient = pymongo.MongoClient(config['DATABASE']['CONNECTION_STRING'])
db = mongoClient[config['DATABASE']['NAME']]
search = db['jabref/jabref_new_results'].find({}, no_cursor_timeout=True)
for issue in search: 
  del issue['_id']
  if not db['jabref/jabref_results'].find_one(issue):
    print("RESULTADO DIFERENTE NA ISSUE:", issue)
    break
search.close()