import os

import sys

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
# app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
app.config["SECRET_KEY"] = 'q11PdxmVF88eD7jaGEFr9A'
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")

# Begin the routes
@app.route("/")
@login_required # The user must be logged in to see the index page
def index():
    """Show portfolio of stocks"""

    # Create a stocks table storing information about the stock such as the symbol, price, name
    db.execute("""CREATE TABLE IF NOT EXISTS stocks
                    (Username TEXT,
                     Symbol TEXT,
                     Name TEXT,
                     Shares NUMERIC,
                     Price DECIMAL(6,2),
                     Total DECIMAL(6,2),
                     CASH NUMERIC,
                     Transacted )"""
                   )

    # In order to know which user is currently logged in, we must create a session (session['username'] = request.form.get("username"))
    nameuser = session['username']

    # Check how many rows currently exist in the stocks table by querying the database
    num_rows = db.execute("""SELECT COUNT(*) as count FROM stocks""")

    # Then obtain the actual value which tells us the number of observations in the table
    for row in num_rows:
        obs = row['count']
    
    # Grab the cash amount from the user in the users table
    cash = db.execute("""SELECT cash FROM users WHERE username = (?)""", nameuser)
    amount = cash[0]['cash']
    
    # Set an empty list of users
    users = []
    
    # Query the stocks database for all the users who have bought stocks
    user_check = db.execute("""SELECT Username FROM stocks""")
    
    # Append these users to the users list
    for user in user_check:
        users.append(user['Username'])

    # We check for two conditions:
        #1. If there there are no observations in the stocks table, then display the current user's cash amount
        #2. If it's a new registrant, we don't want to display the existing user's stocks, so just display their intial
          # cash amount instead as queried from the users database
    if obs == 0 or nameuser not in users:

        # In this case, render the bought template which just sumarizes what they bought so far
        return render_template('bought.html', amount=amount)
    
    # Run a SQL query to select only the relevant info, will be passed into a template
    final = db.execute("""SELECT Symbol, Name, Shares, Price, Total FROM stocks
                              WHERE Username = (?)""", nameuser)
    
    # Sum the total column; ie, the total cost of all stocks bought
    total_column = db.execute("""SELECT SUM(Total) as Total FROM stocks WHERE Username = (?)""", nameuser)
    
    # Substract the cash amount from the total price of stocks bought, this is the cash remaining
    amount = amount - total_column[0]['Total']
    
    # Then sum up everything, it should add to $10,000
    final_sum = total_column[0]['Total'] + amount
    
    # Convert to a dollar format
    amount = usd(amount)
    final_sum = usd(final_sum)
    
    # Finally, render the bought.html template, passing in the stocks that were bought, cash remaining, and the cumulative sum
    return render_template("bought.html", final=final, amount=amount, final_sum=final_sum)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    # If method is POST
    if request.method == "POST":
        # Get the information entered in the "Symbol" box of the buy page, make sure it's uppercase
        symbol = request.form.get("symbol").upper()
        
        # If these user didn't enter a symbol, or the symbol doesn't exist, return an apology message
        if not symbol or lookup(symbol) == None:
            return apology("Invalid symbol")

        # Get the information entered in the "Shares" box of the buy page
        shares = request.form.get("shares")

        # If the share that was entered is not a digit, is negative, or is equal to 0, return an apology message
        if not shares.isdigit() or shares == '0':
            return apology("Please enter a positive share amount")

        # If both fields were not entered, return an apology message
        if not symbol and not shares:
            return apology("Please make sure both fields are completed")
        
        # The share amount came in as a str, so convert to int so that calculations can be made
        shares = int(request.form.get("shares"))    

        # Create a new table for the history of transactions made, this will be used to track the stocks that are being bought
        db.execute("""CREATE TABLE IF NOT EXISTS history
                    (Username TEXT,
                     Symbol TEXT,
                     Shares NUMERIC,
                     Price NUMERIC,
                     Transacted SMALLDATETIME)"""
                   )


        # Creating a table to store stock information from user
        db.execute("""CREATE TABLE IF NOT EXISTS stocks
                    (Username TEXT,
                     Symbol TEXT,
                     Name TEXT,
                     Shares NUMERIC,
                     Price NUMERIC,
                     Total NUMERIC
                     CASH NUMERIC)"""
                   )
        
        # The lookup function returns three things: a) name, b) price, c) symbol of stock
        stock_info = lookup(symbol)
        
        # Doing stock_info["name"] obtains the value associated with the key of "name"
        symbol_name = stock_info["name"]
        
        # stock_info["price"] obtains the value associated with the key of "price", float converts this value to a float
        symbol_price = float(stock_info["price"])
        
        # The total amount bought is just the number of shares times price
        total = float(shares * symbol_price)

        # Keep track of the current user in session
        nameuser = session['username']

        # Select the cash amount from the user in session
        cash = db.execute("""SELECT cash FROM users WHERE username = (?)""", nameuser)
        
        # Run this SQL query to extract information for the index page
        final = db.execute("""SELECT Symbol, Name, Shares, Price, Total FROM stocks
                              WHERE Username = (?)""", nameuser)
                              
        # Calculate the final sum again, want to check if it exceeds the cash amount or not
        final_sum = 0

        # All SQL queries return a dictionary, value['Total'] gives us the amount of each value associated with the key 'Total'
        for value in final:
            # Aggregate by adding each shares * price amount to the final sum
            final_sum += value['Total'] 
        
        # Check if the current shares wanting to be bought for a symbol plus their current investments
        # is greater than the cash the user has, then return an apology
        if final_sum + (int(shares) * symbol_price) > cash[0]['cash']:
            return apology("Cannot afford another share!")
        
        ### After this check has been made, we now start inserting information into the stocks table
        num_rows = db.execute("""SELECT COUNT(*) as count FROM stocks""")

        # Grab the number of observations that currently exists in the stocks table
        for row in num_rows:
            obs = row['count']

        # Initialize an array with 0 elements
        symbol_list = []

        # Check two conditions:
            #1. If the stocks table is currently empty, then insert the current username, symbol, name, shares, price, and total that was bought
            #2. Else, if there is something already in the table, check for two condtions:
                #a) If The symbol that was entered matches what's currently in the stocks table, then UPDATE the share and total amounts for the current user
                #b) Otherwise, INSERT that new symbol into the table for the current user
        if obs == 0:
            # Inserting information into the db if there are no observations at first
            db.execute("""INSERT INTO stocks (Username, Symbol, Name, Shares, Price, Total)
                          VALUES (?,?,?,?,?,?)""", nameuser, symbol.upper(), symbol_name, shares, usd(symbol_price),
                          total)

            records = db.execute("""SELECT Symbol, Name, Shares, Price, Total
                                    FROM stocks WHERE Username = (?)""", nameuser)

        elif obs != 0:

            records = db.execute("""SELECT Symbol, Name, Shares, Price, Total
                                    FROM stocks WHERE Username = (?)""", nameuser)
            
            # Append symbols into the symbol_list list
            for record in records:
                symbol_list.append(record['Symbol'].upper())
            
            # Query for the current number of shares of the symbol that was bought for the current user
            sharedb = db.execute("""SELECT Shares FROM stocks WHERE Symbol = (?) AND
                                    Username = (?)""", symbol.upper(), nameuser)

            if symbol.upper() in symbol_list:
                shares += sharedb[0]['Shares']
                db.execute("""UPDATE stocks SET Shares = (?) WHERE Symbol = (?) AND Username = (?)""", shares, symbol.upper(), nameuser)
                total = float(symbol_price) * shares
                db.execute("""UPDATE stocks SET Total =(?) WHERE Symbol = (?) AND Username = (?)""", total, symbol.upper(), nameuser)

            elif symbol.upper() not in symbol_list:
                db.execute("""INSERT INTO stocks (Username, Symbol, Name, Shares, Price, Total)
                VALUES(?,?,?,?,?,?)""", nameuser, symbol.upper(), symbol_name, shares, usd(symbol_price), total)
            
        # Create a history table, if it doesn't already exist, to insert a history of transactions made
        db.execute("""CREATE TABLE IF NOT EXISTS history
                    (Username TEXT,
                     Symbol TEXT,
                     Shares NUMERIC,
                     Price NUMERIC,
                     Transacted SMALLDATETIME)"""
                   )
                   
        # INSERT the current transaction that was made into the history table 
        shares = int(request.form.get("shares"))
        db.execute("""INSERT INTO history (Username, Symbol, Shares, Price, Transacted)
                                          VALUES(?,?,?,?,DATETIME('now', 'localtime'))""", nameuser, symbol.upper(), shares, usd(symbol_price))
    
        # Redirect the user to the main page, which summarized the user's current stocks bought
        return redirect("/")

    # If method is GET:
    else:
        # Render the buy.html template
        return render_template("buy.html")

@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    
    # Get the current user that is logged into the session
    nameuser = session['username']
    
    # If the user clicks on the "History", try to return the history page at first
    try:
        # First query the db for all relevant info
        past_purchases = db.execute("""SELECT Symbol, Shares, Price, Transacted
                  FROM history WHERE Username = (?)""", nameuser)
                  
        # Then display it, passing in the query into the template
        return render_template("history.html", past_purchases=past_purchases)
    
    # If nothing is currently in the page, return an apology
    except:
        return apology("You haven't made any transactions yet!")

# Get page of username password (GET) then log user in (POST)
@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username, store it in rows
        # :username is dynamic, get what they typed in from username field
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        # rows[0]["id"] represents id of the first row (the user id)
        session["user_id"] = rows[0]["id"]

        # VERY IMPORTANT, WE NEED TO KNOW WHO THE CURRENT USER TO ENTER THE STOCKS THEY BOUGHT INTO THE TABLES
        session['username'] = request.form.get("username")

        # Redirect user to home page, after the user has logged in
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    # If they access the Quote tab, just show them the page where they can enter a symbol and ask for a quote
    if request.method == "GET":
        return render_template("quote.html")
    
    # Otherwise, it's a POST request, ie they enter the information into the form and click "Quote"
    else:
        # Get the symbol entered
        symbol = request.form.get("symbol").upper()
        
        # If nothing was entered but the Quote button was submitted, return an apology
        if not symbol:
            return apology("Please look up a stock")
        
        # Otherwise, lookup of the symbol, and pass in the dictionary to a template which displays the price, name, and symbol of the stock
        quote = lookup(symbol)
        return render_template("quoted.html", quote=quote)


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""


    if request.method == "GET":
        return render_template("register.html") #Display form that lets user register for an account

    # POST
    else:
        username = request.form.get("username")
        
        # Check if the username field is blank
        if not username:
            return apology("You must provide a valid username")
        
        handler = db.execute("SELECT username FROM users")

        # Check if the username entered matches a another user in the database. If it does, they have to pick a new username
        for user in handler:
            if user['username'] == username:
                return apology("Username has already been taken")
    
        password = request.form.get("password")
        
        # If no password entered, return an apology
        if not password:
            return apology("Enter a valid password")
        
        # Similary for the confirmation password
        confirmation = request.form.get("confirmation")
        if not confirmation:
            return apology("Please confirm your password")
        
        # If passwords don't match
        if password != confirmation:
            return apology("Passwords do not match")
        
        # Hash password for security 
        password_hash = generate_password_hash(password)

        # INSERT this information everytime a new user registers
        db.execute("INSERT INTO users (username, hash) VALUES (:username, :hash)", username=username, hash=password_hash)
        
        # Return to index page which displayed all the information of the stocks bought by user
        return redirect("/")
        
# Personal touch: Allow user to reset their password if they forgot it
@app.route("/reset", methods=["GET", "POST"])
def reset_password():
    
    # Once they click on the "Forgot Password", GET the page where they can enter information to change it
    if request.method == "GET":
        return render_template("reset.html")
    
    # POST: they filled out the form and clicked on "Reset Password"
    else:
        query_user = db.execute("SELECT username FROM users")
        
        username = request.form.get("username")
        
        user_list = []
        
        # Append all the list of users that currently exist in the db
        for user in query_user:
            user_list.append(user['username'].lower())
        
        # Make sure that they had an account so that their password can be changed
        if username not in user_list:
            return apology("Username not found")
        
        if not username:
            return apology("Please enter your username")
        
        # Similarly run checks for the confirmation password
        newpass = request.form.get("newpass")
        if not newpass:
            return apology("Please complete all fields")
        
        confirmpass = request.form.get("confirmpass")
        if not confirmpass:
            return apology("Please complete all fields")
            
        if newpass != confirmpass:
            return apology("Passwords do not match")
        
        # Generate a new password hash for that new password
        newpassword_hash = generate_password_hash(newpass)
        
        # Update the users db with that new password hash
        db.execute("""UPDATE users SET hash = (?) WHERE username = (?)""", newpassword_hash, username)
        
        # Redirect the user to the login page where they can enter their new password to login
        return render_template("login.html")

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    
    # User clicks on "Sell" bar, which returns them to a page where they can submit stocks they want to sell (GET)
    if request.method == "GET":
        return render_template("sell.html")

    # User fills out the form and submits is (POST)
    else:
        
        # This part is almost indentical to the /buy route
        symbol = request.form.get("symbol").upper()

        if not symbol or lookup(symbol) == None:
            return apology("Invalid symbol")
        
        # Get the share amount, which comes in as a string. e.g ('5')
        shares = request.form.get("shares")

        # Make sure the share amount is a positive integer
        if not shares.isdigit() or shares == '0':
            return apology("Please enter a positive share amount")

        if (not symbol or lookup(symbol) == None) and not shares:
            return apology("Please make sure both fields are completed")
        
        # Added this again because we need an integer to perform caluclations
        shares = int(request.form.get("shares"))

        # Grab the stock's name, price, and total price (shares * price)
        stock_info = lookup(symbol)
        symbol_name = stock_info["name"]
        symbol_price = float(stock_info["price"])
        total = float(int(shares) * symbol_price)
        
        # Since we are selling, want to format the shares to be negative in the history page
        temp_shares = "-" + str(shares)
        
        # Keep track of current user logged in the session
        nameuser = session['username']

        # Insert the above information into the history's table, with the Transacted column being
        # The current time the transaction was made
        db.execute("""INSERT INTO history (Username, Symbol, Shares, Price, Transacted)
                                          VALUES(?,?,?,?,DATETIME('now', 'localtime'))""", nameuser, symbol.upper(), temp_shares, usd(symbol_price))

        # Grab the existing share amount associated with the current stock entered for the current user
        query = db.execute("""SELECT Shares, Total FROM stocks WHERE Username = (?)
                              AND Symbol = (?)""", nameuser, symbol)
        
        # Check if the shares they want to sell exceed the shares they currently own, then return an apology message
        if shares > query[0]['Shares']:
            return apology("Cannot sell more shares than you own!")

        # Else, just subtract the current shares they own from the share amount they entered
        subtract_shares = query[0]['Shares'] - shares
        # Also subtract the current total from the total in the db
        subtract_total = query[0]['Total'] - total

        # If the user happens to sell all of that particular stock, make sure to delete that row from the database
        if subtract_shares == 0:
            db.execute("""DELETE FROM stocks WHERE Symbol = (?) AND Username = (?)""", symbol, nameuser)

        # Finally, UPDATE the stocks table with the new share amount for the current stock entered for the current user in session
        db.execute("""UPDATE stocks SET Shares = (?) WHERE Symbol = (?) and Username = (?)""", subtract_shares, symbol, nameuser)
        # UPDATE the stocks table with the new total amount for the current stock entered for the current user in session
        db.execute("""UPDATE stocks SET Total = (?) WHERE Symbol = (?) and Username = (?)""", subtract_total, symbol, nameuser)

        # Redirect the current user to the summary table page
        return redirect("/")

def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
