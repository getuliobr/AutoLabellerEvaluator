from datetime import datetime, timezone

from bs4 import BeautifulSoup
import requests, csv, time, re
from config import config

from compareAlgorithms.tfidf import get_tfidf_filtered
from compareAlgorithms.sbert import get_sbert_embeddings

def query(q):
    try:
        r = requests.post(
            'https://api.github.com/graphql',
            json = {'query': q},
            headers={
                'Authorization': f'bearer {config["GITHUB"]["TOKEN"]}'
            }
        )
        return r.json()
    except Exception as e:
        print("Error querying github:", e)
        if r:
            print(r.status_code, r.text)
        print("Waiting 10s trying to fix")
        time.sleep(10)
        return query(q)

def get_closed_issue_with_linked_pr(owner, repo, cursor=None, date='2000-01-01T00:00:00Z', first = 49):
    def buildQuery(cursor, date):
        after = f', after: "{cursor}"' if cursor else ''
        dateFilter = f' created:>{date}' if date else ''
        return f'''
    query {{
        search(query: "repo:{owner}/{repo} is:issue state:closed linked:pr{dateFilter} sort:created-asc", type: ISSUE, first: {first}{after}) {{
        issueCount
        edges {{
            node {{
            ... on Issue {{
                number
                state
                title
                body
                labels(first: 100) {{
                    nodes {{
                        name
                    }}
                }}
                closedAt
                createdAt
                timelineItems(first: 100) {{
                    nodes {{
                        ... on ClosedEvent {{
                            stateReason
                            closer {{
                                ... on PullRequest {{
                                    number
                                    title
                                    state
                                    createdAt
                                    closedAt
                                    mergedAt
                                    files(first: 100) {{
                                        nodes {{
                                        ... on PullRequestChangedFile {{
                                            path
                                        }}
                                        }}
                                    }}
                                }}
                            }}
                        }}
                    }}
                }}
            }}
            }}
        }}
        pageInfo {{
            endCursor
            hasNextPage
        }}
        }}
        rateLimit {{
            cost
            remaining
            resetAt
        }}
    }}'''
    # print(q)
    result = query(buildQuery(cursor, date))
    try:
        if "errors" in result and len(result['errors']):
            print("Got error:", result['errors'] )
            print("Waiting 10s trying to fix")
            time.sleep(10)
            return get_closed_issue_with_linked_pr(owner, repo, cursor=cursor, date=date, first=first)
        return result['data']['search']['edges'], result['data']['search']['pageInfo'], result['data']['search']['issueCount'], result['data']['rateLimit']
    except Exception as e:
        print("err:", result)
        raise e

def clean_up(setLowercase, removeLinks, removeDigits, removeStopWords):
    def wrapped(issue):
        issue = issue["node"]
        issue["labels"] = [ node["name"] for node in issue["labels"]["nodes"] if node ]
        
        linkedPrs = [ node["closer"] for node in issue["timelineItems"]["nodes"] if node and node["stateReason"] == "COMPLETED" and node["closer"]]
        files = []
        
        for pr in linkedPrs:
            if not pr["files"]:
                continue
            prFiles = pr["files"]["nodes"] 
            for file in prFiles:
                if file:
                    files.append(file["path"])
        
        issue["files"] = list(set(files))
        
        issue["prs"] = list(set([ pr["number"] for pr in linkedPrs ]))
        issue["closed_at"] = issue["closedAt"]
        issue["created_at"] = issue["createdAt"]
    
        issue["lowercase"] = setLowercase
        issue["removeLinks"] = removeLinks
        issue["removeDigits"] = removeDigits
        issue["removeStopWords"] = removeStopWords
    
        issue["tfidf"] = get_tfidf_filtered(issue)
        issue["sbert"] = get_sbert_embeddings(issue)
                
        del issue["timelineItems"], issue["closedAt"], issue["createdAt"], issue["state"]
        return issue
    return wrapped

def get_issues(owner, repo, pb, label, date='2000-01-01T00:00:00Z', setLowercase=False, removeLinks=False, removeDigits=False, removeStopWords=False):
    issues = []
    cursor = None
    total = None
    while True:
        print(date if len(issues) == 0 else issues[-1]["node"]["createdAt"], cursor, len(issues))
        start = time.time()
        issueList, pageInfo, issueCount, rateLimit = get_closed_issue_with_linked_pr(owner, repo, cursor=cursor, date=date)
        elapsed = time.time() - start
        label.config(text=f"Window has {issueCount} issues ({len(issues) + len(issueList)}{'' if total is None else f'/{total}'})")
        if total is None:
            total = issueCount

        cost = rateLimit['cost']
        hourlyUsageRate = cost / 5000
        timeout = max(0, 3600 * hourlyUsageRate - elapsed)
        print("Sleeping for", timeout, "seconds to avoid hitting the rate limit")
        # time.sleep(timeout)
        issues.extend(issueList)

        if total:
            percentage = len(issues)/total * 100
            pb['value'] = percentage if percentage <= 100 else 100 # in case a issue gets closed right when we are running and we end up with more issues than the initial total

        if pageInfo["hasNextPage"]:
            cursor = pageInfo["endCursor"]
            continue

        if not issueList:
            print("No more pages, done fetching issues")
            break

        last_created_at = issueList[-1]["node"]["createdAt"]
        if last_created_at == date:
            print("No progress on date window, done fetching issues")
            break
        print(f"Hit pagination end ({len(issueList)} in last page) — restarting from created:>{last_created_at}")
        date = last_created_at
        cursor = None
    return list(map(clean_up(setLowercase, removeLinks, removeDigits, removeStopWords), issues))

def get_projects(first=100, language='javascript'):
    reposQueryBuilder = lambda after='null': f'''query {{
  search(
    query: "good-first-issues:>5 forks:>5 stars:>5"
    type: REPOSITORY
    first: 100
    after: {after}
  ) {{
    repositoryCount
    nodes {{
      ... on Repository {{
        nameWithOwner
        stars: stargazerCount
        languages(first: 1, orderBy: {{field: SIZE, direction: DESC}}) {{
          nodes {{
            name
          }}
        }}
        closedIssues: issues(states: [CLOSED]) {{
          totalCount
        }}
        closedGFI: issues(
          labels: ["good first issue", "good-first-issue"]
          states: [CLOSED]
        ) {{
          totalCount
        }}
        mergedPR: pullRequests(states: [MERGED]) {{
          totalCount
        }}
      }}
    }}
    pageInfo {{
      endCursor
      hasNextPage
      hasPreviousPage
    }}
  }}
}}
    '''
    hasNextPage = True
    after = 'null'
    repos = []
    while hasNextPage:
        print(1)
        q = query(reposQueryBuilder(after))
        print(12)
        reposData = q["data"]["search"]
        pageInfo = reposData["pageInfo"]
        after = f'"{pageInfo["endCursor"]}"'
        hasNextPage = pageInfo["hasNextPage"]

        repos.extend(reposData["nodes"])
    # cleanRepoData = lambda x: {
    #     "repo": x["nameWithOwner"],
    #     "stars": x["stars"],
    #     "language": x["languages"]["nodes"][0]["name"] if len(x["languages"]["nodes"]) else "-",
    #     "closedIssues": x["closedIssues"]["totalCount"],
    #     "closedGFI": x["closedGFI"]["totalCount"],
    #     "mergedPR": x["mergedPR"]["totalCount"]
    # }
    cleanRepoData = lambda x: [
        x["nameWithOwner"],
        x["stars"],
        x["languages"]["nodes"][0]["name"] if len(x["languages"]["nodes"]) else "N/A",
        x["closedIssues"]["totalCount"],
        x["closedGFI"]["totalCount"],
        x["mergedPR"]["totalCount"]
    ]
    repos = list(filter(lambda x: x[4] > 100 ,map(cleanRepoData, repos)))
    return repos


def get_project_data(project):
    owner, name = project.split('/')
    r = requests.get(f'https://github.com/{project}')
    try: 
        soup = BeautifulSoup(r.text, 'html.parser')
        contributors = soup.find("a", { "class": "Link--primary no-underline Link d-flex flex-items-center", "href": re.compile(f'/{project}/graphs/contributors', re.IGNORECASE)})
        contributors = contributors.contents[1].contents[0].replace(',', '')
    except Exception as e:
        print(project)
        print(e)
        raise Exception()
    q = query(f'''query {{
  repository(owner: "{owner}", name: "{name}") {{
    stargazerCount
		forks {{
      totalCount
    }}
    languages(first:1, orderBy: {{field: SIZE, direction: DESC}}) {{
      nodes {{
        name
      }}
    }}
  }}
}}
    ''')
    data = q['data']['repository']
    stars = data['stargazerCount']
    forks = data['forks']['totalCount']
    language = data['languages']['nodes'][0]['name']
    return contributors, stars, forks, language

# issues = get_issues('jabref', 'jabref')
# print(issues, len(issues))
if __name__ == "__main__":
    get_project_data('apache/airflow')
    # projects = get_projects()
    # print("Encontrei", len(projects), "projetos")

    # with open('projetos.csv', 'w+') as f:
    #     writer = csv.writer(f)
    #     writer.writerows(projects)
