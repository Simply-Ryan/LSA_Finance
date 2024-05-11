import csv
import datetime
import pytz
import requests
import urllib
import uuid
import sqlite3

from flask import redirect, render_template, request, session, g
from functools import wraps


def apology(message, code=400):
    """Render message as an apology to user."""

    def escape(s):
        """
        Escape special characters.

        https://github.com/jacebrowning/memegen#special-characters
        """
        for old, new in [
            ("-", "--"),
            (" ", "-"),
            ("_", "__"),
            ("?", "~q"),
            ("%", "~p"),
            ("#", "~h"),
            ("/", "~s"),
            ('"', "''"),
        ]:
            s = s.replace(old, new)
        return s

    return render_template("apology.html", top=code, bottom=escape(message)), code


def login_required(f):
    """
    Decorate routes to require login.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session or session["user_id"] is None:
            return redirect("/login")
        return f(*args, **kwargs)

    return decorated_function


def using_database(function):
    @wraps(function)
    def decorated_function(*args, **kwargs):
        def get_db():
            if 'db' not in g:
                g.db = sqlite3.connect('database.db')
            return g.db

        def close_db(e=None):
            db = g.pop('db', None)
            if db is not None:
                db.close()

        db = get_db()
        try:
            return function(db, *args, **kwargs)
        finally:
            close_db()

    return decorated_function


def check_form(fields):
    for field in fields:
        if not field:
            return False
    return True


def lookup(symbol):
    """Look up quote for symbol."""

    # Prepare API request
    try:
        symbol = symbol.upper()
    except ValueError:
        return None
    end = datetime.datetime.now(pytz.timezone("US/Eastern"))
    start = end - datetime.timedelta(days=7)

    # Yahoo Finance API
    url = (
        f"https://query1.finance.yahoo.com/v7/finance/download/{urllib.parse.quote_plus(symbol)}"
        f"?period1={int(start.timestamp())}"
        f"&period2={int(end.timestamp())}"
        f"&interval=1d&events=history&includeAdjustedClose=true"
    )

    # Query API
    try:
        response = requests.get(
            url,
            cookies={"session": str(uuid.uuid4())},
            headers={"Accept": "*/*", "User-Agent": request.headers.get("User-Agent")},
        )
        response.raise_for_status()

        # CSV header: Date,Open,High,Low,Close,Adj Close,Volume
        quotes = list(csv.DictReader(response.content.decode("utf-8").splitlines()))
        price = round(float(quotes[-1]["Adj Close"]), 2)
        return {"price": price, "symbol": symbol}
    except (KeyError, IndexError, requests.RequestException, ValueError):
        return None


def usd(value):
    """Format value as USD."""
    return f"${value:,.2f}"