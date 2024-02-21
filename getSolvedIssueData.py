import json

from bs4 import BeautifulSoup
import requests

from octokit import Octokit

from pymongo.collection import Collection

from config import config
import re
import time

from graphql import get_issues

def getSolvedIssues_old(owner, repo, pb, label, dbCollection: Collection):
  octokit = Octokit(auth='installation', app_id=config['GITHUB']['APP_IDENTIFIER'], private_key=config['GITHUB']['PRIVATE_KEY'])
  
  searchString = f'repo:{owner}/{repo} state:closed linked:pr is:issue sort:created'
  data = octokit.search.issues_and_pull_requests(q=searchString, per_page=100).json
  
  
  issuesList = data['items']
  total = data['total_count']
  total_saved = dbCollection.count_documents({})
  label.config(text=f"Total issues: {total}")
  # TODO: fazer isso aqui funcionar bem e rapido
  if total_saved == total:
    return
  page = 2
  while len(issuesList) != total:
    pb['value'] = len(issuesList)/total * 100
    label.config(text=f"Page: {page} - {len(issuesList)}/{total}")
    data = octokit.search.issues_and_pull_requests(q=searchString, per_page=100, page=page).json
    try:
      issuesList.extend(data['items'])
      page += 1
    except:
      errMessage = data['message']
      if errMessage == 'Only the first 1000 search results are available':
        lastIssue = issuesList[-1]
        created = lastIssue['created_at']
        searchString = f'repo:{owner}/{repo} state:closed linked:pr is:issue sort:created created:<{created}'
        print('Now fetching issues created before:', created)
        page = 1
      elif errMessage.startswith('API rate limit exceeded for installation ID'):
        print('Rate limit exceeded, waiting 10 seconds')
        time.sleep(10)
      else:
        print(errMessage)
        fetchedAll = True

  label.config(text=f"Fetching issue data")
  pb['value'] = 0

  for num, issue in enumerate(issuesList):
    label.config(text=f"Getting issue {issue['html_url']}")
    pb['value'] = (num + 1)/len(issuesList) * 100
    r = requests.get(issue['html_url'])

    soup = BeautifulSoup(r.text, 'html.parser')
    issueForm = soup.find("form", { "aria-label": re.compile('Link issues')})

    linkedMergedPR = [f"https://github.com{i.parent['href']}" for i in issueForm.find_all('svg', attrs={ "aria-label": re.compile('Merged Pull Request')})]
    filesSolvingThisIssue = []


    for pr in linkedMergedPR:
      label.config(text=f"Getting pull request {pr} files")
      fetchedAll = False
      filesInThisPR = []
      page = 1
      while not fetchedAll and len(filesInThisPR) < 3000:
        branchOwner, branchRepo = pr.split('https://github.com/')[1].split('/')[:2]
        try:
          data = octokit.pulls.list_files(owner=branchOwner, repo=branchRepo, pull_number=pr.split('/')[-1], page=page, per_page=100)
          files = data.json
          if len(files) < 100:
            fetchedAll = True
          filesInThisPR.extend(list(map(lambda x: x['filename'], files)))
          page += 1
        except Exception as e:
          if files['message'] == 'Bad credentials':
            print('Reauthenticate')
            octokit = Octokit(auth='installation', app_id=config['GITHUB']['APP_IDENTIFIER'], private_key=config['GITHUB']['PRIVATE_KEY'])
      filesSolvingThisIssue.extend(filesInThisPR)

    dbCollection.update_one({
      'number': issue['number']
    },{"$set": {
      'title': issue['title'],
      'body': issue['body'],
      'number': issue['number'],
      'files': filesSolvingThisIssue,
      'labels': list(map(lambda x: x['name'], issue['labels'])),
      'closed_at': issue['closed_at'],
    }}, upsert=True)

def getSolvedIssues(owner, repo, pb, label, dbCollection: Collection):
  label.config(text=f"Fetching issues using graphql")
  issues = get_issues(owner, repo)
  total = len(issues)
  for i, issue in enumerate(issues):
    label.config(text=f"Inserting issue: {issue['number']}, done: {i}/{total}")
    pb['value'] = (i+1)/total * 100
    dbCollection.update_one({
      'number': issue['number']
    },{"$set": {
      el: issue[el] for el in issue
    }}, upsert=True)