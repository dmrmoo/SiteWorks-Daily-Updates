from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

import json
import os


SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

CREDENTIALS_FILE = "/home/grendel/SiteWorks-Daily-Updates/secrets/google-oath.json"
TOKEN_FILE = "/home/grendel/SiteWorks-Daily-Updates/secrets/gmail-token.json"

DOWNLOAD_DIR = "/home/grendel/SiteWorks-Daily-Updates/gmail_reports"


def get_credentials():
    creds = None

    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(
            TOKEN_FILE,
            SCOPES
        )

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())

    if not creds or not creds.valid:
        raise RuntimeError("Gmail credentials are not valid.")

    return creds


def find_report(service):
    query = (
        'from:estimating@siteworkscsi.com '
        'subject:"Morning Bid Report" '
        'has:attachment'
    )

    results = service.users().messages().list(
        userId="me",
        q=query,
        maxResults=10
    ).execute()

    return results.get("messages", [])


def get_message(service, message_id):
    return service.users().messages().get(
        userId="me",
        id=message_id
    ).execute()


def find_json_attachments(payload):
    attachments = []

    def walk(part):
        filename = part.get("filename", "")
        body = part.get("body", {})

        if filename.lower().endswith(".json"):
            attachments.append({
                "filename": filename,
                "attachment_id": body.get("attachmentId"),
                "size": body.get("size", 0)
            })

        for child in part.get("parts", []):
            walk(child)

    walk(payload)

    return attachments


def download_attachment(service, message_id, attachment_id):
    attachment = service.users().messages().attachments().get(
        userId="me",
        messageId=message_id,
        id=attachment_id
    ).execute()

    import base64

    data = attachment["data"]

    return base64.urlsafe_b64decode(data + "===")


os.makedirs(DOWNLOAD_DIR, exist_ok=True)

creds = get_credentials()

service = build(
    "gmail",
    "v1",
    credentials=creds
)

messages = find_report(service)

print(f"Found {len(messages)} matching email(s).")

if not messages:
    print("No matching report emails found.")
    exit(0)


# Use the newest matching message
message_id = messages[0]["id"]

message = get_message(service, message_id)

headers = message["payload"].get("headers", [])

subject = next(
    (
        h["value"]
        for h in headers
        if h["name"].lower() == "subject"
    ),
    ""
)

sender = next(
    (
        h["value"]
        for h in headers
        if h["name"].lower() == "from"
    ),
    ""
)

print()
print("Email:")
print("------")
print("From:", sender)
print("Subject:", subject)

attachments = find_json_attachments(message["payload"])

print()
print(f"Found {len(attachments)} JSON attachment(s).")

if not attachments:
    print("No JSON attachment found.")
    exit(1)


attachment = attachments[0]

print("Attachment:", attachment["filename"])
print("Size:", attachment["size"], "bytes")

data = download_attachment(
    service,
    message_id,
    attachment["attachment_id"]
)

output_path = os.path.join(
    DOWNLOAD_DIR,
    attachment["filename"]
)

with open(output_path, "wb") as file:
    file.write(data)

print()
print("Downloaded to:")
print(output_path)


# Validate JSON
try:
    with open(output_path, "r", encoding="utf-8") as file:
        report = json.load(file)

    print()
    print("JSON validation: SUCCESS")
    print("JSON type:", type(report).__name__)

    if isinstance(report, dict):
        print("Keys:", list(report.keys()))

        if "projects" in report:
            print("Projects:", len(report["projects"]))

    elif isinstance(report, list):
        print("Items:", len(report))

except json.JSONDecodeError as error:
    print()
    print("JSON validation: FAILED")
    print(error)
