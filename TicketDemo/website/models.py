from time import timezone
from . import db
from flask_login import UserMixin
from sqlalchemy.sql import func
from datetime import datetime
import datetime
import time

class User(db.Model, UserMixin):
    __tablename__ = 'User'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150),unique=True)
    username = db.Column(db.String(150),unique=True)
    password = db.Column(db.String(150))
    usertype = db.Column(db.String(20))
    date_created = db.Column(db.DateTime, default = time.strftime("%d/%B/%Y %H:%M:%S") )
    #tickets = db.relationship('Ticket', backref='User',passive_deletes=True)
    #consulted = db.relationship('Ticket', backref='User',passive_deletes=True)
    comments = db.relationship('Comment',backref='User',passive_deletes=True)


class Ticket(db.Model):
    __tablename__ = 'Ticket'
    id = db.Column(db.Integer, primary_key=True)
    custname = db.Column(db.String(150),unique=True)
    custreq = db.Column(db.String(150))
    date_created = db.Column(db.DateTime, default = time.strftime("%d/%B/%Y %H:%M:%S"))
    author_id = db.Column(db.Integer, db.ForeignKey('User.id',ondelete="CASCADE"),nullable=False)
    consultant_id = db.Column(db.Integer, db.ForeignKey('User.id',ondelete="CASCADE"),nullable=True)
    author = db.relationship("User",foreign_keys=[author_id])
    consultant = db.relationship("User",foreign_keys=[consultant_id])
    status = db.Column(db.String(150))
    comments = db.relationship('Comment',backref='Ticket',passive_deletes=True)
    hours = db.Column(db.Float)
    cost = db.Column(db.Float)

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(200),nullable=False)
    date_created = db.Column(db.DateTime, default = time.strftime("%d-%b-%Y %H:%M:%S") , index =True)
    author = db.Column(db.Integer, db.ForeignKey(
        'User.id', ondelete="CASCADE"),nullable=False)
    ticket_id = db.Column(db.Integer, db.ForeignKey(
        'Ticket.id', ondelete="CASCADE"),nullable=False)
    status = db.Column(db.String(20))