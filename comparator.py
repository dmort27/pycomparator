# Set OpenMP/threading environment variables before importing numpy/sklearn
# This prevents pthread_mutex_init errors on macOS (especially Apple Silicon)
import os
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

import json
import re
import sqlite3
from pathlib import Path

import numpy as np
import panphon.distance
from flask import Flask, g, jsonify, render_template, request

from alignment import CognateAligner
from embeddings import CognateEmbedder, build_embedder_from_db
from ipa_normalize import normalize_to_ipa

# Panphon distance calculator for morph selection
dst = panphon.distance.Distance()

app = Flask(__name__)

DATABASE = "db/borderlands.sqlite3"
EMBEDDER_CACHE = "db/embedder_cache.pkl"

# Load or build the embedder
print("Loading cognate embedder...")
import sqlite3 as _sqlite3
_conn = _sqlite3.connect(DATABASE)
_c = _conn.cursor()

_cache_loaded = False
if Path(EMBEDDER_CACHE).exists():
    try:
        embedder = CognateEmbedder.load(EMBEDDER_CACHE)
        # Load langids separately
        _c.execute("SELECT refid, langid FROM reflexes")
        _rows = _c.fetchall()
        langid_map = {r[0]: r[1] for r in _rows}
        langids = [langid_map.get(refid, -1) for refid in embedder.refids]
        _cache_loaded = True
    except RuntimeError as e:
        print(f"Warning: {e}")
        print("Rebuilding embedder cache...")
        Path(EMBEDDER_CACHE).unlink()

if not _cache_loaded:
    embedder, langids = build_embedder_from_db(DATABASE, alpha=0.4)
    embedder.save(EMBEDDER_CACHE)

# Pre-load lookup data for potential cognates (cached at startup for fast queries)
_c.execute("SELECT refid, langid, ipaform, gloss FROM reflexes")
reflex_lookup = {r[0]: (r[1], r[2], r[3]) for r in _c.fetchall()}
_c.execute("SELECT DISTINCT plangid FROM descendant_of")
proto_langids = {r[0] for r in _c.fetchall()}

# Build lang_to_protos: mapping from langid -> set of proto-language ancestors
# This uses descendant_of relationships for actual linguistic groupings
_c.execute("SELECT langid, plangid FROM descendant_of")
lang_to_protos = {}
for langid, plangid in _c.fetchall():
    if langid not in lang_to_protos:
        lang_to_protos[langid] = set()
    lang_to_protos[langid].add(plangid)

_conn.close()

print(f"Done. Loaded {len(embedder.refids)} reflexes.")


def regenerate_embeddings():
    """
    Regenerate all embeddings from the database.
    Call this after bulk data changes.
    """
    global embedder, langids, reflex_lookup
    print("Regenerating embeddings from database...")
    embedder, langids = build_embedder_from_db(DATABASE, alpha=0.4)
    embedder.save(EMBEDDER_CACHE)
    
    # Reload reflex_lookup
    import sqlite3 as _sqlite3
    _conn = _sqlite3.connect(DATABASE)
    _c = _conn.cursor()
    _c.execute("SELECT refid, langid, ipaform, gloss FROM reflexes")
    reflex_lookup = {r[0]: (r[1], r[2], r[3]) for r in _c.fetchall()}
    _conn.close()
    
    print(f"Done. Regenerated embeddings for {len(embedder.refids)} reflexes.")


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


def find_potential_cognates(langid1: int, ipaform1: str, gloss1: str, alpha: float, subgroup_penalty: float = 1.0) -> None:
    """
    Find potential cognates using pre-computed embeddings.
    
    Args:
        langid1: Language ID to exclude from results
        ipaform1: Normalized IPA form to match (without tones)
        gloss1: Gloss to match
        alpha: Weight for phonetic vs semantic (higher = more phonetic)
        subgroup_penalty: Additive penalty for languages not sharing a proto-language ancestor
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
    
    # Get proto-language ancestors for source language (e.g., Proto-Tangkhulic for Kachai)
    source_protos = lang_to_protos.get(langid1, set())
    
    # Build results using cached lookups
    results = []
    for refid, dist in similar:
        if refid in reflex_lookup:
            langid2, ipaform2, gloss2 = reflex_lookup[refid]
            # Apply subgroup penalty: ADD penalty to languages that don't share
            # any proto-language ancestor with the source language
            # This ensures languages from the same family (e.g., Tangkhulic) rank first
            target_protos = lang_to_protos.get(langid2, set())
            shares_proto = bool(source_protos & target_protos)  # set intersection
            if not source_protos or not shares_proto:
                dist = dist + subgroup_penalty
            results.append((refid, langid2, ipaform2, gloss2, dist))
    
    # Re-sort by distance after applying penalty
    results.sort(key=lambda x: x[4])
    
    # Ensure potcogs table exists and clear it
    c = get_db().cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS "potcogs" (
         "langid" integer NOT NULL,
         "refid" integer NOT NULL PRIMARY KEY,
         "ipaform" text NOT NULL,
         "gloss" text,
         "sim" real NOT NULL)""")
    c.execute("DELETE FROM potcogs")
    c.executemany(
        "INSERT INTO potcogs (refid, langid, ipaform, gloss, sim) VALUES (?, ?, ?, ?, ?)",
        results,
    )
    get_db().commit()


def find_potential_reconstructions(ipaform1: str, gloss1: str, alpha: float) -> None:
    """
    Find potential reconstructions (protoforms) using pre-computed embeddings.
    
    Args:
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
        exclude_langid=None,  # Don't exclude any language
        langids=langids,
    )
    
    # Build results using cached lookups (proto_langids cached at startup)
    results = []
    for refid, dist in similar:
        if refid in reflex_lookup:
            langid2, ipaform2, gloss2 = reflex_lookup[refid]
            # Only include protoforms (reflexes whose language is a proto-language)
            if langid2 in proto_langids:
                results.append((refid, langid2, ipaform2, gloss2, dist))
    
    # Ensure potrecons table exists and clear it
    c = get_db().cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS "potrecons" (
         "langid" integer NOT NULL,
         "refid" integer NOT NULL PRIMARY KEY,
         "ipaform" text NOT NULL,
         "gloss" text,
         "sim" real NOT NULL)""")
    c.execute("DELETE FROM potrecons")
    c.executemany(
        "INSERT INTO potrecons (refid, langid, ipaform, gloss, sim) VALUES (?, ?, ?, ?, ?)",
        results,
    )
    get_db().commit()


def find_potential_reflexes(ipaform1: str, gloss1: str, alpha: float, plangid: int = None, subgroup_penalty: float = 1.0) -> None:
    """
    Find potential reflexes for a protoform using pre-computed embeddings.
    
    This finds regular reflexes (non-proto-language items) that might be
    descendants of a given protoform. Results are stored in the potcogs table.
    
    Args:
        ipaform1: Normalized IPA form of the protoform
        gloss1: Gloss of the protoform
        alpha: Weight for phonetic vs semantic (higher = more phonetic)
        plangid: Proto-language ID (used to boost descendants of this proto-language)
        subgroup_penalty: Additive penalty for non-descendant languages (1.0 = add 1.0 to distance)
    """
    # Update embedder alpha if different
    embedder.alpha = alpha
    
    # Find similar items using embeddings (fast!)
    similar = embedder.find_similar(
        query_form=ipaform1,
        query_gloss=gloss1,
        exclude_langid=None,  # Don't exclude any language
        langids=langids,
    )
    
    # Get descendant languages for the given proto-language (for subgroup penalty)
    # This is the only dynamic query needed
    descendant_langids = set()
    if plangid:
        c = get_db().cursor()
        c.execute("SELECT langid FROM descendant_of WHERE plangid = ?", (plangid,))
        descendant_langids = {r[0] for r in c.fetchall()}
    
    # Build results using cached lookups (reflex_lookup, proto_langids cached at startup)
    results = []
    for refid, dist in similar:
        if refid in reflex_lookup:
            langid2, ipaform2, gloss2 = reflex_lookup[refid]
            # Only include non-protoforms (regular reflexes, not proto-languages)
            if langid2 not in proto_langids:
                # Apply subgroup penalty: ADD penalty to non-descendant languages
                # This ensures descendant items always rank before non-descendant items
                if langid2 not in descendant_langids:
                    dist = dist + subgroup_penalty
                results.append((refid, langid2, ipaform2, gloss2, dist))
    
    # Re-sort by distance after applying penalty
    results.sort(key=lambda x: x[4])
    
    # Ensure potcogs table exists and clear it
    c = get_db().cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS "potcogs" (
         "langid" integer NOT NULL,
         "refid" integer NOT NULL PRIMARY KEY,
         "ipaform" text NOT NULL,
         "gloss" text,
         "sim" real NOT NULL)""")
    c.execute("DELETE FROM potcogs")
    c.executemany(
        "INSERT INTO potcogs (refid, langid, ipaform, gloss, sim) VALUES (?, ?, ?, ?, ?)",
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
    # Client table columns: [checkbox, langid, refid, lname, ipaform, gloss, is_supporting, form]
    # Map client column index to server column name (checkbox is col 0, not sortable)
    cols = [None, "reflexes.langid", "refid", "lname", "ipaform", "gloss", "is_supporting", "form"]
    # limit parameters
    start = request.args.get("start", 0, type=int)
    length = request.args.get("length", 0, type=int)
    draw = request.args.get("draw", 0, type=int)
    # Search strings for language, form, and gloss (columns 3, 4, 5 in client table)
    lang_search = request.args.get("columns[3][search][value]", "", type=str)
    form_search = request.args.get("columns[4][search][value]", "", type=str)
    gloss_search = request.args.get("columns[5][search][value]", "", type=str)
    

    # Order - default to lname (column 3) if invalid
    order_col = request.args.get("order[0][column]", 3, type=int)
    order = cols[order_col] if order_col < len(cols) and cols[order_col] else "lname"
    direction = request.args.get("order[0][dir]", "asc", type=str)
    if direction not in ["asc", "desc"]:
        direction = "asc"
    ordering_term = f"{order} {direction}"
    
    # Build search conditions with regex support
    # Search the ipaform column when filtering by "Form"
    params = []
    lang_cond = build_search_condition("langnames.name", lang_search, params)
    form_cond = build_search_condition("ipaform", form_search, params)
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
    form_cond2 = build_search_condition("ipaform", form_search, params2)
    gloss_cond2 = build_search_condition("gloss", gloss_search, params2)
    where_clause2 = f"WHERE {lang_cond2} AND {form_cond2} AND {gloss_cond2}"
    
    c.execute(
        f"""SELECT reflexes.langid,
                   reflexes.refid,
                   langnames.name AS lname,
                   ipaform,
                   gloss,
                   CASE WHEN reflex_of.refid IS NOT NULL THEN 1 ELSE 0 END AS is_supporting,
                   form
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
    # Client table columns: [checkbox, langid, refid, lname, ipaform, gloss, sim]
    # Map client column index to server column name (checkbox is col 0, not sortable)
    cols = [None, "potcogs.langid", "refid", "lname", "ipaform", "gloss", "sim"]
    # limit parameters
    start = request.args.get("start", 0, type=int)
    length = request.args.get("length", 0, type=int)
    draw = request.args.get("draw", 0, type=int)
    # Search strings for language, form, and gloss (columns 3, 4, 5 in client table)
    lang_search = request.args.get("columns[3][search][value]", "", type=str)
    form_search = request.args.get("columns[4][search][value]", "", type=str)
    gloss_search = request.args.get("columns[5][search][value]", "", type=str)
    # Order - default to sim (column 6) if invalid
    order_col = request.args.get("order[0][column]", 6, type=int)
    order = cols[order_col] if order_col < len(cols) and cols[order_col] else "sim"
    direction = request.args.get("order[0][dir]", "asc", type=str)
    if direction not in ["asc", "desc"]:
        direction = "asc"
    ordering_term = f"{order} {direction}"
    
    # Build search conditions with regex support
    params = []
    lang_cond = build_search_condition("langnames.name", lang_search, params)
    form_cond = build_search_condition("ipaform", form_search, params)
    gloss_cond = build_search_condition("gloss", gloss_search, params)
    where_clause = f"WHERE {lang_cond} AND {form_cond} AND {gloss_cond}"
    
    # Database interactions
    c = get_db().cursor()
    # lnames is missing because that comes from a join with langnames
    c.execute("""CREATE TABLE IF NOT EXISTS "potcogs" (
         "langid" integer NOT NULL,
         "refid" integer NOT NULL PRIMARY KEY,
         "ipaform" text NOT NULL,
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
    form_cond2 = build_search_condition("ipaform", form_search, params2)
    gloss_cond2 = build_search_condition("gloss", gloss_search, params2)
    where_clause2 = f"WHERE {lang_cond2} AND {form_cond2} AND {gloss_cond2}"
    
    c.execute(
        f"""SELECT DISTINCT
                potcogs.langid,
                refid,
                langnames.name AS lname,
                ipaform,
                gloss,
                sim
            FROM potcogs JOIN langnames ON langnames.langid=potcogs.langid
            {where_clause2}
            ORDER BY {ordering_term}
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
    # Columns: ID (refid), PLID (plangid), Proto-Language (lname), Form (ipaform), Gloss
    # When potrecons=true, add sim column at end
    cols = ["refid", "plangid", "lname", "ipaform", "gloss"]
    # limit parameters
    start = request.args.get("start", 0, type=int)
    length = request.args.get("length", 0, type=int)
    draw = request.args.get("draw", 0, type=int)
    # Filter by refids (comma-separated list of reflex ids to find their protoforms)
    refids_param = request.args.get("refids", "", type=str)
    # Filter by prefids (comma-separated list of protoform ids to show directly)
    prefids_param = request.args.get("prefids", "", type=str)
    # Filter by potential reconstructions (from potrecons table)
    potrecons = request.args.get("potrecons", "false", type=str).lower() == "true"
    # Search strings for language, form, and gloss
    lang_search = request.args.get("columns[2][search][value]", "", type=str)
    form_search = request.args.get("columns[3][search][value]", "", type=str)
    gloss_search = request.args.get("columns[4][search][value]", "", type=str)
    # Order
    order_col = request.args.get("order[0][column]", 0, type=int)
    direction = request.args.get("order[0][dir]", "asc", type=str)
    if direction not in ["asc", "desc"]:
        direction = "asc"
    
    c = get_db().cursor()
    
    # Build search conditions with regex support
    # Search the ipaform column when filtering by "Form"
    params = []
    lang_cond = build_search_condition("langnames.name", lang_search, params)
    form_cond = build_search_condition("ipaform", form_search, params)
    gloss_cond = build_search_condition("gloss", gloss_search, params)
    
    params2 = []
    lang_cond2 = build_search_condition("lname", lang_search, params2)
    form_cond2 = build_search_condition("ipaform", form_search, params2)
    gloss_cond2 = build_search_condition("gloss", gloss_search, params2)
    
    # If showing potential reconstructions from potrecons table
    if potrecons:
        # Ensure potrecons table exists
        c.execute("""CREATE TABLE IF NOT EXISTS "potrecons" (
             "langid" integer NOT NULL,
             "refid" integer NOT NULL PRIMARY KEY,
             "ipaform" text NOT NULL,
             "gloss" text,
             "sim" real NOT NULL)""")
        
        # For potrecons, default order by sim (similarity score)
        if order_col == 0:
            ordering_term = "sim asc"  # Lower is better
        else:
            order = cols[order_col] if order_col < len(cols) else "sim"
            ordering_term = f"{order} {direction}"
        
        c.execute("SELECT COUNT(*) FROM potrecons")
        total = int(c.fetchone()[0])
        
        c.execute(
            f"""SELECT COUNT(*) FROM potrecons
                JOIN langnames ON langnames.langid=potrecons.langid
                WHERE {lang_cond} AND {form_cond} AND {gloss_cond}""",
            params,
        )
        filtered_total = int(c.fetchone()[0])
        
        c.execute(
            f"""SELECT potrecons.refid, potrecons.langid, langnames.name AS lname, 
                       potrecons.ipaform, potrecons.gloss, potrecons.sim
                FROM potrecons
                JOIN langnames ON langnames.langid=potrecons.langid
                WHERE {lang_cond2} AND {form_cond2} AND {gloss_cond2}
                ORDER BY {ordering_term}
                LIMIT ? OFFSET ?""",
            params2 + [length, start],
        )
    # If filtering by prefids, show those protoforms directly
    elif prefids_param:
        order = cols[order_col] if order_col < len(cols) else cols[0]
        ordering_term = f"{order} {direction}"
        
        prefids = [int(r) for r in prefids_param.split(",") if r.strip().isdigit()]
        if not prefids:
            return jsonify({"draw": draw, "recordsTotal": 0, "recordsFiltered": 0, "data": []})
        
        placeholders = ",".join("?" * len(prefids))
        
        c.execute(
            f"""SELECT COUNT(*) FROM (
                SELECT DISTINCT reflexes.refid FROM reflexes
                INNER JOIN descendant_of ON reflexes.langid=plangid
                WHERE reflexes.refid IN ({placeholders})
            )""",
            prefids,
        )
        total = int(c.fetchone()[0])
        
        c.execute(
            f"""SELECT COUNT(*) FROM (
                SELECT DISTINCT reflexes.refid FROM reflexes
                INNER JOIN descendant_of ON reflexes.langid=plangid
                JOIN langnames ON langnames.langid=reflexes.langid
                WHERE reflexes.refid IN ({placeholders})
                AND {lang_cond} AND {form_cond} AND {gloss_cond}
            )""",
            prefids + params,
        )
        filtered_total = int(c.fetchone()[0])
        
        c.execute(
            f"""SELECT DISTINCT reflexes.refid, plangid, langnames.name AS lname, ipaform, gloss
                FROM reflexes
                INNER JOIN descendant_of ON plangid=reflexes.langid
                JOIN langnames ON langnames.langid=reflexes.langid
                WHERE reflexes.refid IN ({placeholders})
                AND {lang_cond2} AND {form_cond2} AND {gloss_cond2}
                ORDER BY {ordering_term}
                LIMIT ? OFFSET ?""",
            prefids + params2 + [length, start],
        )
    # If filtering by refids, find protoforms associated with those reflexes
    elif refids_param:
        order = cols[order_col] if order_col < len(cols) else cols[0]
        ordering_term = f"{order} {direction}"
        
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
            f"""SELECT DISTINCT reflexes.refid, plangid, langnames.name AS lname, ipaform, gloss
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
        order = cols[order_col] if order_col < len(cols) else cols[0]
        ordering_term = f"{order} {direction}"
        
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
            f"""SELECT DISTINCT refid, plangid, langnames.name AS lname, ipaform, gloss
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
        "SELECT reflexes.refid, langnames.name, ipaform, gloss, morph_index FROM reflexes JOIN reflex_of ON reflex_of.refid=reflexes.refid JOIN langnames on reflexes.langid=langnames.langid WHERE prefid=? LIMIT ? OFFSET ?",
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
    global langids, reflex_lookup
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
    # Get the new refid
    c.execute("SELECT last_insert_rowid()")
    refid = c.fetchone()[0]
    # Update embeddings for the new reflex
    embedder.update_embedding(refid, ipaform or "", gloss or "")
    langids.append(langid)
    reflex_lookup[refid] = (langid, ipaform, gloss)
    return jsonify({"success": "Entry successfully added"})


##############################################################################
# Add reflexes to and remove reflexes from cognate sets
##############################################################################


def compute_best_morph_index(form: str, protoform: str) -> int:
    """
    Compute the best morph index by finding the morph with lowest
    phonological feature error rate compared to the protoform.
    
    Args:
        form: The reflex form (space or hyphen delimited morphs)
        protoform: The reconstructed protoform to compare against
        
    Returns:
        Index of the morph with lowest feature error rate
    """
    if not form or not protoform:
        return 0
    
    morphs = re.split(" |-", form)
    if len(morphs) <= 1:
        return 0
    
    best_index = 0
    best_error = float('inf')
    
    for i, morph in enumerate(morphs):
        if not morph:
            continue
        try:
            error = dst.feature_error_rate(morph, protoform)
            if error < best_error:
                best_error = error
                best_index = i
        except Exception:
            # If panphon fails on this morph, skip it
            pass
    
    return best_index


@app.route("/addsupporting")
def add_supporting_form():
    print("/addsupporting")
    refid = request.args.get("refid", 0, type=int)
    prefid = request.args.get("prefid", 0, type=int)
    plangid = request.args.get("plangid", 0, type=int)
    print(f"Add {refid} to {prefid} in {plangid}")
    c = get_db().cursor()
    
    # Get the protoform for comparison
    c.execute("SELECT ipaform FROM reflexes WHERE refid=?", (prefid,))
    proto_row = c.fetchone()
    protoform = proto_row[0] if proto_row else ""
    
    # Get the reflex form
    c.execute("SELECT ipaform FROM reflexes WHERE refid=?", (refid,))
    form_row = c.fetchone()
    form = form_row[0] if form_row else ""
    
    # Check if this reflex is already in the set
    c.execute(
        "SELECT COUNT(*) FROM reflex_of WHERE prefid=? AND refid=?", (prefid, refid)
    )
    is_new = not c.fetchone()[0]
    
    if is_new:
        # Compute best morph index based on feature error rate
        best_morph_index = compute_best_morph_index(form, protoform)
        c.execute(
            "INSERT INTO reflex_of (prefid, refid, plangid, morph_index) VALUES (?, ?, ?, ?)",
            (prefid, refid, plangid, best_morph_index),
        )
        get_db().commit()
    
    # Get current morph index
    c.execute(
        "SELECT morph_index FROM reflex_of WHERE refid=? AND prefid=?", (refid, prefid)
    )
    morph_index = c.fetchone()[0]
    
    morphs = list(enumerate(re.split(" |-", form)))
    return render_template(
        "supporting_dialog.jinja2", 
        refid=refid, 
        prefid=prefid,
        morphs=morphs, 
        morph_index=morph_index,
        form=form,
        protoform=protoform
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
# Find potential reconstructions (protoforms)
##############################################################################


@app.route("/findpotrecons")
def find_pot_recons():
    ipaform = request.args.get("ipaform", "", type=str)
    gloss = request.args.get("gloss", "", type=str)
    alpha = request.args.get("alpha", 0.4, type=float)  # 0=semantic only, 1=phonetic only (optimal: 0.4)
    find_potential_reconstructions(ipaform, gloss, alpha)
    return jsonify({"success": "Reconstructions successfully ranked"})





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
    global reflex_lookup
    refid = request.args.get("refid", 0, type=int)
    form = request.args.get("form", "", type=str)
    gloss = request.args.get("gloss", "", type=str)
    # Recompute normalized IPA form when form changes
    ipaform = normalize_to_ipa(form)
    c = get_db().cursor()
    c.execute("UPDATE reflexes SET form=?, gloss=?, ipaform=? WHERE refid=?", (form, gloss, ipaform, refid))
    get_db().commit()
    # Update embedding for the modified reflex
    embedder.update_embedding(refid, ipaform or "", gloss or "")
    # Update lookup cache
    if refid in reflex_lookup:
        langid = reflex_lookup[refid][0]
        reflex_lookup[refid] = (langid, ipaform, gloss)
    return jsonify({"success": "Updated successfully!"})


@app.route("/updateipaform")
def update_ipaform():
    """Update just the ipaform field for a reflex (from the Select Morph dialog)."""
    global reflex_lookup
    refid = request.args.get("refid", 0, type=int)
    ipaform = request.args.get("ipaform", "", type=str)
    c = get_db().cursor()
    c.execute("UPDATE reflexes SET ipaform=? WHERE refid=?", (ipaform, refid))
    get_db().commit()
    # Update embedding (need to get the gloss)
    if refid in reflex_lookup:
        langid, _, gloss = reflex_lookup[refid]
        embedder.update_embedding(refid, ipaform or "", gloss or "")
        reflex_lookup[refid] = (langid, ipaform, gloss)
    # Return the new morphs list for updating the dialog
    morphs = re.split(" |-", ipaform)
    return jsonify({"success": "Updated successfully!", "morphs": morphs})


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


@app.route("/newetymondialog")
def new_etymon_dialog():
    """Return the dialog HTML for creating a new etymon."""
    c = get_db().cursor()
    c.execute(
        "SELECT DISTINCT langnames.langid, langnames.name "
        + "FROM langnames "
        + "INNER JOIN descendant_of ON plangid=langnames.langid "
        + "ORDER BY langnames.name"
    )
    plangs = c.fetchall()
    return render_template("new_set_dialog.jinja2", plangs=plangs)


@app.route("/addnewetymon")
def add_new_etymon():
    """Add a new etymon (protoform) without linking to any reflex."""
    global langids
    plangid = request.args.get("plangid", 0, type=int)
    protoform = request.args.get("protoform", "", type=str)
    protogloss = request.args.get("protogloss", "", type=str)
    
    # Validate inputs
    if not protoform.strip():
        return jsonify({"error": "Proto-form cannot be empty"}), 400
    if not protogloss.strip():
        return jsonify({"error": "Proto-gloss cannot be empty"}), 400
    if plangid <= 0:
        return jsonify({"error": "Invalid proto-language ID"}), 400
    
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
    # Also add to potrecons table so it appears in potrecons mode
    c.execute(
        "INSERT OR REPLACE INTO potrecons (langid, refid, ipaform, gloss, sim) VALUES (?, ?, ?, ?, ?)",
        (plangid, prefid, ipaform, protogloss, 0.0),
    )
    get_db().commit()
    print(f"Added new etymon: prefid={prefid}, plangid={plangid}, form={protoform}, gloss={protogloss}, ipaform={ipaform}")
    # Update embeddings for the new etymon
    embedder.update_embedding(prefid, ipaform, protogloss)
    # Update langids list
    langids.append(plangid)
    return jsonify({"success": "Etymon successfully added", "prefid": prefid, "ipaform": ipaform})


@app.route("/findpotreflexes")
def find_pot_reflexes():
    """Find potential reflexes for a protoform/reconstruction."""
    ipaform = request.args.get("ipaform", "", type=str)
    gloss = request.args.get("gloss", "", type=str)
    plangid = request.args.get("plangid", 0, type=int)
    alpha = request.args.get("alpha", 0.4, type=float)
    find_potential_reflexes(ipaform, gloss, alpha, plangid=plangid if plangid else None)
    return jsonify({"success": "Potential reflexes computed"})


# Legacy endpoints kept for backward compatibility
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
    # Also add to potrecons table so it appears in potrecons mode
    c.execute(
        "INSERT OR REPLACE INTO potrecons (langid, refid, ipaform, gloss, sim) VALUES (?, ?, ?, ?, ?)",
        (plangid, prefid, ipaform, protogloss, 0.0),
    )
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


##############################################################################
# Minimal Generalization Analysis
##############################################################################


@app.route("/minimal_generalization")
def minimal_generalization():
    """
    Analyze correspondence sets to find minimal distinguishing generalizations.

    For each correspondence set reflecting a single proto phoneme, finds the
    minimal generalization that distinguishes that set from the others based
    on preceding and following context in the protoform.

    Query parameters:
        plangid: Proto-language ID (required)
        phoneme: Proto phoneme to analyze (required)

    Returns:
        JSON with analysis results including pairwise generalizations
    """
    from correspondence import extract_correspondence_sets_for_protolang
    from minimal_generalization import analyze_correspondence_sets

    plangid = request.args.get("plangid", type=int)
    phoneme = request.args.get("phoneme", type=str)

    if plangid is None:
        return jsonify({"error": "plangid parameter is required"}), 400
    if phoneme is None:
        return jsonify({"error": "phoneme parameter is required"}), 400

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

    # Analyze the specified phoneme
    analysis = analyze_correspondence_sets(corr_sets, proto_lang_name, phoneme)

    return jsonify({
        "proto_language": proto_lang_name,
        "plangid": plangid,
        "phoneme": phoneme,
        "analysis": analysis
    })


@app.route("/proto_phonemes")
def proto_phonemes():
    """
    Get list of proto phonemes that have multiple correspondence sets.

    These are the phonemes where minimal generalization analysis is useful.

    Query parameters:
        plangid: Proto-language ID (required)

    Returns:
        JSON with list of proto phonemes and their correspondence set counts
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

    # Count correspondence sets per proto phoneme
    phoneme_counts = {}
    for cs in corr_sets:
        pp = cs.pattern.phonemes.get(proto_lang_name, '')
        if pp:
            phoneme_counts[pp] = phoneme_counts.get(pp, 0) + 1

    # Return phonemes with 2+ correspondence sets, sorted by count
    result = [
        {"phoneme": pp, "count": count}
        for pp, count in sorted(phoneme_counts.items(), key=lambda x: -x[1])
        if count >= 2
    ]

    return jsonify({
        "proto_language": proto_lang_name,
        "plangid": plangid,
        "phonemes": result
    })


@app.route("/cognates_by_phoneme")
def cognates_by_phoneme():
    """
    Get all cognate sets where a specific language has a specific phoneme.
    
    Args (via query params):
        plangid: Proto-language ID
        language: Language name to filter by
        phoneme: Phoneme to search for
        
    Returns:
        JSON with matching cognate sets and their alignments
    """
    from correspondence import extract_correspondence_sets_for_protolang
    
    plangid = request.args.get("plangid", 0, type=int)
    language = request.args.get("language", "", type=str)
    phoneme = request.args.get("phoneme", "", type=str)
    
    if not plangid or not language or not phoneme:
        return jsonify({"error": "Missing required parameters"}), 400
    
    c = get_db().cursor()
    
    # Get proto-language name
    c.execute("SELECT name FROM langnames WHERE langid = ?", (plangid,))
    row = c.fetchone()
    if not row:
        return jsonify({"error": "Proto-language not found"}), 404
    proto_lang_name = row[0]
    
    # Extract all correspondence sets
    corr_sets, languages = extract_correspondence_sets_for_protolang(
        c, plangid, proto_lang_name
    )
    
    # Find cognate sets where the specified language has the specified phoneme
    matching_cognate_sets = []
    
    for corr_set in corr_sets:
        for cog_set in corr_set.cognate_sets:
            # Check if this cognate set has the phoneme for the language
            if cog_set.alignment and cog_set.column_index < len(cog_set.alignment):
                col = cog_set.alignment[cog_set.column_index]
                if col.get(language, '') == phoneme:
                    matching_cognate_sets.append(cog_set.to_dict())
    
    # Remove duplicates (same prefid)
    seen_prefids = set()
    unique_cognate_sets = []
    for cs in matching_cognate_sets:
        if cs['prefid'] not in seen_prefids:
            seen_prefids.add(cs['prefid'])
            unique_cognate_sets.append(cs)
    
    return jsonify({
        "language": language,
        "phoneme": phoneme,
        "proto_language": proto_lang_name,
        "languages": languages,
        "cognate_sets": unique_cognate_sets
    })


##############################################################################
# Data Upload
##############################################################################


@app.route("/upload_dialog")
def upload_dialog():
    """Render the upload data dialog with available proto-languages."""
    c = get_db().cursor()
    c.execute(
        """SELECT DISTINCT langnames.langid, langnames.name
           FROM langnames
           JOIN descendant_of ON langnames.langid = descendant_of.plangid
           ORDER BY langnames.name"""
    )
    protolanguages = [{"langid": row[0], "name": row[1]} for row in c.fetchall()]
    return render_template("upload_data_dialog.jinja2", protolanguages=protolanguages)


@app.route("/preview_upload", methods=["POST"])
def preview_upload():
    """
    Preview the data to be uploaded.
    
    Parses the uploaded file and returns processed forms for preview.
    """
    from form_processor import detect_delimiter, parse_lexicon_file, process_form
    
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400
    
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400
    
    try:
        content = file.read().decode("utf-8")
    except UnicodeDecodeError:
        try:
            file.seek(0)
            content = file.read().decode("latin-1")
        except Exception as e:
            return jsonify({"error": f"Could not decode file: {e}"}), 400
    
    delimiter = detect_delimiter(content)
    entries = parse_lexicon_file(content, delimiter)
    
    if not entries:
        return jsonify({"error": "No valid entries found in file"}), 400
    
    # Process and preview first 10 entries
    preview = []
    for gloss, form in entries[:10]:
        processed, original = process_form(form)
        preview.append({
            "gloss": gloss,
            "original": original,
            "processed": processed
        })
    
    return jsonify({
        "preview": preview,
        "total_entries": len(entries),
        "delimiter": "tab" if delimiter == "\t" else "comma"
    })


@app.route("/upload_data", methods=["POST"])
def upload_data():
    """
    Upload language data to the database.
    
    Creates a new language entry and adds all lexical entries.
    """
    from form_processor import detect_delimiter, parse_lexicon_file, process_form
    
    langname = request.form.get("langname", "").strip()
    protolang_ids = request.form.getlist("protolang")
    
    if not langname:
        return jsonify({"error": "Language name is required"}), 400
    
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400
    
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400
    
    try:
        content = file.read().decode("utf-8")
    except UnicodeDecodeError:
        try:
            file.seek(0)
            content = file.read().decode("latin-1")
        except Exception as e:
            return jsonify({"error": f"Could not decode file: {e}"}), 400
    
    delimiter = detect_delimiter(content)
    entries = parse_lexicon_file(content, delimiter)
    
    if not entries:
        return jsonify({"error": "No valid entries found in file"}), 400
    
    conn = get_db()
    c = conn.cursor()
    
    try:
        # Check if language already exists
        c.execute("SELECT langid FROM langnames WHERE name = ?", (langname,))
        existing = c.fetchone()
        
        if existing:
            langid = existing[0]
        else:
            # Add new language
            c.execute("INSERT INTO langnames (name) VALUES (?)", (langname,))
            langid = c.lastrowid
        
        # Add descendant_of relationships
        for plangid in protolang_ids:
            try:
                plangid = int(plangid)
                # Check if relationship already exists
                c.execute(
                    "SELECT id FROM descendant_of WHERE langid = ? AND plangid = ?",
                    (langid, plangid)
                )
                if not c.fetchone():
                    c.execute(
                        "INSERT INTO descendant_of (langid, plangid) VALUES (?, ?)",
                        (langid, plangid)
                    )
            except ValueError:
                continue
        
        # Add lexical entries
        added_count = 0
        for gloss, form in entries:
            processed_form, original_form = process_form(form)
            
            # Insert into reflexes table
            # ipaform stores the processed form, form stores the original
            c.execute(
                """INSERT INTO reflexes (langid, sourceid, form, gloss, ipaform)
                   VALUES (?, -1, ?, ?, ?)""",
                (langid, original_form, gloss, processed_form)
            )
            added_count += 1
        
        conn.commit()
        
        # Regenerate embeddings after bulk upload
        regenerate_embeddings()
        
        return jsonify({
            "success": True,
            "langid": langid,
            "langname": langname,
            "entries_added": added_count,
            "message": f"Successfully added {added_count} entries for {langname}"
        })
        
    except Exception as e:
        conn.rollback()
        return jsonify({"error": f"Database error: {e}"}), 500


@app.route("/regenerate_embeddings")
def regenerate_embeddings_route():
    """
    API endpoint to regenerate all embeddings.
    Useful after manual database changes or to force a refresh.
    """
    try:
        regenerate_embeddings()
        return jsonify({
            "success": True,
            "count": len(embedder.refids),
            "message": f"Successfully regenerated embeddings for {len(embedder.refids)} reflexes"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
