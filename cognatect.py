import gensim.downloader as api
import numpy as np
from numpy import dot
from numpy.linalg import norm
import panphon.distance
import re

wv = api.load('word2vec-google-news-300')
dist = panphon.distance.Distance()

def compute_gloss_embedding(gloss):
    vectors = []
    for word in re.findall('[A-Za-z]+', gloss):
        try:
            vectors.append(wv[word])
        except KeyError:
            pass
    return sum(vectors)

def compute_similarity_score(form1, form2, gloss1, gloss2):
    fd = dist.feature_edit_distance_div_maxlen(form1, form2)
    print(f'fd={fd}')
    v1 = compute_gloss_embedding(gloss1)
    v2 = compute_gloss_embedding(gloss2)
    cos_sim = dot(v1, v2)/(norm(v1)*norm(v2))
    print(f'cos_sim={cos_sim}')
    return cos_sim / (fd + 1) 