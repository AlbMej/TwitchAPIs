# Twitch Application

Feel free to access the application at: https://twitchapis.pythonanywhere.com/

To run the application locally review the sections below.

## Setup

### Docker 

Since the project is containerized using Docker, in your terminal simply run: `docker compose up`

This will build and start the container. The port in use is 5000. In case of port errors, refer to the last section titled Common Issues

### Stopping the container

To stop the container:
1. Hit `CTRL+C` in the terminal to stop said container

Sometimes this hangs so if it does, refer to 2. and 3.

2. `docker ps` to get the container id of the running container
3. `docker stop <CONTAINER ID>` to kill the container

### To run it without Docker, you need to have Python 3 installed (Virtual environments are optional but recommended).

1. Create a virtual Python environment. For this project, I chose virtualenv. For virtualenv we do so by running the command:

    `virtualenv env --python=python3.9`

2. Activate your virtual environment:

    `. env/bin/activate`

3. Install the dependencies via

    `pip install -r requirements.txt`

    or 

    `pip3 install -r requirements.txt`

    Depending on which version python each pip points to. 

## REST API Endpoints

### Locally
| # | Endpoints                                                    | HTTP Method | Description                                                  |
|---|--------------------------------------------------------------|-------------|--------------------------------------------------------------|
| 1 | http://localhost:5000/api/all_records                        | GET         | Get all the user records in JSON format                      |
| 2 | http://localhost:5000/api/get_user/<userId\>                 | GET         | Get a single user whose ID matches the supplied one          |
| 3 | http://localhost:5000/api/list_users                         | GET         | Get the list of all non-banned users sorted by creation date |
| 4 | http://localhost:5000/api/ban_user/<userId\>,<bannedUntil\>  | PUT         | Update the user with userId to ban status                    |
| 5 | http://localhost:5000/api/create_user/<userName\>            | POST        | Create a new user record with the supplied userName          |

### Deployed Application
| # | Endpoints                                                          | HTTP Method | Description                                                  |
|---|--------------------------------------------------------------------|-------------|--------------------------------------------------------------|
| 1 | https://twitchapis.pythonanywhere.com/api/all_records              | GET         | Get all the user records in JSON format                      |
| 2 | https://twitchapis.pythonanywhere.com/api/get_user/<userId\>       | GET         | Get a single user whose ID matches the supplied one          |
| 3 | https://twitchapis.pythonanywhere.com/api/list_users               | GET         | Get the list of all non-banned users sorted by creation date |
| 4 | https://twitchapis.pythonanywhere.com/api/<userId\>,<bannedUntil\> | PUT         | Update the user with userId to ban status                    |
| 5 | https://twitchapis.pythonanywhere.com/api/<userName\>              | POST        | Create a new user record with the supplied userName          |

## API Usage Notes

When running the project locally, the IP address in use can be found in the terminal output of the running application. Localhost is usually `127.0.0.1`

The bannedUntil parameter is required to be in one of the following formats:

- Year-month-day: `YYYY-MM-DD` | Ex: "2023-04-20"
- The datetime + UTC format found in the csv: `YYYY-MM-DD:Thh:mm:ss.msZ` | Ex: "2019-05-20T16:41:59.832Z"

NOTE: The bans are handled in UTC time, thus the bannedUntil parameter should be given in UTC time to avoid confusion.

## Regarding bans

When have a couple of options:

    1. We can leverage a scheduler to handle the unbanning task
    2. Use the asyncio library to write an asynchronous function that checks all bans based on the current time for every elapsed time period x.
    3. Whenever the user tries to access some content/perform some action, query the database to check their ban status and time.
        3.1. If it is still before the user's `banned_until` datetime, the user remains banned
        3.2. If the `banned_until` datetime has elaspsed, unban said user (set `is_banned` to False and `banned_until` to null)

For simplicity sakes, the project mimics the 3rd option by querying the database whenever there is a call to any of the REST APIs.

To improve upon this we could have another table in the database for all the banned users. It could include things like ban reason, time of ban, banned_until, etc.
We query this table instead (since we could have a lot of users in the main table). Then, when we unban users we update the main table (and if wanted we could remove them from the banned table).

## Project Submission

- Project is zipped ✅
- Seed CSV file is located at the root of the project ✅
- Instructions for running code included in this README ✅
    - Project is containerized ✅
- Instructions for downloading 3rd party dependencies provided in README ✅
- No binary artifacts in submission ✅

## Common Issues

If you're port is in use, refer to: https://stackoverflow.com/questions/39322089/node-js-port-3000-already-in-use-but-it-actually-isnt

