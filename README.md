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

We used GPT 5.2 to generate code diffs used to solve the issues. It's possible that the same prompts produce different results.

1. **API_KEY:** Your OpenAI API key..

- **OLLAMA**:

We used qwen3.6:35b and gpt-oss:120b (high, medium) to generate code diffs used to solve the tasks. It's possible that the same prompts produce different results.

1. **BASE_URL**: Ollama base url. e.g.: http://localhost:11434
2. **MODEL**: Ollama model name. e.g.: gpt-oss:120b

# Installing the dataset

With MongoDB running and the configuration file filled out, use `mongorecover` with the `dataset.gz` to be able to run the evaluation scripts.

# Installing dependencies

We developed and ran the study using Python version 3.10.8 and pip 23.1.2.

We used several libraries to run this research, including:

```
beautifulsoup4==4.14.3
gensim==4.4.0
matplotlib==3.10.8
nltk==3.9.4
numpy==2.4.4
openai==2.32.0
pandas==3.0.2
pymongo==4.17.0
Requests==2.33.1
scikit_learn==1.8.0
scipy==1.17.1
seaborn==0.13.2
sentence_transformers==5.4.0
torch==2.9.0
tqdm==4.67.1
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

Just run the command `python3 qp3.py`, change the value of `IS_2026_RUN`: `False` for pre 2026 issues, and `True` for issues created and closed >= `2026-01-01`.
