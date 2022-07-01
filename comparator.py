import json
# import panphon.distance
# from selectors import EpollSelector
import re
import sqlite3
import sys
from typing import Any
import numpy as np
import panphon2
from markdownTable import markdownTable
from numpy import dot
from numpy.linalg import norm
from numpy.random import rand
from scipy.spatial.distance import cosine
from sklearn.metrics.pairwise import cosine_similarity
import gensim.downloader as api
from flask import Flask, g, jsonify, render_template, request

app = Flask(__name__)

print('Loading word2vec...')
wv = api.load('word2vec-google-news-300') 
print('Done.')

# Database setup

print('Loading FeatureTable...')
ft = panphon2.FeatureTable()
print('Done.')

DATABASE = 'db/borderlands.sqlite3'

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

##############################################################################
# Utility functions for cognate detection
##############################################################################

def compute_gloss_embedding(gloss: str) -> Any:
    vectors = []
    global wv
    global ft
    for word in re.findall('[A-Za-z]+', gloss):
        try:
            vectors.append(wv[word])
        except KeyError:
            vectors.append(rand(300))
    return sum(vectors)

def compute_similarity_score(form1: str, form2: str, gloss1: str, gloss2: str, beta: float) -> float:
    # fd = dist.feature_edit_distance_div_maxlen(form1, form2) + 0.000000001
    maxlen = max(len(form1), len(form2))
    fd = ft.feature_edit_distance(form1, form2) / maxlen
    v1 = compute_gloss_embedding(gloss1)
    v2 = compute_gloss_embedding(gloss2)
    np.seterr(invalid='ignore')
    cos_dist = cosine(v1, v2)
    # score = float(((1 + beta**2) * cos_dist * fd) / (beta**2 * cos_dist + fd + sys.float_info.epsilon))
    score = cos_dist + (fd * beta)
    return score

def find_potential_cognates(langid1: int, form1: str, gloss1: str, beta: float) -> "list[list[str]]":
    c = get_db().cursor()
    # c.execute('''CREATE TABLE IF NOT EXISTS "potcogs" (
    #      "refid" integer NOT NULL PRIMARY KEY,
    #      "langid" integer NOT NULL,
    #      "form" text NOT NULL,
    #      "gloss" text,
    #      "sim" real NOT NULL)''')
    # get_db().commit()
    c.execute('''DELETE FROM potcogs''')
    get_db().commit()
    print('Retrieving reflexes...')
    c.execute('''SELECT DISTINCT refid, langid, form, gloss 
                 FROM reflexes
                 WHERE langid IS NOT ?''', (langid1,))
    results = []
    print('Computing similarities...')
    for (refid2, langid2, form2, gloss2) in c:
        sim = compute_similarity_score(form1, form2, gloss1, gloss2, beta)
        results.append([refid2, langid2, form2, gloss2, sim])
    c.executemany('''INSERT INTO potcogs (refid, langid, form, gloss, sim) 
                     VALUES (?, ?, ?, ?, ?)''', results)
    get_db().commit()

##############################################################################
# Utility functions for presenting parsed forms
##############################################################################

def parse_form(form):
    return [m.groups() for m in re.finditer('([^ -]+)( |-|)', form)]
    
def strong_morph(form, i):
    if len(form) > i:
        morph, delim = form[i]
        form[i] = ('<strong>{}</strong>'.format(morph), delim)
    return form

def join_form(form):
    return ''.join([''.join(m) for m in form])

def strong_form(form, i):
    morphs = parse_form(form)
    if morphs:
        return join_form(strong_morph(morphs, i))
    else:
        return ''

##############################################################################
# The page
##############################################################################

@app.route('/')
def root():
    return render_template('index.jinja2')

##############################################################################
# Data for the four main tables
##############################################################################

@app.route('/reflexes', methods=['GET', 'POST'])
def reflexes():
    # All data should have the following shape
    cols = ['reflexes.langid', 'refid', 'lname', 'form', 'gloss']
    # limit parameters
    start = request.args.get('start', 0, type=int)
    length = request.args.get('length', 0, type=int)
    draw = request.args.get('draw', 0, type=int)
    # Search strings for language, form, and gloss
    lang_search = '%{}%'.format(request.args.get('columns[2][search][value]', '', type=str))
    form_search = '%{}%'.format(request.args.get('columns[3][search][value]', '', type=str))
    gloss_search = '%{}%'.format(request.args.get('columns[4][search][value]', '', type=str))
    # Order
    order = cols[request.args.get('order[0][column]', 2, type=int)]
    direction = request.args.get('order[0][dir]', 'asc', type=str)
    if direction not in ['asc', 'desc']: direction = 'asc'
    ordering_term = f'{order} {direction}'
    print(ordering_term)
    # Database interactions
    c = get_db().cursor()
    c.execute('SELECT COUNT(*) FROM reflexes;')
    total = int(c.fetchone()[0])
    c.execute('''SELECT COUNT(*)
                 FROM reflexes JOIN langnames on langnames.langid=reflexes.langid
                 WHERE langnames.name LIKE ? AND form LIKE ? AND gloss LIKE ?''',
              (lang_search, form_search, gloss_search))
    filtered_total = int(c.fetchone()[0])
    c.execute(("""SELECT reflexes.langid,
                         refid,
                         langnames.name AS lname,
                         form,
                         gloss
                  FROM reflexes
                  JOIN langnames ON langnames.langid=reflexes.langid
                  WHERE lname LIKE ? AND form LIKE ? AND gloss LIKE ?
                  ORDER BY %s
                  LIMIT ? OFFSET ?""") % ordering_term,
              (lang_search, form_search, gloss_search,
               length, start))
    reflexes = c.fetchall()
    return jsonify({'draw': draw,
                    'recordsTotal': total,
                    'recordsFiltered': filtered_total,
                    'data': reflexes})

@app.route('/potcogs', methods=['GET', 'POST'])
def potcogs():
    # All data for potcogs should take this shape:
    cols = ['potcogs.langid', 'refid', 'lname', 'form', 'gloss', 'sim']
    # limit parameters
    start = request.args.get('start', 0, type=int)
    length = request.args.get('length', 0, type=int)
    draw = request.args.get('draw', 0, type=int)
    # Search strings for language, form, and gloss
    lang_search = '%{}%'.format(request.args.get('columns[2][search][value]', '', type=str))
    form_search = '%{}%'.format(request.args.get('columns[3][search][value]', '', type=str))
    gloss_search = '%{}%'.format(request.args.get('columns[4][search][value]', '', type=str))
    # Order
    order = cols[request.args.get('order[0][column]', 0, type=int)]
    direction = request.args.get('order[0][dir]', 'asc', type=str)
    if direction not in ['asc', 'desc']: direction = 'asc'
    ordering_term = f'{order} {direction}'
    # Database interactions
    c = get_db().cursor()
    # lnames is missing because that comes from a join with langnames
    c.execute('''CREATE TABLE IF NOT EXISTS "potcogs" (
         "langid" integer NOT NULL,
         "refid" integer NOT NULL PRIMARY KEY,
         "form" text NOT NULL,
         "gloss" text,
         "sim" real NOT NULL)''')
    get_db().commit()
    c.execute('SELECT COUNT(*) FROM potcogs;')
    total = int(c.fetchone()[0])
    c.execute('''SELECT COUNT(*)
              FROM potcogs JOIN langnames on langnames.langid=potcogs.langid
              WHERE langnames.name LIKE ? AND form LIKE ? AND gloss LIKE ?''',
              (lang_search, form_search, gloss_search))
    filtered_total = int(c.fetchone()[0])
    c.execute(('''SELECT DISTINCT
                    potcogs.langid,
                    refid,
                    langnames.name AS lname,
                    form,
                    gloss,
                    sim
              FROM potcogs JOIN langnames ON langnames.langid=potcogs.langid
              WHERE lname LIKE ? AND form LIKE ? AND gloss LIKE ?
              ORDER BY %s
              LIMIT ? OFFSET ?''') % 'sim ASC',
              (lang_search, form_search, gloss_search,
               length, start))
    potcogs = c.fetchall()
    return jsonify({'draw': draw,
                    'recordsTotal': total,
                    'recordsFiltered': filtered_total,
                    'data': potcogs})

@app.route('/protoforms')
def protoforms():
    cols = ['refid', 'lname', 'form', 'gloss']
    # limit parameters
    start = request.args.get('start', 0, type=int)
    length = request.args.get('length', 0, type=int)
    draw = request.args.get('draw', 0, type=int)
    # Search strings for language, form, and gloss
    lang_search = '%{}%'.format(request.args.get('columns[2][search][value]', '', type=str))
    form_search = '%{}%'.format(request.args.get('columns[3][search][value]', '', type=str))
    gloss_search = '%{}%'.format(request.args.get('columns[4][search][value]', '', type=str))
    # Order
    order = cols[request.args.get('order[0][column]', 0, type=int)]
    direction = request.args.get('order[0][dir]', 'asc', type=str)
    if direction not in ['asc', 'desc']: direction = 'asc'
    ordering_term = '{} {}'.format(order, direction)
    c = get_db().cursor()
    c.execute("SELECT COUNT(*) FROM (SELECT DISTINCT refid FROM reflexes " +
              "INNER JOIN descendant_of ON reflexes.langid=plangid)")
    total = int(c.fetchone()[0])
    c.execute("SELECT COUNT(*) " +
              "FROM (SELECT DISTINCT refid " +
              "FROM reflexes " +
              "INNER JOIN descendant_of ON reflexes.langid=plangid " +
              "JOIN langnames ON langnames.langid=reflexes.langid "
              "WHERE langnames.name LIKE ? AND form LIKE ? AND gloss LIKE ?)",
              (lang_search, form_search, gloss_search))
    filtered_total = int(c.fetchone()[0])
    c.execute(("SELECT DISTINCT refid, plangid, langnames.name AS lname, form, gloss " +
	           "FROM reflexes " +
	           "INNER JOIN descendant_of ON plangid=reflexes.langid " +
	           "JOIN langnames ON langnames.langid=reflexes.langid " +
	           "WHERE lname LIKE ? AND form like ? AND gloss LIKE ? " +
	           "ORDER BY %s " +
	           "LIMIT ? OFFSET ?") % ordering_term,
               (lang_search, form_search, gloss_search,
                length, start))
    protoforms = c.fetchall()
    data = {'draw': draw,
            'recordsTotal': total,
            'recordsFiltered': filtered_total,
            'data': protoforms}
    return jsonify(data)

@app.route('/supporting')
def supporting():
    start = request.args.get('start', 0, type=int)
    length = request.args.get('length', 0, type=int)
    draw = request.args.get('draw', 0, type=int)
    prefid = request.args.get('prefid', 55760, type=int)
    c = get_db().cursor()
    c.execute('SELECT COUNT(*) FROM reflex_of')
    total = int(c.fetchone()[0])
    c.execute('SELECT COUNT(*) FROM (SELECT DISTINCT reflexes.refid FROM reflexes JOIN reflex_of ON reflex_of.refid=reflexes.refid WHERE prefid=?)', (prefid,))
    filtered_total = int(c.fetchone()[0])
    c.execute("SELECT reflexes.refid, langnames.name, form, gloss, morph_index FROM reflexes JOIN reflex_of ON reflex_of.refid=reflexes.refid JOIN langnames on reflexes.langid=langnames.langid WHERE prefid=? LIMIT ? OFFSET ?", (prefid, length, start))
    supporting_forms = [[r, l, strong_form(f, i), g, i] for (r, l, f, g, i) in c.fetchall()]
    json = jsonify({'draw': draw,
                    'recordsTotal': total,
                    'recordsFiltered': filtered_total,
                    'data': supporting_forms})
    print(json)
    return json

##############################################################################
# Add reflexes to master list
##############################################################################

@app.route('/newreflexdialog')
def new_reflex_dialog():
    c = get_db().cursor()
    c.execute('SELECT DISTINCT langid, name ' + 
              'FROM langnames ' + 
              'ORDER BY name')
    langs = c.fetchall()
    return render_template('new_reflex_dialog.jinja2', langs=langs)

@app.route('/addnewreflex')
def add_new_reflex():
    langid = request.args.get('langid', 0, type=int)
    sourceid = request.args.get('sourceid', 0, type=int)
    form = request.args.get('form', '', type=str)
    gloss = request.args.get('gloss', '', type=str)
    c = get_db().cursor()
    c.execute('INSERT INTO reflexes (langid, sourceid, form, gloss) VALUES (?, ?, ?, ?)', 
        (langid, sourceid, form, gloss))
    get_db().commit()
    return jsonify({'success': 'Entry successfully added'})

##############################################################################
# Add reflexes to and remove reflexes from cognate sets
##############################################################################

@app.route('/addsupporting')
def add_supporting_form():
    print('/addsupporting')
    refid = request.args.get('refid', 0, type=int)
    prefid = request.args.get('prefid', 0, type=int)
    plangid = request.args.get('plangid', 0, type=int)
    print(f'Add {refid} to {prefid} in {plangid}')
    c = get_db().cursor()
    c.execute('SELECT COUNT(*) FROM reflex_of WHERE prefid=? AND refid=?', (prefid, refid))
    if not c.fetchone()[0]:
        c.execute('INSERT INTO reflex_of (prefid, refid, plangid, morph_index) VALUES (?, ?, ?, ?)',
                  (prefid, refid, plangid, 0))
        get_db().commit()
    c.execute('SELECT morph_index FROM reflex_of WHERE refid=? AND prefid=?',
              (refid, prefid))
    morph_index = c.fetchone()[0]
    c.execute('SELECT form FROM reflexes WHERE refid=?', (refid,))
    form = c.fetchone()[0]
    morphs = enumerate(re.split(' |-', form))
    return render_template('supporting_dialog.jinja2',
                           refid=refid,
                           morphs=morphs,
                           morph_index=morph_index)

@app.route('/removesupporting')
def remove_supporting_form():
    print('/removesupporting')
    refid = request.args.get('refid', 0, type=int)
    prefid = request.args.get('prefid', 0, type=int)
    print(f'Remove {refid} from {prefid}')
    c = get_db().cursor()
    c.execute('''DELETE FROM reflex_of WHERE refid=? and prefid=?''', (refid, prefid))
    get_db().commit()
    return jsonify({'success': 'Supporting form successfully removed'})

##############################################################################
# Find potential cognates
##############################################################################

@app.route('/findpotcogs')
def find_pot_cogs():
    langid = request.args.get('langid', 0, type=int)
    form = request.args.get('form', '', type=str)
    gloss = request.args.get('gloss', '', type=str)
    find_potential_cognates(langid, form, gloss, 2)
    return jsonify({'success': 'Reflexes successfully ranked'})


##############################################################################
# Remove reflexes (supporting forms) from cognate sets
##############################################################################

@app.route('/removesupporting')
def removed_reflex():
    refid = request.args.get('refid', -1, type=int)
    prefid = request.args.get('prefid', -1, type=int)
    c = get_db().cursor()
    c.execute('DELETE FROM reflex_of WHERE refid=? AND prefid=?',
              (refid, prefid))
    get_db().commit()
    return jsonify({'success': 'Removed successfully'})

##############################################################################
# Edit reflexes
##############################################################################

@app.route('/reflexdialog')
def reflex_dialog():
    id = request.args.get('refid', 0, type=int)
    lname = request.args.get('lname', '', type=str)
    form = request.args.get('form', '', type=str)
    gloss = request.args.get('gloss', '', type=str)
    return render_template('edit_dialog.jinja2', id=id, lname=lname, form=form, gloss=gloss)

@app.route('/updatereflex')
def update_reflex():
    refid = request.args.get('refid', 0, type=int)
    form = request.args.get('form', '', type=str)
    gloss = request.args.get('gloss', '', type=str)
    c = get_db().cursor()
    c.execute('UPDATE reflexes SET form=?, gloss=? WHERE refid=?', (form, gloss, refid))
    get_db().commit()
    return jsonify({'success': 'Updated successfully!'})

##############################################################################
# Delete reflexes
##############################################################################

@app.route('/deletereflex')
def delete_reflex():
    refid = request.args.get('refid', -1, type=int)
    c = get_db().cursor()
    c.execute('DELETE FROM reflexes WHERE refid=?', (refid,))
    c.execute('DELETE FROM reflex_of WHERE refid=?', (refid,))
    get_db().commit()
    return jsonify({'success': 'Deleted successfully'})

##############################################################################
# Add correspondence set
##############################################################################

@app.route('/newsetdialog')
def new_set_dialog():
    langname = request.args.get('langname', '', type=str)
    form = request.args.get('form', '', type=str)
    gloss = request.args.get('gloss', '', type=str)
    num_morphs = len(re.split('- ', form))
    c = get_db().cursor()
    c.execute('SELECT DISTINCT langnames.langid, langnames.name ' +
              'FROM langnames ' +
              'INNER JOIN descendant_of ON plangid=langnames.langid ' +
              'ORDER BY langnames.name')
    plangs = c.fetchall()
    return render_template('new_set_dialog.jinja2',
                            plangs=plangs,
                            langname=langname,
                            form=form,
                            gloss=gloss,
                            num_morphs=num_morphs)

@app.route('/addnewset')
def add_new_set():
    refid = request.args.get('refid', 0, type=int)
    plangid = request.args.get('plangid', 0, type=int)
    protoform = request.args.get('protoform', '', type=str)
    protogloss = request.args.get('protogloss', '', type=str)
    morph_index = request.args.get('morph_index', 0, type=int)
    c = get_db().cursor()
    c.execute('INSERT INTO reflexes (langid, sourceid, form, gloss) VALUES (?, -2, ?, ?)', (plangid, protoform, protogloss))
    get_db().commit()
    c.execute('SELECT LAST_INSERT_ROWID()')
    prefid = c.fetchone()[0]
    c.execute('INSERT INTO reflex_of (refid, prefid, plangid, morph_index) VALUES (?, ?, ?, ?)', 
               (refid, prefid, plangid, morph_index))
    get_db().commit()
    return jsonify({'success': 'Set successfully added'})

##############################################################################
# Edit protoforms
##############################################################################

##############################################################################
# Edits morphs of supporting forms
##############################################################################

@app.route('/updatemorph')
def update_morph():
    refid = request.args.get('refid', 0, type=int)
    prefid = request.args.get('prefid', 0, type=int)
    morph_index = request.args.get('morph_index', 0, type=int)
    print(f"morph_index: {morph_index}")
    c = get_db().cursor()
    c.execute('UPDATE reflex_of SET morph_index=? WHERE refid=? AND prefid=?', (morph_index, refid, prefid))
    get_db().commit()
    return jsonify({'success': 'Updated successfully'})

##############################################################################
# Delete protoforms
##############################################################################

@app.route('/deleteprotoform')
def delete_protoform():
    prefid = request.args.get('prefid', -1, type=int)
    print(f'Delete prefid={prefid}')
    c = get_db().cursor()
    c.execute('DELETE FROM reflexes WHERE refid=?', (prefid,))
    c.execute('DELETE FROM reflex_of WHERE prefid=?', (prefid,))
    get_db().commit()
    return jsonify({'success': 'Deleted successfully'})
