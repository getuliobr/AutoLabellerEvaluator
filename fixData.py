import pymongo
from config import config

# Use this tool to fix the data in the database
REPO = ''

mongoClient = pymongo.MongoClient(config['DATABASE']['CONNECTION_STRING'])
db = mongoClient[config['DATABASE']['NAME']]
collection = db[f'{REPO}_results']

cursor = collection.find({})

for doc in cursor:
  splitAt = doc['issue'].rindex('-')
  title, number = doc['issue'][:splitAt - 1], int(doc['issue'][splitAt+2:])
  doc['issue'] = title
  doc['number'] = number
  id = doc['_id']
  del doc['_id']
  collection.update_one({
    '_id': id,
  },{
    "$set": doc
  })