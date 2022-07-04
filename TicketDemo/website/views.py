from unicodedata import category
from flask import Blueprint, render_template, request,flash,redirect,url_for,jsonify
from flask_login import login_required, current_user,login_user
from .models import ImageDB, MasterAlertConfig,MasterAlertAudit,MasterResetHistory, Question, Status, Ticket, User, Comment,TicketQuestionMap, Effort, TicketEffortMap
from . import db
from datetime import datetime
import time
import json
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash


views = Blueprint("views",__name__)

@views.route("/")
@views.route("/home")
@login_required
def home():
    alertaudits = MasterAlertAudit.query.all()
    if current_user.usertype == 'assignee':
        tickets = Ticket.query.filter_by(assignee_id=current_user.id).all()
    else:
        tickets = Ticket.query.all()
    return render_template("dashboard.html",user=current_user,tickets=tickets,alertaudits=alertaudits)


@views.route("/create-ticket",methods=['GET','POST'])
@login_required
def create_ticket():
    questions = Question.query.all()
    masteralertconfig = MasterAlertConfig.query.all()
    if(questions and masteralertconfig):
        if request.method == "POST":
            now = time.strftime("%d/%B/%Y %H:%M:%S")
            status= "Opened"
            ticket = Ticket(author_id = current_user.id,status=status,date_created=now,last_modified=now)
            custname = request.form.get("custname")
            title = request.form.get("title")
            region = request.form.get("region")
            ticket.custname = custname
            ticket.title = title
            ticket.region = region
            db.session.add(ticket)
            db.session.commit()
            for question in questions:
                ticketquestionmap = TicketQuestionMap(ticket_id=ticket.id,question_id=question.id)
                db.session.add(ticketquestionmap)
            db.session.commit()
            for question in questions:
                answer = request.form.get("q"+str(question.id))
                map = TicketQuestionMap.query.filter_by(ticket_id=ticket.id,question_id=question.id).first()
                map.value = str(answer)
            if(custname and title):
                db.session.commit()
                alertmechanism("Opened", ticket.id)
            else:
                flash("Enter required details",category="error")
            return redirect(url_for("views.home"))

        return render_template("create_ticket.html",questions=questions,user=current_user)

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
    return render_template("ticketsby.html",user=current_user,tickets=tickets,username=username)


@views.route("/tickets/<ticket_id>")
@login_required
def tickets(ticket_id):
    efforts = Effort.query.all()
    assignees = User.query.filter_by(usertype='assignee').all()
    ticketquestionmaps = TicketQuestionMap.query.filter_by(ticket_id=ticket_id).all()
    ticketeffortmaps = TicketEffortMap.query.filter_by(ticket_id=ticket_id).all()
    questions = Question.query.all()
    statuses = Status.query.all()
    images_raw = ImageDB.query.all()
    images_list = proc_image(images_raw,ticket_id)
    ticket = Ticket.query.filter_by(id=ticket_id).first()
    comments = Comment.query.filter(Comment.ticket_id==ticket_id).order_by(Comment.id.asc()).all()
    if not ticket:
        flash("Invalid ticket ID",category='error')
        return redirect(url_for('views.home'))
    return render_template("current_ticket.html",user=current_user,ticket=ticket,comments=comments,ticketquestionmaps=ticketquestionmaps,questions=questions,ticketeffortmaps=ticketeffortmaps,efforts=efforts,assignees=assignees,statuses=statuses,images_list=images_list)


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
                    pass
                else:
                    flash("Please do effort estimation before closing ticket",category="error")
                    return redirect('/tickets/'+str(ticket_id))
            ticket.status = status
            ticket.last_modified = now
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
    efforts = Effort.query.all()
    ticket = Ticket.query.filter_by(id=ticket_id).first()
    if request.method == "POST":
        if(efforts):
            for effort in efforts:
                answer = request.form.get("e"+str(effort.id))
                map = TicketEffortMap.query.filter_by(ticket_id=ticket.id,effort_id=effort.id).first()
                map.value = str(answer)
            db.session.commit()
        else:
            flash("Please complete Master Setup first",category="error")
        return redirect(url_for("views.home"))
    if(TicketEffortMap.query.filter_by(ticket_id=ticket_id).first()):
        reason = "So that duplicate mapping not created" 
    else:
        for effort in efforts:
            ticketeffortmap = TicketEffortMap(ticket_id=ticket_id,effort_id=effort.id)
            db.session.add(ticketeffortmap)
        db.session.commit()
    return render_template("estimate_details.html",ticket=ticket,efforts=efforts,user=current_user)


@views.route("/edit-ticket/<ticket_id>",methods=['GET','POST'])
@login_required
def edit_ticket(ticket_id):
    questions = Question.query.all()
    statuses = Status.query.all()
    efforts = Effort.query.all()
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
                ticket.custname=custname
                ticket.title=title
                ticket.last_modified = now
                for question in questions:
                    answer = request.form.get("q"+str(question.id))
                    map = TicketQuestionMap.query.filter_by(ticket_id=ticket.id,question_id=question.id).first()
                    if(map):
                        map.value = str(answer)
                db.session.commit()

            elif(current_user.usertype=='assignee'):
                custname = request.form.get('custname')
                title = request.form.get('title')
                status = request.form.get('status')
                ticket.custname=custname
                ticket.title=title
                ticket.status = status
                ticket.last_modified = now
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
                db.session.commit()
            else:
                custname = request.form.get('custname')
                title = request.form.get('title')
                status = request.form.get('status')
                ticket.custname=custname
                ticket.title=title
                ticket.status = status
                ticket.last_modified = now
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
                db.session.commit()
            return redirect('/tickets/'+str(ticket_id))

    return render_template('edit_ticket.html',user=current_user,assignees = assignees,ticket=ticket,efforts=efforts,statuses=statuses,questions=questions,ticketquestionmaps=ticketquestionmaps,ticketeffortmaps=ticketeffortmaps)


@views.route("/reopen-ticket/<ticket_id>",methods=['GET'])
@login_required
def reopen_ticket(ticket_id):
    ticket = Ticket.query.filter_by(id=ticket_id).first()
    ticket.status = "Opened"
    db.session.commit()
    return redirect('/tickets/'+str(ticket_id))


@views.route("/master",methods=['GET'])
@login_required
def master():
    if(current_user.usertype!="admin"):
        flash("You do not have admin access to this page", category='error')
        return redirect('/home')
    return render_template('master.html',user=current_user)

    

@views.route("/master-question-home",methods=['GET','POST'])
@login_required
def master_question_home():
    questions = Question.query.all()
    return render_template('master_question.html',user=current_user,questions=questions)

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
    return render_template('master_status.html',user=current_user,statuses=statuses)

@views.route("/master-status",methods=['POST'])
@login_required
def master_status():
    now = time.strftime("%d/%B/%Y %H:%M:%S")
    if request.method == "POST":
        output = request.get_json()
        for ele in output:
            if(Status.query.all()):
                pass
            else:
                status1 = Status(status="Opened",date_created=now,author_id=current_user.id)
                status2 = Status(status="Assigned",date_created=now,author_id=current_user.id)
                status3 = Status(status="In-Review",date_created=now,author_id=current_user.id)
                status4 = Status(status="Closed",date_created=now,author_id=current_user.id)
                db.session.add(status1)
                db.session.add(status2)
                db.session.add(status3)
                db.session.add(status4)
                db.session.commit()
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
    return render_template('master_effort.html',user=current_user,efforts=efforts)

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
        recipients = request.form.get('recipients')
        if(MasterAlertConfig.query.filter_by(ticket_status=ticket_status).first()):
            flash("Status already exists",category="error")
            return redirect('/master-alert-home')
        alert = MasterAlertConfig(ticket_status=ticket_status,alert_subject=alert_subject,alert_body=alert_body,recipients=recipients)
        db.session.add(alert)
        db.session.commit()
        return redirect('/master-alert-home')

    return render_template('master_alert.html',user=current_user,alerts=alerts,statuses=statuses)


@views.route("/delete-alert/<alert_id>",methods=['GET'])
@login_required
def delete_alert(alert_id):
    alert = MasterAlertConfig.query.filter_by(id=alert_id).first()
    db.session.delete(alert)
    db.session.commit()
    return redirect('/master-alert-home')


import PIL.Image as Image
import io
import base64
import numpy as np
import cv2

@views.route("/attach-image/<ticket_id>",methods=['POST'])
@login_required
def attach_image(ticket_id):
    pic = request.files['pic']
    if not pic:
        return 'No pic uploaded!', 400

    filename = secure_filename(pic.filename)
    mimetype = pic.mimetype
    if not filename or not mimetype:
        return 'Bad upload!', 400

    img = ImageDB(img=pic.read(), name=filename, mimetype=mimetype,ticket_id=ticket_id)
    db.session.add(img)
    db.session.commit()
    return redirect('/tickets/'+str(ticket_id))


@views.route("/delete-image/<image_id>",methods=['GET'])
@login_required
def delete_image(image_id):
    img = ImageDB.query.filter_by(id=image_id).first()
    ticket_id = img.ticket_id
    db.session.delete(img)
    db.session.commit()
    return redirect('/tickets/'+str(ticket_id))

def proc_image(images_raw,ticket_id):
    images_list=[]
    for image_raw in images_raw:
        if(str(image_raw.ticket_id) == str(ticket_id)):
            npimg = np.fromstring(image_raw.img, np.uint8)
            img = cv2.imdecode(npimg,cv2.IMREAD_COLOR)
            img = Image.fromarray(img.astype("uint8"))
            rawBytes = io.BytesIO()
            img.save(rawBytes, "JPEG")
            rawBytes.seek(0)
            img_base64 = base64.b64encode(rawBytes.read())
            img_base64 = str(img_base64).lstrip('b')
            img_base64 = str(img_base64).strip("'")
            imgtuple = (img_base64,image_raw.id)
            images_list.append(imgtuple)
    return images_list

def alertmechanism(ticket_status, ticket_id):
    current = MasterAlertConfig.query.filter_by(ticket_status=ticket_status).first()
    print(ticket_status)
    ticket = Ticket.query.filter_by(id = ticket_id ).first()
    admins = User.query.filter_by(usertype = "admin").all()
    reporter_id = ticket.author_id
    assignee_id = ticket.assignee_id
    reporter = User.query.filter_by(id = reporter_id).first()
    reporter_email = reporter.email
    assignee = User.query.filter_by(id = assignee_id).first()
    if(assignee):
        assignee_email = assignee.email
    alertsub =  current.alert_subject
    alertbody = current.alert_body
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
    db.session.add(emailaudit)
    db.session.commit()

@views.route("/master-reset-home",methods=['GET'])
@login_required
def master_reset_home():
    admins = User.query.filter_by(usertype = "admin").all()
    resets = MasterResetHistory.query.all()
    return render_template('master_reset.html',resets=resets,user=current_user,admins=admins)

@views.route("/master-reset",methods=['GET'])
@login_required
def master_reset():
    now = time.strftime("%d/%B/%Y %H:%M:%S")
    MasterAlertConfig.query.delete()
    MasterAlertAudit.query.delete()
    Comment.query.delete()
    ImageDB.query.delete()
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
    return render_template('viewprofile.html',user=current_user)