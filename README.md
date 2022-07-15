# Scoping_Automation

## Requirements:

Python Modules to be installed:
- Flask
- flask_login
- flask_sqlalchemy
- psycopg2
- pillow
- opencv-python
- xlwt

## Libraries Used

* [Werkzeug](https://werkzeug.palletsprojects.com/en/2.1.x/) - It is used to create a WSGI (Web Server Gateway Interface) compatible web application in Python.
* [Flask_login](https://flask-login.readthedocs.io/en/latest/) - Flask-Login provides user session management for Flask. It handles the common tasks of logging in, logging     out, and remembering your users'.

## Installation

Install Flask using pip command : 'pip install flask'.
 Steps to run:
 * Install all modules given above using pip
 * Connect with local PostgreSQL database:
    * Install PostgreSQL
    * Open pgAdmin4
    * Create new database and name it "TicketDemo"
    * Open init.py and update the following line with your password:' 'postgresql://postgres:(password)@localhost/TicketDemo' '

## Connect PostgreSQL Using Python
```python
def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = "Any key"
    app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:(password)@localhost/TicketDemo'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)
```
## Create Database Using Python
```python
def create_database(app):
    if not path.exists("website/TicketDemo"):
        #db.drop_all(app=app)
        db.create_all(app=app)
        #print("Created database")
```
## Run
```python
from website import create_app

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
 ```
 
Useful Links 
* [How to install PIP for Python on Windows, Mac and Linux](https://www.makeuseof.com/tag/install-pip-for-python/)
