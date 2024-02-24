import csv
import re
from string import digits
from tkinter import *
from tkinter.ttk import Progressbar

from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize

from compareAlgorithms.sbert import *
from compareAlgorithms.tfidf import *
from compareAlgorithms.word2vec import *

from precision.average_precision import mapk, apk

from getSolvedIssueData import getSolvedIssues
import threading
import datetime

from torch import Tensor


from collections import OrderedDict

import pymongo
from config import config

DELIMITER = ';'
QUOTE = "'"

def getFloatFromValue(value):
    return value if type(value) == float else value.item()

class EvalutorWindow:
    def __init__(self, win):
        self.strategies = {
            'sbert': sbert,
            'tfidf': tfidf,
            'word2vec': word2vec,
            'w2vGithub': word2vecGithub
        }

        self.dataOptions = [
            'title',
            'body',
            'title + body'
        ]

        self.mongoClient = pymongo.MongoClient(config['DATABASE']['CONNECTION_STRING'])
        self.db = self.mongoClient[config['DATABASE']['NAME']]

        self.issues = None
        self.lastRepo = None

        self.repoUrlLabel = Label(win, text='owner/repo')
        self.repoUrlLabel.place(x=100, y=50)
        self.repoUrl = Entry(bd=3, width= 50)
        self.repoUrl.place(x=200, y=50)

        self.kLabel = Label(win, text='K')
        self.kLabel.place(x=100, y=100)
        self.k = Entry(bd=3, width= 5)
        self.k.place(x=120, y=100)
        self.k.insert(0, '1, 3, 5')

        self.compareDataLabel = Label(win, text='Compare data')
        self.compareDataLabel.place(x=200, y=100)

        self.compare = StringVar()
        self.compare.set('title')
        self.compareOptions = OptionMenu(win, self.compare, *self.dataOptions)
        self.compareOptions.place(x=300, y=100)
        
        self.useAPILabel = Label(win, text='Fetch from API')
        self.useAPILabel.place(x=400, y=100)
        self.useAPI = IntVar()
        self.useAPI.set(1)
        self.useAPICheck = Checkbutton(win, variable=self.useAPI)
        self.useAPICheck.place(x=500, y=100)

        

        self.lowercaseLabel = Label(win, text='Convert to lowercase')
        self.lowercaseLabel.place(x=100, y=150)
        self.lowercase = IntVar()
        self.lowerCaseCheck = Checkbutton(win, variable=self.lowercase)
        self.lowerCaseCheck.place(x=300, y=150)

        self.linksLabel=Label(win, text='Remove links')
        self.linksLabel.place(x=100, y=200)
        self.links = IntVar()
        self.linksCheck = Checkbutton(win, variable=self.links)
        self.linksCheck.place(x=300, y=200)

        self.digitsLabel=Label(win, text='Remove digits')
        self.digitsLabel.place(x=100, y=250)
        self.digits = IntVar()
        self.digitsCheck = Checkbutton(win, variable=self.digits)
        self.digitsCheck.place(x=300, y=250)
        
        self.stopWordsLabel = Label(win, text='Remove stop words')
        self.stopWordsLabel.place(x=100, y=300)
        self.stopWords = IntVar()
        self.stopWordsCheck = Checkbutton(win, variable=self.stopWords)
        self.stopWordsCheck.place(x=300, y=300)

        self.lemmatizationLabel = Label(win, text='Lemmatize corpus')
        self.lemmatizationLabel.place(x=100, y=350)
        self.lemmatization = IntVar()
        self.lemmatizationCheck = Checkbutton(win, variable=self.lemmatization)
        self.lemmatizationCheck.place(x=300, y=350)
        
        self.removeTextFilesLabel = Label(win, text='Remove text files')
        self.removeTextFilesLabel.place(x=350, y=150)
        self.removeTextFiles = IntVar()
        self.removeTextFilesCheck = Checkbutton(win, variable=self.removeTextFiles)
        self.removeTextFilesCheck.place(x=550, y=150)

        self.goodFirstIssueLabel = Label(win, text='Use good first issues only')
        self.goodFirstIssueLabel.place(x=350, y=200)
        self.goodFirstIssue = IntVar()
        self.goodFirstIssueCheck = Checkbutton(win, variable=self.goodFirstIssue)
        self.goodFirstIssueCheck.place(x=550, y=200)

        self.goodFirstIssueTagNameLabel = Label(win, text='Good First Issue label')
        self.goodFirstIssueTagNameLabel.place(x=350, y=250)
        self.goodFirstIssueTagName = Entry(bd=3, width=15)
        self.goodFirstIssueTagName.place(x=500, y=250)
        self.goodFirstIssueTagName.insert(0, 'good first issue')

        self.startDateLabel = Label(win, text='Start date')
        self.startDateLabel.place(x=350, y=300)
        self.startDate = Entry(bd=3, width=15)
        self.startDate.place(x=500, y=300)
        self.startDate.insert(0, '2020-06-01')
        
        self.daysBeforeLabel = Label(win, text='Days before')
        self.daysBeforeLabel.place(x=350, y=350)
        self.daysBefore = Entry(bd=3, width=15)
        self.daysBefore.place(x=500, y=350)
        self.daysBefore.insert(0, '30')

        self.strategyLabel = Label(win, text='Strategy')
        self.strategyLabel.place(x=100, y=400)

        self.strategy = StringVar()
        self.strategy.set('tfidf')

        self.strategyOptions = OptionMenu(win, self.strategy, *self.strategies.keys())
        self.strategyOptions.place(x=200, y=400)

        self.submitButton = Button(win, text='Submit', command=self.submit, anchor=CENTER, width=20)
        self.submitButton.place(x=300, y=450, anchor=CENTER)

        self.pbLabel = Label(win, text='Waiting...', anchor=CENTER)
        self.pbLabel.place(x=300, y=490, anchor=CENTER)
        self.pb = Progressbar(
            win,
            orient='horizontal',
            mode='determinate',
            length=400
        )
        self.pb.place(x=300, y=510, anchor=CENTER)
        

    def submit(self):
        self.submitButton.config(state=DISABLED)
        self.collection = self.db[self.repoUrl.get()]
        self.outCollection = self.db[self.repoUrl.get() + '_results']
        self.thread = threading.Thread(target=self.runThread)
        self.thread.start()
        
    def runThread(self):
        owner, repo = self.repoUrl.get().split('/')
        setLowercase = self.lowercase.get()
        removeLinks = self.links.get()
        removeDigits = self.digits.get()
        removeStopWords = self.stopWords.get()
        useLemmatization = self.lemmatization.get()
        strategy = self.strategies[self.strategy.get()]
        k = list(map(lambda x: int(x), self.k.get().replace(' ', '').split(',')))
        compareData = self.compare.get()

        if self.lastRepo != self.repoUrl.get():
            self.issues = None
            self.lastRepo = self.repoUrl.get()
        
        if self.useAPI.get():
            getSolvedIssues(owner, repo, self.pb, self.pbLabel, self.collection)
        
        # TODO: escolher o inicio e fim do intervalo de issues na interface
        query = {
            'files.0': {'$exists': True},
            'created_at': {
                '$gte': self.startDate.get()
            }
        }
        
        if self.goodFirstIssue.get():
            query['labels'] = self.goodFirstIssueTagName.get()
        
        allIssues = self.collection.find(query).sort('closed_at', pymongo.ASCENDING)
        self.calculated = 0 # Começa em um porque a primeira issue não tem issues para comparar
        self.total = self.collection.count_documents(query)
        threads = []
        for issue in allIssues:
            # TODO: adicionar checkbox para remover ja calculadas
            gfi = 1 if self.goodFirstIssueTagName.get() in issue['labels'] else 0
            filtros = {
                'number': issue['number'],
                'compare': self.compare.get(),
                'tecnica': self.strategy.get(),
                'filtros': {
                    'lowercase': self.lowercase.get(),
                    'removeLinks': self.links.get(),
                    'removeDigits': self.digits.get(),
                    'removeStopWords': self.stopWords.get(),
                    'lemmatization': self.lemmatization.get(),
                    'removeTextFiles': self.removeTextFiles.get(),
                    'goodFirstIssue': gfi,
                    'daysBefore': int(self.daysBefore.get())
                }
            }
            if self.outCollection.count_documents(filtros) == len(k): # TODO: Melhorar isso
                print(f'Pulando {issue["title"][:20]} - {issue["number"]} pois já foi calculada')
                self.calculated += 1
                continue
            
            
            daysBefore = datetime.datetime.strptime(issue['closed_at'], '%Y-%m-%dT%H:%M:%S%z')
            daysBefore = daysBefore - datetime.timedelta(int(self.daysBefore.get()))
            
            issuesClosedBefore = self.collection.find(
                {'closed_at': {
                    '$lte': issue['closed_at'],
                    '$gte': daysBefore.strftime('%Y-%m-%d')
                    }
                }).sort('closed_at', pymongo.DESCENDING) # Vai pegando as issues mais velhas para mais novas e para garantir que o primeira é a mais nova ordena
                        
            issues = {issue['title']: issue for issue in issuesClosedBefore}
            if len(issues) <= max(k):
                primeiraIssue = list(issues.keys())[0]
                print(f'Pulando {primeiraIssue[:20]} - {issues[primeiraIssue]["number"]} pois não tem issues suficientes para serem sugeridas')
                self.calculated += 1
                continue # Não tem issues para comparar

            corpus = {}
            for title in issues:
                issue = issues[title]
                data = ''
                if compareData == 'title':
                    data = title
                elif compareData == 'body':
                    data = issue['body']
                else:
                    data = f"{title} {issue['body'] if issue['body'] != None else ''}"

                if data == None:
                    data = ''

                if setLowercase:
                    data = data.lower()
                
                if removeLinks:
                    data = re.sub(r'http\S+', '', data)
                
                if removeDigits:
                    remove_digits = str.maketrans('', '', digits)
                    data = data.translate(remove_digits)
                
                if removeStopWords:
                    stop_words = set(stopwords.words('english'))
                    word_tokens = word_tokenize(data)
                    data = [w for w in word_tokens if not w in stop_words]
                    data = ' '.join(data)
                
                # if useLemmatization:
                #     data = lemmatizatizeCorpus(data)
                corpus[data] = issue
            
            t = threading.Thread(target=self.calculateSimilarities, args=(corpus, strategy, k))
            t.start()
            threads.append(t)
        
        for thread in threads:
            thread.join()
        
        self.submitButton.config(state=NORMAL)

    def calculateSimilarities(self, corpus, strategy, k, writer = None):
        self.calculated += 1
        self.pbLabel.config(text=f'Calculating similarities: {self.calculated}/{self.total} ')
        self.pb['value'] = self.calculated / self.total * 100

        currIssue = list(corpus.keys())[0]

        sb = strategy(list(corpus.keys()), currIssue)
        ordered = sorted(sb, key=lambda x: x[1], reverse=True)
        
        currSolvedBy = corpus[currIssue]['files']
        
        FILES_FORMAT = ('.txt', '.md')
        if self.removeTextFiles.get():
            currSolvedBy = list(filter(lambda x: not x.lower().endswith(FILES_FORMAT), currSolvedBy))
        
        if(len(currSolvedBy) == 0):
            print(f'Pulando {currIssue[:20]} - {corpus[currIssue]["number"]} pois não tem arquivos resolvidos')
            return
               
        for useK in k:
            self.saveResult(corpus, currIssue, ordered, useK, currSolvedBy)
    
    def saveResult(self, corpus, currIssue, ordered, useK, currSolvedBy):
        '''
        data|repositorio|issue|#arquivos|topk|tecnica|mapk|min_sim|max_sim|mediana_sim|#acertos|#erros|arquivos_resolvidos_de_verdade|arquivos_sugestoes
        
        ultimas 3000 issues
        '''
        
        gfi = 1 if self.goodFirstIssueTagName.get() in corpus[currIssue]['labels'] else 0
        
        output = {
            'data': corpus[currIssue]['closed_at'],
            'repositorio': self.repoUrl.get(),
            'issue': f"{corpus[currIssue]['title']}",
            'number': corpus[currIssue]['number'],
            'arquivos': len(currSolvedBy),
            'topk': useK,
            'tecnica': self.strategy.get(),
            'compare': self.compare.get(),
            'filtros': {
                'lowercase': self.lowercase.get(),
                'removeLinks': self.links.get(),
                'removeDigits': self.digits.get(),
                'removeStopWords': self.stopWords.get(),
                'lemmatization': self.lemmatization.get(),
                'removeTextFiles': self.removeTextFiles.get(),
                'goodFirstIssue': gfi,
                'daysBefore': int(self.daysBefore.get()),
            },
            'arquivos_resolvidos_de_verdade': currSolvedBy,
            'mapk': 0,
            'min_sim': getFloatFromValue(ordered[useK - 1][1]),
            'max_sim': getFloatFromValue(ordered[0][1]),
            'mediana_sim': getFloatFromValue(ordered[useK // 2][1]),
            'acertos': 0,
            'erros': 0,
            'arquivos_sugeridos': [],
            'issues_sugeridas': []
        }
        
        FILES_FORMAT = ('.txt', '.md')
        if self.removeTextFiles.get():
            currSolvedBy = list(filter(lambda x: not x.lower().endswith(FILES_FORMAT), currSolvedBy))
            
        apkArr = []
        for i in range(useK):
            currSugestion = ordered[i][0]
            currSimilarity = ordered[i][1]
            currSugestionFiles = corpus[currSugestion]['files']
            currSugestionNumber = corpus[currSugestion]['number']
            if self.removeTextFiles.get():
                currSugestionFiles = list(filter(lambda x: not x.lower().endswith(FILES_FORMAT), currSugestionFiles))
            output['arquivos_sugeridos'].extend(currSugestionFiles)
            output['issues_sugeridas'].append([currSugestionNumber, currSimilarity])
            currApk = apk(currSolvedBy, currSugestionFiles, len(currSolvedBy))
            apkArr.append(currApk)
  
        
  
        output['arquivos_sugeridos'] = list(OrderedDict.fromkeys(output['arquivos_sugeridos']))
        output['acertos'] = len([x for x in output['arquivos_sugeridos'] if x in output['arquivos_resolvidos_de_verdade']])
        output['erros'] = len(output['arquivos_sugeridos']) - output['acertos']
        output['mapk'] = np.mean(apkArr)
        
        self.outCollection.update_one({
                'number': output['number'],
                'topk': output['topk'],
                'tecnica': output['tecnica'],
                'compare': output['compare'],
                'filtros': {
                    'lowercase': output['filtros']['lowercase'],
                    'removeLinks': output['filtros']['removeLinks'],
                    'removeDigits': output['filtros']['removeDigits'],
                    'removeStopWords': output['filtros']['removeStopWords'],
                    'lemmatization': output['filtros']['lemmatization'],
                    'removeTextFiles': output['filtros']['removeTextFiles'],
                    'goodFirstIssue': output['filtros']['goodFirstIssue'],
                    'daysBefore': output['filtros']['daysBefore'], 
                },
            },{
                "$set": output
            },
            upsert=True
        )


window=Tk()
mywin=EvalutorWindow(window)
window.title('Evaluate Comparison Methods')
window.geometry("650x550+10+10")
window.mainloop()