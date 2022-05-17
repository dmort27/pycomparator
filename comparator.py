import sqlite3
import re

from flask import Flask, jsonify, g, request, render_template
app = Flask(__name__)

# Database setup

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

# Utility functions for presenting parsed forms

def parse_form(form):
    return [m.groups() for m in re.finditer('([^ -]+)( |-|)', form)]

def strong_morph(form, i):
    morph, delim = form[i]
    form[i] = ('<strong>{}</strong>'.format(morph), delim)
    return form

def join_form(form):
    return ''.join([''.join(m) for m in form])

def strong_form(form, i):
    return join_form(strong_morph(parse_form(form), i))

# The page

@app.route('/')
def root():
    return render_template('index.jinja2')

# Data for the three main tables

@app.route('/reflexes', methods=['GET', 'POST'])
def reflexes():
    cols = ['refid', 'lname', 'form', 'gloss']
    # limit parameters
    start = request.args.get('start', 0, type=int)
    length = request.args.get('length', 0, type=int)
    draw = request.args.get('draw', 0, type=int)
    # Search strings for language, form, and gloss
    lang_search = '%{}%'.format(request.args.get('columns[1][search][value]', '', type=str))
    form_search = '%{}%'.format(request.args.get('columns[2][search][value]', '', type=str))
    gloss_search = '%{}%'.format(request.args.get('columns[3][search][value]', '', type=str))
    # Order
    order = cols[request.args.get('order[0][column]', 0, type=int)]
    direction = request.args.get('order[0][dir]', 'asc', type=str)
    if direction not in ['asc', 'desc']: direction = 'asc'
    ordering_term = '{} {}'.format(order, direction)
    # Database interactions
    c = get_db().cursor()
    c.execute('SELECT COUNT(*) FROM reflexes;')
    total = int(c.fetchone()[0])
    c.execute("SELECT COUNT(*) " +
              "FROM reflexes JOIN langnames on langnames.langid=reflexes.langid " +
              "WHERE langnames.name LIKE ? AND form LIKE ? AND gloss LIKE ?",
              (lang_search, form_search, gloss_search))
    filtered_total = int(c.fetchone()[0])
    c.execute(("SELECT refid, langnames.name AS lname, form, gloss " +
              "FROM reflexes JOIN langnames ON langnames.langid=reflexes.langid " +
              "WHERE lname LIKE ? AND form LIKE ? AND gloss LIKE ?" +
              "ORDER BY %s " +
              "LIMIT ? OFFSET ?") % ordering_term,
              (lang_search, form_search, gloss_search,
               length, start))
    reflexes = c.fetchall()
    return jsonify({'draw': draw,
                    'recordsTotal': total,
                    'recordsFiltered': filtered_total,
                    'data': reflexes})

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

# Dialog for editing reflexes

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

# Functions for additing and editing (choosing morphs for) supporting forms

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

# Functions for deleting reflexes and protoforms

@app.route('/deletereflex')
def delete_reflex():
    refid = request.args.get('refid', -1, type=int)
    c = get_db().cursor()
    c.execute('DELETE FROM reflexes WHERE refid=?', (refid,))
    c.execute('DELETE FROM reflex_of WHERE refid=?', (refid,))
    get_db().commit()
    return jsonify({'success': 'Deleted successfully'})

@app.route('/deleteprotoform')
def delete_protoform():
    prefid = request.args.get('prefid', -1, type=int)
    print(f'Delete prefid={prefid}')
    c = get_db().cursor()
    c.execute('DELETE FROM reflexes WHERE refid=?', (prefid,))
    c.execute('DELETE FROM reflex_of WHERE prefid=?', (prefid,))
    get_db().commit()
    return jsonify({'success': 'Deleted successfully'})

# Remove supporting forms

@app.route('/removesupporting')
def removed_reflex():
    refid = request.args.get('refid', -1, type=int)
    prefid = request.args.get('prefid', -1, type=int)
    c = get_db().cursor()
    c.execute('DELETE FROM reflex_of WHERE refid=? AND prefid=?',
              (refid, prefid))
    get_db().commit()
    return jsonify({'success': 'Removed successfully'})
