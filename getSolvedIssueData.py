import json

from bs4 import BeautifulSoup
import requests

from octokit import Octokit

from config import config
import re

def getSolvedIssues(owner, repo, pb, label):
  octokit = Octokit(auth='installation', app_id=config['GITHUB']['APP_IDENTIFIER'], private_key=config['GITHUB']['PRIVATE_KEY'])

  data = octokit.search.issues_and_pull_requests(q=f'repo:{owner}/{repo} state:closed linked:pr is:issue', per_page=100).json
  issuesList = data['items']
  total = data['total_count']
  label.config(text=f"Total issues: {total}")
  
  page = 2
  while len(issuesList) != total:
    pb['value'] = len(issuesList)/total * 100
    label.config(text=f"Page: {page} - {len(issuesList)}/{total}")
    data = octokit.search.issues_and_pull_requests(q=f'repo:{owner}/{repo} state:closed linked:pr is:issue', per_page=100, page=page).json
    try:
      issuesList.extend(data['items'])
      page += 1
    except:
      break

  filesThatSolveIssue = {}

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
        files = octokit.pulls.list_files(owner=owner, repo=repo, pull_number=pr.split('/')[-1], page=page, per_page=100).json
        if len(files) < 100:
          fetchedAll = True
        page += 1
        filesInThisPR.extend(list(map(lambda x: x['filename'], files)))
      filesSolvingThisIssue.extend(filesInThisPR)
    
    filesThatSolveIssue[issue['title']] = {
      'body': issue['body'],
      'files': filesSolvingThisIssue
    }

  return filesThatSolveIssue