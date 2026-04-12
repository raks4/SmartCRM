from django.contrib import admin

from .models import Lead, LeadNote, Reminder


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ("id", "company_name", "contact_name", "stage", "estimated_value", "last_touch")
    list_filter = ("stage", "source")
    search_fields = ("company_name", "contact_name", "contact_email")


@admin.register(LeadNote)
class LeadNoteAdmin(admin.ModelAdmin):
    list_display = ("id", "lead", "owner", "channel", "created_at")
    list_filter = ("channel",)
    search_fields = ("lead__company_name", "owner", "note")


@admin.register(Reminder)
class ReminderAdmin(admin.ModelAdmin):
    list_display = ("id", "lead", "task", "due_at", "is_done")
    list_filter = ("is_done",)
    search_fields = ("lead__company_name", "task")
