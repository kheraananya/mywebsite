from asyncio import constants
from time import timezone
from . import db
from flask_login import UserMixin
import sqlalchemy
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
    comments = db.relationship('Comment',backref='User',passive_deletes=True)
    status = db.Column(db.String(20))


class Ticket(db.Model):
    __tablename__ = 'Ticket'
    id = db.Column(db.Integer, primary_key=True)
    custname = db.Column(db.String(2000))
    title = db.Column(db.String(2000))
    region = db.Column(db.String(200))
    date_created = db.Column(db.DateTime, default = time.strftime("%d/%B/%Y %H:%M:%S"))
    last_modified = db.Column(db.DateTime, default = time.strftime("%d/%B/%Y %H:%M:%S"))
    author_id = db.Column(db.Integer, db.ForeignKey('User.id',ondelete="CASCADE"),nullable=False)
    assignee_id = db.Column(db.Integer, db.ForeignKey('User.id',ondelete="CASCADE"),nullable=True)
    author = db.relationship("User",foreign_keys=[author_id])
    assignee = db.relationship("User",foreign_keys=[assignee_id])
    status = db.Column(db.String(200))
    comments = db.relationship('Comment',backref='Ticket',passive_deletes=True)

class Comment(db.Model):
    __tablename__ = 'Comment'
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text,nullable=False)
    date_created = db.Column(db.DateTime, default = time.strftime("%d-%b-%Y %H:%M:%S") , index =True)
    author = db.Column(db.Integer, db.ForeignKey(
        'User.id', ondelete="CASCADE"),nullable=False)
    ticket_id = db.Column(db.Integer, db.ForeignKey(
        'Ticket.id', ondelete="CASCADE"),nullable=False)
    status = db.Column(db.String(20))

class TicketQuestionMap(db.Model):
    __tablename__ = 'TicketQuestionMap'
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey('Ticket.id', ondelete="CASCADE"),nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('Question.id', ondelete="CASCADE"),nullable=False)
    value = db.Column(db.String(2000))

class TicketEffortMap(db.Model):
    __tablename__ = 'TicketEffortMap'
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey('Ticket.id', ondelete="CASCADE"),nullable=False)
    effort_id = db.Column(db.Integer, db.ForeignKey('Effort.id', ondelete="CASCADE"),nullable=False)
    value = db.Column(db.String(2000))
    

class Question(db.Model):
    __tablename__ = 'Question'
    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.String(2000),nullable=False)
    date_created = db.Column(db.DateTime, default = time.strftime("%d/%B/%Y %H:%M:%S"))
    author_id = db.Column(db.Integer, db.ForeignKey('User.id',ondelete="CASCADE"),nullable=False)

class Effort(db.Model):
    __tablename__ = 'Effort'
    id = db.Column(db.Integer, primary_key=True)
    effort = db.Column(db.String(2000),nullable=False)
    date_created = db.Column(db.DateTime, default = time.strftime("%d/%B/%Y %H:%M:%S"))
    author_id = db.Column(db.Integer, db.ForeignKey('User.id',ondelete="CASCADE"),nullable=False)

class Status(db.Model):
    __tablename__ = 'Status'
    id = db.Column(db.Integer, primary_key=True)
    status = db.Column(db.String(2000),nullable=False)
    date_created = db.Column(db.DateTime, default = time.strftime("%d/%B/%Y %H:%M:%S"))
    author_id = db.Column(db.Integer, db.ForeignKey('User.id',ondelete="CASCADE"),nullable=False)

class MasterAlertConfig(db.Model):
    __tablename__ = 'MasterAlertConfig'
    id = db.Column(db.Integer, primary_key=True)
    ticket_status = db.Column(db.String(200))
    alert_subject = db.Column(db.String(500))
    alert_body = db.Column(db.String(5000))
    body_type =  db.Column(db.String(100))
    recipients = db.Column(db.String(200))

class MasterAlertAudit(db.Model):
    __tablename__ = 'MasterAlertAudit'
    id = db.Column(db.Integer, primary_key=True)
    ticket_status = db.Column(db.String(200))
    alert_subject = db.Column(db.String(500))
    alert_body = db.Column(db.String(5000))
    recipients = db.Column(db.String(200))
    sent_on = db.Column(db.DateTime, default = time.strftime("%d/%B/%Y %H:%M:%S"))

class File(db.Model):
    __tablename__ = 'File'
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.LargeBinary)
    name = db.Column(db.Text, nullable=False)
    mimetype = db.Column(db.Text, nullable=False)
    ticket_id = db.Column(db.Integer, db.ForeignKey('Ticket.id', ondelete="CASCADE"),nullable=False)

class MasterResetHistory(db.Model):
    __tablename__ = 'MasterResetHistory'
    id = db.Column(db.Integer, primary_key=True)
    reset_by = db.Column(db.Integer, db.ForeignKey('User.id',ondelete="CASCADE"),nullable=False)
    reset_on = db.Column(db.DateTime, default = time.strftime("%d/%B/%Y %H:%M:%S"))