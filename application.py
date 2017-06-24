import os
import re
from flask import Flask, jsonify, render_template, request, url_for
from flask_jsglue import JSGlue

from cs50 import SQL
from helpers import lookup

# configure application
app = Flask(__name__)
JSGlue(app)

# ensure responses aren't cached
if app.config["DEBUG"]:
    @app.after_request
    def after_request(response):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Expires"] = 0
        response.headers["Pragma"] = "no-cache"
        return response

# configure CS50 Library to use SQLite database
db = SQL("sqlite:///mashup.db")

@app.route("/")
def index():
    """Render map."""
    if not os.environ.get("API_KEY"):
        raise RuntimeError("API_KEY not set")
    return render_template("index.html", key=os.environ.get("API_KEY"))

@app.route("/articles")
def articles():
    """Look up articles for geo."""
    return jsonify(lookup(request.args.get("geo")))

@app.route("/search")
def search():
    """Search for places that match query."""
    q = request.args.get("q")
    if q.isdigit():
        # if input is a postal code
        rows = db.execute("SELECT * FROM places WHERE postal_code LIKE :q", q=q+'%')
    else:
        # else extract state_code (optional) and look up the place entered
        place = q.split(',')
        state_code = ''
        state_name = ''
        for i in range(len(q) -1):
            if q[i].isupper() and q[i+1].isupper():
                state_code = q[i] + q[i+1]
                q = q[0:i]
                break
        if state_code == 'US':
            state_code = ''
        if not state_code and len(place) > 1:
            state_name = place[1].strip()
        if not state_code and not state_name:
            rows = db.execute("SELECT * FROM places WHERE place_name LIKE :q", q=q+'%')
        elif state_code:
            print('querying q {} for code {}'.format(q, state_code))
            rows = db.execute("SELECT * FROM places WHERE place_name LIKE :q AND admin_code1 = :state_code",
                                q='%'+q.strip()+'%', state_code=state_code)
        elif state_name:
            print('querying q {} for name {}'.format(q, state_name))
            rows = db.execute("SELECT * FROM places WHERE place_name LIKE :q AND admin_name1 = :state_name",
                                q='%'+place[0].strip()+'%', state_name=state_name)
    return jsonify((rows))

@app.route("/update")
def update():
    """Find up to 10 places within view."""

    # ensure parameters are present
    if not request.args.get("sw"):
        raise RuntimeError("missing sw")
    if not request.args.get("ne"):
        raise RuntimeError("missing ne")

    # ensure parameters are in lat,lng format
    if not re.search("^-?\d+(?:\.\d+)?,-?\d+(?:\.\d+)?$", request.args.get("sw")):
        raise RuntimeError("invalid sw")
    if not re.search("^-?\d+(?:\.\d+)?,-?\d+(?:\.\d+)?$", request.args.get("ne")):
        raise RuntimeError("invalid ne")

    # explode southwest corner into two variables
    (sw_lat, sw_lng) = [float(s) for s in request.args.get("sw").split(",")]

    # explode northeast corner into two variables
    (ne_lat, ne_lng) = [float(s) for s in request.args.get("ne").split(",")]

    # find 10 cities within view, pseudorandomly chosen if more within view
    if (sw_lng <= ne_lng):

        # doesn't cross the antimeridian
        rows = db.execute("""SELECT * FROM places
            WHERE :sw_lat <= latitude AND latitude <= :ne_lat AND (:sw_lng <= longitude AND longitude <= :ne_lng)
            GROUP BY country_code, place_name, admin_code1
            ORDER BY RANDOM()
            LIMIT 10""",
            sw_lat=sw_lat, ne_lat=ne_lat, sw_lng=sw_lng, ne_lng=ne_lng)

    else:

        # crosses the antimeridian
        rows = db.execute("""SELECT * FROM places
            WHERE :sw_lat <= latitude AND latitude <= :ne_lat AND (:sw_lng <= longitude OR longitude <= :ne_lng)
            GROUP BY country_code, place_name, admin_code1
            ORDER BY RANDOM()
            LIMIT 10""",
            sw_lat=sw_lat, ne_lat=ne_lat, sw_lng=sw_lng, ne_lng=ne_lng)

    # output places as JSON
    return jsonify(rows)
