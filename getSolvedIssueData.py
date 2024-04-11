import json

from bs4 import BeautifulSoup
import requests

from octokit import Octokit

from pymongo.collection import Collection

from config import config
import re
import time

from graphql import get_issues

def getSolvedIssues(owner, repo, pb, label, dbCollection: Collection, closedDate='2000-01-01', setLowercase=False, removeLinks=False, removeDigits=False, removeStopWords=False):
  label.config(text=f"Fetching issues using graphql")
  issues = get_issues(owner, repo, date=closedDate, setLowercase=setLowercase, removeLinks=removeLinks, removeDigits=removeDigits, removeStopWords=removeStopWords)
  total = len(issues)
  for i, issue in enumerate(issues):
    label.config(text=f"Inserting issue: {issue['number']}, done: {i}/{total}")
    pb['value'] = (i+1)/total * 100
    dbCollection.update_one({
      'number': issue['number'],
      'lowercase': setLowercase,
      'removeLinks': removeLinks,
      'removeDigits': removeDigits,
      'removeStopWords': removeStopWords
    },{"$set": {
      el: issue[el] for el in issue
    }}, upsert=True)