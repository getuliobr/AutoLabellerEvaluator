[![pt-br](https://img.shields.io/badge/lang-pt--br-green.svg)](./README.pt-br.md)

Here contains the source code of the tool for collecting, suggesting and results of GitHub issues.

In the dataset provided, we provide the data used for the development of our research, such as the issues from the 35 repositories mined, with the pull requests and files that closed the issues.

# Filling the configuration file

To replicate this research or mine new data, you will need to create a `config.ini` file following the template present in `config.ini.example`. You will need to fill in the following data:

- **GITHUB**:

1. **TOKEN:** You’ll need to create an access token [here](https://github.com/settings/tokens). For this paper, we used the classic token. If you’re only mining data from public projects, you don't need to enable any permissions.

- **DATABASE**:

We used a Docker container with the MongoDB image to perform this research.

1. **CONTAINER_NAME:** Name of the MongoDB container, used to make and restore backups.
2. **CONNECTION_STRING:** String to connect to MongoDB. We haven’t tested strings that include the username and password, so they might not work.
3. **NAME:** Name of the database in MongoDB. We used the name `evaluator`; if you change it, you may need to rename the `evaluator` folder inside the `backup` directory to match the new name.

- **OPENAI**:

We used GPT 3.5 and 4 to generate code to solve the tasks. It's possible that the same prompts produce different results. The generated code is included in the dataset we provided (in the MongoDB collection: `jabref/jabref_gpt_results`).

1. **API_KEY:** Your OpenAI API key..

# Installing the dataset

With MongoDB running and the configuration file filled out, simply run the command `./loadBackup.sh`.

# Installing dependencies

We developed and ran the study using Python version 3.10.8 and pip 23.1.2.

We used several libraries to run this research, including:

```
beautifulsoup4==4.12.3
codebleu==0.6.0
gensim==4.2.0
matplotlib==3.6.2
nltk==3.7
numpy==1.23.5
octokit==0.0.1
octokitpy==0.15.0
openai==1.16.2
pandas==1.5.1
pymongo==4.3.3
requests==2.25.1
scikit_learn==1.4.1.post1
scipy==1.13.0
seaborn==0.13.2
sentence_transformers==2.2.2
torch==1.12.1+cu116
unidiff==0.7.5
```

You can install all libraries with the command: `pip3 install -r requirements.txt`.

# Running

## Mining and running tests

You can mine and run tests with the command: `python3 main.py`.

A window will appear where you can configure preprocessing and other options, such as:

- **owner/repo:** The repository to mine, e.g., `jabref/jabref` or `godotengine/godot`.
- **K:** The TopK values, separated by commas, e.g., `1,3` or `1,3,5`.
- **Compare Data:** What will be passed to the text similarity algorithms.
- **Fetch from API:** Whether to mine data from GitHub or use already-mined data.
- **Use good first issues only:** Only good first issues will be tested.
- **Good First Issue label:** Some repositories don't use lowercase labels or use different names like "easy task". Enter the label name used by the repo here. It will automatically mark the task as beginner-friendly in the results.
- **Start date:** Issues created from this date onward are part of the test group.
- **Days before:** Time window.
- **Closed date:** Issues closed from this date onward will be mined.
- **Strategy:** Which text similarity algorithm to use.

Lemmatization is not implemented and will not generate results.

Finally, after configuring, just press the `submit` button and it will mine the repository and run the tests automatically.

## Analysis

### Statistics

To get the number of issues, PRs, files, and tests, run: `python3 count_issues.py`.

### RQ1 and RQ2

To obtain the results of QP1 and QP2, run the script: `python3 qp12.py`. If you only want good first issues, uncomment line 86.

### RQ3

Just run the command `python3 qp3.py`.
