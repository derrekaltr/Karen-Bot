"""ImapSmtpAdapter with in-memory SMTP/IMAP fakes."""

from email import message_from_bytes

from karenbot.channels.base import OutboundMessage
from karenbot.channels.imap_smtp import ImapSmtpAdapter, ImapSmtpConfig
from karenbot.channels.mime_utils import build_mime, message_id_for_key

CONFIG = ImapSmtpConfig(
    email="dana@example.com",
    smtp_host="smtp.example.com",
    imap_host="imap.example.com",
    username="dana@example.com",
    password="app-password",
)


class FakeSMTP:
    def __init__(self, outbox: list):
        self.outbox = outbox

    def send_message(self, mime):
        self.outbox.append(mime)

    def quit(self):
        pass


class FakeIMAP:
    """Shared-state fake: folders hold raw message bytes."""

    def __init__(self, folders: dict[str, list[bytes]]):
        self.folders = folders
        self.selected: str | None = None

    def select(self, folder, readonly=False):
        name = folder.strip('"')
        if name not in self.folders:
            return "NO", []
        self.selected = name
        return "OK", [b""]

    def append(self, folder, flags, date, raw):
        self.folders.setdefault(folder.strip('"'), []).append(raw)
        return "OK", [b""]

    def search(self, charset, *criteria):
        assert self.selected is not None
        if criteria and criteria[0] == "HEADER":
            header, wanted = criteria[1], criteria[2]
            hits = []
            for index, raw in enumerate(self.folders[self.selected], start=1):
                mime = message_from_bytes(raw)
                if (mime.get(header) or "").strip() == wanted:
                    hits.append(str(index).encode())
            return "OK", [b" ".join(hits)]
        indexes = [
            str(i).encode() for i in range(1, len(self.folders[self.selected]) + 1)
        ]
        return "OK", [b" ".join(indexes)]

    def fetch(self, num, spec):
        raw = self.folders[self.selected][int(num) - 1]
        return "OK", [(b"1 (RFC822 ...)", raw)]

    def logout(self):
        pass


def make_adapter():
    smtp_outbox: list = []
    folders: dict[str, list[bytes]] = {"Sent": [], "INBOX": []}
    adapter = ImapSmtpAdapter(
        CONFIG,
        smtp_factory=lambda cfg: FakeSMTP(smtp_outbox),
        imap_factory=lambda cfg: FakeIMAP(folders),
    )
    return adapter, smtp_outbox, folders


OUT = OutboundMessage(
    idempotency_key="case:c2:action:a5",
    recipient_address="support@corp.example",
    subject="Refund request",
    body="Please refund USD 120.",
)


def test_send_appends_to_sent_and_is_idempotent():
    adapter, smtp_outbox, folders = make_adapter()
    receipt1 = adapter.send(OUT)
    receipt2 = adapter.send(OUT)  # found in Sent via Message-ID; no second SMTP send
    assert receipt1 == receipt2
    assert len(smtp_outbox) == 1
    assert len(folders["Sent"]) == 1
    assert receipt1.provider_message_id == message_id_for_key(OUT.idempotency_key)


def test_find_by_idempotency_key_after_crash():
    adapter, smtp_outbox, folders = make_adapter()
    assert adapter.find_by_idempotency_key(OUT.idempotency_key) is None
    adapter.send(OUT)
    found = adapter.find_by_idempotency_key(OUT.idempotency_key)
    assert found is not None


def test_fetch_inbound_threads_by_references_root():
    adapter, _, folders = make_adapter()
    receipt = adapter.send(OUT)
    reply = build_mime(
        OutboundMessage(
            idempotency_key="corp-reply-1",
            recipient_address="dana@example.com",
            subject="Re: Refund request",
            body="We can offer you $60.",
        ),
        from_addr="support@corp.example",
        in_reply_to=receipt.provider_message_id,
        references=[receipt.provider_message_id],
    )
    folders["INBOX"].append(reply.as_bytes())
    inbound = adapter.fetch_inbound()
    assert len(inbound) == 1
    # Threads back to our sent message: conversation continuity holds.
    assert inbound[0].provider_thread_id == receipt.provider_message_id
    assert "offer you $60" in inbound[0].body
