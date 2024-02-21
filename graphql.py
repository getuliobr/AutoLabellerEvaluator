# import axios from "axios";
# import dotenv from "dotenv";

# dotenv.config();
# const { GITHUB_TOKEN } = process.env;

# export default (query) => axios.post(
#   'https://api.github.com/graphql',
#   { query },
#   {
#     headers: {
#       'Authorization': `bearer ${GITHUB_TOKEN}`,
#       'Content-Type': 'application/x-www-form-urlencoded'
#     }
#   }
# );

import time
import requests, csv
from config import config


def query(q):
    return requests.post(
        'https://api.github.com/graphql',
        json = {'query': q},
        headers={
            'Authorization': f'bearer {config["GITHUB"]["TOKEN"]}'
        }
    ).json()


def get_closed_issue_with_linked_pr(owner, repo, date='2000-01-01T00:00:00Z', first = 49):
    # tem um outro jeito de achar o pr que fechou a issue por meio do evento closed e olhar no campo state-reason se for completed tem como achar o pr
    buildQuery = lambda date: f'''
    query {{
        search(query: "repo:{owner}/{repo} is:issue state:closed linked:pr created:>{date} sort:created-asc", type: ISSUE, first: {first}) {{
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
                        ... on CrossReferencedEvent {{
                            willCloseTarget
                            source {{
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
        }}
        rateLimit {{
            cost
            remaining
            resetAt
        }}
    }}'''
    ## QUERY NOVA QUE PEGA SO O EVENTO DE FECHAMENTO
    buildQuery = lambda date: f'''
    query {{
        search(query: "repo:{owner}/{repo} is:issue state:closed linked:pr created:>{date} sort:created-asc", type: ISSUE, first: {first}) {{
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
        }}
        rateLimit {{
            cost
            remaining
            resetAt
        }}
    }}'''
    # print(q)
    result = query(buildQuery(date))
    try:
        if "errors" in result and len(result['errors']):
            print("Got error:", result['errors'] )
            print("Waiting 10s trying to fix")
            time.sleep(10)
            return get_closed_issue_with_linked_pr(owner, repo, date, first)
        return result['data']['search']['edges']
    except Exception as e:
        print("err:", result)
        raise e

def clean_up(issue):
    issue = issue["node"]
    issue["labels"] = [ node["name"] for node in issue["labels"]["nodes"] if node ]
    linkedPrs = [ node["closer"] for node in issue["timelineItems"]["nodes"] if node and node["stateReason"] == "COMPLETED" and node["closer"]]
    # linkedPrs = [ pr["source"] for pr in unlinkedPrs ]
    issue["files"] = list(set( file["path"] for pr in linkedPrs for file in pr["files"]["nodes"] if file ))
    issue["prs"] = list(set([ pr["number"] for pr in linkedPrs ]))
    issue["closed_at"] = issue["closedAt"]
    issue["created_at"] = issue["createdAt"]
    del issue["timelineItems"], issue["closedAt"], issue["createdAt"], issue["state"]
    return issue

def get_issues(owner, repo, date='2000-01-01T00:00:00Z'):
    issues = []
    lastFetch = -1
    while lastFetch:
        date = date if not len(issues) else issues[-1]['node']['createdAt']
        print(date, len(issues))
        issueList = get_closed_issue_with_linked_pr(owner, repo, date)
        issues.extend(issueList)
        lastFetch = len(issueList)
    return list(map(clean_up, issues))

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


# issues = get_issues('jabref', 'jabref')
# print(issues, len(issues))
if __name__ == "__main__":
    projects = get_projects()
    print("Encontrei", len(projects), "projetos")

    with open('projetos.csv', 'w+') as f:
        writer = csv.writer(f)
        writer.writerows(projects)