import pymongo
from config import config

REPO = 'jabref/jabref'


mongoClient = pymongo.MongoClient(config['DATABASE']['CONNECTION_STRING'])
db = mongoClient[config['DATABASE']['NAME']]


for repo in db.list_collection_names():
  if repo.endswith('_results'):
    continue
  
  collection = db[repo]

  closedBefore = []

  with collection.find({
    'created_at': {
      '$lte': '2019-12-31',
    }
  }, no_cursor_timeout=True) as search:

    for issue in search: 
      closedBefore.append(issue['number'])
  
  if not len(closedBefore):
    continue
  
  possivelRecalcular = []
  
  resultsCollection = db[repo + '_results']
  with resultsCollection.find({
    'issues_sugeridas': {
      '$elemMatch': {
        '$elemMatch': {
          '$in': closedBefore
        }
      },
    }
  }, no_cursor_timeout=True) as search:

    for issue in search:
      print(issue)
      break
      possivelRecalcular.append(issue['number'])
  break
  # print(repo, len(possivelRecalcular), possivelRecalcular[0])