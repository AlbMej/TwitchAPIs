# -----------------------------------------------------------
# Creating REST APIs to test static CSV files for Twitch
#
# Alberto Mejia
# -----------------------------------------------------------
import numpy as np
import pandas as pd
import re, os, sqlite3
from urllib.parse import urlencode
from datetime import datetime, date
from typing import List, Dict, Tuple
from flask_restful import Resource, Api, reqparse
from flask import Flask, request, render_template, flash, redirect, url_for, jsonify

app = Flask(__name__)
api = Api(app)

@app.route("/")
def index():
    return "Twitch Static CSV API"

def get_db_connection() -> Tuple[sqlite3.Connection, sqlite3.Cursor]:
    """
    Create sqlite database and cursor
    """
    conn = sqlite3.connect('twitch.db')
    cursor  = conn.cursor()
    return conn, cursor


def create_table_from_static_csv():
    """
    Creates the table from the static csv
    """
    print("Creating table from csv....")
    conn, cursor = get_db_connection()
    # cursor.execute("DROP TABLE users") # For local testing

    # IF NOT EXISTS
    create_table_query = '''CREATE TABLE users (
                            user_id INTEGER PRIMARY KEY UNIQUE,
                            user_name TEXT NOT NULL UNIQUE,
                            created_at TEXT NOT NULL,
                            is_banned INTEGER,
                            banned_until datetime)'''
    cursor.execute(create_table_query) 
    conn.commit() # Commit changes

    DATA_PATH = './db.csv'
    df = pd.read_csv(DATA_PATH)
    df.to_sql(name='users', con=conn, if_exists='append', index=False)
    print("Done!")


def get_all_records() -> List[Dict]:
    conn, cursor = get_db_connection()
    users = []
    data = cursor.execute("SELECT * FROM users").fetchall()
    for user in data:
        users.append(
            {
                "user_id":      user[0],
                "user_name":    user[1],
                "created_at":   user[2],
                "is_banned":    user[3],
                "banned_until": user[4],
            }
        )
    return users


def check_bans():
    """
    Checks to see if there are any users to unban. If so update their corresponding is_banned and banned_until.
    """
    users = get_all_records()
    current_time = datetime.utcnow().isoformat(sep='T', timespec='milliseconds') + 'Z'
    for user in users:
        if user['is_banned'] and user['banned_until'] is None:
            continue  # This is a perma ban

        if user['is_banned'] and user['banned_until'] is not None:
            if user['banned_until'] < current_time:
                unban_user(user['user_id'])  # Unban this user


def unban_user(userId: int):
    """
    Unban the user with the specified userId
    """
    print(f'Unbanning user {userId}...')
    conn, cursor = get_db_connection()
    args = (None, False, userId)
    query = "UPDATE users SET banned_until =?, is_banned =? WHERE user_id ==?"
    result = cursor.execute(query, args)
    conn.commit() # Commit changes


### REST APIs ###


@app.route("/api/all_records", methods=['GET'])
def AllRecords():
    """
    Returns all the user records in JSON form.
    """
    check_bans()
    users = get_all_records()
    return jsonify(users)


@app.route("/api/get_user/<string:userId>", methods=['GET'])
def GetUser(userId: str) -> str:
    """
    Args:
        userId: A ID of the user to get

    Returns:
        The User corresponding to userID
    """
    check_bans()
    conn, cursor = get_db_connection()
    query = "SELECT * FROM users WHERE user_id ==?"
    args = (userId, )
    result = cursor.execute(query, args).fetchone()
    print(f'Getting user {userId}...  | {result}')
    user = []
    if result is None:
        # return ('', 404)
        return ({'user': user}, 404) # Not found
    else:
        user.append({
                        "user_id":      result[0],
                        "user_name":    result[1],
                        "created_at":   result[2],
                        "is_banned":    result[3],
                        "banned_until": result[4],
                    })
        return ({'user': user}, 200)  


@app.route("/api/list_users", methods=['GET'])
def ListUsers() -> List[str]:
    """
    Returns:
        A list of non-banned users sorted by account creation date
    """
    check_bans()
    conn, cursor = get_db_connection()
    query = f"SELECT * FROM users WHERE is_banned != {True}"
    result = cursor.execute(query).fetchall()
    users = []

    print(f'Listing users... | {result}')  
    if result == []:
        return ({'nonBannedUsers': users}, 404)
    else:
        for user in result:
            users.append(
                {
                    "user_id":      user[0],
                    "user_name":    user[1],
                    "created_at":   user[2],
                    "is_banned":    user[3],
                    "banned_until": user[4],
                }
            )
        return ({'nonBannedUsers': users}, 200)


@app.route("/api/ban_user/<string:userId>", methods=['PUT'])
@app.route("/api/ban_user/<string:userId>,<string:bannedUntil>", methods=['PUT'])
def BanUser(userId: str, bannedUntil: str = None):
    """
    Args:
        userId: A ID of the user to ban
        
        bannedUntil:
            Date denoting the end date of a user's ban (month/date/year)
            If None then user is permanently banned
    """
    check_bans()
    conn, cursor = get_db_connection()
    banned = np.nan
    if bannedUntil is not None:
        datetime_units = re.split("[-/T:. ]", bannedUntil)
        if len(datetime_units) == 3: 
            date = datetime.strptime(bannedUntil, '%Y-%m-%d')#.date()
            banned = date.isoformat(sep='T', timespec='milliseconds') + 'Z'
        
        if len(datetime_units) == 7:
            date = datetime.strptime(bannedUntil,'%Y-%m-%dT%H:%M:%S.%fZ')#.date()
            banned = date.isoformat(sep='T', timespec='milliseconds') + 'Z'

    args = (banned, True, userId) # Parameterized 
    query = "UPDATE users SET banned_until =?, is_banned =? WHERE user_id ==?"
    print(f'Banning user {userId} till {banned}...', end=" ")
    try:
        result = cursor.execute(query, args)
        print(f"| {list(result)}")
        conn.commit() # Commit changes
        return ('OK', 200)

    except:
        print("Failed to create user")
        return ('Failed to ban user', 400) # Failure

    conn.commit() # Commit changes


@app.route("/api/create_user/<string:userName>", methods=['POST'])
def CreateUser(userName: str):
    """
    Args:
        userName: The username of the new user to create

    Returns:
        The User corresponding to userID
    """
    check_bans()
    conn, cursor = get_db_connection()
    user_id = None       # Primary Key type handles ID generation (ROWID)
    created_at = datetime.utcnow().isoformat(sep='T', timespec='milliseconds') + 'Z'
    is_banned = False    # A new user is unbanned
    banned_until = None

    new_row = (user_id, userName, created_at, is_banned, banned_until) # Args
    query = "INSERT INTO users VALUES(?, ?, ?, ?, ?)"
    print(f'Creating user {userName}...', end=" ")
    try:
        result = cursor.execute(query, new_row)
        print(f"| {list(result)}")
        conn.commit() # Commit changes
        return ('Successively created user', 201) # Created

    except:
        print("Failed to create user")
        return ('Failed to create user', 400)     # Failure
    

if __name__ == '__main__':
    try:
        create_table_from_static_csv()
    except:
        None
    PORT = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=PORT, debug=True)  # Run Flask app