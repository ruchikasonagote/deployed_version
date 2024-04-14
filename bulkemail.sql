DROP DATABASE if exists BULKEMAIL;
CREATE DATABASE BULKEMAIL;
USE BULKEMAIL;

CREATE TABLE User (
     User_id INT auto_increment primary KEY,
     User_name VARCHAR(255) NOT NULL,
     UserEmail_id VARCHAR(255) NOT NULL UNIQUE,
     Role ENUM('Teaching Assistant', 'Event Coordinator'),
     Passwordhash VARCHAR(255) NOT NULL 
);

CREATE TABLE Template (
    Template_id INT auto_increment primary KEY,
    Template_name VARCHAR(255) NOT NULL,
    Template_content TEXT
);

CREATE TABLE Email_Group (
    Group_id INT auto_increment PRIMARY KEY,
    Group_name VARCHAR(255) NOT NULL,
    group_address VARCHAR(255) NOT NULL,
    User_id INT,
    FOREIGN KEY (User_id) REFERENCES User(User_id)
);

CREATE TABLE RecipientList (
    Recipient_id INT auto_increment PRIMARY KEY,
    RecipientEmail_id VARCHAR(255) NOT NULL,
    User_id INT,
    Recipient_name VARCHAR(255) NOT NULL,
    Gender CHAR(1),
    Company VARCHAR(255),
    Marks INT CHECK (Marks >= 0 AND Marks < 1000),
    FOREIGN KEY (User_id) REFERENCES User(User_id)
);

CREATE TABLE Email (
    EmailLog_id INT auto_increment PRIMARY KEY,
    Email_subject varchar(255),
    Email_content TEXT,
    DeliveryStatus ENUM('not delivered', 'delivered'),
    Timestamp DATETIME NOT NULL,
    SMTP_serveraddress VARCHAR(255) NOT NULL,
    User_id INT NOT NULL,
    Template_id INT NOT NULL,
    FOREIGN KEY (User_id) REFERENCES User(User_id),
    FOREIGN KEY (Template_id) REFERENCES Template(Template_id)
);

CREATE TABLE Group_receiver (
    EmailLog_id INT,
    Group_id INT,
    PRIMARY KEY (EmailLog_id, Group_id),
    FOREIGN KEY (EmailLog_id) REFERENCES Email(EmailLog_id),
    FOREIGN KEY (Group_id) REFERENCES Email_Group(Group_id)
);

CREATE TABLE Individual_receiver (
    EmailLog_id INT,
    Recipient_id INT,
    PRIMARY KEY (EmailLog_id, Recipient_id),
    FOREIGN KEY (EmailLog_id) REFERENCES Email(EmailLog_id),
    FOREIGN KEY (Recipient_id) REFERENCES RecipientList(Recipient_id)
);

CREATE TABLE Memberof (
    Group_id INT,
    Recipient_id INT,
    PRIMARY KEY (Group_id, Recipient_id),
    FOREIGN KEY (Group_id) REFERENCES Email_Group(Group_id),
    FOREIGN KEY (Recipient_id) REFERENCES RecipientList(Recipient_id)
);

INSERT INTO Template (Template_id, Template_name, Template_content) VALUES 
(1, 'Individual Mail', 'Your Template Content'),
(2, 'Same Mail', 'Content');
