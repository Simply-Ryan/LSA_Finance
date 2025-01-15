import csv
import datetime
import pytz
import requests
import urllib
import uuid
import sqlite3
import json

# Stock Market API
import finnhub

from flask import redirect, render_template, request, session, g
from functools import wraps

api_key = "cu05qhpr01ql96gpu91gcu05qhpr01ql96gpu920"
finnhub_client = finnhub.Client(api_key)

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
    
    # Request data from Finnhub
    data = finnhub_client.quote(symbol)
    lookup = finnhub_client.symbol_lookup(symbol)

    # If symbol is invalid, look stock up instead.
    if data["c"] == 0:
        result = lookup["result"]
        quote = {"found": 0, "results": result}

        return quote

    company_name = lookup['result'][0]['description']
    price = data['c']
    change = data['d']
    percent_change = data['dp']
    day_high = data['h']
    day_low = data['l']
    quote = {"found": 1, "company_name": company_name,"price": price, "symbol": symbol, "change": change, "percent_change": percent_change, "day_high": day_high, "day_low": day_low}

    return quote


def usd(value):
    """Format value as USD."""
    return f"{value:,.2f}$"