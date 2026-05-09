class NotificationSender:
    """
    Stub for Phase 3 NotificationSender to prevent import errors.
    """
    def __init__(self, channel: str = "email"):
        self.channel = channel
        
    def send(self, subject: str, plain_text: str, html: str = ""):
        print(f"[NotificationSender] Sending {self.channel} notification:")
        print(f"Subject: {subject}")
        print(f"Body: {plain_text}")
