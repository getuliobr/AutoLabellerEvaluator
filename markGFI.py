import pymongo
from config import config
from bson.objectid import ObjectId

# FALAR SOBRE O REACT TER MULTIPLOS GFI

REPOS = {
  'azerothcore/azerothcore-wotlk': ['Good first issue'],
  'CleverRaven/Cataclysm-DDA': ['Good First Issue'],
  'WordPress/gutenberg': ['Good First Issue'],
  'mattermost/mattermost': ['Good First Issue'],
}

for REPO in REPOS:
  mongoClient = pymongo.MongoClient(config['DATABASE']['CONNECTION_STRING'])
  db = mongoClient[config['DATABASE']['NAME']]
  dataDB = db[REPO]
  resultsDB = db[f'{REPO}_results']
  
  for label in REPOS[REPO]:
    gfiList = dataDB.find({'labels': {
      '$in': [label]
    }})
    for issue in gfiList:     
      number = issue['number']
      gfiResultList = resultsDB.find({'number': number, 'filtros.goodFirstIssue': 0})
      for gfi in gfiResultList:
        resultsDB.update_one({'_id': ObjectId(gfi['_id']) }, {'$set': { "filtros.goodFirstIssue" : 1  }}, upsert=False)