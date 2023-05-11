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
            'word2vec': word2vec
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
        self.k.insert(0, '5')

        self.compareDataLabel = Label(win, text='Compare data')
        self.compareDataLabel.place(x=200, y=100)

        self.compare = StringVar()
        self.compare.set('title')
        
        self.compareOptions = OptionMenu(win, self.compare, *self.dataOptions)
        self.compareOptions.place(x=300, y=100)

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

        self.startIssueNumberLabel = Label(win, text='Start issue')
        self.startIssueNumberLabel.place(x=350, y=300)
        self.startIssueNumber = Entry(bd=3, width=15)
        self.startIssueNumber.place(x=500, y=300)

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
        k = int(self.k.get())
        compareData = self.compare.get()

        if self.lastRepo != self.repoUrl.get():
            self.issues = None
            self.lastRepo = self.repoUrl.get()
        
        getSolvedIssues(owner, repo, self.pb, self.pbLabel, self.collection)
        
        # TODO: escolher o inicio e fim do intervalo de issues na interface
        query = {}
        if self.goodFirstIssue.get():
            query['labels'] = self.goodFirstIssueTagName.get()
        if self.startIssueNumber.get() != '':
            query['number'] = {
                '$gte': int(self.startIssueNumber.get())
            }
        
        allIssues = self.collection.find(query).sort('closed_at', pymongo.ASCENDING)
        self.calculated = 0 # Começa em um porque a primeira issue não tem issues para comparar
        self.total = self.collection.count_documents(query)
        for issue in allIssues:
            issuesClosedBefore = self.collection.find(
                {'closed_at': {
                    '$lte': issue['closed_at']
                    }
                }).sort('closed_at', pymongo.DESCENDING) # Vai pegando as issues mais velhas para mais novas e para garantir que o primeira é a mais nova ordena
            
            issues = {issue['title']: issue for issue in issuesClosedBefore}
            if len(issues) == 1:
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
            
            
            self.calculateSimilarities(corpus, strategy, k)
        
        self.submitButton.config(state=NORMAL)

    def calculateSimilarities(self, corpus, strategy, k, writer = None):
        self.calculated += 1
        self.pbLabel.config(text=f'Calculating similarities: {self.calculated}/{self.total} ')
        self.pb['value'] = self.calculated / self.total * 100

        currIssue = list(corpus.keys())[0]

        sb = strategy(list(corpus.keys()), currIssue)
        ordered = sorted(sb, key=lambda x: x[1], reverse=True)
        useK = min(k, len(ordered))
        
        currSolvedBy = corpus[currIssue]['files']
        
        FILES_FORMAT = ('.txt', '.md')
        if self.removeTextFiles.get():
            currSolvedBy = list(filter(lambda x: not x.lower().endswith(FILES_FORMAT), currSolvedBy))
        
        if(len(currSolvedBy) == 0):
            return
        
        '''
        data|repositorio|issue|#arquivos|topk|tecnica|mapk|min_sim|max_sim|mediana_sim|#acertos|#erros|arquivos_resolvidos_de_verdade|arquivos_sugestoes
        
        ultimas 3000 issues
        '''

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
                'goodFirstIssue': self.goodFirstIssue.get(),
            },
            'arquivos_resolvidos_de_verdade': currSolvedBy,
            'mapk': 0,
            'min_sim': getFloatFromValue(ordered[useK - 1][1]),
            'max_sim': getFloatFromValue(ordered[0][1]),
            'mediana_sim': getFloatFromValue(ordered[useK // 2][1]),
            'acertos': 0,
            'erros': 0,
            'arquivos_sugeridos': []
        }
        
        apkArr = []
        for i in range(useK):
            currSugestion = ordered[i][0]
            currSugestionFiles = corpus[currSugestion]['files']
            if self.removeTextFiles.get():
                currSugestionFiles = list(filter(lambda x: not x.lower().endswith(FILES_FORMAT), currSugestionFiles))
            output['arquivos_sugeridos'].extend(currSugestionFiles)
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