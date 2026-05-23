from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
import mysql.connector
from datetime import date, datetime
import random
import os

app = Flask(__name__)
app.secret_key = "banking_secret_2024"

def get_db():
    return mysql.connector.connect(
        host=os.environ.get("MYSQLHOST", "localhost"),
        user=os.environ.get("MYSQLUSER", "root"),
        password=os.environ.get("MYSQLPASSWORD", "Pass@123"),
        database=os.environ.get("MYSQLDATABASE", "banking_system"),
        port=int(os.environ.get("MYSQLPORT", 3306))
    )

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        db = get_db()
        cur = db.cursor(dictionary=True)
        cur.execute("SELECT * FROM users WHERE username=%s AND password=%s", (username, password))
        user = cur.fetchone()
        if user:
            session["user"] = user["username"]
            session["role"] = user["role"]
            return redirect(url_for("dashboard"))
        flash("Wrong username or password!")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect(url_for("login"))
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT COUNT(*) AS c FROM customers")
    customers = cur.fetchone()["c"]
    cur.execute("SELECT COUNT(*) AS c FROM accounts")
    accounts = cur.fetchone()["c"]
    cur.execute("SELECT COALESCE(SUM(balance),0) AS s FROM accounts")
    balance = cur.fetchone()["s"]
    cur.execute("SELECT COUNT(*) AS c FROM transactions")
    txns = cur.fetchone()["c"]
    cur.execute("SELECT t.transaction_id, t.account_number, t.transaction_type, t.amount, t.transaction_date, c.name FROM transactions t LEFT JOIN accounts a ON t.account_number=a.account_number LEFT JOIN customers c ON a.customer_id=c.customer_id ORDER BY t.transaction_date DESC LIMIT 8")
    recent = cur.fetchall()
    return render_template("dashboard.html", customers=customers, accounts=accounts, balance=balance, txns=txns, recent=recent)

@app.route("/customers")
def customers():
    if "user" not in session:
        return redirect(url_for("login"))
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT c.customer_id, c.name, c.phone, c.email, a.account_number, a.account_type, a.balance, a.created_date FROM customers c JOIN accounts a ON c.customer_id=a.customer_id ORDER BY c.customer_id DESC")
    data = cur.fetchall()
    return render_template("customers.html", customers=data)

@app.route("/new-account", methods=["GET", "POST"])
def new_account():
    if "user" not in session:
        return redirect(url_for("login"))
    if request.method == "POST":
        name = request.form["name"]
        phone = request.form["phone"]
        email = request.form["email"]
        address = request.form["address"]
        acc_type = request.form["acc_type"]
        db = get_db()
        cur = db.cursor()
        cur.execute("INSERT INTO customers (name,phone,email,address,created_date) VALUES (%s,%s,%s,%s,%s)", (name, phone, email, address, date.today()))
        db.commit()
        cid = cur.lastrowid
        acc_num = "ACC" + str(random.randint(100000, 999999))
        cur.execute("INSERT INTO accounts (account_number,customer_id,account_type,balance,created_date) VALUES (%s,%s,%s,0,%s)", (acc_num, cid, acc_type, date.today()))
        db.commit()
        flash("Account " + acc_num + " created for " + name + "!")
        return redirect(url_for("customers"))
    return render_template("new_account.html")

@app.route("/deposit", methods=["GET", "POST"])
def deposit():
    if "user" not in session:
        return redirect(url_for("login"))
    if request.method == "POST":
        acc = request.form["account"]
        amt = float(request.form["amount"])
        db = get_db()
        cur = db.cursor(dictionary=True)
        cur.execute("SELECT * FROM accounts WHERE account_number=%s", (acc,))
        if not cur.fetchone():
            flash("Account not found!")
            return redirect(url_for("deposit"))
        cur2 = db.cursor()
        cur2.execute("UPDATE accounts SET balance=balance+%s WHERE account_number=%s", (amt, acc))
        cur2.execute("INSERT INTO transactions (account_number,transaction_type,amount,transaction_date,description) VALUES (%s,'deposit',%s,%s,'Cash Deposit')", (acc, amt, datetime.now()))
        db.commit()
        flash("Rs." + str(amt) + " deposited successfully!")
        return redirect(url_for("dashboard"))
    return render_template("transaction.html", type="deposit")

@app.route("/withdraw", methods=["GET", "POST"])
def withdraw():
    if "user" not in session:
        return redirect(url_for("login"))
    if request.method == "POST":
        acc = request.form["account"]
        amt = float(request.form["amount"])
        db = get_db()
        cur = db.cursor(dictionary=True)
        cur.execute("SELECT * FROM accounts WHERE account_number=%s", (acc,))
        account = cur.fetchone()
        if not account:
            flash("Account not found!")
            return redirect(url_for("withdraw"))
        if float(account["balance"]) < amt:
            flash("Insufficient balance!")
            return redirect(url_for("withdraw"))
        cur2 = db.cursor()
        cur2.execute("UPDATE accounts SET balance=balance-%s WHERE account_number=%s", (amt, acc))
        cur2.execute("INSERT INTO transactions (account_number,transaction_type,amount,transaction_date,description) VALUES (%s,'withdraw',%s,%s,'Cash Withdrawal')", (acc, amt, datetime.now()))
        db.commit()
        flash("Rs." + str(amt) + " withdrawn successfully!")
        return redirect(url_for("dashboard"))
    return render_template("transaction.html", type="withdraw")

@app.route("/transfer", methods=["GET", "POST"])
def transfer():
    if "user" not in session:
        return redirect(url_for("login"))
    if request.method == "POST":
        from_acc = request.form["from_account"]
        to_acc = request.form["to_account"]
        amt = float(request.form["amount"])
        db = get_db()
        cur = db.cursor(dictionary=True)
        cur.execute("SELECT * FROM accounts WHERE account_number=%s", (from_acc,))
        src = cur.fetchone()
        cur.execute("SELECT * FROM accounts WHERE account_number=%s", (to_acc,))
        dst = cur.fetchone()
        if not src or not dst:
            flash("Account not found!")
            return redirect(url_for("transfer"))
        if float(src["balance"]) < amt:
            flash("Insufficient balance!")
            return redirect(url_for("transfer"))
        cur2 = db.cursor()
        cur2.execute("UPDATE accounts SET balance=balance-%s WHERE account_number=%s", (amt, from_acc))
        cur2.execute("UPDATE accounts SET balance=balance+%s WHERE account_number=%s", (amt, to_acc))
        cur2.execute("INSERT INTO transactions (account_number,transaction_type,amount,transaction_date,description) VALUES (%s,'transfer',%s,%s,%s)", (from_acc, amt, datetime.now(), "Transfer to " + to_acc))
        cur2.execute("INSERT INTO transactions (account_number,transaction_type,amount,transaction_date,description) VALUES (%s,'transfer',%s,%s,%s)", (to_acc, amt, datetime.now(), "Transfer from " + from_acc))
        db.commit()
        flash("Rs." + str(amt) + " transferred successfully!")
        return redirect(url_for("dashboard"))
    return render_template("transfer.html")

@app.route("/transactions")
def transactions():
    if "user" not in session:
        return redirect(url_for("login"))
    acc = request.args.get("acc", "")
    db = get_db()
    cur = db.cursor(dictionary=True)
    if acc:
        cur.execute("SELECT * FROM transactions WHERE account_number=%s ORDER BY transaction_date DESC", (acc,))
    else:
        cur.execute("SELECT * FROM transactions ORDER BY transaction_date DESC LIMIT 50")
    data = cur.fetchall()
    return render_template("transactions.html", transactions=data, acc=acc)

@app.route("/loans")
def loans():
    if "user" not in session:
        return redirect(url_for("login"))
    db = get_db()
    cur = db.cursor(dictionary=True)
    try:
        cur.execute("SELECT l.*, c.name FROM loans l JOIN accounts a ON l.account_number=a.account_number JOIN customers c ON a.customer_id=c.customer_id ORDER BY l.loan_id DESC")
        data = cur.fetchall()
    except:
        data = []
    return render_template("loans.html", loans=data)

@app.route("/api/balance/<acc>")
def api_balance(acc):
    if "user" not in session:
        return jsonify({"error": "not logged in"}), 401
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT a.account_number, a.balance, a.account_type, c.name FROM accounts a JOIN customers c ON a.customer_id=c.customer_id WHERE a.account_number=%s", (acc,))
    row = cur.fetchone()
    if row:
        row["balance"] = float(row["balance"])
        return jsonify(row)
    return jsonify({"error": "not found"}), 404

if __name__ == "__main__":
    app.run(debug=True)