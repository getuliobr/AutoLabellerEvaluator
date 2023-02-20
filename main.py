from tkinter import *
class MyWindow:
    def __init__(self, win):
        self.repoUrlLabel = Label(win, text='Repo URL')
        self.repoUrlLabel.place(x=100, y=50)
        self.repoUrl = Entry(bd=3, width= 50)
        self.repoUrl.place(x=200, y=50)

        self.lowercaseLabel = Label(win, text='Convert to lowercase')
        self.lowercaseLabel.place(x=100, y=100)
        self.lowercase = IntVar()
        self.lowerCaseCheck = Checkbutton(win, variable=self.lowercase)
        self.lowerCaseCheck.place(x=300, y=100)

        self.linksLabel=Label(win, text='Remove links')
        self.linksLabel.place(x=100, y=150)
        self.links = IntVar()
        self.linksCheck = Checkbutton(win, variable=self.links)
        self.linksCheck.place(x=300, y=150)

        self.digitsLabel=Label(win, text='Remove digits')
        self.digitsLabel.place(x=100, y=200)
        self.digits = IntVar()
        self.digitsCheck = Checkbutton(win, variable=self.digits)
        self.digitsCheck.place(x=300, y=200)
        
        self.stopWordsLabel = Label(win, text='Remove stop words')
        self.stopWordsLabel.place(x=100, y=250)
        self.stopWords = IntVar()
        self.stopWordsCheck = Checkbutton(win, variable=self.stopWords)
        self.stopWordsCheck.place(x=300, y=250)

        self.submitButton = Button(win, text='Submit', command=self.submit, anchor=CENTER, width=20)
        self.submitButton.place(x=300, y=300, anchor=CENTER)


    def submit(self):
      print(self.repoUrl.get())
      print(self.lowercase.get())
      print(self.links.get())
      print(self.digits.get())
      print(self.stopWords.get())

window=Tk()
mywin=MyWindow(window)
window.title('Evaluate Comparison Methods')
window.geometry("600x350+10+10")
window.mainloop()