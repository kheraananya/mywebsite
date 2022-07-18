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
 
 ## Steps to Deploy:

 * Install all modules given above using pip
 * Connect with PostgreSQL database on server:
    * Install PostgreSQL
    * Open pgAdmin4
    * Create new database and name it accordingly, depending on the team deploying (Example: CAMPSCO for Campaign Team)
    * Open init.py and update the following line with your password:' 'postgresql://postgres:(password)@localhost/(database_name)' '

## Connect PostgreSQL Using Python
```python
def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = "Any key"
    app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:(password)@localhost/(database_name)'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)
```

## Run
```python
from website import create_app

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
 ```
 
 ## Steps to Alter Database Schema
 
 * Run the SQL ALTER query inside pgAdmin4
 * Document the query inside DB_Queries.sql in the template format provided
 
Useful Links 
* [How to install PIP for Python on Windows, Mac and Linux](https://www.makeuseof.com/tag/install-pip-for-python/)
