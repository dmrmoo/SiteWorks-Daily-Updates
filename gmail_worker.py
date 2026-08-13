import base64
import json
import os
import time
import urllib.request
import urllib.error

from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials


# --------------------------------------------------
# Configuration
# --------------------------------------------------

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly"
]

CREDENTIALS_FILE = (
    "/home/grendel/SiteWorks-Daily-Updates/secrets/google-oauth.json"
)

TOKEN_FILE = (
    "/home/grendel/SiteWorks-Daily-Updates/secrets/gmail-token.json"
)

DOWNLOAD_DIR = (
    "/home/grendel/SiteWorks-Daily-Updates/gmail_reports"
)

STATE_FILE = (
    "/home/grendel/SiteWorks-Daily-Updates/secrets/gmail-worker-state.json"
)

API_URL = "https://swdaily.rememberingmayflower.com/api/morning-report"

API_KEY = os.environ.get("SITEWORKS_API_KEY")

CHECK_INTERVAL = 60


# --------------------------------------------------
# Gmail authentication
# --------------------------------------------------

def get_credentials():
    if not os.path.exists(TOKEN_FILE):
        raise RuntimeError(
            f"Gmail token not found: {TOKEN_FILE}"
        )

    creds = Credentials.from_authorized_user_file(
        TOKEN_FILE,
        SCOPES
    )

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())

    if not creds.valid:
        raise RuntimeError(
            "Gmail credentials are invalid."
        )

    return creds


# --------------------------------------------------
# State management
# --------------------------------------------------

def load_state():
    if not os.path.exists(STATE_FILE):
        return {
            "processed_messages": []
        }

    try:
        with open(STATE_FILE, "r") as file:
            return json.load(file)

    except Exception:
        return {
            "processed_messages": []
        }


def save_state(state):
    temp_file = STATE_FILE + ".tmp"

    with open(temp_file, "w") as file:
        json.dump(state, file, indent=2)

    os.replace(temp_file, STATE_FILE)


# --------------------------------------------------
# Gmail functions
# --------------------------------------------------

def find_reports(service):
    query = (
        'from:estimating@siteworkscsi.com '
        'subject:"Morning Bid Report" '
        'has:attachment '
        'newer_than:2d'
    )

    result = service.users().messages().list(
        userId="me",
        q=query,
        maxResults=20
    ).execute()

    return result.get("messages", [])


def get_message(service, message_id):
    return service.users().messages().get(
        userId="me",
        id=message_id
    ).execute()


def find_json_attachment(payload):

    found = []

    def walk(part):

        filename = part.get("filename", "")
        body = part.get("body", {})

        if filename.lower().endswith(".json"):

            attachment_id = body.get("attachmentId")

            if attachment_id:
                found.append({
                    "filename": filename,
                    "attachment_id": attachment_id
                })

        for child in part.get("parts", []):
            walk(child)

    walk(payload)

    return found


def download_attachment(
    service,
    message_id,
    attachment_id
):

    result = (
        service
        .users()
        .messages()
        .attachments()
        .get(
            userId="me",
            messageId=message_id,
            id=attachment_id
        )
        .execute()
    )

    encoded = result["data"]

    return base64.urlsafe_b64decode(
        encoded + "==="
    )


# --------------------------------------------------
# SiteWorks API
# --------------------------------------------------

def send_to_siteworks(report):

    if not API_KEY:
        raise RuntimeError(
            "SITEWORKS_API_KEY environment variable is not set."
        )

    body = json.dumps(report).encode("utf-8")

    request = urllib.request.Request(
        API_URL,
        data=body,
        method="POST"
    )

    request.add_header(
        "Content-Type",
        "application/json"
    )

    request.add_header(
        "x-api-key",
        API_KEY
    )

    try:

        with urllib.request.urlopen(
            request,
            timeout=30
        ) as response:

            response_body = response.read().decode(
                "utf-8"
            )

            if response.status < 200 or response.status >= 300:
                raise RuntimeError(
                    f"API returned HTTP {response.status}: "
                    f"{response_body}"
                )

            return response_body

    except urllib.error.HTTPError as error:

        error_body = error.read().decode(
            "utf-8",
            errors="replace"
        )

        raise RuntimeError(
            f"SiteWorks API returned HTTP "
            f"{error.code}: {error_body}"
        )


# --------------------------------------------------
# Process one email
# --------------------------------------------------

def process_message(
    service,
    message_id,
    state
):

    if message_id in state["processed_messages"]:
        return False

    print(
        f"Processing Gmail message: {message_id}",
        flush=True
    )

    message = get_message(
        service,
        message_id
    )

    headers = message["payload"].get(
        "headers",
        []
    )

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

    print(
        f"From: {sender}",
        flush=True
    )

    print(
        f"Subject: {subject}",
        flush=True
    )

    attachments = find_json_attachment(
        message["payload"]
    )

    if not attachments:
        print(
            "No JSON attachment found.",
            flush=True
        )

        return False

    attachment = attachments[0]

    print(
        f"Downloading: {attachment['filename']}",
        flush=True
    )

    data = download_attachment(
        service,
        message_id,
        attachment["attachment_id"]
    )

    os.makedirs(
        DOWNLOAD_DIR,
        exist_ok=True
    )

    output_path = os.path.join(
        DOWNLOAD_DIR,
        attachment["filename"]
    )

    with open(
        output_path,
        "wb"
    ) as file:

        file.write(data)

    # Validate JSON
    try:

        report = json.loads(
            data.decode("utf-8")
        )

    except json.JSONDecodeError as error:

        print(
            f"Invalid JSON: {error}",
            flush=True
        )

        return False

    if not isinstance(report, dict):
        print(
            "Report is not a JSON object.",
            flush=True
        )

        return False

    projects = report.get("projects")

    if not isinstance(projects, list):
        print(
            "Report does not contain a projects array.",
            flush=True
        )

        return False

    print(
        f"Validated report with {len(projects)} projects.",
        flush=True
    )

    # Send to SiteWorks
    print(
        "Sending report to SiteWorks API...",
        flush=True
    )

    result = send_to_siteworks(
        report
    )

    print(
        f"SiteWorks response: {result}",
        flush=True
    )

    # Only mark processed AFTER successful API call
    state["processed_messages"].append(
        message_id
    )

    # Keep the state file reasonably small
    state["processed_messages"] = (
        state["processed_messages"][-100:]
    )

    save_state(state)

    print(
        "Report successfully processed.",
        flush=True
    )

    return True


# --------------------------------------------------
# Main worker
# --------------------------------------------------

def main():

    print(
        "SiteWorks Gmail worker starting...",
        flush=True
    )

    print(
        f"Watching: {API_URL}",
        flush=True
    )

    creds = get_credentials()

    service = build(
        "gmail",
        "v1",
        credentials=creds
    )

    state = load_state()

    print(
        "Gmail connection established.",
        flush=True
    )

    while True:

        try:

            messages = find_reports(
                service
            )

            # Gmail normally returns newest first.
            # Reverse so older unprocessed reports are
            # handled before newer ones.
            messages.reverse()

            for message in messages:

                try:

                    process_message(
                        service,
                        message["id"],
                        state
                    )

                except Exception as error:

                    print(
                        f"ERROR processing message "
                        f"{message['id']}: {error}",
                        flush=True
                    )

            time.sleep(
                CHECK_INTERVAL
            )

        except Exception as error:

            print(
                f"Worker error: {error}",
                flush=True
            )

            # Wait before retrying
            time.sleep(30)


if __name__ == "__main__":
    main()
