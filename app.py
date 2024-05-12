import sqlite3
from flask import Flask, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash
from helpers import apology, using_database, login_required, check_form, lookup, usd

# Setup
app = Flask(__name__)
app.jinja_env.filters["usd"] = usd
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)
connection = sqlite3.connect("database.db")
db = connection.cursor()

db.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        first_name TEXT NOT NULL,
        last_name TEXT NOT NULL,
        username TEXT NOT NULL UNIQUE,
        hashed_password TEXT NOT NULL UNIQUE
    )
""")

db.execute("""
    CREATE TABLE IF NOT EXISTS accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        balance NUMERIC DEFAULT 1000.00,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
""")

db.execute("""
    CREATE TABLE IF NOT EXISTS stocks (
        user_id INTEGER NOT NULL,
        symbol TEXT NOT NULL,
        amount NUMERIC NOT NULL,
        unit_value NUMERIC NOT NULL,
        total_value NUMERIC NOT NULL,
        buy_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES user(id)
    )
""")

db.execute("""
    CREATE TABLE IF NOT EXISTS history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        type TEXT,
        sender_id INTEGER NOT NULL,
        receiver_id INTEGER NOT NULL,
        symbol TEXT NOT NULL,
        amount NUMERIC NOT NULL,
        unit_value NUMERIC NOT NULL,
        total_value NUMERIC NOT NULL,
        date_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (sender_id) REFERENCES users(id)
        FOREIGN KEY (receiver_id) REFERENCES users(id)
    )
""")

connection.commit()
connection.close()

# Redirect to home
@app.route("/")
def index():
    return redirect("/home")

# Register
@app.route("/register", methods=["GET", "POST"])
@using_database
def register(connected):
    # User already logged in
    if "user_id" in session:
        return redirect("/home")

    if request.method == "GET":
        return render_template("register.html")
    
    first_name = request.form.get("firstname")
    last_name = request.form.get("lastname")
    username = request.form.get("username")
    password = request.form.get("password")
    password_confirm = request.form.get("confirmation")

    # Check all form content is valid
    if not check_form((first_name, last_name, username, password, password_confirm)):
        return apology("Required fields must be filled.", 403)
    
    # Database connection
    db = connected.cursor()

    # Check unique username
    exists = db.execute("SELECT id FROM users WHERE username = ?", [username]).fetchone()
    if exists:
        return apology("Username already exists.", 403)

    # Create account
    password = generate_password_hash(password)
    db.execute("INSERT INTO users (first_name, last_name, username, hashed_password) VALUES (?, ?, ?, ?)", (first_name, last_name, username, password))
    user_id = db.execute("SELECT id FROM users WHERE username = ?", [username]).fetchone()[0]
    db.execute("INSERT INTO accounts (user_id) VALUES (?)", [user_id])
    connected.commit()
    session["user_id"] = user_id

    return redirect("/home")

# Log In
@app.route("/login", methods=["GET", "POST"])
@using_database
def login(connected):
    # User already logged in
    if "user_id" in session:
        return redirect("/home")

    if request.method == "GET":
        return render_template("login.html")
    
    # Database connection
    db = connected.cursor()

    # Check user exists
    username = request.form.get("username")
    user_id = db.execute("SELECT id FROM users WHERE username = ?", [username]).fetchone()
    hashed_password = db.execute("SELECT hashed_password FROM users WHERE username = ?", [username]).fetchone()
    
    if not user_id or not check_password_hash(hashed_password[0], request.form.get("password")):
        return apology("Incorrect username or password", 403)
    
    # Log user in
    session["user_id"] = user_id[0]
    
    return redirect("/home")

@app.route("/home")
@login_required
@using_database
def home(connected):
    db = connected.cursor()

    # Rendering currently owned stocks and portfolio
    user_balance = db.execute("SELECT balance FROM accounts WHERE user_id = ?", [session["user_id"]]).fetchone()[0]
    holdings = db.execute("SELECT symbol, amount, unit_value, total_value, buy_time FROM stocks WHERE user_id = ?", [session["user_id"]]).fetchall()
    net_value = user_balance

    # Convert tuples to lists and perform calculations
    holdings = [list(stock) for stock in holdings]

    for stock in holdings:
        stock.append(stock[3] - (stock[1] * lookup(stock[0])["price"]))  # Total Buy Price - Total Current Price (Total Profit/Loss)
        net_value += stock[2] * stock[1]  # Buy Price * Amount

    return render_template("home.html", user_balance=user_balance, holdings=holdings, net_value=net_value)


# Edit user balance (Paper Trade)
@app.route("/edit", methods=["GET", "POST"])
@login_required
@using_database
def edit_balance(connected):
    if request.method == "GET":
        return render_template("edit.html")
    
    # Check form
    edited_balance = request.form.get("amount")
    try:
        float(edited_balance)
    except ValueError:
        return apology("Amount must be numeric.")
    
    db = connected.cursor()

    if request.form.get("reset_portfolio") == "true":
        db.execute("DELETE FROM stocks WHERE user_id = ?", [session["user_id"]])
        db.execute("DELETE FROM history WHERE sender_id = ? or receiver_id = ?", (session["user_id"], session["user_id"]))
        db.execute("UPDATE accounts SET balance = ? WHERE user_id = ?", (edited_balance, session["user_id"]))
    else:
        db.execute("UPDATE accounts SET balance = ? WHERE user_id = ?", (edited_balance, session["user_id"]))

    connected.commit()

    return redirect("/home")

@app.route("/quote")
# @login_required
def quote():
    return render_template("quote.html")

@app.route("/quoted")
# @login_required
def quoted():
    quote = lookup(request.args.get("symbol"))

    if quote is None:
        return apology("Invalid stock symbol", 403)

    return render_template("quoted.html", quote=quote)

# Buy stocks
@app.route("/buy", methods=["GET", "POST"])
@login_required
@using_database
def buy(connected):
    if request.method == "GET":
        return render_template("buy.html")
    
    # Check fields
    try:
        amount = int(request.form.get("amount"))
    except ValueError:
        return apology("Invalid number of shares", 403)
    
    stock = lookup(request.form.get("symbol"))
    if stock is None:
        return apology("Invalid stock symbol", 403)
    
    # Not enough funds
    db = connected.cursor()
    user_balance = db.execute("SELECT balance FROM accounts WHERE user_id = ?", [session["user_id"]]).fetchone()
    total_price = amount * stock["price"]
    after_transaction = int(user_balance[0])- total_price
    if after_transaction < 0:
        return apology("Insufficient funds", 403)
    
    # Buy shares
    db.execute("UPDATE accounts SET balance = ? WHERE user_id = ?", (after_transaction, session["user_id"]))
    already_owned = db.execute("SELECT amount, unit_value FROM stocks WHERE user_id = ?", [session["user_id"]]).fetchone()
    # If user already has this stock at same price (useless to make a new stock when you can just add to amount)
    if not already_owned or already_owned[1] != stock["price"]:
        db.execute("INSERT INTO stocks (user_id, symbol, amount, unit_value, total_value) VALUES (?, ?, ?, ?, ?)", (session["user_id"], stock["symbol"], amount, stock["price"], total_price))
    else:
        db.execute("UPDATE stocks SET amount = ?", (int(already_owned[0]) + amount))
    db.execute("INSERT INTO history (type, sender_id, receiver_id, symbol, amount, unit_value, total_value) VALUES (?, ?, ?, ?, ?, ?, ?)", ("Buy", session["user_id"], session["user_id"], stock["symbol"], amount, stock["price"], total_price))
    connected.commit()

    return redirect("/home")

@app.route("/sell", methods=["GET", "POST"])
@login_required
@using_database
def sell(connected):
    db = connected.cursor()

    if request.method == "GET":
        # Fetch all symbols from the database
        holdings = db.execute("SELECT symbol FROM stocks WHERE user_id = ?", [session["user_id"]]).fetchall()
        unique_symbols = list(set(holdings))

        return render_template("sell.html", holdings=unique_symbols)
    
    stock = lookup(request.form.get("symbol"))
    if stock is None:
        return apology("Invalid stock symbol", 403)
    
    # Check fields
    try:
        amount = int(request.form.get("amount"))
    except ValueError:
        return apology("Invalid number of shares", 403)
    
    stocks = db.execute("SELECT amount FROM stocks WHERE user_id = ? AND symbol = ?", (session["user_id"], stock["symbol"])).fetchall()

    if stocks is None:
        return apology("No shares owned", 403)
    
    owned_amount = 0

    # Loop through stock
    for share in stocks:
        owned_amount += share[0]

    if owned_amount < amount: # Doesn't own enough
        return apology("Not enough shares owned", 403)
    elif owned_amount == amount: # Owns just enough
        db.execute("DELETE FROM stocks WHERE user_id = ? AND symbol = ?", (session["user_id"], stock["symbol"]))
    else: # Owns more than enough - First in stocks tuple sold first
        # Loop through the stocks and delete the appropriate amount starting from the oldest ones
        for owned_stock in stocks:
            if amount >= owned_stock[0]:  # If the amount to sell is greater than or equal to the amount of this stock
                db.execute("DELETE FROM stocks WHERE user_id = ? AND symbol = ? AND amount = ?", (session["user_id"], stock["symbol"], owned_stock[0]))
                amount -= owned_stock[0]
            else:  # If the amount to sell is less than the amount of this stock
                db.execute("UPDATE stocks SET amount = ? WHERE user_id = ? AND symbol = ? AND amount = ?", (owned_stock[0] - amount, session["user_id"], stock["symbol"], owned_stock[0]))
                break
    
    # Give money to user and log to history
    db.execute("UPDATE accounts SET balance = balance + ? WHERE user_id = ?", (amount * stock["price"], session["user_id"]))
    db.execute("INSERT INTO history (type, sender_id, receiver_id, symbol, amount, unit_value, total_value) VALUES (?, ?, ?, ?, ?, ?, ?)", ("Sell", session["user_id"], session["user_id"], stock["symbol"], amount, stock["price"], stock["price"] * amount))
    connected.commit()

    return redirect("/home")

@app.route("/history")
@login_required
@using_database
def history(connected):
    # Get user history
    db = connected.cursor()
    history = db.execute("SELECT type, sender_id, receiver_id, symbol, amount, unit_value, total_value, date_time FROM history WHERE sender_id = ? OR receiver_id = ?", (session["user_id"], session["user_id"])).fetchall()

    # Replace IDs by usernames
    for i, event in enumerate(history):
        event = list(event)
        sender_username = db.execute("SELECT username FROM users WHERE id = ?", [event[1]]).fetchone()
        receiver_username = db.execute("SELECT username FROM users WHERE id = ?", [event[2]]).fetchone()
        event[1] = sender_username[0]
        event[2] = receiver_username[0]
        history[i] = event  # Assign the modified list back to the history list

    return render_template("history.html", history=history)

# User settings
@app.route("/settings")
@login_required
@using_database
def settings(connected):
    db = connected.cursor()

    # Get output as dictionary
    db.row_factory = sqlite3.Row
    profile = dict(db.execute("SELECT first_name, last_name, username FROM users WHERE id = ?", [session["user_id"]]).fetchone())
    # Revert
    db.row_factory = sqlite3.Row

    return render_template("settings.html", profile=profile)

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

@app.route("/delete_account")
@login_required
@using_database
def delete_account(connected):
    db = connected.cursor()
    db.execute("DELETE FROM history WHERE user_id = ?", [session["user_id"]])
    db.execute("DELETE FROM stocks WHERE user_id = ?", [session["user_id"]])
    db.execute("DELETE FROM accounts WHERE user_id = ?", [session["user_id"]])
    db.execute("DELETE FROM users WHERE id = ?", [session["user_id"]])
    connected.commit()
    session.clear()
    return redirect("/register")