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

import requests
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
    # print(q)
    result = query(buildQuery(date))
    try:
        return result['data']['search']['edges']
    except Exception as e:
        print('err', e)
        print(result)

def clean_up(issue):
    print(issue)
    issue = issue["node"]
    issue["labels"] = [ node["name"] for node in issue["labels"]["nodes"] if node ]
    linkedPrs = [ node["source"] for node in issue["timelineItems"]["nodes"] if node and node["source"].get("state") == "MERGED" ]
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

    # print(query(buildQuery(date)))

# let prs = [];
# let lastFetch = -1;

# while(lastFetch) {
#     let prlist
#     if (lastFetch < 0) prlist = await SearchPR(REPO_OWNER, REPO_NAME, GFI_NAME);
#     else prlist = await SearchPR(REPO_OWNER, REPO_NAME, GFI_NAME, prs[prs.length - 1].node.createdAt);
#     prs.push(...prlist)
#     lastFetch = prlist.length
#     console.log(prs.length)

# }


issues = get_issues('jabref', 'jabref')
print(issues, len(issues))