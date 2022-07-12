from asyncio.windows_events import NULL
from cProfile import run
from unicodedata import category
from flask import Blueprint, render_template, request,flash,redirect,url_for,jsonify,send_file,Response
from flask_login import login_required, current_user,login_user
from sqlalchemy import null
from .models import File, MasterAlertConfig,MasterAlertAudit,MasterResetHistory, MasterTicketCode, Question, Status, Ticket, User, Comment,TicketQuestionMap, Effort, TicketEffortMap
from . import db
from datetime import datetime,timedelta
import time
import smtplib, ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import json
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from configparser import ConfigParser

file = 'devconfig.ini'
config = ConfigParser()
config.read(file)
logopath = ''+str(config['logo']['path'])+''

views = Blueprint("views",__name__)

def run_query():
    query = 'ALTER TABLE public."User" DROP newcol'
    if(query):
        db.session.execute(str(query))
        db.session.commit()


@views.route("/")
@views.route("/home")
@login_required
def home():
    #run_query()
    yearago = str(datetime.today() - timedelta(days=365)).split(" ")[0]
    now = str(datetime.today()).split(" ")[0]
    assignees = User.query.filter_by(usertype="assignee").all()
    reporters = User.query.filter_by(usertype="reporter").all()
    statuses = Status.query.all()
    tickets_date_created = []
    tickets_date_closed = []
    if(current_user.usertype=="assignee"):
        tickets_closed = Ticket.query.filter(Ticket.assignee_id==current_user.id,Ticket.date_created>yearago).order_by(Ticket.date_created.asc()).all()
        for ticket in tickets_closed:
            tickets_date_closed.append(str(ticket.date_closed))
        tickets = Ticket.query.filter(Ticket.assignee_id==current_user.id,Ticket.date_created>yearago).order_by(Ticket.date_created.asc()).all()
        for ticket in tickets:
            tickets_date_created.append(str(ticket.date_created))
    elif(current_user.usertype=="reporter"):
        tickets = Ticket.query.filter(Ticket.author_id==current_user.id,Ticket.date_created>yearago).order_by(Ticket.date_created.asc()).all()
        for ticket in tickets:
            tickets_date_created.append(str(ticket.date_created))
            tickets_date_closed.append(str(ticket.date_closed))
    elif(current_user.usertype=="admin"):
        tickets = Ticket.query.filter(Ticket.date_created>yearago).order_by(Ticket.date_created.asc()).all()
        for ticket in tickets:
            tickets_date_created.append(str(ticket.date_created))
            tickets_date_closed.append(str(ticket.date_closed))
    count_vs_status = []
    for status in statuses :
        if current_user.usertype == 'assignee':
            count = Ticket.query.filter_by(status = status.status,assignee_id=current_user.id).count()
        elif current_user.usertype == 'reporter':
            count = Ticket.query.filter_by(status = status.status,author_id=current_user.id).count()
        else:
            count = Ticket.query.filter_by(status = status.status).count()
        stat_tuple = (count,status.status)
        count_vs_status.append(stat_tuple)
        prevpie = current_user.username
    else:
        prevpie = null
    return render_template("dashboard.html",user=current_user,logopath=logopath,count_vs_status=json.dumps(count_vs_status),tickets_date_created=json.dumps(tickets_date_created),tickets_date_closed=json.dumps(tickets_date_closed),assignees=assignees,reporters=reporters,prevstartdate=yearago,prevenddate=now,prevassignee=null,prevreporter=null,prevdatetype="created",prevpie=prevpie)


@views.route("/")
@views.route("/all-tickets")
@login_required
def all_tickets():
    if current_user.usertype == 'assignee':
        tickets = Ticket.query.filter_by(assignee_id=current_user.id).all()
    else:
        tickets = Ticket.query.all()
    return render_template("all_tickets.html",user=current_user,tickets=tickets,logopath=logopath)

@views.route("/")
@views.route("/alert-audit")
@login_required
def alert_audit():
    alertaudits = MasterAlertAudit.query.all()
    return render_template("alert_audit.html",user=current_user,alertaudits=alertaudits,logopath=logopath)


@views.route("/create-ticket",methods=['GET','POST'])
@login_required
def create_ticket():
    questions = Question.query.all()
    masteralertconfig = MasterAlertConfig.query.all()
    masterticketcode = MasterTicketCode.query.first()
    if(questions and masteralertconfig):
        if request.method == "POST":
            now = time.strftime("%d/%B/%Y %H:%M:%S")
            status= "Opened"
            ticket = Ticket(author_id = current_user.id,status=status,date_created=now,last_modified=now)
            custname = request.form.get("custname")
            title = request.form.get("title")
            region = request.form.get("region")
            startdate = request.form.get("startdate")
            ticket.custname = custname
            ticket.title = title
            ticket.region = region
            ticket.startdate = startdate
            ticket.ticket_code = masterticketcode.code
            db.session.add(ticket)
            if(custname and title and startdate and region):
                db.session.commit()
            else:
                flash("Enter required details",category="error")
                return redirect(url_for("views.create_ticket"))
            for question in questions:
                ticketquestionmap = TicketQuestionMap(ticket_id=ticket.id,question_id=question.id)
                db.session.add(ticketquestionmap)
                db.session.commit()
            for question in questions:
                answer = request.form.get("q"+str(question.id))
                map = TicketQuestionMap.query.filter_by(ticket_id=ticket.id,question_id=question.id).first()
                map.value = str(answer)
            if(custname and title and startdate and region):
                db.session.commit()
                alertmechanism("Opened", ticket.id)
            else:
                flash("Enter required details",category="error")
                return redirect(url_for("views.create_ticket"))
            return redirect(url_for("views.all_tickets"))
        return render_template("create_ticket.html",questions=questions,user=current_user,logopath=logopath)

    else:
        flash("Please complete Master Setup first",category="error")
        return redirect(url_for("views.home"))



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
    return render_template("ticketsby.html",user=current_user,tickets=tickets,username=username,logopath=logopath)


@views.route("/tickets/<ticket_id>")
@login_required
def tickets(ticket_id):
    efforts = Effort.query.order_by(Effort.id.asc()).all()
    assignees = User.query.filter_by(usertype='assignee').all()
    ticketquestionmaps = TicketQuestionMap.query.filter_by(ticket_id=ticket_id).order_by(TicketQuestionMap.id.asc()).all()
    ticketeffortmaps = TicketEffortMap.query.filter_by(ticket_id=ticket_id).order_by(TicketEffortMap.id.asc()).all()
    questions = Question.query.order_by(Question.id.asc()).all()
    statuses = Status.query.all()
    files_raw = File.query.filter_by(ticket_id=ticket_id).all()
    files_list = proc_files(files_raw,ticket_id)
    ticket = Ticket.query.filter_by(id=ticket_id).first()
    comments = Comment.query.filter(Comment.ticket_id==ticket_id).order_by(Comment.id.asc()).all()
    if not ticket:
        flash("Invalid ticket ID",category='error')
        return redirect(url_for('views.home'))
    return render_template("current_ticket.html",user=current_user,logopath=logopath,ticket=ticket,comments=comments,ticketquestionmaps=ticketquestionmaps,questions=questions,ticketeffortmaps=ticketeffortmaps,efforts=efforts,assignees=assignees,statuses=statuses,files_list=files_list)


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
            if(ticket.assignee_id):
                curr_assignee_id = ticket.assignee_id
                curr_assignee = User.query.filter_by(id=curr_assignee_id).first()
                curr_assignee.status="Available"
            output = request.get_json()
            result = json.loads(output)
            assignee_name = str(result)
            assignee = User.query.filter_by(username=assignee_name).first()
            assignee_id = assignee.id
            ticket.assignee_id = assignee_id
            ticket.status = "Assigned"
            ticket.date_assigned = now
            ticket.last_modified = now
            assignee.status = "Occupied"
            db.session.commit()
            alertmechanism(ticket.status, ticket.id)
            return redirect('/tickets/'+str(ticket_id))
    return redirect('/tickets/'+str(ticket_id))


@views.route("/update-status/<ticket_id>",methods=['GET','POST'])
@login_required
def update_status(ticket_id):
    ticketeffortmap = TicketEffortMap.query.filter_by(ticket_id=ticket_id).all()
    statuses = Status.query.all()
    if(statuses):
        pass
    else:
        flash("Please complete Master Setup first",category="error")
        return render_template("/tickets/"+ticket.id)
    now = time.strftime("%d/%B/%Y %H:%M:%S")
    ticket = Ticket.query.filter_by(id=ticket_id).first()
    oldstatus = ticket.status
    if not ticket:
        flash("Ticket does not exist", category='error')
    elif current_user.usertype == 'reporter':
        flash("You do not have permission to update status",category='error')
    elif current_user.id != ticket.assignee_id and current_user.usertype != 'admin':
        flash("You are not the assignee assigned to this ticket",category='error')
    else:
        if request.method == "POST":
            output = request.get_json()
            result = json.loads(output)
            status = str(result)
            if(status=="Closed"):
                if(ticketeffortmap):
                    ticket.assignee.status = "Available"
                    ticket.date_closed = now
                else:
                    #flash("Please do effort estimation before closing ticket",category="error")
                    return redirect('/tickets/'+str(ticket_id))
            ticket.status = status
            ticket.last_modified = now
            comment_text = "Ticket Status changed from '"+str(oldstatus)+"' to '"+str(status)+"'"
            comment = Comment(text=str(comment_text),author=current_user.id,ticket_id=ticket_id,date_created=now)
            db.session.add(comment) 
            db.session.commit()
            alertmechanism(ticket.status, ticket.id)
            #flash("Status updated",category='success')
            return redirect('/tickets/'+str(ticket_id))
    return redirect('/tickets/'+str(ticket_id))

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
    efforts = Effort.query.order_by(Effort.id.asc()).all()
    ticket = Ticket.query.filter_by(id=ticket_id).first()
    ticketeffortmaps = TicketEffortMap.query.filter_by(ticket_id=ticket_id).all()
    if request.method == "POST":
        if(efforts):
            for effort in efforts:
                answer = request.form.get("e"+str(effort.id))
                map = TicketEffortMap.query.filter_by(ticket_id=ticket.id,effort_id=effort.id).first()
                map.value = str(answer)
            comment = Comment(text="Effort Estimation Details Updated",author=current_user.id,ticket_id=ticket_id,date_created=now)
            db.session.add(comment) 
            db.session.commit()
        else:
            flash("Please complete Master Setup first",category="error")
        return redirect('/tickets/'+str(ticket_id))
    if(TicketEffortMap.query.filter_by(ticket_id=ticket_id).first()):
        reason = "So that duplicate mapping not created"
    else:
        for effort in efforts:
            ticketeffortmap = TicketEffortMap(ticket_id=ticket_id,effort_id=effort.id)
            db.session.add(ticketeffortmap)
        db.session.commit()
    return render_template("estimate_details.html",ticket=ticket,efforts=efforts,user=current_user,logopath=logopath,ticketeffortmaps=ticketeffortmaps)


@views.route("/edit-ticket/<ticket_id>",methods=['GET','POST'])
@login_required
def edit_ticket(ticket_id):
    questions = Question.query.order_by(Question.id.asc()).all()
    statuses = Status.query.order_by(Status.id.asc()).all()
    efforts = Effort.query.order_by(Effort.id.asc()).all()
    ticketquestionmaps = TicketQuestionMap.query.filter_by(ticket_id=ticket_id).all()
    ticketeffortmaps = TicketEffortMap.query.filter_by(ticket_id=ticket_id).all()
    now = time.strftime("%d/%B/%Y %H:%M:%S")
    ticket = Ticket.query.filter_by(id=ticket_id).first()
    assignees = User.query.filter_by(usertype='assignee').all()
    if not ticket:
        flash("Ticket does not exist", category='error')
    else:
        if request.method == "POST":
            if(current_user.usertype=='reporter'):
                custname = request.form.get('custname')
                title = request.form.get('title')
                region = request.form.get('region')
                startdate = request.form.get('startdate')
                ticket.custname=custname
                ticket.title=title
                ticket.region=region
                ticket.startdate=startdate
                ticket.last_modified = now
                if(custname and title and region and startdate):    
                    db.session.commit()
                else:
                    flash("Enter required details",category="error")
                    return redirect('/edit-ticket/'+str(ticket_id))
                for question in questions:
                    answer = request.form.get("q"+str(question.id))
                    map = TicketQuestionMap.query.filter_by(ticket_id=ticket.id,question_id=question.id).first()
                    if(map):
                        map.value = str(answer)
                if(custname and title and region and startdate):    
                    comment = Comment(text="Ticket was edited",author=current_user.id,ticket_id=ticket_id,date_created=now)
                    db.session.add(comment)
                    db.session.commit()
                else:
                    flash("Enter required details",category="error")
                    return redirect('/edit-ticket/'+str(ticket_id))

            elif(current_user.usertype=='assignee'):
                custname = request.form.get('custname')
                title = request.form.get('title')
                region = request.form.get('region')
                startdate = request.form.get('startdate')
                ticket.custname=custname
                ticket.title=title
                ticket.region=region
                ticket.startdate=startdate
                ticket.last_modified = now
                if(custname and title and region and startdate):    
                    db.session.commit()
                else:
                    flash("Enter required details",category="error")
                    return redirect('/edit-ticket/'+str(ticket_id))
                for question in questions:
                    qanswer = request.form.get("q"+str(question.id))
                    qmap = TicketQuestionMap.query.filter_by(ticket_id=ticket.id,question_id=question.id).first()
                    if(qmap):
                        qmap.value = str(qanswer)
                for effort in efforts:
                    eanswer = request.form.get("e"+str(effort.id))
                    emap = TicketEffortMap.query.filter_by(ticket_id=ticket.id,effort_id=effort.id).first()
                    if(emap):
                        emap.value = str(eanswer)
                if(custname and title and region and startdate):
                    comment = Comment(text="Ticket was edited",author=current_user.id,ticket_id=ticket_id,date_created=now)
                    db.session.add(comment) 
                    db.session.commit()
                else:
                    flash("Enter required details",category="error")
                    return redirect('/edit-ticket/'+str(ticket_id))
            else:
                custname = request.form.get('custname')
                title = request.form.get('title')
                region = request.form.get('region')
                startdate = request.form.get('startdate')
                ticket.custname=custname
                ticket.title=title
                ticket.region=region
                ticket.startdate=startdate
                ticket.last_modified = now
                if(custname and title and region and startdate):    
                    db.session.commit()
                else:
                    flash("Enter required details",category="error")
                    return redirect('/edit-ticket/'+str(ticket_id))
                for question in questions:
                    qanswer = request.form.get("q"+str(question.id))
                    qmap = TicketQuestionMap.query.filter_by(ticket_id=ticket.id,question_id=question.id).first()
                    if(qmap):
                        qmap.value = str(qanswer)
                for effort in efforts:
                    eanswer = request.form.get("e"+str(effort.id))
                    emap = TicketEffortMap.query.filter_by(ticket_id=ticket.id,effort_id=effort.id).first()
                    if(emap):
                        emap.value = str(eanswer)
                if(custname and title and region and startdate):
                    comment = Comment(text="Ticket was edited",author=current_user.id,ticket_id=ticket_id,date_created=now)
                    db.session.add(comment)    
                    db.session.commit()
                else:
                    flash("Enter required details",category="error")
                    return redirect('/edit-ticket/'+str(ticket_id))
            return redirect('/tickets/'+str(ticket_id))

    return render_template('edit_ticket.html',user=current_user,logopath=logopath,assignees = assignees,ticket=ticket,efforts=efforts,statuses=statuses,questions=questions,ticketquestionmaps=ticketquestionmaps,ticketeffortmaps=ticketeffortmaps)


@views.route("/reopen-ticket/<ticket_id>",methods=['GET'])
@login_required
def reopen_ticket(ticket_id):
    ticket = Ticket.query.filter_by(id=ticket_id).first()
    ticket.status = "Opened"
    ticket.date_closed = None
    db.session.commit()
    return redirect('/tickets/'+str(ticket_id))


@views.route("/master-question-home",methods=['GET','POST'])
@login_required
def master_question_home():
    questions = Question.query.all()
    return render_template('master_question.html',user=current_user,logopath=logopath,questions=questions)

@views.route("/master-question",methods=['POST'])
@login_required
def master_question():
    now = time.strftime("%d/%B/%Y %H:%M:%S")
    if request.method == "POST":
        output = request.get_json()
        for ele in output:
            if(str(ele["value"])!=""):
                question = Question(question=str(ele["value"]),date_created=now,author_id=current_user.id)
                db.session.add(question)
            else:
                flash("Please fill question field",category="error")
            db.session.commit()
    return redirect('/master')

@views.route("/delete-question/<question_id>",methods=['GET'])
@login_required
def delete_question(question_id):
    question = Question.query.filter_by(id=question_id).first()
    if(TicketQuestionMap.query.filter_by(question_id=question.id).first()):
        flash("This question cannot be deleted since some tickets are using it", category='error')
        return redirect('/master-question-home')
    db.session.delete(question)
    db.session.commit()
    return redirect('/master-question-home')

@views.route("/master-status-home",methods=['GET','POST'])
@login_required
def master_status_home():
    statuses = Status.query.all()
    return render_template('master_status.html',user=current_user,logopath=logopath,statuses=statuses)

@views.route("/master-status",methods=['POST'])
@login_required
def master_status():
    now = time.strftime("%d/%B/%Y %H:%M:%S")
    if request.method == "POST":
        output = request.get_json()
        for ele in output:
            status = Status(status=str(ele["value"]),date_created=now,author_id=current_user.id)
            db.session.add(status)
            db.session.commit()
            
    return redirect('/master')

@views.route("/delete-status/<status_id>",methods=['GET'])
@login_required
def delete_status(status_id):
    status = Status.query.filter_by(id=status_id).first()
    if(Ticket.query.filter_by(status=status.status).first()):
        flash("This status cannot be deleted since some tickets are using it", category='error')
        return redirect('/master-status-home')
    db.session.delete(status)
    db.session.commit()
    return redirect('/master-status-home')


@views.route("/master-effort-home",methods=['GET','POST'])
@login_required
def master_effort_home():
    efforts = Effort.query.all()
    return render_template('master_effort.html',logopath=logopath,user=current_user,efforts=efforts)

@views.route("/master-effort",methods=['POST'])
@login_required
def master_effort():
    now = time.strftime("%d/%B/%Y %H:%M:%S")
    if request.method == "POST":
        output = request.get_json()
        for ele in output:
            if(str(ele["value"])!=""):
                effort = Effort(effort=str(ele["value"]),date_created=now,author_id=current_user.id)
                db.session.add(effort)
            db.session.commit()
    return redirect('/master')

@views.route("/delete-effort/<effort_id>",methods=['GET'])
@login_required
def delete_effort(effort_id):
    effort = Effort.query.filter_by(id=effort_id).first()
    if(TicketEffortMap.query.filter_by(effort_id=effort.id).first()):
        flash("This effort cannot be deleted since some tickets are using it", category='error')
        return redirect('/master-effort-home')
    db.session.delete(effort)
    db.session.commit()
    return redirect('/master-effort-home')


@views.route("/master-alert-home",methods=['GET','POST'])
@login_required
def master_alert_home():
    alerts = MasterAlertConfig.query.all()
    statuses = Status.query.all()
    if request.method == 'POST':
        ticket_status = request.form.get('ticket_status')
        alert_subject = request.form.get('alert_subject')
        alert_body = request.form.get('alert_body')
        body_type = request.form['body_type']
        recipients = request.form.get('recipients')
        curr = MasterAlertConfig.query.filter_by(ticket_status=ticket_status).first()
        if(curr):
            curr.alert_subject = alert_subject
            curr.alert_body = alert_body
            curr.body_type = body_type
            curr.recipients = recipients
            db.session.commit()
            flash("Alert config updated",category="success")
            return redirect('/master-alert-home')
        else:
            alert = MasterAlertConfig(ticket_status=ticket_status,alert_subject=alert_subject,alert_body=alert_body,body_type=body_type,recipients=recipients)
            db.session.add(alert)
            db.session.commit()
            return redirect('/master-alert-home')

    return render_template('master_alert.html',user=current_user,logopath=logopath,alerts=alerts,statuses=statuses)


@views.route("/delete-alert/<alert_id>",methods=['GET'])
@login_required
def delete_alert(alert_id):
    alert = MasterAlertConfig.query.filter_by(id=alert_id).first()
    db.session.delete(alert)
    db.session.commit()
    return redirect('/master-alert-home')

@views.route("/master-reset-home",methods=['GET'])
@login_required
def master_reset_home():
    admins = User.query.filter_by(usertype = "admin").all()
    resets = MasterResetHistory.query.all()
    return render_template('master_reset.html',resets=resets,logopath=logopath,user=current_user,admins=admins)

@views.route("/master-reset",methods=['GET'])
@login_required
def master_reset():
    now = time.strftime("%d/%B/%Y %H:%M:%S")
    MasterAlertConfig.query.delete()
    MasterAlertAudit.query.delete()
    Comment.query.delete()
    File.query.delete()
    TicketEffortMap.query.delete()
    TicketQuestionMap.query.delete()
    Effort.query.delete()
    Question.query.delete()
    Status.query.delete()
    Ticket.query.delete()
    User.query.filter_by(usertype="reporter").delete()
    User.query.filter_by(usertype="assignee").delete()
    newreset = MasterResetHistory(reset_by=current_user.id,reset_on=now)
    db.session.add(newreset)
    db.session.commit()
    return redirect('/master-reset-home')

@views.route("/master-ticketcode-home",methods=['GET','POST'])
@login_required
def master_ticketcode_home():
    now = time.strftime("%d/%B/%Y %H:%M:%S")
    if(Status.query.all()):
        pass
    else:
        status1 = Status(status="Opened",date_created=now)
        status2 = Status(status="Assigned",date_created=now)
        status3 = Status(status="In-Review",date_created=now)
        status4 = Status(status="Closed",date_created=now)
        db.session.add(status1)
        db.session.add(status2)
        db.session.add(status3)
        db.session.add(status4)
        db.session.commit()
    if(Effort.query.all()):
        pass
    else:
        effort1 = Effort(effort="Total Effort(Hours)",date_created=now)
        effort2 = Effort(effort="Total Cost($)",date_created=now)
        db.session.add(effort1)
        db.session.add(effort2)
        db.session.commit()
    masterticketcode = MasterTicketCode.query.first()
    if(masterticketcode):
        pass
    else:
        masterticketcode = MasterTicketCode()
        db.session.add(masterticketcode)
    if request.method == 'POST':
        ticketcode = request.form.get('ticketcode')
        masterticketcode.code = ticketcode
        db.session.commit()
    return render_template('master_ticketcode.html',user=current_user,logopath=logopath,ticket_code=masterticketcode.code)

import PIL.Image as Image
import io
import base64
import numpy as np
import cv2

@views.route("/attach-file/<ticket_id>",methods=['POST'])
@login_required
def attach_file(ticket_id):
    upload = request.files['upload']
    if not upload:
        return 'No pic uploaded!', 400

    filename = secure_filename(upload.filename)
    mimetype =upload.mimetype
    if not filename or not mimetype:
        return 'Bad upload!', 400

    file = File(data=upload.read(), name=filename, mimetype=mimetype,ticket_id=ticket_id)
    db.session.add(file)
    db.session.commit()
    return redirect('/tickets/'+str(ticket_id))


@views.route("/delete-file/<file_id>",methods=['GET'])
@login_required
def delete_file(file_id):
    file = File.query.filter_by(id=file_id).first()
    ticket_id = file.ticket_id
    db.session.delete(file)
    db.session.commit()
    return redirect('/tickets/'+str(ticket_id))

@views.route("/download-file/<file_id>",methods=['GET'])
@login_required
def download_file(file_id):
    file = File.query.filter_by(id=file_id).first()
    ticket_id = file.ticket_id
    if(file):
        return send_file(io.BytesIO(file.data),attachment_filename=file.name,as_attachment=True)
    else:
        flash("File not found",category="error")
        return redirect('/tickets/'+str(ticket_id))

@views.route("/display-image/<file_id>",methods=['GET'])
@login_required
def display_image(file_id):
    file = File.query.filter_by(id=file_id).first()
    npimg = np.fromstring(file.data, np.uint8)
    img = cv2.imdecode(npimg,cv2.IMREAD_COLOR)
    img = Image.fromarray(img.astype("uint8"))
    rawBytes = io.BytesIO()
    img.save(rawBytes, "JPEG")
    rawBytes.seek(0)
    img_base64 = base64.b64encode(rawBytes.read())
    img_base64 = str(img_base64).lstrip('b')
    img_base64 = str(img_base64).strip("'")
    return render_template("display_image.html",user=current_user,logopath=logopath,imgsrc=img_base64)

def proc_files(files_raw,ticket_id):
    files_list=[]
    for file_raw in files_raw:
        if(str(file_raw.ticket_id) == str(ticket_id) and (file_raw.mimetype=="image/jpeg" or file_raw.mimetype=="image/png")):
            npimg = np.fromstring(file_raw.data, np.uint8)
            img = cv2.imdecode(npimg,cv2.IMREAD_COLOR)
            img = Image.fromarray(img.astype("uint8"))
            rawBytes = io.BytesIO()
            img.save(rawBytes, "JPEG")
            rawBytes.seek(0)
            img_base64 = base64.b64encode(rawBytes.read())
            img_base64 = str(img_base64).lstrip('b')
            img_base64 = str(img_base64).strip("'")
            imgtuple = (img_base64,file_raw.id,file_raw.mimetype)
            files_list.append(imgtuple)
        else:
            filetuple = (file_raw.name,file_raw.id,file_raw.mimetype)
            files_list.append(filetuple)
    return files_list

def alertmechanism(ticket_status, ticket_id):
    current = MasterAlertConfig.query.filter_by(ticket_status=ticket_status).first()
    ticket = Ticket.query.filter_by(id = ticket_id).first()
    ticket_code = ticket.ticket_code
    admins = User.query.filter_by(usertype = "admin").all()
    reporter_id = ticket.author_id
    assignee_id = ticket.assignee_id
    reporter = User.query.filter_by(id = reporter_id).first()
    reporter_email = reporter.email
    assignee = User.query.filter_by(id = assignee_id).first()
    if(assignee):
        assignee_email = assignee.email
    else:
        assignee_email = ""
    alertsub =  current.alert_subject
    alertbody = current.alert_body
    alertbody = alertbody.replace("<ticket_id>",str(ticket_code)+str(ticket_id))
    alertbody = alertbody.replace("<ticket_status>",str(ticket_status))
    body_type = current.body_type
    recipients = current.recipients
    arr = recipients.split(";")
    recipients_email = ""
    for i  in range(len(arr)) :

        if arr[i] == "reporter" :
            recipients_email  = recipients_email + ";" + reporter_email
        
        elif arr[i] == "assignee" :
            recipients_email  = recipients_email + ";" +  assignee_email
        elif arr[i] == 'admin':
            for admin in admins:
                admin_email = admin.email
                recipients_email  = recipients_email + ";" +  admin_email
                
       
    recipients_email = recipients_email.strip(";")
    emailaudit = MasterAlertAudit(ticket_status = ticket_status , alert_subject  = alertsub , alert_body = alertbody , recipients = str(recipients_email) )
    #emailbysmtp(recipients_email , alertsub , alertbody , body_type)
    db.session.add(emailaudit)
    db.session.commit()

@views.route("/viewprofile",methods=['GET','POST'])
@login_required
def view_profile():   
    if request.method == 'POST':
        password1 = request.form.get("password1")
        password2 = request.form.get("password2")
        if password1 != password2:
            flash('Passwords do not match',category='error')
        elif len(password1) < 6:
            flash('Password is too short',category='error')
        else:
            user=current_user
            password = generate_password_hash(password1,method="sha256")
            user.password=password
            db.session.commit()
            login_user(user,remember=True)
            flash('Password changed successfully')
            return redirect(url_for('views.home'))
    return render_template('viewprofile.html',logopath=logopath,user=current_user)

@views.route("/forgot-password",methods=['GET','POST'])
def forgot_password(): 
    if request.method == 'POST':
        username=request.form.get("username")
        password1 = request.form.get("password1")
        password2 = request.form.get("password2")
        if password1 != password2:
            flash('Passwords do not match',category='error')
        elif len(password1) < 6:
            flash('Password is too short',category='error')
        else:
            user=User.query.filter_by(username=username).first()
            password = generate_password_hash(password1,method="sha256")
            user.password=password
            db.session.commit()
            login_user(user,remember=True)
            flash('Password changed successfully')
            return redirect(url_for('views.home'))
    return render_template('forgotpassword.html',user=current_user,logopath=logopath)

def emailbysmtp(recipients_email , alertsub , alertbody , body_type):
    arr = recipients_email.split(";")
    sender_email = ''+str(config['email']['sendermail'])+''
    password = ''+str(config['email']['senderpwd'])+''
    for i in arr :
        receiver_email = str(i)
    
        message = MIMEMultipart("alternative")
        message["Subject"] = alertsub
        message["From"] = sender_email
        message["To"] = receiver_email
        if(body_type == 'HTML'):
            html = alertbody
            part1 = MIMEText(html, "html")
            message.attach(part1)
        else:
            text = alertbody
            part2 = MIMEText(text, "text")
            message.attach(part2)

        context = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.login(sender_email, password)
            server.sendmail(
                sender_email, receiver_email, message.as_string()
            )


import xlwt

@views.route("/export-audit",methods=['GET','POST'])
@login_required
def export_audit():
    audits = MasterAlertAudit.query.all()
    output = io.BytesIO()
    workbook = xlwt.Workbook()
    sh = workbook.add_sheet('Alert Audit')
    sh.write(0, 0, 'Id')
    sh.write(0, 1, 'Ticket Status')
    sh.write(0, 2, 'Alert Subject')
    sh.write(0, 3, 'Alert Body')
    sh.write(0, 4, 'Recipients')
    sh.write(0, 5, 'Sent On')

    idx = 0
    for audit in audits:
        sh.write(idx+1, 0, str(audit.id))
        sh.write(idx+1, 1, audit.ticket_status)
        sh.write(idx+1, 2, audit.alert_subject)
        sh.write(idx+1, 3, audit.alert_body)
        sh.write(idx+1, 4, audit.recipients)
        sh.write(idx+1, 5, str(audit.sent_on))
        idx += 1
    
    workbook.save(output)
    output.seek(0)
    return Response(output, mimetype="application/ms-excel", headers={"Content-Disposition":"attachment;filename=alert_audit.xls"})




@views.route("/export-alltickets",methods=['GET','POST'])
@login_required
def export_alltickets():
    tickets = Ticket.query.all()
    questions = Question.query.all()
    efforts = Effort.query.all()
    output = io.BytesIO()
    workbook = xlwt.Workbook()
    sh = workbook.add_sheet('All Tickets')
    sh.write(0, 0, 'Ticket Number')
    sh.write(0, 1, 'Customer Name')
    sh.write(0, 2, 'Reporter Name')
    sh.write(0, 3, 'Current Status')
    sh.write(0, 4, 'Assignee Name')
    sh.write(0, 5, 'Requirement Title')
    sh.write(0, 6, 'Region')
    sh.write(0, 7, 'Approx Start Date')
    sh.write(0, 8, 'Created On')
    sh.write(0, 9, 'Assigned On')
    sh.write(0, 10, 'Closed On')
    sh.write(0, 11, 'Last Modified On')
    i=12
    for question in questions:
        sh.write(0,i,question.question)
        i=i+1
    for effort in efforts:
        sh.write(0,i,effort.effort)
        i=i+1
    idx = 0
    for ticket in tickets:
        sh.write(idx+1, 0, str(ticket.ticket_code)+str(ticket.id))
        sh.write(idx+1, 1, ticket.custname)
        sh.write(idx+1, 2, ticket.author.username)
        sh.write(idx+1, 3, ticket.status)
        if(ticket.assignee_id):
            sh.write(idx+1, 4, ticket.assignee.username)
        else:
            sh.write(idx+1, 4, "Not Assigned")
        sh.write(idx+1, 5, ticket.title)
        sh.write(idx+1, 6, ticket.region)
        sh.write(idx+1, 7, str(ticket.startdate))
        sh.write(idx+1, 8, str(ticket.date_created))
        sh.write(idx+1, 9, str(ticket.date_assigned))
        sh.write(idx+1, 10, str(ticket.date_closed))
        sh.write(idx+1, 11, str(ticket.last_modified))
        j=12
        for question in questions:
            ticketquestionmap = TicketQuestionMap.query.filter_by(ticket_id=ticket.id,question_id=question.id).first()
            if(ticketquestionmap):
                sh.write(idx+1, j, ticketquestionmap.value)
            else:
                sh.write(idx+1, j, "null")
            j=j+1
        
        for effort in efforts:
            ticketeffortmap = TicketEffortMap.query.filter_by(ticket_id=ticket.id,effort_id=effort.id).first()
            if(ticketeffortmap):
                sh.write(idx+1, j, ticketeffortmap.value)
            else:
                sh.write(idx+1, j, "null")
            j=j+1
        idx += 1
    
    workbook.save(output)
    output.seek(0)
    return Response(output, mimetype="application/ms-excel", headers={"Content-Disposition":"attachment;filename=all_tickets.xls"})


@views.route("/graph-settings",methods=['GET','POST'])
@login_required
def graph_settings():
    yearago = str(datetime.today() - timedelta(days=365)).split(" ")[0]
    assignees = User.query.filter_by(usertype="assignee").all()
    reporters = User.query.filter_by(usertype="reporter").all()
    statuses = Status.query.all()
    count_vs_status = []
    tickets_closed = Ticket.query.filter(Ticket.date_created>yearago).order_by(Ticket.date_created.asc()).all()
    tickets_date_closed = []
    for ticket in tickets_closed:
        tickets_date_closed.append(str(ticket.date_closed))
    for status in statuses :
        count = Ticket.query.filter_by(status = status.status).count()
        stat_tuple = (count,status.status)
        count_vs_status.append(stat_tuple)
    tickets_dates = []
    datetype = request.form.get("datebox")
    startdate = request.form.get('startdate')
    enddate = request.form.get('enddate')
    reporter = request.form.get('reporters')
    assignee = request.form.get('assignees')
    #if(startdate<yearago):
        #flash("Please enter start date less than a year ago",category="error")
    if(str(datetype)=="assigned"):
        if(startdate and enddate):
            tickets_created = Ticket.query.filter(Ticket.date_assigned>startdate,Ticket.date_assigned<enddate,Ticket.date_assigned>yearago).order_by(Ticket.date_created.asc()).all()
        elif(startdate):
            tickets_created = Ticket.query.filter(Ticket.date_assigned>startdate,Ticket.date_assigned>yearago).order_by(Ticket.date_created.asc()).all()
        elif(enddate):
            tickets_created = Ticket.query.filter(Ticket.date_assigned<enddate,Ticket.date_assigned>yearago).order_by(Ticket.date_created.asc()).all()
        else:
            tickets_created = Ticket.query.filter(Ticket.date_assigned>yearago).order_by(Ticket.date_created.asc()).all()
        for ticket in tickets_created:
            if(reporter and assignee):
                if(ticket.assignee):
                    if(ticket.author.username==reporter and ticket.assignee.username==assignee):
                        tickets_dates.append(str(ticket.date_assigned))
            elif(reporter):
                if(ticket.author.username==reporter):
                    tickets_dates.append(str(ticket.date_assigned))
            elif(assignee):
                if(ticket.assignee):
                    if(ticket.assignee.username==assignee):
                        tickets_dates.append(str(ticket.date_assigned))
            else:
                tickets_dates.append(str(ticket.date_assigned))
    else:
        if(startdate and enddate):
            tickets_created = Ticket.query.filter(Ticket.date_created>startdate,Ticket.date_created<enddate,Ticket.date_created>yearago).order_by(Ticket.date_created.asc()).all()
        elif(startdate):
            tickets_created = Ticket.query.filter(Ticket.date_created>startdate,Ticket.date_created>yearago).order_by(Ticket.date_created.asc()).all()
        elif(enddate):
            tickets_created = Ticket.query.filter(Ticket.date_created<enddate,Ticket.date_created>yearago).order_by(Ticket.date_created.asc()).all()
        else:
            tickets_created = Ticket.query.filter(Ticket.date_created>yearago).order_by(Ticket.date_created.asc()).all()
        for ticket in tickets_created:
            if(reporter and assignee):
                if(ticket.assignee):
                    if(ticket.author.username==reporter and ticket.assignee.username==assignee):
                        tickets_dates.append(str(ticket.date_created))
            elif(reporter):
                if(ticket.author.username==reporter):
                    tickets_dates.append(str(ticket.date_created))
            elif(assignee):
                if(ticket.assignee):
                    if(ticket.assignee.username==assignee):
                        tickets_dates.append(str(ticket.date_created))
            else:
                tickets_dates.append(str(ticket.date_created))
    return render_template("dashboard.html",user=current_user,logopath=logopath,count_vs_status=json.dumps(count_vs_status),tickets_date_created=json.dumps(tickets_dates),tickets_date_closed=json.dumps(tickets_date_closed),assignees=assignees,reporters=reporters,prevstartdate=startdate,prevenddate=enddate,prevassignee=assignee,prevreporter=reporter,prevdatetype=datetype,prevpie=null)



@views.route("/piegraph-settings",methods=['GET','POST'])
@login_required
def piegraph_settings():
    yearago = str(datetime.today() - timedelta(days=365)).split(" ")[0]
    tickets_created = Ticket.query.filter(Ticket.date_created>yearago).order_by(Ticket.date_created.asc()).all()
    tickets_date_created = []
    for ticket in tickets_created:
        tickets_date_created.append(str(ticket.date_created))
    assignees = User.query.filter_by(usertype="assignee").all()
    reporters = User.query.filter_by(usertype="reporter").all()
    statuses = Status.query.all()
    count_vs_status = []
    for status in statuses :
        count = Ticket.query.filter_by(status = status.status).count()
        stat_tuple = (count,status.status)
        count_vs_status.append(stat_tuple)
    assignee_name = request.form.get('pie_assignees')
    assignee = User.query.filter_by(username=assignee_name).first()
    if(assignee):
        assignee_id = assignee.id
        tickets_closed = Ticket.query.filter(Ticket.assignee_id==assignee_id,Ticket.date_closed>yearago).order_by(Ticket.date_created.asc()).all()
    else:
        tickets_closed = Ticket.query.filter(Ticket.date_closed>yearago).order_by(Ticket.date_created.asc()).all()
    tickets_dates_closed = []
    for ticket in tickets_closed:
        tickets_dates_closed.append(str(ticket.date_closed))
    return render_template("dashboard.html",user=current_user,logopath=logopath,count_vs_status=json.dumps(count_vs_status),tickets_date_created=json.dumps(tickets_date_created),tickets_date_closed=json.dumps(tickets_dates_closed),assignees=assignees,reporters=reporters,prevstartdate=null,prevenddate=null,prevassignee=null,prevreporter=null,prevdatetype="created",prevpie=assignee_name)


@views.route("/edit-effort/<effort_id>",methods=['POST'])
@login_required
def edit_effort(effort_id):
    now = time.strftime("%d/%B/%Y %H:%M:%S")
    effort = Effort.query.filter_by(id=effort_id).first()
    if request.method == "POST":
        output = request.get_json()
        result = json.loads(output)
        newtext = str(result["newtext"])
        effort.effort = newtext
        db.session.commit()
    return redirect('/master-effort-home')

@views.route("/edit-question/<question_id>",methods=['POST'])
@login_required
def edit_question(question_id):
    now = time.strftime("%d/%B/%Y %H:%M:%S")
    question = Question.query.filter_by(id=question_id).first()
    if request.method == "POST":
        output = request.get_json()
        result = json.loads(output)
        newtext = str(result["newtext"])
        question.question = newtext
        db.session.commit()
    return redirect('/master-question-home')

@views.route("/edit-status/<status_id>",methods=['POST'])
@login_required
def edit_status(status_id):
    now = time.strftime("%d/%B/%Y %H:%M:%S")
    status = Status.query.filter_by(id=status_id).first()
    if request.method == "POST":
        output = request.get_json()
        result = json.loads(output)
        newtext = str(result["newtext"])
        status.status = newtext
        db.session.commit()
    return redirect('/master-status-home')