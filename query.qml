{
  search(
    query: "good-first-issues:>5 forks:>5 stars:>5"
    type: REPOSITORY
    first: 100
  ) {
    repositoryCount
    nodes {
      ... on Repository {
        nameWithOwner
        stars: stargazerCount
        languages(first: 1, orderBy: {field: SIZE, direction: DESC}) {
          nodes {
            name
          }
        }
        closedIssues: issues(states: [CLOSED]) {
          totalCount
        }
        closedGFI: issues(
          labels: ["good first issue", "good-first-issue"]
          states: [CLOSED]
        ) {
          totalCount
        }
        mergedPR: pullRequests(states: [MERGED]) {
          totalCount
        }
      }
    }
    pageInfo {
      endCursor
      hasNextPage
      hasPreviousPage
    }
  }
}