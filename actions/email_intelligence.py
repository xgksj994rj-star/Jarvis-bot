"""Email Intelligence - Gmail/Outlook integration"""
import imaplib
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import json


def read_emails(email_address, password, mailbox="INBOX", limit=5):
    """Fetch unread emails from Gmail/Outlook"""
    try:
        # Connect to Gmail IMAP server
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(email_address, password)
        mail.select(mailbox)
        
        # Search for unread emails
        status, messages = mail.search(None, "UNSEEN")
        email_ids = messages[0].split()[-limit:]
        
        emails = []
        for email_id in email_ids:
            status, msg_data = mail.fetch(email_id, "(RFC822)")
            msg = msg_data[0][1]
            emails.append(str(msg))
        
        mail.close()
        mail.logout()
        return f"Found {len(emails)} unread emails"
    except Exception as e:
        return f"Error reading emails: {str(e)}"


def send_email(recipient, subject, body, email_address, password):
    """Send email via SMTP"""
    try:
        msg = MIMEMultipart()
        msg["From"] = email_address
        msg["To"] = recipient
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))
        
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.login(email_address, password)
        server.send_message(msg)
        server.quit()
        
        return f"Email sent to {recipient}"
    except Exception as e:
        return f"Error sending email: {str(e)}"


def search_emails(query, email_address, password):
    """Search emails by keyword"""
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(email_address, password)
        mail.select("INBOX")
        
        status, messages = mail.search(None, "TEXT", query)
        email_ids = messages[0].split()
        
        mail.close()
        mail.logout()
        
        return f"Found {len(email_ids)} emails matching '{query}'"
    except Exception as e:
        return f"Error searching emails: {str(e)}"


def summarize_emails(email_address, password, num_emails=5):
    """Summarize recent emails"""
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(email_address, password)
        mail.select("INBOX")
        
        status, messages = mail.search(None, "ALL")
        email_ids = messages[0].split()[-num_emails:]
        
        summary = f"Last {len(email_ids)} emails:\n"
        for email_id in email_ids:
            status, msg_data = mail.fetch(email_id, "(BODY[HEADER])")
            header = msg_data[0][1].decode()
            summary += f"- {header}\n"
        
        mail.close()
        mail.logout()
        
        return summary
    except Exception as e:
        return f"Error summarizing emails: {str(e)}"
