from unicodedata import category
from flask import Blueprint, render_template, request,flash,redirect,url_for,jsonify
from flask_login import login_required, current_user
from .models import Ticket, User, Comment
from . import db
from datetime import datetime
import time
import json

views = Blueprint("views",__name__)

@views.route("/")
@views.route("/home")
@login_required
def home():
    if current_user.usertype == 'assignee':
        tickets = Ticket.query.filter_by(assignee_id=current_user.id).all()
    else:
        tickets = Ticket.query.all()
    return render_template("dashboard.html",user=current_user,tickets=tickets)


@views.route("/create-ticket",methods=['GET','POST'])
@login_required
def create_ticket():
    if request.method == "POST":
        custname = request.form.get('custname')
        custreq = request.form.get('custreq')
        status = "Ticket Created"
        if not custname or not custreq:
            flash("Please fill all fields",category='error')
        else:
            ticket = Ticket(custname=custname,custreq=custreq,author_id = current_user.id,status=status)
            db.session.add(ticket)
            db.session.commit()
            flash("Ticket Created",category='success')
            return redirect(url_for('views.home'))


    return render_template('create_ticket.html',user=current_user)


@views.route("/delete-ticket/<id>")
@login_required
def delete_ticket(id):
    now = time.strftime("%d/%B/%Y %H:%M:%S")
    ticket = Ticket.query.filter_by(id=id).first()

    if not ticket:
        flash("Ticket does not exist", category='error')
    elif current_user.id != ticket.author_id:
        flash("You do not have permission to delete this ticket",category='error')
    else:
        db.session.delete(ticket)
        ticket.last_modified = now
        db.session.commit()
        flash('Ticket Deleted',category='success')
    return redirect(url_for('views.home'))

@views.route("/ticketsby/<username>")
@login_required
def ticketsby(username):
    user = User.query.filter_by(username=username).first()
    if not user:
        flash("No user with that username exists",category='error')
        return redirect(url_for('views.home'))

    tickets = Ticket.query.filter_by(author_id=user.id).all()
    return render_template("ticketsby.html",user=current_user,tickets=tickets,username=username)


@views.route("/tickets/<ticket_id>")
@login_required
def tickets(ticket_id):
    ticket = Ticket.query.filter_by(id=ticket_id).first()
    comments = Comment.query.filter(Comment.ticket_id==ticket_id).order_by(Comment.id.asc()).all()
    if not ticket:
        flash("Invalid ticket ID",category='error')
        return redirect(url_for('views.home'))
    return render_template("current_ticket.html",user=current_user,ticket=ticket,comments=comments)


@views.route("/assign-assignee/<ticket_id>",methods=['GET','POST'])
@login_required
def assign_assignee(ticket_id):
    now = time.strftime("%d/%B/%Y %H:%M:%S")
    ticket = Ticket.query.filter_by(id=ticket_id).first()
    assignees = User.query.filter_by(usertype='assignee').all()
    if not ticket:
        flash("Ticket does not exist", category='error')
    elif current_user.usertype != 'admin':
        flash("You do not have permission to assign assignee",category='error')
    else:
        if request.method == "POST":
            assignee_name = request.form.get('assignee-name')
            status = "assignee assigned"
            assignee = User.query.filter_by(username=assignee_name).first()
            assignee_id = assignee.id
            ticket.assignee_id = assignee_id
            ticket.status = status
            ticket.last_modified = now
            assignee.status = "Occupied"
            db.session.commit()
            flash("assignee Assigned",category='success')
            return redirect('/tickets/'+str(ticket_id))
    
    return render_template('assign_assignee.html',user=current_user,assignees = assignees)


@views.route("/update-status/<ticket_id>",methods=['GET','POST'])
@login_required
def update_status(ticket_id):
    now = time.strftime("%d/%B/%Y %H:%M:%S")
    ticket = Ticket.query.filter_by(id=ticket_id).first()
    if not ticket:
        flash("Ticket does not exist", category='error')
    elif current_user.usertype != 'assignee':
        flash("You do not have permission to update status",category='error')
    elif current_user.id != ticket.assignee_id:
        flash("You are not the assignee assigned to this ticket",category='error')
    else:
        if request.method == "POST":
            status = request.form.get('status')
            ticket.status = status
            ticket.last_modified = now
            db.session.commit()
            if status == 'Completed':
                return redirect('/estimated-details/'+str(ticket.id))
            flash("Status updated",category='success')
            return redirect('/tickets/'+str(ticket_id))
    return render_template('update_status.html',user=current_user)

@views.route("create-comment/<ticket_id>",methods=['POST'])
@login_required
def create_comment(ticket_id):
    ticket = Ticket.query.filter_by(id=ticket_id).first()
    now = time.strftime("%d/%B/%Y %H:%M:%S")
    text = request.form.get('text')

    if not text:
        flash("Comment cannot be empty",category='error')
    else:
        if ticket:
            comment = Comment(text=text,author=current_user.id,ticket_id=ticket_id,date_created=now)
            db.session.add(comment)
            ticket.last_modified = now
            db.session.commit()
        else:
            flash("Post does not exist",category='error')

    return redirect('/tickets/'+str(ticket_id))


@views.route("/delete-comment/<comment_id>")
@login_required
def delete_comment(comment_id):
    now = time.strftime("%d/%B/%Y %H:%M:%S")
    comment = Comment.query.filter_by(id=comment_id).first()
    ticket_id = comment.ticket_id
    ticket = Ticket.query.filter_by(id=ticket_id).first()
    if not comment:
       flash("Comment does not exist", category='error')
    elif current_user.id != comment.author:
        flash("You are not authorized to delete this comment", category='error')
    else:
        comment.status = "Deleted"
        ticket.last_modified = now
        db.session.commit()
        
    return redirect('/tickets/'+str(ticket_id))

@views.route("/edit-comment/<comment_id>",methods=['POST'])
@login_required
def edit_comment(comment_id):
    now = time.strftime("%d/%B/%Y %H:%M:%S")
    comment = Comment.query.filter_by(id=comment_id).first()
    ticket_id = comment.ticket_id
    ticket = Ticket.query.filter_by(id=ticket_id).first()
    if not comment:
        flash("Comment does not exist", category='error')
    elif current_user.id != comment.author:
        flash("You do not have permission to update status",category='error')
    else:
        if request.method == "POST":
            output = request.get_json()
            result = json.loads(output)
            newtext = str(result["newtext"])
            comment.text = newtext
            comment.status = "Edited"
            ticket.last_modified = now
            db.session.commit()
            flash("Comment Edited",category='success')
    return redirect('/tickets/'+str(ticket_id))


@views.route("/estimated-details/<ticket_id>",methods=['GET','POST'])
@login_required
def estimated_details(ticket_id):
    now = time.strftime("%d/%B/%Y %H:%M:%S")
    ticket = Ticket.query.filter_by(id=ticket_id).first()
    if request.method == "POST":
        hours = request.form.get('hours')
        cost = request.form.get('cost')
        ticket.hours = hours
        ticket.cost = cost
        ticket.last_modified = now
        db.session.commit()
        flash("Estimated Details Updated",category='success')
        return redirect('/tickets/'+str(ticket_id))
    return render_template('estimate_details.html',user=current_user)

@views.route("/edit-ticket/<ticket_id>",methods=['GET','POST'])
@login_required
def edit_ticket(ticket_id):
    now = time.strftime("%d/%B/%Y %H:%M:%S")
    ticket = Ticket.query.filter_by(id=ticket_id).first()
    assignees = User.query.filter_by(usertype='assignee').all()
    if not ticket:
        flash("Ticket does not exist", category='error')
    else:
        if request.method == "POST":
            if(current_user.usertype=='reporter'):
                custname = request.form.get('custname')
                custreq = request.form.get('custreq')
                ticket.custname=custname
                ticket.custreq=custreq
                ticket.last_modified = now
                db.session.commit()
            elif(current_user.usertype=='assignee'):
                custname = request.form.get('custname')
                custreq = request.form.get('custreq')
                status = request.form.get('status')
                hours = request.form.get('hours')
                cost = request.form.get('cost')
                ticket.custname=custname
                ticket.custreq=custreq
                ticket.hours = hours
                ticket.status = status
                ticket.cost = cost
                ticket.last_modified = now
                db.session.commit()
            else:
                custname = request.form.get('custname')
                custreq = request.form.get('custreq')
                status = request.form.get('status')
                hours = request.form.get('hours')
                cost = request.form.get('cost')
                assignee_name = request.form.get('assignee-name')
                assignee = User.query.filter_by(username=assignee_name).first()
                assignee_id = assignee.id
                ticket.assignee_id = assignee_id
                ticket.custname=custname
                ticket.custreq=custreq
                ticket.hours = hours
                ticket.status = status
                ticket.cost = cost
                ticket.last_modified = now
                db.session.commit()
            return redirect('/tickets/'+str(ticket_id))

    return render_template('edit_ticket.html',user=current_user,assignees = assignees,ticket=ticket)