import json
from datetime import datetime

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods

from .models import Lead, LeadNote, Reminder


def parse_json_body(request: HttpRequest):
    try:
        return json.loads(request.body.decode("utf-8")) if request.body else {}
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


def serialize_lead(lead: Lead):
    return {
        "id": lead.id,
        "company_name": lead.company_name,
        "contact_name": lead.contact_name,
        "contact_email": lead.contact_email,
        "contact_phone": lead.contact_phone,
        "source": lead.source,
        "stage": lead.stage,
        "estimated_value": float(lead.estimated_value),
        "assigned_to": lead.assigned_to,
        "last_touch": lead.last_touch.isoformat() if lead.last_touch else None,
        "notes": lead.notes,
        "created_at": lead.created_at.isoformat(),
    }


def serialize_note(note: LeadNote):
    return {
        "id": note.id,
        "lead_id": note.lead_id,
        "owner": note.owner,
        "channel": note.channel,
        "note": note.note,
        "created_at": note.created_at.isoformat(),
    }


def serialize_reminder(reminder: Reminder):
    return {
        "id": reminder.id,
        "lead_id": reminder.lead_id,
        "task": reminder.task,
        "due_at": reminder.due_at.isoformat(),
        "is_done": reminder.is_done,
    }


@csrf_exempt
@require_http_methods(["POST"])
def login_view(request: HttpRequest):
    data = parse_json_body(request)
    if data is None:
        return JsonResponse({"detail": "Invalid JSON payload."}, status=400)

    username = data.get("username", "").strip()
    password = data.get("password", "")

    user = authenticate(request, username=username, password=password)
    if not user:
        return JsonResponse({"detail": "Invalid credentials."}, status=401)

    login(request, user)
    return JsonResponse(
        {
            "user": {
                "id": user.id,
                "username": user.username,
                "is_staff": user.is_staff,
            }
        }
    )


@csrf_exempt
@require_http_methods(["POST"])
def logout_view(request: HttpRequest):
    logout(request)
    return JsonResponse({"detail": "Logged out."})


@require_GET
def session_view(request: HttpRequest):
    if not request.user.is_authenticated:
        return JsonResponse({"authenticated": False}, status=401)

    return JsonResponse(
        {
            "authenticated": True,
            "user": {
                "id": request.user.id,
                "username": request.user.username,
                "is_staff": request.user.is_staff,
            },
        }
    )


@login_required
@require_http_methods(["GET", "POST"])
@csrf_exempt
def leads_collection_view(request: HttpRequest):
    if request.method == "GET":
        leads = Lead.objects.order_by("-created_at")
        return JsonResponse({"items": [serialize_lead(lead) for lead in leads]})

    data = parse_json_body(request)
    if data is None:
        return JsonResponse({"detail": "Invalid JSON payload."}, status=400)

    company_name = (data.get("company_name") or "").strip()
    contact_name = (data.get("contact_name") or "").strip()

    if not company_name or not contact_name:
        return JsonResponse({"detail": "company_name and contact_name are required."}, status=400)

    last_touch = None
    if data.get("last_touch"):
        try:
            last_touch = datetime.strptime(data["last_touch"], "%Y-%m-%d").date()
        except ValueError:
            return JsonResponse({"detail": "last_touch must be YYYY-MM-DD."}, status=400)

    lead = Lead.objects.create(
        company_name=company_name,
        contact_name=contact_name,
        contact_email=(data.get("contact_email") or "").strip(),
        contact_phone=(data.get("contact_phone") or "").strip(),
        source=(data.get("source") or "").strip(),
        stage=(data.get("stage") or Lead.STAGE_NEW),
        estimated_value=data.get("estimated_value") or 0,
        assigned_to=(data.get("assigned_to") or "").strip(),
        last_touch=last_touch,
        notes=(data.get("notes") or "").strip(),
    )

    return JsonResponse({"item": serialize_lead(lead)}, status=201)


@login_required
@require_http_methods(["PATCH"])
@csrf_exempt
def lead_update_view(request: HttpRequest, lead_id: int):
    data = parse_json_body(request)
    if data is None:
        return JsonResponse({"detail": "Invalid JSON payload."}, status=400)

    try:
        lead = Lead.objects.get(pk=lead_id)
    except Lead.DoesNotExist:
        return JsonResponse({"detail": "Lead not found."}, status=404)

    for field in [
        "company_name",
        "contact_name",
        "contact_email",
        "contact_phone",
        "source",
        "stage",
        "assigned_to",
        "notes",
    ]:
        if field in data:
            setattr(lead, field, data[field])

    if "estimated_value" in data:
        lead.estimated_value = data["estimated_value"]

    if "last_touch" in data:
        if data["last_touch"]:
            try:
                lead.last_touch = datetime.strptime(data["last_touch"], "%Y-%m-%d").date()
            except ValueError:
                return JsonResponse({"detail": "last_touch must be YYYY-MM-DD."}, status=400)
        else:
            lead.last_touch = None

    lead.save()
    return JsonResponse({"item": serialize_lead(lead)})


@login_required
@require_http_methods(["POST"])
@csrf_exempt
def lead_note_create_view(request: HttpRequest, lead_id: int):
    data = parse_json_body(request)
    if data is None:
        return JsonResponse({"detail": "Invalid JSON payload."}, status=400)

    try:
        lead = Lead.objects.get(pk=lead_id)
    except Lead.DoesNotExist:
        return JsonResponse({"detail": "Lead not found."}, status=404)

    note_text = (data.get("note") or "").strip()
    owner = (data.get("owner") or request.user.username).strip()
    channel = (data.get("channel") or LeadNote.CHANNEL_EMAIL).strip().lower()

    if not note_text:
        return JsonResponse({"detail": "note is required."}, status=400)

    note = LeadNote.objects.create(lead=lead, owner=owner, channel=channel, note=note_text)
    return JsonResponse({"item": serialize_note(note)}, status=201)


@login_required
@require_GET
def dashboard_view(request: HttpRequest):
    leads = list(Lead.objects.all())

    pipeline = {
        "new": 0,
        "qualified": 0,
        "proposal": 0,
        "negotiation": 0,
        "won": 0,
        "lost": 0,
    }

    total_value = 0.0
    won_value = 0.0

    for lead in leads:
        pipeline[lead.stage] = pipeline.get(lead.stage, 0) + 1
        value = float(lead.estimated_value)
        total_value += value
        if lead.stage == Lead.STAGE_WON:
            won_value += value

    reminders = Reminder.objects.select_related("lead").order_by("due_at")[:8]
    notes = LeadNote.objects.select_related("lead").order_by("-created_at")[:8]

    conversion_rate = 0
    if leads:
        conversion_rate = round((pipeline.get("won", 0) / len(leads)) * 100)

    return JsonResponse(
        {
            "metrics": {
                "total_value": round(total_value, 2),
                "won_value": round(won_value, 2),
                "conversion_rate": conversion_rate,
            },
            "pipeline": pipeline,
            "reminders": [serialize_reminder(item) for item in reminders],
            "activity": [serialize_note(item) for item in notes],
        }
    )
