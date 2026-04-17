import json
import os
from urllib import error, request as urllib_request
from datetime import datetime
from django.db import IntegrityError

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods

from .models import Lead, LeadNote, Reminder


STAGE_PROBABILITY = {
    Lead.STAGE_NEW: 0.12,
    Lead.STAGE_QUALIFIED: 0.28,
    Lead.STAGE_PROPOSAL: 0.46,
    Lead.STAGE_NEGOTIATION: 0.66,
    Lead.STAGE_WON: 1.0,
    Lead.STAGE_LOST: 0.02,
}


def seed_demo_leads_if_empty():
    if Lead.objects.exists():
        return

    demo_leads = [
        {
            "company_name": "Acme Corp",
            "contact_name": "Wile Coyote",
            "contact_email": "wile@acme.com",
            "contact_phone": "555-0199",
            "source": "Referral",
            "stage": Lead.STAGE_PROPOSAL,
            "estimated_value": 50000,
            "assigned_to": "admin",
            "last_touch": timezone.now().date(),
            "notes": "Asked for proposal revisions and implementation timeline.",
        },
        {
            "company_name": "Stark Industries",
            "contact_name": "Tony Stark",
            "contact_email": "tony@stark.com",
            "contact_phone": "555-0200",
            "source": "Website",
            "stage": Lead.STAGE_NEGOTIATION,
            "estimated_value": 1200000,
            "assigned_to": "admin",
            "last_touch": timezone.now().date(),
            "notes": "Procurement review in progress; security questionnaire pending.",
        },
        {
            "company_name": "Wayne Enterprises",
            "contact_name": "Bruce Wayne",
            "contact_email": "bruce@wayne.com",
            "contact_phone": "555-0300",
            "source": "Direct",
            "stage": Lead.STAGE_WON,
            "estimated_value": 850000,
            "assigned_to": "admin",
            "last_touch": timezone.now().date(),
            "notes": "Deal closed. Kickoff scheduled for next sprint.",
        },
        {
            "company_name": "Oscorp",
            "contact_name": "Norman Osborn",
            "contact_email": "norman@oscorp.com",
            "contact_phone": "555-0500",
            "source": "Organic Search",
            "stage": Lead.STAGE_QUALIFIED,
            "estimated_value": 400000,
            "assigned_to": "admin",
            "last_touch": timezone.now().date(),
            "notes": "Qualified lead. Technical demo requested for decision committee.",
        },
    ]

    for item in demo_leads:
        Lead.objects.create(**item)


def _clamp(value: float, lower: float, upper: float):
    return max(lower, min(upper, value))


def build_lead_ai_insight(lead: Lead, note_count: int = 0, open_reminders: int = 0):
    now_date = timezone.now().date()
    days_since_touch = (now_date - lead.last_touch).days if lead.last_touch else 999
    base_prob = STAGE_PROBABILITY.get(lead.stage, 0.2)

    value = float(lead.estimated_value or 0)
    value_bonus = 0.08 if value >= 100000 else 0.03 if value >= 25000 else 0.0
    activity_bonus = min(note_count, 5) * 0.015
    stale_penalty = 0.22 if days_since_touch > 14 else 0.1 if days_since_touch > 7 else 0.0
    reminder_penalty = min(open_reminders, 4) * 0.02

    notes_text = (lead.notes or "").lower()
    positive_signals = ["budget", "approved", "signed", "pilot", "interested", "urgent"]
    risk_signals = ["delay", "silent", "no response", "price", "blocked", "later"]

    text_bonus = 0.05 if any(token in notes_text for token in positive_signals) else 0.0
    text_penalty = 0.08 if any(token in notes_text for token in risk_signals) else 0.0

    win_probability = _clamp(
        base_prob + value_bonus + activity_bonus + text_bonus - stale_penalty - reminder_penalty - text_penalty,
        0.03,
        0.99,
    )
    ai_score = round(win_probability * 100)

    if lead.stage in [Lead.STAGE_WON, Lead.STAGE_LOST]:
        next_action = "Archive outcome and capture lessons learned"
    elif days_since_touch > 14:
        next_action = "High urgency: schedule a call within 24h"
    elif lead.stage in [Lead.STAGE_PROPOSAL, Lead.STAGE_NEGOTIATION]:
        next_action = "Send a concise value recap and close-date proposal"
    elif lead.stage == Lead.STAGE_QUALIFIED:
        next_action = "Book discovery meeting and confirm budget/timeline"
    else:
        next_action = "Run qualification checklist and identify decision maker"

    risk_level = "high" if ai_score < 35 else "medium" if ai_score < 65 else "low"
    expected_value = round(value * win_probability, 2)
    recommended_follow_up_days = 1 if risk_level == "high" else 3 if risk_level == "medium" else 5

    return {
        "lead_id": lead.id,
        "company_name": lead.company_name,
        "stage": lead.stage,
        "estimated_value": value,
        "expected_value": expected_value,
        "win_probability": round(win_probability * 100, 1),
        "ai_score": ai_score,
        "risk_level": risk_level,
        "days_since_touch": days_since_touch if lead.last_touch else None,
        "open_reminders": open_reminders,
        "activity_count": note_count,
        "next_action": next_action,
        "recommended_follow_up_days": recommended_follow_up_days,
    }


def parse_json_body(request: HttpRequest):
    try:
        return json.loads(request.body.decode("utf-8")) if request.body else {}
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


def _call_ollama(prompt: str):
    ollama_base = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    preferred_model = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:3b")
    ollama_timeout = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "45"))
    ollama_keep_alive = os.getenv("OLLAMA_KEEP_ALIVE", "10m")
    generation_options = {
        "temperature": float(os.getenv("OLLAMA_TEMPERATURE", "0.1")),
        "num_predict": int(os.getenv("OLLAMA_NUM_PREDICT", "96")),
        "num_ctx": int(os.getenv("OLLAMA_NUM_CTX", "1024")),
    }

    def _build_candidates(model_name: str):
        return [
            (
                f"{ollama_base.rstrip('/')}/api/generate",
                {
                    "model": model_name,
                    "prompt": prompt,
                    "stream": False,
                    "keep_alive": ollama_keep_alive,
                    "options": generation_options,
                },
                "response",
            ),
            (
                f"{ollama_base.rstrip('/')}/api/chat",
                {
                    "model": model_name,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "keep_alive": ollama_keep_alive,
                    "options": generation_options,
                },
                "message.content",
            ),
        ]

    model_candidates = [preferred_model]
    fallback_models = [m.strip() for m in os.getenv("OLLAMA_FALLBACK_MODELS", "llama3.2,qwen2.5-coder:3b").split(",") if m.strip()]
    for model_name in fallback_models:
        if model_name not in model_candidates:
            model_candidates.append(model_name)

    last_error = None
    for model_name in model_candidates:
        candidates = _build_candidates(model_name)
        for ollama_url, payload, response_field in candidates:
            encoded_payload = json.dumps(payload).encode("utf-8")
            req = urllib_request.Request(
                ollama_url,
                data=encoded_payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )

            try:
                with urllib_request.urlopen(req, timeout=ollama_timeout) as resp:
                    body = resp.read().decode("utf-8")
                    data = json.loads(body)
            except error.HTTPError as exc:
                error_body = ""
                try:
                    error_body = exc.read().decode("utf-8")
                except Exception:
                    error_body = ""

                if exc.code == 404 and "model" in error_body.lower() and "not found" in error_body.lower():
                    last_error = f"Model {model_name} not found in local Ollama"
                    break

                last_error = f"{ollama_url} returned HTTP {exc.code}"
                if exc.code == 404:
                    continue
                return None, f"Could not use Ollama at {ollama_url}: HTTP {exc.code}"
            except error.URLError as exc:
                return None, f"Could not reach Ollama at {ollama_url}: {exc.reason}"
            except TimeoutError:
                return None, "Ollama request timed out."
            except json.JSONDecodeError:
                return None, "Ollama returned non-JSON response."

            if response_field == "response":
                response_text = (data or {}).get("response", "").strip()
            else:
                response_text = ((data or {}).get("message") or {}).get("content", "").strip()

            if response_text:
                return response_text, None

            last_error = f"{ollama_url} returned empty response"

    return None, last_error or "Ollama did not return a valid response."


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


def _fast_snapshot_answer(user_prompt: str, data_snapshot: dict):
    prompt = user_prompt.lower()
    lead_count = data_snapshot.get("lead_count", 0)
    total_pipeline_value = data_snapshot.get("total_pipeline_value", 0)
    highest_lead = data_snapshot.get("highest_lead")
    stage_counts = data_snapshot.get("stage_counts") or {}
    top_leads = data_snapshot.get("top_leads") or []

    if lead_count == 0:
        return None

    asks_highest = "highest" in prompt and ("lead" in prompt or "value" in prompt)
    asks_total = "total pipeline" in prompt or ("pipeline" in prompt and "value" in prompt)
    asks_count = "lead count" in prompt or ("how many" in prompt and "lead" in prompt)
    asks_stage = "stage" in prompt or "breakdown" in prompt or "funnel" in prompt
    asks_top = "top" in prompt and ("lead" in prompt or "opportun" in prompt)

    if not any([asks_highest, asks_total, asks_count, asks_stage, asks_top]):
        return None

    lines = []

    if asks_count:
        lines.append(f"- Lead count: {lead_count}")

    if asks_total:
        lines.append(f"- Total pipeline value: ${total_pipeline_value:,.0f}")

    if asks_highest:
        if highest_lead:
            lines.append(
                "- Highest lead value: "
                f"{highest_lead['company_name']} (${highest_lead['estimated_value']:,.0f}, stage={highest_lead['stage']})"
            )
        else:
            lines.append("- Highest lead value: Data not available")

    if asks_stage and stage_counts:
        lines.append(
            "- Stage breakdown: "
            f"new={stage_counts.get('new', 0)}, "
            f"qualified={stage_counts.get('qualified', 0)}, "
            f"proposal={stage_counts.get('proposal', 0)}, "
            f"negotiation={stage_counts.get('negotiation', 0)}, "
            f"won={stage_counts.get('won', 0)}, "
            f"lost={stage_counts.get('lost', 0)}"
        )

    if asks_top and top_leads:
        top3 = top_leads[:3]
        lines.append("- Top opportunities:")
        for item in top3:
            lines.append(f"  - {item['company_name']} (${item['estimated_value']:,.0f}, stage={item['stage']})")

    lines.append("- Next step: ask a focused follow-up (e.g., 'what should I do this week to close top 2 deals?').")
    return "\n".join(lines)


def _fallback_chat_answer(user_prompt: str, data_snapshot: dict, ollama_error: str | None = None):
    lead_count = data_snapshot.get("lead_count", 0)
    stage_counts = data_snapshot.get("stage_counts") or {}
    top_leads = data_snapshot.get("top_leads") or []
    total_pipeline_value = float(data_snapshot.get("total_pipeline_value") or 0)

    won = stage_counts.get("won", 0)
    conversion_rate = round((won / lead_count) * 100) if lead_count else 0

    lines = [
        "Local AI is in fast fallback mode.",
        f"- Lead count: {lead_count}",
        f"- Pipeline value: ${total_pipeline_value:,.0f}",
        f"- Current conversion: {conversion_rate}%",
    ]

    if top_leads:
        top = top_leads[0]
        lines.append(
            f"- Top opportunity: {top['company_name']} (${top['estimated_value']:,.0f}, stage={top['stage']})"
        )

    lines.append("- Suggested next action: prioritize leads in proposal/negotiation and schedule follow-ups within 48h.")
    lines.append(f"- Your question was: {user_prompt[:120]}")

    if ollama_error:
        lines.append(f"- Model status: {ollama_error}")

    return "\n".join(lines)


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
def signup_view(request: HttpRequest):
    data = parse_json_body(request)
    if data is None:
        return JsonResponse({"detail": "Invalid JSON payload."}, status=400)

    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    confirm_password = data.get("confirm_password") or ""

    if not username or not password:
        return JsonResponse({"detail": "username and password are required."}, status=400)

    if password != confirm_password:
        return JsonResponse({"detail": "password and confirm_password must match."}, status=400)

    if len(password) < 8:
        return JsonResponse({"detail": "password must be at least 8 characters."}, status=400)

    try:
        user = User.objects.create_user(username=username, password=password)
    except IntegrityError:
        return JsonResponse({"detail": "Username already exists."}, status=409)

    login(request, user)
    return JsonResponse(
        {
            "user": {
                "id": user.id,
                "username": user.username,
                "is_staff": user.is_staff,
            }
        },
        status=201,
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
        seed_demo_leads_if_empty()
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


@require_GET
def ai_insights_view(_request: HttpRequest):
    leads = list(Lead.objects.prefetch_related("activity_notes", "reminders").all())
    lead_insights = []

    for lead in leads:
        note_count = lead.activity_notes.count()
        open_reminders = lead.reminders.filter(is_done=False).count()
        lead_insights.append(build_lead_ai_insight(lead, note_count=note_count, open_reminders=open_reminders))

    ranked = sorted(lead_insights, key=lambda item: item["ai_score"], reverse=True)
    at_risk = sorted(
        [item for item in lead_insights if item["risk_level"] != "low"],
        key=lambda item: item["ai_score"],
    )

    total_expected_revenue = round(sum(item["expected_value"] for item in lead_insights), 2)
    total_pipeline_value = round(sum(item["estimated_value"] for item in lead_insights), 2)

    avg_win_probability = 0.0
    if lead_insights:
        avg_win_probability = round(
            sum(item["win_probability"] for item in lead_insights) / len(lead_insights),
            1,
        )

    return JsonResponse(
        {
            "summary": {
                "lead_count": len(lead_insights),
                "average_win_probability": avg_win_probability,
                "expected_revenue": total_expected_revenue,
                "pipeline_value": total_pipeline_value,
                "forecast_gap": round(total_pipeline_value - total_expected_revenue, 2),
            },
            "top_opportunities": ranked[:5],
            "at_risk": at_risk[:5],
            "all": ranked,
        }
    )


@csrf_exempt
@require_http_methods(["POST"])
def ai_chat_view(request: HttpRequest):
    data = parse_json_body(request)
    if data is None:
        return JsonResponse({"detail": "Invalid JSON payload."}, status=400)

    user_prompt = (data.get("prompt") or "").strip()
    if not user_prompt:
        return JsonResponse({"detail": "prompt is required."}, status=400)

    leads = list(Lead.objects.all())
    leads_by_value = sorted(leads, key=lambda item: float(item.estimated_value), reverse=True)

    top_leads = []
    for lead in leads_by_value[:3]:
        top_leads.append(
            {
                "company_name": lead.company_name,
                "stage": lead.stage,
                "estimated_value": float(lead.estimated_value),
                "last_touch": lead.last_touch.isoformat() if lead.last_touch else None,
                "notes": (lead.notes or "")[:80],
            }
        )

    stage_counts = {
        Lead.STAGE_NEW: 0,
        Lead.STAGE_QUALIFIED: 0,
        Lead.STAGE_PROPOSAL: 0,
        Lead.STAGE_NEGOTIATION: 0,
        Lead.STAGE_WON: 0,
        Lead.STAGE_LOST: 0,
    }
    total_pipeline_value = 0.0
    for lead in leads:
        stage_counts[lead.stage] = stage_counts.get(lead.stage, 0) + 1
        total_pipeline_value += float(lead.estimated_value or 0)

    highest_lead = None
    if leads_by_value:
        lead = leads_by_value[0]
        highest_lead = {
            "company_name": lead.company_name,
            "estimated_value": float(lead.estimated_value),
            "stage": lead.stage,
        }

    data_snapshot = {
        "lead_count": len(leads),
        "total_pipeline_value": round(total_pipeline_value, 2),
        "highest_lead": highest_lead,
        "stage_counts": stage_counts,
        "top_leads": top_leads,
    }

    if data_snapshot["lead_count"] == 0:
        return JsonResponse(
            {
                "model": "rule-based",
                "reply": (
                    "No leads exist in backend data yet.\n"
                    "- Highest lead value: Data not available\n"
                    "- Total pipeline value: 0\n"
                    "Next step: create at least one lead in backend, then ask again for highest lead value and top opportunities."
                ),
            }
        )

    fast_reply = _fast_snapshot_answer(user_prompt, data_snapshot)
    if fast_reply:
        return JsonResponse(
            {
                "model": "rule-based-fast",
                "reply": fast_reply,
            }
        )

    system_prompt = (
        "You are a CRM copilot that MUST stay grounded in the provided CRM data. "
        "Use exact numbers and company names from the data snapshot when available. "
        "NEVER output placeholders like [Insert ...]. "
        "If a value is missing, explicitly say 'Data not available'. "
        "Keep response concise with bullets and include concrete next steps. "
        "Limit to at most 6 bullet points."
    )
    compiled_prompt = (
        f"{system_prompt}\n\n"
        f"CRM data snapshot:\n{json.dumps(data_snapshot, ensure_ascii=True)}\n\n"
        f"User request:\n{user_prompt[:180]}\n\n"
        "Return a compact answer for a sales rep, grounded only in snapshot data."
    )

    response_text, err = _call_ollama(compiled_prompt)
    if err:
        return JsonResponse(
            {
                "model": "rule-based-fallback",
                "reply": _fallback_chat_answer(user_prompt, data_snapshot, ollama_error=err),
                "degraded": True,
            }
        )

    return JsonResponse(
        {
            "model": os.getenv("OLLAMA_MODEL", "llama3.2"),
            "reply": response_text,
        }
    )
