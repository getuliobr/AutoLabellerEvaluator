from config import config
import pymongo

from openai import OpenAI
client = OpenAI(api_key=config['OPENAI']['API_KEY'])


mongoClient = pymongo.MongoClient(config['DATABASE']['CONNECTION_STRING'])
db = mongoClient[config['DATABASE']['NAME']]

issueCollection = db['jabref/jabref']
resultsCollection = db['jabref/jabref_results']
gptResultsCollection = db['jabref/jabref_gpt_results']

# 6678 numero da primeira gfi criada >= 2020-07-01
filtro = {"filtros.goodFirstIssue": 1, "number": {"$gte": 6678}, "topk": 1, "filtros.daysBefore": 30, "tecnica": "sbert"}

with resultsCollection.find(filtro) as results:
  for result in results:
    number = result['number']
    issue = issueCollection.find_one({'number': number})
    body = issue['body']
    title = issue['title']
    gpt = f'Pretend you are a developer for the jabref/jabref GitHub project and please give me just and only the code or code snippet you think would solve this issue: TITLE: {title} BODY: {body}'
        
    model = 'gpt-4-turbo-preview'
    
    if gptResultsCollection.find_one({
      'number': number,
      'model': model
    }):
      continue
    
    response = client.chat.completions.create(
      model=model,
      messages=[
        {"role": "user", "content": gpt}
      ]
    )
    print(response)
    response = response.choices[0].message.content
    # dbCollection.update_one({
    #   'number': issue['number'],
    #   'lowercase': setLowercase,
    #   'removeLinks': removeLinks,
    #   'removeDigits': removeDigits,
    #   'removeStopWords': removeStopWords
    # },{"$set": {
    #   el: issue[el] for el in issue
    # }}, upsert=True)
    
    gptResultsCollection.update_one({
      'number': number,
      'model': model
    }, {'$set': {
      'number': number,
      'model': model,
      'response': response
    }}, upsert=True)