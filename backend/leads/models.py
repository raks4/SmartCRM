from django.db import models


class Lead(models.Model):
    STAGE_NEW = "new"
    STAGE_QUALIFIED = "qualified"
    STAGE_PROPOSAL = "proposal"
    STAGE_NEGOTIATION = "negotiation"
    STAGE_WON = "won"
    STAGE_LOST = "lost"

    STAGE_CHOICES = [
        (STAGE_NEW, "New"),
        (STAGE_QUALIFIED, "Qualified"),
        (STAGE_PROPOSAL, "Proposal"),
        (STAGE_NEGOTIATION, "Negotiation"),
        (STAGE_WON, "Won"),
        (STAGE_LOST, "Lost"),
    ]

    company_name = models.CharField(max_length=180)
    contact_name = models.CharField(max_length=120)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=32, blank=True)
    source = models.CharField(max_length=80, blank=True)
    stage = models.CharField(max_length=24, choices=STAGE_CHOICES, default=STAGE_NEW)
    estimated_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    assigned_to = models.CharField(max_length=120, blank=True)
    last_touch = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.company_name} ({self.get_stage_display()})"


class LeadNote(models.Model):
    CHANNEL_EMAIL = "email"
    CHANNEL_CALL = "call"
    CHANNEL_MEETING = "meeting"
    CHANNEL_CHAT = "chat"

    CHANNEL_CHOICES = [
        (CHANNEL_EMAIL, "Email"),
        (CHANNEL_CALL, "Call"),
        (CHANNEL_MEETING, "Meeting"),
        (CHANNEL_CHAT, "Chat"),
    ]

    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="activity_notes")
    owner = models.CharField(max_length=120)
    channel = models.CharField(max_length=24, choices=CHANNEL_CHOICES, default=CHANNEL_EMAIL)
    note = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.lead.company_name}: {self.channel}"


class Reminder(models.Model):
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="reminders")
    task = models.CharField(max_length=180)
    due_at = models.DateTimeField()
    is_done = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.task} ({'done' if self.is_done else 'pending'})"
