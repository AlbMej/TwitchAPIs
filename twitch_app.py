# -----------------------------------------------------------
# Creating REST APIs to test static CSV files for Twitch
#
# Alberto Mejia
# -----------------------------------------------------------
import json
import git
import numpy as np
import pandas as pd
import re, os, sqlite3
from datetime import datetime
from typing import List, Dict, Tuple
from flask_restful import Api
from flask import Flask, request, jsonify, abort

import hmac
import hashlib
import secret_config

# --- Get W_SECRET for GitHub Actions Deployment to PythonAnywhere
W_SECRET = secret_config.PYANY_WEBHOOK_SECRET


def is_valid_signature(x_hub_signature, data, private_key):
    # x_hub_signature and data are from the webhook payload
    # private key is your webhook secret
    hash_algorithm, github_signature = x_hub_signature.split('=', 1)
    algorithm = hashlib.__dict__.get(hash_algorithm)
    encoded_key = bytes(private_key, 'latin-1')
    mac = hmac.new(encoded_key, msg=data, digestmod=algorithm)
    return hmac.compare_digest(mac.hexdigest(), github_signature)


app = Flask(__name__)
api = Api(app)


@app.route("/")
def index():
    return "Twitch Static CSV API"


# --- Database Functions ---

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
    conn.commit()  # Commit changes

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
    conn.commit()  # Commit changes


# --- REST API Endpoints ---

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
        return ({'user': user}, 404)  # Not found
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
            date = datetime.strptime(bannedUntil, '%Y-%m-%d')  # .date()
            banned = date.isoformat(sep='T', timespec='milliseconds') + 'Z'

        if len(datetime_units) == 7:
            date = datetime.strptime(bannedUntil, '%Y-%m-%dT%H:%M:%S.%fZ')  # .date()
            banned = date.isoformat(sep='T', timespec='milliseconds') + 'Z'

    args = (banned, True, userId)  # Parameterized
    query = "UPDATE users SET banned_until =?, is_banned =? WHERE user_id ==?"
    print(f'Banning user {userId} till {banned}...', end=" ")
    try:
        result = cursor.execute(query, args)
        print(f"| {list(result)}")
        conn.commit()  # Commit changes
        return ('OK', 200)

    except Exception as e:
        print(f"Failed to ban user: {e}")
        return ('Failed to ban user', 400)  # Failure


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

    new_row = (user_id, userName, created_at, is_banned, banned_until)  # Args
    query = "INSERT INTO users VALUES(?, ?, ?, ?, ?)"
    print(f'Creating user {userName}...', end=" ")
    try:
        result = cursor.execute(query, new_row)
        print(f"| {list(result)}")
        conn.commit()  # Commit changes
        return ('Successively created user', 201)  # Created
    
    except Exception as e:
        print(f"Failed to create user: {e}")
        return ('Failed to create user', 400)  # Failure


# --- GitHub Webhook for PythonAnywhere Deployment ---
@app.route('/update_server', methods=['POST'])
def github_webhook():
    # Reference: https://medium.com/@aadibajpai/deploying-to-pythonanywhere-via-github-6f967956e664
    if request.method != 'POST':
        return 'OK'
    else:
        py_anywhere_source_code_dir = '/home/twitchapis/mysite'
        abort_code = 418
        # Do initial validations on required headers

        # Abort incomplete request. Request must be well formed
        if 'X-Github-Event' not in request.headers:
            abort(abort_code)

        # Abort. Invalid request
        if 'X-Github-Delivery' not in request.headers:
            abort(abort_code)

        # Abort. Unauthorized request
        if 'X-Hub-Signature' not in request.headers:
            abort(abort_code)

        # Abort if not JSON. Cannot parse the payload
        if not request.is_json:
            abort(abort_code)

        # Abort. Source cannot be identified
        if 'User-Agent' not in request.headers:
            abort(abort_code)

        # Abort if request does not come from GitHub's own webhook service
        ua = request.headers.get('User-Agent')
        if not ua.startswith('GitHub-Hookshot/'):
            abort(abort_code)

        event = request.headers.get('X-GitHub-Event')
        if event == "ping":
            return json.dumps({'msg': 'Hi!'})
        if event != "push":
            return json.dumps({'msg': "Wrong event type"})

        x_hub_signature = request.headers.get('X-Hub-Signature')
        # webhook content type should be application/json for request.data to have the payload
        # request.data is empty in case of x-www-form-urlencoded
        if not is_valid_signature(x_hub_signature, request.data, W_SECRET):
            print('Deploy signature failed: {sig}'.format(sig=x_hub_signature))
            abort(abort_code)  # Abort. Anyone with webhook URL could trigger a deployment on the server

        payload = request.get_json()
        if payload is None:
            print('Deploy payload is empty: {payload}'.format(
                payload=payload))
            abort(abort_code)

        if payload['ref'] != 'refs/heads/master':
            return json.dumps({'msg': 'Not master; ignoring'})

        repo = git.Repo(py_anywhere_source_code_dir)
        origin = repo.remotes.origin

        pull_info = origin.pull()

        if len(pull_info) == 0:
            return json.dumps({'msg': "Didn't pull any information from remote!"})
        if pull_info[0].flags > 128:
            return json.dumps({'msg': "Didn't pull any information from remote!"})

        commit_hash = pull_info[0].commit.hexsha
        build_commit = f'build_commit = "{commit_hash}"'
        print(f'{build_commit}')
        return 'Updated PythonAnywhere server to commit {commit}'.format(commit=commit_hash)


if __name__ == '__main__':
    try:
        create_table_from_static_csv()
    except Exception as e:
        print(f"Failed to create table from CSV: {e}")
    PORT = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=PORT, debug=True)  # Run Flask app
