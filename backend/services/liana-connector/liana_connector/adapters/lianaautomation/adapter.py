"""LianaAutomation adapter. NOT BUILT YET.

From the LianaAutomation API docs the team has:
- Host: https://rest.automation.lianacloud.com/api/v1 (supports OAuth 2.0
  Bearer tokens). HMAC-SHA256 signing is deprecated and ends 31 Dec 2026, so
  do not implement it.
- Events go in with POST /import. Use the no_duplicates option so a retried
  message does not create a second record.

Backlog card: "Send contact requests to LianaAutomation". Waiting for a
working LianaAutomation test account.
"""

from liana_survey_shared.messages import ContactRequested, ContactResolved


class LianaAutomationContactEvents:
    def __init__(self, base_url: str, client_id: str, client_secret: str) -> None:
        self.base_url = base_url
        self.client_id = client_id
        self.client_secret = client_secret

    def send_contact_requested(self, event: ContactRequested) -> None:
        raise NotImplementedError(
            "LianaAutomation adapter is not built yet; use LIANA_ADAPTER=mock"
        )

    def send_contact_resolved(self, event: ContactResolved) -> None:
        raise NotImplementedError(
            "LianaAutomation adapter is not built yet; use LIANA_ADAPTER=mock"
        )
