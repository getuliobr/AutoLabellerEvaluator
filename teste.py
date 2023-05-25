import numpy as np
import pandas as pd
import pymongo
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
from config import config

from octokit import Octokit

octokit = Octokit(auth='installation', app_id=config['GITHUB']['APP_IDENTIFIER'], private_key=config['GITHUB']['PRIVATE_KEY'])

branchOwner = 'microsoft'
branchRepo = 'typescript'
number = 38462

print(octokit.pulls.list_files(owner=branchOwner, repo=branchRepo, pull_number=number, page=1, per_page=100).json)