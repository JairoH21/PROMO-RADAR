from flask import Blueprint, render_template, request, redirect, url_for, flash
from . import get_db
from .marketplaces import search_all

bp = Blueprint("main", __name__)

@bp.route("/")
def index():
    with get_db() as db:
        offers = db.execute("SELECT * FROM offers ORDER BY COALESCE(discount, 0) DESC, id DESC LIMIT 100").fetchall()
        keywords = db.execute("SELECT * FROM keywords ORDER BY term").fetchall()
    return render_template("index.html", offers=offers, keywords=keywords)

@bp.get("/health")
def health():
    return {"status": "ok"}

@bp.post("/keyword")
def add_keyword():
    term = request.form.get("term", "").strip()
    if term:
        with get_db() as db:
            db.execute("INSERT OR IGNORE INTO keywords(term) VALUES (?)", (term,))
            db.commit()
        flash("Palavra-chave adicionada.")
    return redirect(url_for("main.index"))

@bp.post("/scan")
def scan():
    with get_db() as db:
        keywords = db.execute("SELECT term FROM keywords WHERE active=1").fetchall()
    total, errors = 0, []
    for row in keywords:
        try:
            offers = search_all(row["term"])
            with get_db() as db:
                for o in offers:
                    values = [o[k] for k in ["source","external_id","title","url","image_url","price","old_price","discount","score"]]
                    db.execute('''INSERT INTO offers
                    (source,external_id,title,url,image_url,price,old_price,discount,score)
                    VALUES (?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(source,external_id) DO UPDATE SET
                    title=excluded.title,url=excluded.url,image_url=excluded.image_url,
                    price=excluded.price,old_price=excluded.old_price,
                    discount=excluded.discount,score=excluded.score''', values)
                    total += 1
                db.commit()
        except Exception as exc:
            errors.append(f"{row['term']}: {exc}")
    flash(f"{total} ofertas processadas." + ((" Erros: " + " | ".join(errors)) if errors else ""))
    return redirect(url_for("main.index"))
