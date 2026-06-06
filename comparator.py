import json
import re
import sqlite3
from pathlib import Path

import numpy as np
from flask import Flask, g, jsonify, render_template, request

from alignment import CognateAligner
from embeddings import CognateEmbedder, build_embedder_from_db
from ipa_normalize import normalize_to_ipa

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


def regexp(pattern, value):
    """SQLite REGEXP function implementation."""
    if value is None:
        return False
    try:
        return bool(re.search(pattern, str(value), re.IGNORECASE))
    except re.error:
        return False


def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        # Register the REGEXP function
        db.create_function("REGEXP", 2, regexp)
    return db


def build_search_condition(column: str, search_value: str, params: list) -> str:
    """Build search condition - uses REGEXP if explicitly regex-like, else LIKE."""
    if not search_value:
        params.append("%")
        return f"{column} LIKE ?"
    
    # Only treat as regex if it has explicit regex anchors or grouping constructs
    # This avoids treating "n." or "v." as regex patterns
    # Regex indicators: ^ at start, $ at end, or explicit grouping/alternation
    is_regex = (
        search_value.startswith('^') or 
        search_value.endswith('$') or
        '|' in search_value or  # alternation
        ('(' in search_value and ')' in search_value) or  # grouping
        ('[' in search_value and ']' in search_value)  # character class
    )
    
    if is_regex:
        params.append(search_value)
        return f"{column} REGEXP ?"
    else:
        params.append(f"%{search_value}%")
        return f"{column} LIKE ?"


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()


##############################################################################
# Utility functions for cognate detection
##############################################################################


def find_potential_cognates(langid1: int, ipaform1: str, gloss1: str, alpha: float) -> None:
    """
    Find potential cognates using pre-computed embeddings.
    
    Args:
        langid1: Language ID to exclude from results
        ipaform1: Normalized IPA form to match (without tones)
        gloss1: Gloss to match
        alpha: Weight for phonetic vs semantic (higher = more phonetic)
    """
    # Update embedder alpha if different
    embedder.alpha = alpha
    
    # Find similar items using embeddings (fast!)
    similar = embedder.find_similar(
        query_form=ipaform1,
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
    # Added is_supporting and ipaform columns
    cols = ["reflexes.langid", "refid", "lname", "form", "gloss", "is_supporting", "ipaform"]
    # limit parameters
    start = request.args.get("start", 0, type=int)
    length = request.args.get("length", 0, type=int)
    draw = request.args.get("draw", 0, type=int)
    # Search strings for language, form, and gloss
    lang_search = request.args.get("columns[2][search][value]", "", type=str)
    form_search = request.args.get("columns[3][search][value]", "", type=str)
    gloss_search = request.args.get("columns[4][search][value]", "", type=str)
    

    # Order
    order = cols[request.args.get("order[0][column]", 2, type=int)]
    direction = request.args.get("order[0][dir]", "asc", type=str)
    if direction not in ["asc", "desc"]:
        direction = "asc"
    ordering_term = f"{order} {direction}"
    
    # Build search conditions with regex support
    params = []
    lang_cond = build_search_condition("langnames.name", lang_search, params)
    form_cond = build_search_condition("form", form_search, params)
    gloss_cond = build_search_condition("gloss", gloss_search, params)
    where_clause = f"WHERE {lang_cond} AND {form_cond} AND {gloss_cond}"
    
    # Database interactions
    c = get_db().cursor()
    c.execute("SELECT COUNT(*) FROM reflexes;")
    total = int(c.fetchone()[0])
    c.execute(
        f"""SELECT COUNT(*)
            FROM reflexes JOIN langnames on langnames.langid=reflexes.langid
            {where_clause}""",
        params,
    )
    filtered_total = int(c.fetchone()[0])
    
    # Build params again for the main query (need lname alias)
    params2 = []
    lang_cond2 = build_search_condition("lname", lang_search, params2)
    form_cond2 = build_search_condition("form", form_search, params2)
    gloss_cond2 = build_search_condition("gloss", gloss_search, params2)
    where_clause2 = f"WHERE {lang_cond2} AND {form_cond2} AND {gloss_cond2}"
    
    c.execute(
        f"""SELECT reflexes.langid,
                   reflexes.refid,
                   langnames.name AS lname,
                   form,
                   gloss,
                   CASE WHEN reflex_of.refid IS NOT NULL THEN 1 ELSE 0 END AS is_supporting,
                   ipaform
            FROM reflexes
            JOIN langnames ON langnames.langid=reflexes.langid
            LEFT JOIN (SELECT DISTINCT refid FROM reflex_of) AS reflex_of ON reflex_of.refid=reflexes.refid
            {where_clause2}
            ORDER BY {ordering_term}
            LIMIT ? OFFSET ?""",
        params2 + [length, start],
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
    lang_search = request.args.get("columns[2][search][value]", "", type=str)
    form_search = request.args.get("columns[3][search][value]", "", type=str)
    gloss_search = request.args.get("columns[4][search][value]", "", type=str)
    # Order
    order = cols[request.args.get("order[0][column]", 0, type=int)]
    direction = request.args.get("order[0][dir]", "asc", type=str)
    if direction not in ["asc", "desc"]:
        direction = "asc"
    ordering_term = f"{order} {direction}"
    
    # Build search conditions with regex support
    params = []
    lang_cond = build_search_condition("langnames.name", lang_search, params)
    form_cond = build_search_condition("form", form_search, params)
    gloss_cond = build_search_condition("gloss", gloss_search, params)
    where_clause = f"WHERE {lang_cond} AND {form_cond} AND {gloss_cond}"
    
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
        f"""SELECT COUNT(*)
            FROM potcogs JOIN langnames on langnames.langid=potcogs.langid
            {where_clause}""",
        params,
    )
    filtered_total = int(c.fetchone()[0])
    
    # Build params again for the main query (need lname alias)
    params2 = []
    lang_cond2 = build_search_condition("lname", lang_search, params2)
    form_cond2 = build_search_condition("form", form_search, params2)
    gloss_cond2 = build_search_condition("gloss", gloss_search, params2)
    where_clause2 = f"WHERE {lang_cond2} AND {form_cond2} AND {gloss_cond2}"
    
    c.execute(
        f"""SELECT DISTINCT
                potcogs.langid,
                refid,
                langnames.name AS lname,
                form,
                gloss,
                sim
            FROM potcogs JOIN langnames ON langnames.langid=potcogs.langid
            {where_clause2}
            ORDER BY sim ASC
            LIMIT ? OFFSET ?""",
        params2 + [length, start],
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
    # Filter by refids (comma-separated list of reflex ids to find their protoforms)
    refids_param = request.args.get("refids", "", type=str)
    # Search strings for language, form, and gloss
    lang_search = request.args.get("columns[2][search][value]", "", type=str)
    form_search = request.args.get("columns[3][search][value]", "", type=str)
    gloss_search = request.args.get("columns[4][search][value]", "", type=str)
    # Order
    order = cols[request.args.get("order[0][column]", 0, type=int)]
    direction = request.args.get("order[0][dir]", "asc", type=str)
    if direction not in ["asc", "desc"]:
        direction = "asc"
    ordering_term = "{} {}".format(order, direction)
    c = get_db().cursor()
    
    # Build search conditions with regex support
    params = []
    lang_cond = build_search_condition("langnames.name", lang_search, params)
    form_cond = build_search_condition("form", form_search, params)
    gloss_cond = build_search_condition("gloss", gloss_search, params)
    
    params2 = []
    lang_cond2 = build_search_condition("lname", lang_search, params2)
    form_cond2 = build_search_condition("form", form_search, params2)
    gloss_cond2 = build_search_condition("gloss", gloss_search, params2)
    
    # If filtering by refids, find protoforms associated with those reflexes
    if refids_param:
        refids = [int(r) for r in refids_param.split(",") if r.strip().isdigit()]
        if not refids:
            return jsonify({"draw": draw, "recordsTotal": 0, "recordsFiltered": 0, "data": []})
        
        placeholders = ",".join("?" * len(refids))
        
        # Get protoforms (prefids) associated with the selected reflexes
        c.execute(
            f"""SELECT COUNT(*) FROM (
                SELECT DISTINCT reflexes.refid
                FROM reflexes
                INNER JOIN descendant_of ON reflexes.langid=plangid
                WHERE reflexes.refid IN (
                    SELECT DISTINCT prefid FROM reflex_of WHERE refid IN ({placeholders})
                )
            )""",
            refids,
        )
        total = int(c.fetchone()[0])
        
        c.execute(
            f"""SELECT COUNT(*) FROM (
                SELECT DISTINCT reflexes.refid
                FROM reflexes
                INNER JOIN descendant_of ON reflexes.langid=plangid
                JOIN langnames ON langnames.langid=reflexes.langid
                WHERE reflexes.refid IN (
                    SELECT DISTINCT prefid FROM reflex_of WHERE refid IN ({placeholders})
                )
                AND {lang_cond} AND {form_cond} AND {gloss_cond}
            )""",
            refids + params,
        )
        filtered_total = int(c.fetchone()[0])
        
        c.execute(
            f"""SELECT DISTINCT reflexes.refid, plangid, langnames.name AS lname, form, gloss
                FROM reflexes
                INNER JOIN descendant_of ON plangid=reflexes.langid
                JOIN langnames ON langnames.langid=reflexes.langid
                WHERE reflexes.refid IN (
                    SELECT DISTINCT prefid FROM reflex_of WHERE refid IN ({placeholders})
                )
                AND {lang_cond2} AND {form_cond2} AND {gloss_cond2}
                ORDER BY {ordering_term}
                LIMIT ? OFFSET ?""",
            refids + params2 + [length, start],
        )
    else:
        # Original behavior: show all protoforms
        c.execute(
            "SELECT COUNT(*) FROM (SELECT DISTINCT refid FROM reflexes "
            "INNER JOIN descendant_of ON reflexes.langid=plangid)"
        )
        total = int(c.fetchone()[0])
        c.execute(
            f"""SELECT COUNT(*)
                FROM (SELECT DISTINCT refid
                      FROM reflexes
                      INNER JOIN descendant_of ON reflexes.langid=plangid
                      JOIN langnames ON langnames.langid=reflexes.langid
                      WHERE {lang_cond} AND {form_cond} AND {gloss_cond})""",
            params,
        )
        filtered_total = int(c.fetchone()[0])
        c.execute(
            f"""SELECT DISTINCT refid, plangid, langnames.name AS lname, form, gloss
                FROM reflexes
                INNER JOIN descendant_of ON plangid=reflexes.langid
                JOIN langnames ON langnames.langid=reflexes.langid
                WHERE {lang_cond2} AND {form_cond2} AND {gloss_cond2}
                ORDER BY {ordering_term}
                LIMIT ? OFFSET ?""",
            params2 + [length, start],
        )
    
    protoforms = c.fetchall()
    data = {
        "draw": draw,
        "recordsTotal": total,
        "recordsFiltered": filtered_total,
        "data": protoforms,
    }
    return jsonify(data)


# Singleton aligner instance
_cognate_aligner = None


def get_aligner() -> CognateAligner:
    """Get or create the singleton CognateAligner."""
    global _cognate_aligner
    if _cognate_aligner is None:
        _cognate_aligner = CognateAligner()
    return _cognate_aligner


@app.route("/alignment")
def alignment():
    """
    Compute phoneme alignment for a cognate set.
    
    Query parameters:
        prefid: ID of the protoform (required)
        
    Returns:
        JSON with alignment data including:
        - prefid: protoform ID
        - proto_lang: name of proto-language (if available)
        - proto_form: reconstructed form (if available)
        - alignment: list of dicts mapping language -> phoneme
        - languages: ordered list of language names
    """
    prefid = request.args.get("prefid", type=int)
    if prefid is None:
        return jsonify({"error": "prefid parameter is required"}), 400
    
    c = get_db().cursor()
    
    # Get protoform info (use ipaform for alignment)
    c.execute(
        """SELECT reflexes.ipaform, langnames.name
           FROM reflexes
           JOIN langnames ON langnames.langid = reflexes.langid
           WHERE reflexes.refid = ?""",
        (prefid,),
    )
    proto_row = c.fetchone()
    
    if proto_row is None:
        return jsonify({"error": f"Protoform with prefid={prefid} not found"}), 404
    
    proto_form, proto_lang = proto_row
    
    # Check if this is actually a protoform (in descendant_of table)
    c.execute(
        """SELECT COUNT(*) FROM descendant_of
           JOIN reflexes ON reflexes.langid = descendant_of.plangid
           WHERE reflexes.refid = ?""",
        (prefid,),
    )
    is_protoform = c.fetchone()[0] > 0
    
    # Get all reflexes (daughter forms) for this cognate set (use ipaform for alignment)
    c.execute(
        """SELECT langnames.name, reflexes.ipaform, reflex_of.morph_index
           FROM reflex_of
           JOIN reflexes ON reflexes.refid = reflex_of.refid
           JOIN langnames ON langnames.langid = reflexes.langid
           WHERE reflex_of.prefid = ?
           ORDER BY langnames.name""",
        (prefid,),
    )
    daughter_forms = [(row[0], row[1] or '', row[2]) for row in c.fetchall()]
    
    if not daughter_forms:
        return jsonify({
            "error": f"No reflexes found for prefid={prefid}",
            "prefid": prefid,
            "proto_lang": proto_lang if is_protoform else None,
            "proto_form": proto_form if is_protoform else None,
        }), 404
    
    # Compute alignment
    aligner = get_aligner()
    
    if is_protoform:
        protoform_tuple = (proto_lang, proto_form)
    else:
        protoform_tuple = None
    
    result = aligner.align_from_data(
        forms=daughter_forms,
        protoform=protoform_tuple,
        prefid=prefid
    )
    
    return jsonify(result.to_dict())


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
    # Compute normalized IPA form
    ipaform = normalize_to_ipa(form)
    c = get_db().cursor()
    c.execute(
        "INSERT INTO reflexes (langid, sourceid, form, gloss, ipaform) VALUES (?, ?, ?, ?, ?)",
        (langid, sourceid, form, gloss, ipaform),
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
    ipaform = request.args.get("ipaform", "", type=str)
    gloss = request.args.get("gloss", "", type=str)
    alpha = request.args.get("alpha", 0.4, type=float)  # 0=semantic only, 1=phonetic only (optimal: 0.4)
    find_potential_cognates(langid, ipaform, gloss, alpha)
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
    # Recompute normalized IPA form when form changes
    ipaform = normalize_to_ipa(form)
    c = get_db().cursor()
    c.execute("UPDATE reflexes SET form=?, gloss=?, ipaform=? WHERE refid=?", (form, gloss, ipaform, refid))
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
    # Compute normalized IPA form for proto-form
    ipaform = normalize_to_ipa(protoform)
    c = get_db().cursor()
    c.execute(
        "INSERT INTO reflexes (langid, sourceid, form, gloss, ipaform) VALUES (?, -2, ?, ?, ?)",
        (plangid, protoform, protogloss, ipaform),
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


##############################################################################
# Correspondence Sets
##############################################################################


@app.route("/protolanguages")
def get_protolanguages():
    """Get list of proto-languages for dropdown."""
    c = get_db().cursor()
    c.execute(
        """SELECT DISTINCT langnames.langid, langnames.name
           FROM langnames
           JOIN descendant_of ON langnames.langid = descendant_of.plangid
           ORDER BY langnames.name"""
    )
    protolanguages = [{"langid": row[0], "name": row[1]} for row in c.fetchall()]
    return jsonify(protolanguages)


@app.route("/correspondence_sets")
def correspondence_sets():
    """
    Get correspondence sets for a proto-language.
    
    Query parameters:
        plangid: Proto-language ID (required)
        
    Returns:
        JSON with correspondence sets data
    """
    from correspondence import extract_correspondence_sets_for_protolang
    
    plangid = request.args.get("plangid", type=int)
    if plangid is None:
        return jsonify({"error": "plangid parameter is required"}), 400
    
    c = get_db().cursor()
    
    # Get proto-language name
    c.execute("SELECT name FROM langnames WHERE langid = ?", (plangid,))
    row = c.fetchone()
    if row is None:
        return jsonify({"error": f"Proto-language with ID {plangid} not found"}), 404
    
    proto_lang_name = row[0]
    
    # Extract correspondence sets
    corr_sets, languages = extract_correspondence_sets_for_protolang(
        c, plangid, proto_lang_name
    )
    
    return jsonify({
        "proto_language": proto_lang_name,
        "plangid": plangid,
        "languages": languages,
        "correspondence_sets": [cs.to_dict(languages) for cs in corr_sets]
    })


@app.route("/correspondence_sets_dialog")
def correspondence_sets_dialog():
    """Render the correspondence sets dialog template."""
    return render_template("correspondence_sets_dialog.jinja2")
