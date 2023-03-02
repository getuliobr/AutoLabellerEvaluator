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

DELIMITER = ';'
QUOTE = "'"

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
        issues = getSolvedIssues(owner, repo, self.pb, self.pbLabel) if self.issues == None else self.issues
        self.issues = issues

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

            corpus[data] = issue['files']
        
        # if useLemmatization:
        #     corpus = lemmatizatizeCorpus(corpus)

        now = datetime.datetime.now()
        filename = now.strftime("%Y-%m-%d-%H-%M-%S") + ".csv"
        f = open(f'./out/{filename}', 'w+', encoding="utf-8", newline='')

        writer = csv.writer(f, delimiter=DELIMITER, quotechar=QUOTE, quoting=csv.QUOTE_ALL)
        
        header = ['owner/repo', 'k', 'strategy', 'compare', 'lowercase', 'removeLinks', 'removeDigits', 'removeStopWords', 'lemmatization']
        writer.writerow(header)
        writer.writerow([f'{owner}/{repo}', k, self.strategy.get(), compareData, setLowercase, removeLinks, removeDigits, removeStopWords, useLemmatization])

        issueHeader = ['issue', 'mapk']
        for i in range(k):
            issueHeader.extend([f'sugestion{i + 1}',f'similarity{i + 1}',f'apk{i + 1}'])	
        writer.writerow(issueHeader)

        for j, issue in enumerate(corpus.keys()):
            self.pbLabel.config(text=f'Calculating similarities: {j + 1}/{len(corpus.keys())} ')
            self.pb['value'] = (j + 1) / len(corpus.keys()) * 100

            sb = strategy(list(corpus.keys()), issue)
            ordered = sorted(sb, key=lambda x: x[1], reverse=True)
            useK = min(k, len(ordered))
            currRow = [issue, 0]

            currSolvedBy = corpus[issue]
            apkArr = []

            for i in range(useK):
                currSugestion = ordered[i][0]
                currSugestionSimilarity = ordered[i][1]
                currSugestionFiles = corpus[currSugestion]
                currApk = apk(currSolvedBy, currSugestionFiles, k)
                apkArr.append(currApk)
                currRow.extend([currSugestion, currSugestionSimilarity, currApk])

            currRow[1] = np.mean(apkArr)
            writer.writerow(currRow)
        
        f.close()
        self.submitButton.config(state=NORMAL)


window=Tk()
mywin=EvalutorWindow(window)
window.title('Evaluate Comparison Methods')
window.geometry("600x550+10+10")
window.mainloop()