import json
import re
import sqlite3
from pathlib import Path

import numpy as np
from flask import Flask, g, jsonify, render_template, request

from embeddings import CognateEmbedder, build_embedder_from_db

app = Flask(__name__)

DATABASE = "db/borderlands.sqlite3"
EMBEDDER_CACHE = "db/embedder_cache.pkl"

# Load or build the embedder
print("Loading cognate embedder...")
if Path(EMBEDDER_CACHE).exists():
    embedder = CognateEmbedder.load(EMBEDDER_CACHE)
    # Load langids separately
    import sqlite3 as _sqlite3
    _conn = _sqlite3.connect(DATABASE)
    _c = _conn.cursor()
    _c.execute("SELECT refid, langid FROM reflexes")
    _rows = _c.fetchall()
    _conn.close()
    langid_map = {r[0]: r[1] for r in _rows}
    langids = [langid_map.get(refid, -1) for refid in embedder.refids]
else:
    embedder, langids = build_embedder_from_db(DATABASE, alpha=0.4)
    embedder.save(EMBEDDER_CACHE)
print(f"Done. Loaded {len(embedder.refids)} reflexes.")


def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
    return db


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()


##############################################################################
# Utility functions for cognate detection
##############################################################################


def find_potential_cognates(langid1: int, form1: str, gloss1: str, alpha: float) -> None:
    """
    Find potential cognates using pre-computed embeddings.
    
    Args:
        langid1: Language ID to exclude from results
        form1: IPA form to match
        gloss1: Gloss to match
        alpha: Weight for phonetic vs semantic (higher = more phonetic)
    """
    # Update embedder alpha if different
    embedder.alpha = alpha
    
    # Find similar items using embeddings (fast!)
    similar = embedder.find_similar(
        query_form=form1,
        query_gloss=gloss1,
        exclude_langid=langid1,
        langids=langids,
    )
    
    # Build refid -> (langid, form, gloss) lookup
    c = get_db().cursor()
    c.execute("SELECT refid, langid, form, gloss FROM reflexes")
    reflex_data = {r[0]: (r[1], r[2], r[3]) for r in c.fetchall()}
    
    # Clear and populate potcogs table
    c.execute("DELETE FROM potcogs")
    results = []
    for refid, dist in similar:
        if refid in reflex_data:
            langid2, form2, gloss2 = reflex_data[refid]
            results.append([refid, langid2, form2, gloss2, dist])
    
    c.executemany(
        "INSERT INTO potcogs (refid, langid, form, gloss, sim) VALUES (?, ?, ?, ?, ?)",
        results,
    )
    get_db().commit()


##############################################################################
# Utility functions for presenting parsed forms
##############################################################################


def parse_form(form):
    return [m.groups() for m in re.finditer("([^ -]+)( |-|)", form)]


def strong_morph(form, i):
    if len(form) > i:
        morph, delim = form[i]
        form[i] = ("<strong>{}</strong>".format(morph), delim)
    return form


def join_form(form):
    return "".join(["".join(m) for m in form])


def strong_form(form, i):
    morphs = parse_form(form)
    if morphs:
        return join_form(strong_morph(morphs, i))
    else:
        return ""


##############################################################################
# The page
##############################################################################


@app.route("/")
def root():
    return render_template("index.jinja2")


##############################################################################
# Data for the four main tables
##############################################################################


@app.route("/reflexes", methods=["GET", "POST"])
def reflexes():
    # All data should have the following shape
    cols = ["reflexes.langid", "refid", "lname", "form", "gloss"]
    # limit parameters
    start = request.args.get("start", 0, type=int)
    length = request.args.get("length", 0, type=int)
    draw = request.args.get("draw", 0, type=int)
    # Search strings for language, form, and gloss
    lang_search = "%{}%".format(
        request.args.get("columns[2][search][value]", "", type=str)
    )
    form_search = "%{}%".format(
        request.args.get("columns[3][search][value]", "", type=str)
    )
    gloss_search = "%{}%".format(
        request.args.get("columns[4][search][value]", "", type=str)
    )
    # Order
    order = cols[request.args.get("order[0][column]", 2, type=int)]
    direction = request.args.get("order[0][dir]", "asc", type=str)
    if direction not in ["asc", "desc"]:
        direction = "asc"
    ordering_term = f"{order} {direction}"
    print(ordering_term)
    # Database interactions
    c = get_db().cursor()
    c.execute("SELECT COUNT(*) FROM reflexes;")
    total = int(c.fetchone()[0])
    c.execute(
        """SELECT COUNT(*)
                 FROM reflexes JOIN langnames on langnames.langid=reflexes.langid
                 WHERE langnames.name LIKE ? AND form LIKE ? AND gloss LIKE ?""",
        (lang_search, form_search, gloss_search),
    )
    filtered_total = int(c.fetchone()[0])
    c.execute(
        (
            """SELECT reflexes.langid,
                         refid,
                         langnames.name AS lname,
                         form,
                         gloss
                  FROM reflexes
                  JOIN langnames ON langnames.langid=reflexes.langid
                  WHERE lname LIKE ? AND form LIKE ? AND gloss LIKE ?
                  ORDER BY %s
                  LIMIT ? OFFSET ?"""
        )
        % ordering_term,
        (lang_search, form_search, gloss_search, length, start),
    )
    reflexes = c.fetchall()
    return jsonify(
        {
            "draw": draw,
            "recordsTotal": total,
            "recordsFiltered": filtered_total,
            "data": reflexes,
        }
    )


@app.route("/potcogs", methods=["GET", "POST"])
def potcogs():
    # All data for potcogs should take this shape:
    cols = ["potcogs.langid", "refid", "lname", "form", "gloss", "sim"]
    # limit parameters
    start = request.args.get("start", 0, type=int)
    length = request.args.get("length", 0, type=int)
    draw = request.args.get("draw", 0, type=int)
    # Search strings for language, form, and gloss
    lang_search = "%{}%".format(
        request.args.get("columns[2][search][value]", "", type=str)
    )
    form_search = "%{}%".format(
        request.args.get("columns[3][search][value]", "", type=str)
    )
    gloss_search = "%{}%".format(
        request.args.get("columns[4][search][value]", "", type=str)
    )
    # Order
    order = cols[request.args.get("order[0][column]", 0, type=int)]
    direction = request.args.get("order[0][dir]", "asc", type=str)
    if direction not in ["asc", "desc"]:
        direction = "asc"
    ordering_term = f"{order} {direction}"
    # Database interactions
    c = get_db().cursor()
    # lnames is missing because that comes from a join with langnames
    c.execute("""CREATE TABLE IF NOT EXISTS "potcogs" (
         "langid" integer NOT NULL,
         "refid" integer NOT NULL PRIMARY KEY,
         "form" text NOT NULL,
         "gloss" text,
         "sim" real NOT NULL)""")
    get_db().commit()
    c.execute("SELECT COUNT(*) FROM potcogs;")
    total = int(c.fetchone()[0])
    c.execute(
        """SELECT COUNT(*)
              FROM potcogs JOIN langnames on langnames.langid=potcogs.langid
              WHERE langnames.name LIKE ? AND form LIKE ? AND gloss LIKE ?""",
        (lang_search, form_search, gloss_search),
    )
    filtered_total = int(c.fetchone()[0])
    c.execute(
        (
            """SELECT DISTINCT
                    potcogs.langid,
                    refid,
                    langnames.name AS lname,
                    form,
                    gloss,
                    sim
              FROM potcogs JOIN langnames ON langnames.langid=potcogs.langid
              WHERE lname LIKE ? AND form LIKE ? AND gloss LIKE ?
              ORDER BY %s
              LIMIT ? OFFSET ?"""
        )
        % "sim ASC",
        (lang_search, form_search, gloss_search, length, start),
    )
    potcogs = c.fetchall()
    return jsonify(
        {
            "draw": draw,
            "recordsTotal": total,
            "recordsFiltered": filtered_total,
            "data": potcogs,
        }
    )


@app.route("/protoforms")
def protoforms():
    cols = ["refid", "lname", "form", "gloss"]
    # limit parameters
    start = request.args.get("start", 0, type=int)
    length = request.args.get("length", 0, type=int)
    draw = request.args.get("draw", 0, type=int)
    # Search strings for language, form, and gloss
    lang_search = "%{}%".format(
        request.args.get("columns[2][search][value]", "", type=str)
    )
    form_search = "%{}%".format(
        request.args.get("columns[3][search][value]", "", type=str)
    )
    gloss_search = "%{}%".format(
        request.args.get("columns[4][search][value]", "", type=str)
    )
    # Order
    order = cols[request.args.get("order[0][column]", 0, type=int)]
    direction = request.args.get("order[0][dir]", "asc", type=str)
    if direction not in ["asc", "desc"]:
        direction = "asc"
    ordering_term = "{} {}".format(order, direction)
    c = get_db().cursor()
    c.execute(
        "SELECT COUNT(*) FROM (SELECT DISTINCT refid FROM reflexes "
        + "INNER JOIN descendant_of ON reflexes.langid=plangid)"
    )
    total = int(c.fetchone()[0])
    c.execute(
        "SELECT COUNT(*) "
        + "FROM (SELECT DISTINCT refid "
        + "FROM reflexes "
        + "INNER JOIN descendant_of ON reflexes.langid=plangid "
        + "JOIN langnames ON langnames.langid=reflexes.langid "
        "WHERE langnames.name LIKE ? AND form LIKE ? AND gloss LIKE ?)",
        (lang_search, form_search, gloss_search),
    )
    filtered_total = int(c.fetchone()[0])
    c.execute(
        (
            "SELECT DISTINCT refid, plangid, langnames.name AS lname, form, gloss "
            + "FROM reflexes "
            + "INNER JOIN descendant_of ON plangid=reflexes.langid "
            + "JOIN langnames ON langnames.langid=reflexes.langid "
            + "WHERE lname LIKE ? AND form like ? AND gloss LIKE ? "
            + "ORDER BY %s "
            + "LIMIT ? OFFSET ?"
        )
        % ordering_term,
        (lang_search, form_search, gloss_search, length, start),
    )
    protoforms = c.fetchall()
    data = {
        "draw": draw,
        "recordsTotal": total,
        "recordsFiltered": filtered_total,
        "data": protoforms,
    }
    return jsonify(data)


@app.route("/supporting")
def supporting():
    start = request.args.get("start", 0, type=int)
    length = request.args.get("length", 0, type=int)
    draw = request.args.get("draw", 0, type=int)
    prefid = request.args.get("prefid", 55760, type=int)
    c = get_db().cursor()
    c.execute("SELECT COUNT(*) FROM reflex_of")
    total = int(c.fetchone()[0])
    c.execute(
        "SELECT COUNT(*) FROM (SELECT DISTINCT reflexes.refid FROM reflexes JOIN reflex_of ON reflex_of.refid=reflexes.refid WHERE prefid=?)",
        (prefid,),
    )
    filtered_total = int(c.fetchone()[0])
    c.execute(
        "SELECT reflexes.refid, langnames.name, form, gloss, morph_index FROM reflexes JOIN reflex_of ON reflex_of.refid=reflexes.refid JOIN langnames on reflexes.langid=langnames.langid WHERE prefid=? LIMIT ? OFFSET ?",
        (prefid, length, start),
    )
    supporting_forms = [
        [r, l, strong_form(f, i), g, i] for (r, l, f, g, i) in c.fetchall()
    ]
    json = jsonify(
        {
            "draw": draw,
            "recordsTotal": total,
            "recordsFiltered": filtered_total,
            "data": supporting_forms,
        }
    )
    print(json)
    return json


##############################################################################
# Add reflexes to master list
##############################################################################


@app.route("/newreflexdialog")
def new_reflex_dialog():
    c = get_db().cursor()
    c.execute("SELECT DISTINCT langid, name " + "FROM langnames " + "ORDER BY name")
    langs = c.fetchall()
    return render_template("new_reflex_dialog.jinja2", langs=langs)


@app.route("/addnewreflex")
def add_new_reflex():
    langid = request.args.get("langid", 0, type=int)
    sourceid = request.args.get("sourceid", 0, type=int)
    form = request.args.get("form", "", type=str)
    gloss = request.args.get("gloss", "", type=str)
    c = get_db().cursor()
    c.execute(
        "INSERT INTO reflexes (langid, sourceid, form, gloss) VALUES (?, ?, ?, ?)",
        (langid, sourceid, form, gloss),
    )
    get_db().commit()
    return jsonify({"success": "Entry successfully added"})


##############################################################################
# Add reflexes to and remove reflexes from cognate sets
##############################################################################


@app.route("/addsupporting")
def add_supporting_form():
    print("/addsupporting")
    refid = request.args.get("refid", 0, type=int)
    prefid = request.args.get("prefid", 0, type=int)
    plangid = request.args.get("plangid", 0, type=int)
    print(f"Add {refid} to {prefid} in {plangid}")
    c = get_db().cursor()
    c.execute(
        "SELECT COUNT(*) FROM reflex_of WHERE prefid=? AND refid=?", (prefid, refid)
    )
    if not c.fetchone()[0]:
        c.execute(
            "INSERT INTO reflex_of (prefid, refid, plangid, morph_index) VALUES (?, ?, ?, ?)",
            (prefid, refid, plangid, 0),
        )
        get_db().commit()
    c.execute(
        "SELECT morph_index FROM reflex_of WHERE refid=? AND prefid=?", (refid, prefid)
    )
    morph_index = c.fetchone()[0]
    c.execute("SELECT form FROM reflexes WHERE refid=?", (refid,))
    form = c.fetchone()[0]
    morphs = enumerate(re.split(" |-", form))
    return render_template(
        "supporting_dialog.jinja2", refid=refid, morphs=morphs, morph_index=morph_index
    )


@app.route("/removesupporting")
def remove_supporting_form():
    print("/removesupporting")
    refid = request.args.get("refid", 0, type=int)
    prefid = request.args.get("prefid", 0, type=int)
    print(f"Remove {refid} from {prefid}")
    c = get_db().cursor()
    c.execute("""DELETE FROM reflex_of WHERE refid=? and prefid=?""", (refid, prefid))
    get_db().commit()
    return jsonify({"success": "Supporting form successfully removed"})


##############################################################################
# Find potential cognates
##############################################################################


@app.route("/findpotcogs")
def find_pot_cogs():
    langid = request.args.get("langid", 0, type=int)
    form = request.args.get("form", "", type=str)
    gloss = request.args.get("gloss", "", type=str)
    alpha = request.args.get("alpha", 0.4, type=float)  # 0=semantic only, 1=phonetic only (optimal: 0.4)
    find_potential_cognates(langid, form, gloss, alpha)
    return jsonify({"success": "Reflexes successfully ranked"})


##############################################################################
# Remove reflexes (supporting forms) from cognate sets
##############################################################################


@app.route("/removesupporting")
def removed_reflex():
    refid = request.args.get("refid", -1, type=int)
    prefid = request.args.get("prefid", -1, type=int)
    c = get_db().cursor()
    c.execute("DELETE FROM reflex_of WHERE refid=? AND prefid=?", (refid, prefid))
    get_db().commit()
    return jsonify({"success": "Removed successfully"})


##############################################################################
# Edit reflexes
##############################################################################


@app.route("/reflexdialog")
def reflex_dialog():
    id = request.args.get("refid", 0, type=int)
    lname = request.args.get("lname", "", type=str)
    form = request.args.get("form", "", type=str)
    gloss = request.args.get("gloss", "", type=str)
    return render_template(
        "edit_dialog.jinja2", id=id, lname=lname, form=form, gloss=gloss
    )


@app.route("/updatereflex")
def update_reflex():
    refid = request.args.get("refid", 0, type=int)
    form = request.args.get("form", "", type=str)
    gloss = request.args.get("gloss", "", type=str)
    c = get_db().cursor()
    c.execute("UPDATE reflexes SET form=?, gloss=? WHERE refid=?", (form, gloss, refid))
    get_db().commit()
    return jsonify({"success": "Updated successfully!"})


##############################################################################
# Delete reflexes
##############################################################################


@app.route("/deletereflex")
def delete_reflex():
    refid = request.args.get("refid", -1, type=int)
    c = get_db().cursor()
    c.execute("DELETE FROM reflexes WHERE refid=?", (refid,))
    c.execute("DELETE FROM reflex_of WHERE refid=?", (refid,))
    get_db().commit()
    return jsonify({"success": "Deleted successfully"})


##############################################################################
# Add correspondence set
##############################################################################


@app.route("/newsetdialog")
def new_set_dialog():
    langname = request.args.get("langname", "", type=str)
    form = request.args.get("form", "", type=str)
    gloss = request.args.get("gloss", "", type=str)
    num_morphs = len(re.split("- ", form))
    c = get_db().cursor()
    c.execute(
        "SELECT DISTINCT langnames.langid, langnames.name "
        + "FROM langnames "
        + "INNER JOIN descendant_of ON plangid=langnames.langid "
        + "ORDER BY langnames.name"
    )
    plangs = c.fetchall()
    return render_template(
        "new_set_dialog.jinja2",
        plangs=plangs,
        langname=langname,
        form=form,
        gloss=gloss,
        num_morphs=num_morphs,
    )


@app.route("/addnewset")
def add_new_set():
    refid = request.args.get("refid", 0, type=int)
    plangid = request.args.get("plangid", 0, type=int)
    protoform = request.args.get("protoform", "", type=str)
    protogloss = request.args.get("protogloss", "", type=str)
    morph_index = request.args.get("morph_index", 0, type=int)
    c = get_db().cursor()
    c.execute(
        "INSERT INTO reflexes (langid, sourceid, form, gloss) VALUES (?, -2, ?, ?)",
        (plangid, protoform, protogloss),
    )
    get_db().commit()
    c.execute("SELECT LAST_INSERT_ROWID()")
    prefid = c.fetchone()[0]
    c.execute(
        "INSERT INTO reflex_of (refid, prefid, plangid, morph_index) VALUES (?, ?, ?, ?)",
        (refid, prefid, plangid, morph_index),
    )
    get_db().commit()
    return jsonify({"success": "Set successfully added"})


##############################################################################
# Edit protoforms
##############################################################################

##############################################################################
# Edits morphs of supporting forms
##############################################################################


@app.route("/updatemorph")
def update_morph():
    refid = request.args.get("refid", 0, type=int)
    prefid = request.args.get("prefid", 0, type=int)
    morph_index = request.args.get("morph_index", 0, type=int)
    print(f"morph_index: {morph_index}")
    c = get_db().cursor()
    c.execute(
        "UPDATE reflex_of SET morph_index=? WHERE refid=? AND prefid=?",
        (morph_index, refid, prefid),
    )
    get_db().commit()
    return jsonify({"success": "Updated successfully"})


##############################################################################
# Delete protoforms
##############################################################################


@app.route("/deleteprotoform")
def delete_protoform():
    prefid = request.args.get("prefid", -1, type=int)
    print(f"Delete prefid={prefid}")
    c = get_db().cursor()
    c.execute("DELETE FROM reflexes WHERE refid=?", (prefid,))
    c.execute("DELETE FROM reflex_of WHERE prefid=?", (prefid,))
    get_db().commit()
    return jsonify({"success": "Deleted successfully"})
