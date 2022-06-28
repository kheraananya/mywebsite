# Scoping_Automation
# Requirements:

Python Modules to be installed:
- Flask
- flask_sqlalchemy
- psycopg2

Steps to run:
1. Install all modules given above using pip
2. Connect with local PostgreSQL database:
    - Install PostgreSQL
    - Open pgAdmin4
    - Create new database and name it "TicketDemo"
    - Open init.py and update the following line with your password: 'postgresql://postgres:(password)@localhost/TicketDemo'
3. Run app.py
