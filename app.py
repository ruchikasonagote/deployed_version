from glob import escape
from flask import Flask, render_template, request, redirect, url_for, jsonify, session
from flask_mysqldb import MySQL
import config
from werkzeug.security import generate_password_hash, check_password_hash
from flask_cors import CORS
from datetime import datetime
from flask_mail import Mail, Message
import os
import pandas as pd


app = Flask(__name__)
CORS(app)
app.secret_key = "b';\x90q\xe6x\x9c!iZxH\xa1\x81P\xe6f'"
UPLOAD_FOLDER = 'uploads'

app.config['MYSQL_HOST'] = config.MYSQL_HOST
app.config['MYSQL_USER'] = config.MYSQL_USER
app.config['MYSQL_PASSWORD'] = config.MYSQL_PASSWORD
app.config['MYSQL_DB'] = config.MYSQL_DB
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

mysql = MySQL(app)

def lock_table():
    cur = mysql.connection.cursor()
    cur.execute("LOCK TABLES User WRITE")
    return cur

def unlock_table(cur):
    cur.execute("UNLOCK TABLES")
    cur.close()

@app.route('/send_email', methods=['POST'])
def send_email():
    password = request.form.get('password')
    template_selected = request.form.get('template') 
    recipients = request.form.get('recipients')  
    recipient_emails = recipients.split(",") if recipients else []  
    subject = request.form['subject']
    content = request.form['content']
    app.config['MAIL_SERVER'] = 'smtp.gmail.com'
    app.config['MAIL_PORT'] = 465
    app.config['MAIL_USE_TLS'] = False
    app.config['MAIL_USERNAME'] = session.get('usermailid')
    app.config['MAIL_PASSWORD'] = password
    app.config['MAIL_USE_SSL'] = True
    app.config['MAIL_DEFAULT_SENDER'] = session.get('usermailid')
    sender=session.get('usermailid')
    mail = Mail(app)
    cur = lock_table()
    if template_selected == 'template1':
        try:
            all_recipient_emails = [] 
            for recipient_email in recipient_emails:
                is_group_email, group_id = is_group(recipient_email)
                if is_group_email:
                    group_members = retrieve_group_members(recipient_email)  
                    all_recipient_emails.extend(group_members) 
                else:
                    all_recipient_emails.append(recipient_email)
            
            if not all_recipient_emails:
                return 'No recipients have been added.', 400  
            
            msg = Message(subject, recipients=all_recipient_emails, sender=sender)
            msg.body = content
            mail.send(msg)
            # cur = mysql.connection.cursor()

            cur.execute("INSERT INTO Email (Email_subject, Email_content, DeliveryStatus, Timestamp, SMTP_serveraddress, User_id, Template_id) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                        (subject, content, 'Delivered', datetime.now(), 'smtp.gmail.com', session['user_id'], 1)) 
            emaillog_id = cur.lastrowid
            for recipient_email in recipient_emails:
                is_group_email, group_id = is_group(recipient_email) 
                if is_group_email:
                    cur.execute("INSERT INTO Group_receiver(EmailLog_id,Group_id) VALUES (%s,%s)",(emaillog_id, group_id))
                else:
                    recipient_id = fetch_recipient_id(recipient_email)
                    cur.execute("INSERT INTO Individual_receiver(EmailLog_id,Recipient_id) VALUES (%s,%s)",(emaillog_id, recipient_id))
            mysql.connection.commit()
            unlock_table(cur)
            # cur.close()  
            return 'Email sent successfully!'
        except Exception as e:
            return f'Failed to send email. Error: {str(e)}', 500
    else:
        try:
            # cur = mysql.connection.cursor() 
            all_recipient_emails = []  
            for recipient_email in recipient_emails:
                is_group_email, group_id = is_group(recipient_email)  
                if is_group_email:
                    group_members = retrieve_group_members(recipient_email)  
                    all_recipient_emails.extend(group_members)
                else:
                    all_recipient_emails.append(recipient_email)

            for recipient_email in all_recipient_emails:
                recipient_name = get_recipient_name(recipient_email) 
                modified_content = content.replace('{{name}}', recipient_name)  
                msg = Message(subject, recipients=[recipient_email], sender=sender)
                msg.body = modified_content
                mail.send(msg)

            cur.execute("INSERT INTO Email (Email_subject, Email_content, DeliveryStatus, Timestamp, SMTP_serveraddress, User_id, Template_id) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                        (subject, content, 'Delivered', datetime.now(), 'smtp.gmail.com', session['user_id'], 2))  
            emaillog_id = cur.lastrowid
            for recipient_email in recipient_emails:
                is_group_email, group_id = is_group(recipient_email)  
                if is_group_email:
                    cur.execute("INSERT INTO Group_receiver(EmailLog_id,Group_id) VALUES (%s,%s)",(emaillog_id, group_id))
                else:
                    recipient_id = fetch_recipient_id(recipient_email)
                    cur.execute("INSERT INTO Individual_receiver(EmailLog_id,Recipient_id) VALUES (%s,%s)",(emaillog_id, recipient_id))
            mysql.connection.commit()
            unlock_table(cur) 
            # cur.close()
            return 'Email sent successfully!'
        except Exception as e:
            return f'Failed to send email. Error: {str(e)}'
        
        
def fetch_recipient_id(recipient_email):
    try:
        cur = mysql.connection.cursor()
        cur.execute("SELECT Recipient_id FROM RecipientList WHERE RecipientEmail_id = %s", (recipient_email,))
        recipient_id = cur.fetchone()  
        cur.close()
        return recipient_id[0] if recipient_id else None
    except Exception as e:
        return None  
    
def is_group(email):
    cur = mysql.connection.cursor()
    cur.execute("SELECT Group_id FROM Email_Group WHERE Group_address = %s", (email,))
    group = cur.fetchone()
    cur.close()
    return group is not None, group[0] if group else None

def retrieve_group_members(group_address):
    cur = mysql.connection.cursor()
    cur.execute("""SELECT rl.RecipientEmail_id 
                FROM Email_Group eg 
                JOIN Memberof m 
                ON eg.Group_id = m.Group_id 
                JOIN RecipientList rl 
                ON m.Recipient_id = rl.Recipient_id 
                WHERE eg.Group_address = %s""", (group_address,))
    group_members = cur.fetchall()
    email_addresses = [member[0] for member in group_members]
    cur.close()
    return email_addresses


def get_recipient_name(email):
    cur = mysql.connection.cursor()
    cur.execute("SELECT Recipient_name FROM RecipientList WHERE RecipientEmail_id = %s", (email,))
    recipient = cur.fetchone()
    cur.close()
    return recipient[0] if recipient else ''

@app.route('/sentEmails')
def sent_emails():
    user_id = session.get('user_id')
    usermailid = session.get('usermailid')  
    if not user_id:
        return "User not logged in", 401  

    cur = mysql.connection.cursor()
    
    try:
        cur.execute("""
            SELECT e.EmailLog_id, e.Email_subject, e.Email_content, e.DeliveryStatus, e.Timestamp, 
                   GROUP_CONCAT(DISTINCT CONCAT(g.group_address, ' (Group)') SEPARATOR ';') AS group_addresses,
                   GROUP_CONCAT(DISTINCT CONCAT(r.RecipientEmail_id, ' (Individual)') SEPARATOR ';') AS individual_addresses
            FROM Email e
            LEFT JOIN Group_receiver gr ON e.EmailLog_id = gr.EmailLog_id
            LEFT JOIN Email_Group g ON gr.Group_id = g.Group_id
            LEFT JOIN Individual_receiver ir ON e.EmailLog_id = ir.EmailLog_id
            LEFT JOIN RecipientList r ON ir.Recipient_id = r.Recipient_id
            WHERE e.User_id = %s
            GROUP BY e.EmailLog_id, e.Email_subject, e.Email_content, e.DeliveryStatus, e.Timestamp
        """, (user_id,))
        emails = cur.fetchall()
    except Exception as e:
        return str(e), 500  
    finally:
        cur.close()
    return render_template('sentEmails.html', emails=emails,usermailid=usermailid)

@app.route('/', methods=['GET', 'POST'])
def login():
    error = None
    usermailid=None
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        # cur = mysql.connection.cursor()
        cur = lock_table() 
        cur.execute("SELECT * FROM User WHERE UserEmail_id=%s", [email])
        User = cur.fetchone()
        if User and check_password_hash(User[4], password): 
            session['user_id'] = User[0]
            usermailid=User[2]
            session['usermailid'] = usermailid
            session.pop('selected_groups', None)
            session.pop('selected_recipients', None)
            unlock_table(cur) 
            return redirect(url_for('home',usermailid=usermailid))
        else:
            unlock_table(cur)
            error = 'Invalid Credentials. Please try again.'
            return escape(error)
    return render_template('login.html')

@app.route('/registration', methods=['GET', 'POST'])
def registration():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        role = request.form['role']
        password = request.form['password']

        hashed_password = generate_password_hash(password)
        app.logger.info('Received POST request to add User: User_name - %s, UserEmail_id - %s, Role - %s, Passwordhash - %s', username, email, role, hashed_password)
        
        # cur = mysql.connection.cursor()
        cur = lock_table() 
        cur.execute("SELECT * FROM User WHERE User_ID = %s FOR UPDATE", (session['user_id'],))
            
        try:
            cur.execute("INSERT INTO User(User_name, UserEmail_id, Role, Passwordhash) VALUES (%s, %s, %s, %s)", (username, email, role, hashed_password))
            mysql.connection.commit()
            app.logger.info('User added successfully: User_name - %s, UserEmail_id - %s, Role - %s, Passwordhash - %s', username, email, role, hashed_password)
            unlock_table(cur) 
            return redirect(url_for('login'))
        except Exception as e:
            mysql.connection.rollback()
            error = 'Registration failed. User already exists.'
            app.logger.error('Error adding User to database: %s', str(e))
            return error
        finally:
            cur.close()

    return render_template('registration.html')

@app.route('/home', methods=['GET', 'POST'])
def home():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    usermailid = session.get('usermailid')  

    selected_groups = session.get('selected_groups', [])
    selected_recipients = session.get('selected_recipients', [])

    if request.method == 'POST':
        if 'groups[]' in request.form:
            new_selected_groups = request.form.getlist('groups[]')
            selected_groups += new_selected_groups

        if 'recipients[]' in request.form:
            new_selected_recipients = request.form.getlist('recipients[]')
            selected_recipients += new_selected_recipients

        selected_groups = list(set(selected_groups))
        selected_recipients = list(set(selected_recipients))

        session['selected_groups'] = selected_groups
        session['selected_recipients'] = selected_recipients
    else:
        session.pop('selected_groups', None)
        session.pop('selected_recipients', None)
    return render_template('home.html', selected_groups=selected_groups, usermailid=usermailid, selected_recipients=selected_recipients)

def get_user_role(): 
    email = session.get('usermailid')
    cur = mysql.connection.cursor()
    cur.execute("SELECT Role FROM User WHERE UserEmail_id = %s", (email,))
    user_data = cur.fetchone()
    user_role=user_data[0]
    cur.close()
    return user_role

def create_views_if_not_exist():
    with mysql.connection.cursor() as cur:
        cur.execute("SHOW TABLES LIKE 'TeachingAssistantRecipientList'")
        if not cur.fetchone():
            cur.execute("""CREATE VIEW TeachingAssistantRecipientList AS 
                        SELECT Recipient_id, RecipientEmail_id, Recipient_name, Gender, Marks 
                        FROM RecipientList""")
            mysql.connection.commit()

        cur.execute("SHOW TABLES LIKE 'EventCoordinatorRecipientList'")
        if not cur.fetchone():
            cur.execute("""CREATE VIEW EventCoordinatorRecipientList AS 
                        SELECT Recipient_id, RecipientEmail_id, Recipient_name, Gender, Company 
                        FROM RecipientList""")
            mysql.connection.commit()

@app.route('/seeRecipientList')
def recipient_list():
    user_id = session.get('user_id')
    user_role = get_user_role()
    create_views_if_not_exist()  
    recipients=[]
    if user_role == 'Teaching Assistant':
        cur = mysql.connection.cursor()
        cur.execute("""
                SELECT Recipient_id, RecipientEmail_id, Recipient_name, Gender, Marks 
                FROM RecipientList 
                WHERE user_id = %s
            """, (user_id,))
        recipients = cur.fetchall()
        cur.close()
        
        return render_template('seeRecipientList.html', recipients=recipients, user_role=user_role)

    elif user_role == 'Event Coordinator':
        cur = mysql.connection.cursor()
        cur.execute("""
                SELECT Recipient_id, RecipientEmail_id, Recipient_name, Gender, Company 
                FROM RecipientList 
                WHERE user_id = %s
            """, (user_id,))
        recipients = cur.fetchall()
        cur.close()
        return render_template('seeRecipientList.html', recipients=recipients, user_role=user_role)
    else:
        return "Unauthorized Access"

@app.route('/seeGroups')
def groups():
    user_id = session.get('user_id') 
    if not user_id:
        return "User not logged in", 401  

    user_role = get_user_role()
    if user_role is None:
        return "Failed to retrieve user role", 403 
    query = """
        SELECT Group_id, Group_name 
        FROM Email_Group
        WHERE User_id = %s
    """
    try:
        with mysql.connection.cursor() as cur:
            cur.execute(query, (user_id,))
            groups = cur.fetchall()

            group_details = {}
            for group in groups:
                group_id = group[0]
                if user_role == "Teaching Assistant":
                    detail_query = """
                        SELECT RecipientList.Recipient_id, RecipientList.RecipientEmail_id, RecipientList.Recipient_name, RecipientList.Gender, RecipientList.Marks 
                        FROM RecipientList 
                        JOIN Memberof ON RecipientList.Recipient_id = Memberof.Recipient_id 
                        WHERE Memberof.Group_id = %s
                    """
                elif user_role == "Event Coordinator":
                    detail_query = """
                        SELECT RecipientList.Recipient_id, RecipientList.RecipientEmail_id, RecipientList.Recipient_name, RecipientList.Gender, RecipientList.Company 
                        FROM RecipientList 
                        JOIN Memberof ON RecipientList.Recipient_id = Memberof.Recipient_id 
                        WHERE Memberof.Group_id = %s
                    """
                else:
                    return "Unauthorized access", 403  

                cur.execute(detail_query, (group_id,))
                group_details[group_id] = cur.fetchall()

            return render_template('seeGroups.html', groups=groups, group_details=group_details, user_role=user_role)
    except Exception as e:
        return str(e), 500  
    
@app.route('/delete-groups', methods=['POST'])
def delete_groups():
    data = request.get_json()
    group_ids = data['group_ids']
    group_ids = [int(id) for id in group_ids]

    placeholders = ','.join(['%s'] * len(group_ids))

    memberof_query = "DELETE FROM Memberof WHERE Group_id IN ({})".format(placeholders)
    email_group_query = "DELETE FROM Email_Group WHERE Group_id IN ({})".format(placeholders)

    cur = mysql.connection.cursor()
    cur.execute(memberof_query, group_ids)
    cur.execute(email_group_query, group_ids)
    
    mysql.connection.commit()  
    cur.close()

    return jsonify({'success': True})

@app.route('/rename-group', methods=['POST'])
def rename_group():
    data = request.get_json()
    group_id = data['group_id']
    new_name = data['new_name']
    
    cur = mysql.connection.cursor()
    cur.execute("UPDATE Email_Group SET Group_name = %s WHERE Group_id = %s", (new_name, group_id))
    mysql.connection.commit()
    cur.close()

    return jsonify({'success': True})

@app.route('/rename-recipient', methods=['POST'])
def rename_recipient_seeGroups():
    data = request.get_json()
    recipient_id = data['recipient_id']
    new_name = data['new_name']
    
    cur = mysql.connection.cursor()
    cur.execute("UPDATE RecipientList SET Recipient_name = %s WHERE Recipient_id = %s", (new_name, recipient_id))
    mysql.connection.commit()
    cur.close()

    return jsonify({'success': True})

@app.route('/delete-recipients', methods=['POST'])
def delete_recipients():
    data = request.get_json()
    recipient_ids = data['recipient_ids']
    recipient_ids = [int(id) for id in recipient_ids]

    placeholders = ','.join(['%s'] * len(recipient_ids))

    memberof_query = "DELETE FROM Memberof WHERE Recipient_id IN ({})".format(placeholders)

    email_recipient_query = "DELETE FROM RecipientList WHERE Recipient_id IN ({})".format(placeholders)

    cur = mysql.connection.cursor()
    cur.execute(memberof_query, recipient_ids)
    cur.execute(email_recipient_query, recipient_ids)
    
    mysql.connection.commit()  
    cur.close()

    return jsonify({'success': True})

@app.route('/chooseExistedGroups',methods=['GET', 'POST'])
def CEG():
    if request.method == 'POST':
        selected_groups = request.form.getlist('selected_groups')
        return render_template('home.html', selected_groups=selected_groups)
    cur = mysql.connection.cursor()
    cur.execute("SELECT Group_id, Group_name, group_address FROM Email_Group WHERE User_id = %s", (session['user_id'],))
    groups = cur.fetchall()
    cur.close()
    return render_template('chooseExistedGroups.html', groups=groups)

@app.route('/chooseRecipientList', methods=['GET', 'POST'])
def CRL():
    cur = mysql.connection.cursor()
    cur.execute("SELECT Recipient_id, Recipient_name, RecipientEmail_id FROM RecipientList WHERE user_id = %s", (session['user_id'],))
    recipients = cur.fetchall()
    cur.close()
    return render_template('chooseRecipientList.html', recipients=recipients)

@app.route('/insertRecipient', methods=['POST', 'GET'])
def insert_recipient():
    if 'user_id' not in session:
        return jsonify({'error': 'User not logged in'}), 401
    
    user_role = get_user_role()
    if request.method == 'GET':
        return render_template('insertRecipient.html', user_role=user_role)
    elif request.method == 'POST':
        recipient_email = request.form['recipient_email']
        recipient_name = request.form['recipient_name']
        gender = request.form['gender']
        
        marks = request.form.get('marks')  
        company = request.form.get('company')  

        try:
            cur = mysql.connection.cursor()

            if user_role == 'Teaching Assistant':
                if not marks:
                    marks = None

                cur.execute("INSERT INTO RecipientList (RecipientEmail_id, User_id, Recipient_name, Gender, Marks) VALUES (%s, %s, %s, %s, %s)",
                            (recipient_email, session['user_id'], recipient_name, gender, marks))
            else:
                if not company:
                    company = None

                cur.execute("INSERT INTO RecipientList (RecipientEmail_id, User_id, Recipient_name, Gender, Company) VALUES (%s, %s, %s, %s, %s)",
                            (recipient_email, session['user_id'], recipient_name, gender, company))

            mysql.connection.commit()

            return redirect(url_for('home', user_role=user_role))
        except Exception as e:
            mysql.connection.rollback()
        finally:
            cur.close()

@app.route('/deleteRecipients', methods=['POST'])
def delete_r():
    try:
        recipient_ids = request.json.get('recipientIds')

        if recipient_ids:
            cur = mysql.connection.cursor()

            query_memberof = "DELETE FROM Memberof WHERE Recipient_id IN (%s)"
            query_params_memberof = ','.join(['%s'] * len(recipient_ids))
            query_memberof = query_memberof % query_params_memberof
            cur.execute(query_memberof, tuple(recipient_ids))

            query_recipientlist = "DELETE FROM RecipientList WHERE Recipient_id IN (%s)"
            query_params_recipientlist = ','.join(['%s'] * len(recipient_ids))
            query_recipientlist = query_recipientlist % query_params_recipientlist
            cur.execute(query_recipientlist, tuple(recipient_ids))

            mysql.connection.commit()

            cur.close()

            return jsonify({'message': 'Recipients deleted successfully'}), 200
        else:
            return jsonify({'error': 'No recipient IDs provided in the request'}), 400

    except Exception as e:
     
        return jsonify({'error': 'Error deleting recipients: {}'.format(str(e))}), 500

@app.route('/insertRecipient_RL')
def insert_recipient_page_RL():
    group_id = request.args.get('group_id')
    user_role = get_user_role()  
    return render_template('insertRecipient_RL.html', group_id=group_id, user_role=user_role)

@app.route('/insertRecipient_RL', methods=['POST'])
def insert_recipient_RL():
    if 'user_id' not in session:
        return jsonify({'error': 'User not logged in'}), 401

    recipient_email = request.form['recipient_email']
    recipient_name = request.form['recipient_name']
    gender = request.form['gender']
    user_role = get_user_role()  
    
    if user_role == "Teaching Assistant":
        marks = request.form['marks']
        company = None
    elif user_role == "Event Coordinator":
        marks = None
        company = request.form['company']
    else:
        return jsonify({'error': 'Unauthorized role'}), 403

    group_id = request.form['group_id'] 

    try:
        cur = mysql.connection.cursor()
        if user_role == "Teaching Assistant":
            cur.execute("INSERT INTO RecipientList (RecipientEmail_id, User_id, Recipient_name, Gender, Marks) VALUES (%s, %s, %s, %s, %s)",
                        (recipient_email, session['user_id'], recipient_name, gender, marks))
        elif user_role == "Event Coordinator":
            cur.execute("INSERT INTO RecipientList (RecipientEmail_id, User_id, Recipient_name, Gender, Company) VALUES (%s, %s, %s, %s, %s)",
                        (recipient_email, session['user_id'], recipient_name, gender, company))
        
        recipient_id = cur.lastrowid
        cur.execute("INSERT INTO Memberof (Group_id, Recipient_id) VALUES (%s, %s)",
                    (group_id, recipient_id))
        mysql.connection.commit()
        return redirect(url_for('home', user_role=user_role))
    except Exception as e:
        mysql.connection.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()

@app.route('/insertGroup')
def insert_group_page():
    return render_template('insertGroup.html')

@app.route('/insertGroup', methods=['POST'])
def insert_group():
    if 'user_id' not in session:
        return jsonify({'error': 'User not logged in'}), 401
    user_id = session['user_id']

    Group_name = request.form['Group_name']
    group_address = request.form['group_address']

    try:
        with mysql.connection.cursor() as cur:
            cur.execute("INSERT INTO Email_Group (Group_name, group_address, User_id) VALUES (%s, %s, %s)",
                        (Group_name, group_address, user_id))
            mysql.connection.commit()
            return redirect(url_for('home'))
    except Exception as e:
        mysql.connection.rollback()  # Ensures that any error does not affect the database integrity
        return jsonify({'error': str(e)}), 500

@app.route('/uploadfile')
def uploadfile():
    group_id = request.args.get('group_id')
    if not group_id:
        return jsonify({'error': 'Group ID not provided'}), 400  
    return render_template('uploadfile.html', group_id=group_id)

@app.route('/upload', methods=['GET','POST'])
def uploadFile():
    if 'user_id' not in session:
        return jsonify({'error': 'User not logged in'}), 401

    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    group_id = request.args.get('group_id')
    if not group_id:
        return jsonify({'error': 'Group ID not provided'}), 400

    uploaded_file = request.files['file']
    if uploaded_file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    file_path = os.path.join(app.config['UPLOAD_FOLDER'], uploaded_file.filename)
    uploaded_file.save(file_path)

    try:
        parsefile(file_path, session['user_id'], group_id)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    return render_template('home.html')

def parsefile(file_path, user_id, group_id):
    user_role=get_user_role()
    if user_role == 'Teaching Assistant' :
        col_names = ['RecipientEmail_id', 'Recipient_name', 'Gender', 'Marks']
        csv_data = pd.read_csv(file_path, names=col_names, header=None)

        cur = mysql.connection.cursor()
        for index, row in csv_data.iterrows():
            cur.execute("INSERT INTO RecipientList (RecipientEmail_id, User_id, Recipient_name, Gender, Marks) VALUES (%s, %s, %s, %s, %s)",
                        (row[0], user_id, row[1], row[2], row[3]))
            recipient_id = cur.lastrowid
            cur.execute("INSERT INTO Memberof (Group_id, Recipient_id) VALUES (%s, %s)",
                        (group_id, recipient_id))
        mysql.connection.commit()
        cur.close()
    else :
        col_names = ['RecipientEmail_id', 'Recipient_name', 'Gender', 'Company']
    
        csv_data = pd.read_csv(file_path, names=col_names, header=None)

        cur = mysql.connection.cursor()
        for index, row in csv_data.iterrows():
            cur.execute("INSERT INTO RecipientList (RecipientEmail_id, User_id, Recipient_name, Gender, Company) VALUES (%s, %s, %s, %s, %s)",
                        (row[0], user_id, row[1], row[2], row[3]))
            recipient_id = cur.lastrowid
            cur.execute("INSERT INTO Memberof (Group_id, Recipient_id) VALUES (%s, %s)",
                        (group_id, recipient_id))
        mysql.connection.commit()
        cur.close()

if __name__ == '__main__':
    app.run(debug=True)
