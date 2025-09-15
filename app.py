import sqlite3
from flask import Flask, redirect, render_template, url_for, flash, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash
from helpers import apology, using_database, login_required, check_form, lookup, usd

# Setup
app = Flask(__name__)
app.jinja_env.filters["usd"] = usd
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# One-time initialization / table creation
connection = sqlite3.connect("database.db")
db = connection.cursor()

# TO MANUALLY ADD/DELETE USERS: DELETE THEM FROM ALL DATABASES
# EXAMPLE: DELETE FROM users WHERE id = X;
# DELETE FROM accounts WHERE user_id = X; (repeat for all databases except history)

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
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
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
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
""")

# HISTORY TABLE: id, type, sender_id, receiver_id, symbol, amount, unit_value, total_value, date_time
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
        FOREIGN KEY (sender_id) REFERENCES users(id),
        FOREIGN KEY (receiver_id) REFERENCES users(id)
    )
""")

# REQUESTS TABLE: id, type, sender_id, receiver_id, date_time
db.execute("""
    CREATE TABLE IF NOT EXISTS requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        type TEXT,
        sender_id INTEGER NOT NULL,
        receiver_id INTEGER NOT NULL,
        date_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (sender_id) REFERENCES users(id),
        FOREIGN KEY (receiver_id) REFERENCES users(id)
    )
""")

# LEAGUE TABLE: id, owner_id, name, description
db.execute("""
    CREATE TABLE IF NOT EXISTS leagues (
           id INTEGER PRIMARY KEY AUTOINCREMENT,
           owner_id TEXT NOT NULL,
           name TEXT NOT NULL,
           description TEXT
    )
""")

# LEAGUE MEMBERS TABLE: user_id, league_id
db.execute("""
    CREATE TABLE IF NOT EXISTS league_members (
           user_id INTEGER NOT NULL,
           league_id INTEGER NOT NULL,
           FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
           FOREIGN KEY (league_id) REFERENCES leagues(id)
    )
""")

# FRIENDSHIPS TABLE: user1_id, user2_id, date_time
db.execute("""
    CREATE TABLE IF NOT EXISTS friendships (
        user1_id INTEGER NOT NULL,
        user2_id INTEGER NOT NULL,
        date_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user1_id) REFERENCES users(id),
        FOREIGN KEY (user2_id) REFERENCES users(id),
        PRIMARY KEY (user1_id, user2_id)
    )
""")

# Default users (safe: INSERT OR IGNORE + lookup IDs dynamically)
db.execute(
    "INSERT OR IGNORE INTO users (first_name, last_name, username, hashed_password) VALUES (?, ?, ?, ?)",
    ("Official", "Test", "OfficialTest", generate_password_hash("OfficialTest12345_"))
)
db.execute(
    "INSERT OR IGNORE INTO users (first_name, last_name, username, hashed_password) VALUES (?, ?, ?, ?)",
    ("Stock", "Market", "Market", generate_password_hash("StockMarketOfficialAccount12345_"))
)
connection.commit()

officialtest_id = db.execute("SELECT id FROM users WHERE username = ?", ("OfficialTest",)).fetchone()[0]
market_id = db.execute("SELECT id FROM users WHERE username = ?", ("Market",)).fetchone()[0]

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

    # Determine original balance from last Balance Edit; fallback to current balance if none
    ob_row = db.execute(
        "SELECT total_value FROM history WHERE receiver_id = ? AND type = ? ORDER BY date_time ASC LIMIT 1",
        (session["user_id"], "Balance Edit")
    ).fetchone()
    if ob_row:
        original_balance = float(ob_row[0])
    else:
        original_balance = float(db.execute("SELECT balance FROM accounts WHERE user_id = ?", [session["user_id"]]).fetchone()[0])

    user_balance = float(db.execute("SELECT balance FROM accounts WHERE user_id = ?", [session["user_id"]]).fetchone()[0])
    holdings = db.execute("SELECT symbol, amount, unit_value, total_value, buy_time FROM stocks WHERE user_id = ?", [session["user_id"]]).fetchall()
    holdings = [list(stock) for stock in holdings]

    # Rendering requests (replace sender_id with username)
    requests = db.execute("SELECT id, type, sender_id, date_time FROM requests WHERE receiver_id = ?", [session["user_id"]]).fetchall()
    requests = [list(r) for r in requests]
    for r in requests:
        user_name = db.execute("SELECT username FROM users WHERE id = ?", [r[2]]).fetchone()
        r[2] = user_name[0] if user_name else "Unknown"

    # Calculate profits and net value using CURRENT prices
    net_value = user_balance
    for stock in holdings:
        symbol, amount, unit_value, total_value, _buy_time = stock
        current_price = lookup(symbol)["price"]
        current_value = current_price * amount
        buy_cost = total_value  # unit_value * amount at purchase
        profit_loss = current_value - buy_cost
        stock.append(profit_loss)  # append P/L to each stock row
        net_value += current_value

    net_profit = net_value - original_balance  # Net Profit/Loss
    net_profit_percent = round(((net_value - original_balance) / original_balance * 100), 2) if original_balance else 0.0

    return render_template(
        "home.html",
        user_balance=user_balance,
        holdings=holdings,
        net_value=net_value,
        requests=requests,
        net_profit=net_profit,
        net_profit_percent=net_profit_percent
    )


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
        db.execute("DELETE FROM history WHERE sender_id = ? OR receiver_id = ?", (session["user_id"], session["user_id"]))
        db.execute("UPDATE accounts SET balance = ? WHERE user_id = ?", (edited_balance, session["user_id"]))
    else:
        db.execute("UPDATE accounts SET balance = ? WHERE user_id = ?", (edited_balance, session["user_id"]))
    
    # So users can know how much they started with
    db.execute(
        "INSERT INTO history (type, sender_id, receiver_id, symbol, amount, unit_value, total_value) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("Balance Edit", market_id, session["user_id"], "N/A", 1, edited_balance, edited_balance)
    )

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
        # Get user balance
        db = connected.cursor()
        db_request = db.execute("SELECT balance FROM accounts WHERE user_id = ?", [session["user_id"]]).fetchone()
        user_balance = float(db_request[0])
        return render_template("buy.html", userBalance=user_balance)
    
    # Check fields
    try:
        amount = int(request.form.get("amount"))
    except (ValueError, TypeError):
        return apology("Invalid number of shares", 403)
    
    stock = lookup(request.form.get("symbol"))
    if stock is None:
        return apology("Invalid stock symbol", 403)
    
    # Not enough funds
    db = connected.cursor()
    user_balance_row = db.execute("SELECT balance FROM accounts WHERE user_id = ?", [session["user_id"]]).fetchone()
    user_balance = float(user_balance_row[0])
    total_price = amount * stock["price"]
    after_transaction = user_balance - total_price
    if after_transaction < 0:
        return apology("Insufficient funds", 403)
    
    # Buy shares
    db.execute("UPDATE accounts SET balance = ? WHERE user_id = ?", (after_transaction, session["user_id"]))

    # Merge only with an existing lot of the SAME symbol AND SAME unit price
    already_owned = db.execute(
        "SELECT amount FROM stocks WHERE user_id = ? AND symbol = ? AND unit_value = ?",
        (session["user_id"], stock["symbol"], stock["price"])
    ).fetchone()

    if not already_owned:
        db.execute(
            "INSERT INTO stocks (user_id, symbol, amount, unit_value, total_value) VALUES (?, ?, ?, ?, ?)",
            (session["user_id"], stock["symbol"], amount, stock["price"], total_price)
        )
    else:
        new_amount = int(already_owned[0]) + amount
        db.execute(
            "UPDATE stocks SET amount = ?, total_value = ? WHERE user_id = ? AND symbol = ? AND unit_value = ?",
            (new_amount, new_amount * stock["price"], session["user_id"], stock["symbol"], stock["price"])
        )
    
    db.execute(
        "INSERT INTO history (type, sender_id, receiver_id, symbol, amount, unit_value, total_value) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("Buy", market_id, session["user_id"], stock["symbol"], amount, stock["price"], total_price)
    )
    connected.commit()

    return redirect("/home")


@app.route("/sell", methods=["GET", "POST"])
@login_required
@using_database
def sell(connected):
    db = connected.cursor()

    if request.method == "GET":
        # Fetch distinct symbols the user owns
        symbols = db.execute(
            "SELECT DISTINCT symbol FROM stocks WHERE user_id = ?",
            [session["user_id"]]
        ).fetchall()
        unique_symbols = [s[0] for s in symbols]
        return render_template("sell.html", holdings=unique_symbols)
    
    stock = lookup(request.form.get("symbol"))
    if stock is None:
        return apology("Invalid stock symbol", 403)
    
    # Check fields
    try:
        amount = int(request.form.get("amount"))
    except (ValueError, TypeError):
        return apology("Invalid number of shares", 403)
    
    # All individual lots (FIFO by time)
    lots = db.execute(
        "SELECT amount, unit_value FROM stocks WHERE user_id = ? AND symbol = ? ORDER BY buy_time ASC",
        (session["user_id"], stock["symbol"])
    ).fetchall()

    if not lots:
        return apology("No shares owned", 403)
    
    owned_amount = sum(l[0] for l in lots)

    if owned_amount < amount:
        return apology("Not enough shares owned", 403)

    sell_amount = amount  # preserve original requested amount for crediting

    # Reduce / delete lots FIFO
    for lot_amount, lot_unit_value in lots:
        if amount == 0:
            break
        if amount >= lot_amount:
            # delete entire lot
            db.execute(
                "DELETE FROM stocks WHERE user_id = ? AND symbol = ? AND amount = ? AND unit_value = ?",
                (session["user_id"], stock["symbol"], lot_amount, lot_unit_value)
            )
            amount -= lot_amount
        else:
            # reduce this lot
            new_amount = lot_amount - amount
            # Update both amount and total_value to keep consistency
            db.execute(
                "UPDATE stocks SET amount = ?, total_value = ? WHERE user_id = ? AND symbol = ? AND unit_value = ? AND amount = ?",
                (new_amount, new_amount * lot_unit_value, session["user_id"], stock["symbol"], lot_unit_value, lot_amount)
            )
            amount = 0

    # Credit proceeds at current price
    proceeds = sell_amount * stock["price"]
    db.execute("UPDATE accounts SET balance = balance + ? WHERE user_id = ?", (proceeds, session["user_id"]))
    db.execute(
        "INSERT INTO history (type, sender_id, receiver_id, symbol, amount, unit_value, total_value) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("Sell", session["user_id"], market_id, stock["symbol"], sell_amount, stock["price"], proceeds)
    )
    connected.commit()

    return redirect("/home")


@app.route("/history")
@login_required
@using_database
def history(connected):
    # Get user history
    db = connected.cursor()
    history_rows = db.execute(
        "SELECT type, sender_id, receiver_id, symbol, amount, unit_value, total_value, date_time FROM history WHERE sender_id = ? OR receiver_id = ? ORDER BY date_time DESC",
        (session["user_id"], session["user_id"])
    ).fetchall()

    history_list = []
    for event in history_rows:
        event = list(event)
        sender_username = db.execute("SELECT username FROM users WHERE id = ?", [event[1]]).fetchone()
        receiver_username = db.execute("SELECT username FROM users WHERE id = ?", [event[2]]).fetchone()
        event[1] = sender_username[0] if sender_username else "Unknown"
        event[2] = receiver_username[0] if receiver_username else "Unknown"
        history_list.append(event)

    return render_template("history.html", history=history_list)


@app.route("/profile", methods=["GET"])
@login_required
@using_database
def profile(connected):
    username = request.args.get("username")
    if not username:
        return apology("Username not provided", 400)

    # Get user info
    db = connected.cursor()
    user = db.execute("SELECT id, username FROM users WHERE username = ?", [username]).fetchone()
    if not user:
        return apology("User not found", 404)
    user_id = user[0]

    # Get user account balance
    account = db.execute("SELECT balance FROM accounts WHERE user_id = ?", [user_id]).fetchone()
    account_balance = account[0] if account else 0

    # Get owned stocks
    stocks = db.execute("SELECT symbol, amount FROM stocks WHERE user_id = ?", [user_id]).fetchall()

    # Get last activity
    last_activity = db.execute(
        "SELECT date_time FROM history WHERE sender_id = ? OR receiver_id = ? ORDER BY date_time DESC LIMIT 1",
        (user_id, user_id)
    ).fetchone()
    last_activity = last_activity[0][:10] if last_activity else "No activity"  # Extract date from datetime (YYYY-MM-DD)

    return render_template("profile.html", username=user[1], account_balance=account_balance, stocks=stocks, last_activity=last_activity)


@app.route("/friends")
@login_required
@using_database
def friends(connected):
    db = connected.cursor()

    # Get user's friends (both directions)
    friends = db.execute("SELECT user2_id FROM friendships WHERE user1_id = ?", [session["user_id"]]).fetchall()
    friends += db.execute("SELECT user1_id FROM friendships WHERE user2_id = ?", [session["user_id"]]).fetchall()

    # Flatten to list of IDs, exclude self
    friend_ids = [fid[0] for fid in friends if fid[0] != session["user_id"]]

    # Get usernames
    friends_usernames = []
    for fid in friend_ids:
        row = db.execute("SELECT username FROM users WHERE id = ?", [fid]).fetchone()
        if row:
            friends_usernames.append(row[0])
        else:
            friends_usernames.append("Unknown")

    # Pending friend requests
    requests = db.execute(
        "SELECT id, type, sender_id FROM requests WHERE receiver_id = ? AND type = 'Friend'",
        [session["user_id"]]
    ).fetchall()
    requests_list = []
    for r in requests:
        sender_row = db.execute("SELECT username FROM users WHERE id = ?", [r[2]]).fetchone()
        sender_name = sender_row[0] if sender_row else "Unknown"
        requests_list.append([r[0], r[1], sender_name])

    return render_template("friends.html", friends=friends_usernames, requests=requests_list)


@app.route("/friends/add", methods=["GET", "POST"])
@login_required
@using_database
def add_friend(connected):
    db = connected.cursor()

    if request.method == "GET":
        return render_template("add_friend.html")

    # Send friend request
    target_username = request.form.get("username")
    receiver_row = db.execute("SELECT id FROM users WHERE username = ?", [target_username]).fetchone()
    if not receiver_row:
        flash("User does not exist.", "danger")
        return redirect(url_for("home"))

    receiver_id = receiver_row[0]
    if receiver_id == session["user_id"]:
        flash("You cannot add yourself.", "danger")
        return redirect(url_for("home"))
    
    # Check if request already exists (from the other user)
    request_exists = db.execute(
        "SELECT id FROM requests WHERE type = ? AND sender_id = ? AND receiver_id = ?",
        ("Friend", receiver_id, session["user_id"])
    ).fetchone()

    if request_exists:
        # If the other user already sent a request to you, auto-accept (create friendship)
        db.execute("INSERT OR IGNORE INTO friendships (user1_id, user2_id) VALUES (?, ?)", (receiver_id, session["user_id"]))
        db.execute("DELETE FROM requests WHERE id = ?", (request_exists[0],))
        flash(f"You are now friends with {target_username}!", "success")
    else:
        # Otherwise, check for outgoing duplicate
        outgoing_exists = db.execute(
            "SELECT id FROM requests WHERE type = ? AND sender_id = ? AND receiver_id = ?",
            ("Friend", session["user_id"], receiver_id)
        ).fetchone()
        if outgoing_exists:
            flash(f"You have already sent a friend request to {target_username}.", "warning")
        else:
            # Create a new friend request
            db.execute(
                "INSERT INTO requests (type, sender_id, receiver_id) VALUES (?, ?, ?)",
                ("Friend", session["user_id"], receiver_id)
            )
            flash(f"Friend request sent to {target_username}!", "success")
    
    # Log the friend request action (optional history tracking)
    db.execute(
        "INSERT INTO history (type, sender_id, receiver_id, symbol, amount, unit_value, total_value) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("FriendRequest", session["user_id"], receiver_id, "N/A", 1, 1, 1)
    )

    connected.commit()
    return redirect(url_for("home"))

@app.route("/friends/remove", methods=["POST"])
@login_required
@using_database
def remove_friend(connected):
    db = connected.cursor()
    username = request.form.get("username")

    # Find friend ID
    friend = db.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
    if not friend:
        return apology("User not found", 404)

    friend_id = friend[0]
    user_id = session["user_id"]

    # Delete friendship both ways
    db.execute("DELETE FROM friendships WHERE (user1_id = ? AND user2_id = ?) OR (user1_id = ? AND user2_id = ?)",
               (user_id, friend_id, friend_id, user_id))
    connected.commit()

    return redirect("/friends")

@app.route("/leagues/create", methods=["GET", "POST"])
@login_required
@using_database
def create_league(connected):
    if request.method == "GET":
        return render_template("create_league.html")
    
    # Check form validity
    # TODO


@app.route("/leagues/join", methods=["GET", "POST"])
@login_required
@using_database
def join_league(connected):
    if request.method == "GET":
        return render_template("join_league.html")
    
    # Check form validity
    # TODO

@app.route("/friends/accept", methods=["POST"])
@login_required
@using_database
def accept_friend(connected):
    db = connected.cursor()
    request_id = request.form.get("request_id")

    # Get request info
    req = db.execute("SELECT sender_id, receiver_id FROM requests WHERE id = ?", (request_id,)).fetchone()
    if not req:
        return apology("Request not found", 404)

    sender_id, receiver_id = req
    if receiver_id != session["user_id"]:
        return apology("Not authorized", 403)

    # Create friendship
    db.execute("INSERT OR IGNORE INTO friendships (user1_id, user2_id) VALUES (?, ?)", (sender_id, receiver_id))
    # Delete the request
    db.execute("DELETE FROM requests WHERE id = ?", (request_id,))
    connected.commit()

    return redirect("/friends")


@app.route("/friends/decline", methods=["POST"])
@login_required
@using_database
def decline_friend(connected):
    db = connected.cursor()
    request_id = request.form.get("request_id")

    req = db.execute("SELECT receiver_id FROM requests WHERE id = ?", (request_id,)).fetchone()
    if not req or req[0] != session["user_id"]:
        return apology("Not authorized", 403)

    db.execute("DELETE FROM requests WHERE id = ?", (request_id,))
    connected.commit()

    return redirect("/friends")


# User settings
@app.route("/settings")
@login_required
@using_database
def settings(connected):
    # Use row factory properly on the *connection*, not the cursor
    connected.row_factory = sqlite3.Row
    db = connected.cursor()
    profile_row = db.execute(
        "SELECT first_name, last_name, username FROM users WHERE id = ?",
        [session["user_id"]]
    ).fetchone()
    # Revert to default
    connected.row_factory = None

    profile = dict(profile_row) if profile_row else {"first_name": "", "last_name": "", "username": ""}
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
    # Correctly remove history tied to this user
    db.execute("DELETE FROM history WHERE sender_id = ? OR receiver_id = ?", (session["user_id"], session["user_id"]))
    db.execute("DELETE FROM stocks WHERE user_id = ?", [session["user_id"]])
    db.execute("DELETE FROM accounts WHERE user_id = ?", [session["user_id"]])
    db.execute("DELETE FROM users WHERE id = ?", [session["user_id"]])
    connected.commit()
    session.clear()
    return redirect("/register")