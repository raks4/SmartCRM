from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Lead",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("company_name", models.CharField(max_length=180)),
                ("contact_name", models.CharField(max_length=120)),
                ("contact_email", models.EmailField(blank=True, max_length=254)),
                ("contact_phone", models.CharField(blank=True, max_length=32)),
                ("source", models.CharField(blank=True, max_length=80)),
                (
                    "stage",
                    models.CharField(
                        choices=[
                            ("new", "New"),
                            ("qualified", "Qualified"),
                            ("proposal", "Proposal"),
                            ("negotiation", "Negotiation"),
                            ("won", "Won"),
                            ("lost", "Lost"),
                        ],
                        default="new",
                        max_length=24,
                    ),
                ),
                ("estimated_value", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("assigned_to", models.CharField(blank=True, max_length=120)),
                ("last_touch", models.DateField(blank=True, null=True)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name="LeadNote",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("owner", models.CharField(max_length=120)),
                (
                    "channel",
                    models.CharField(
                        choices=[
                            ("email", "Email"),
                            ("call", "Call"),
                            ("meeting", "Meeting"),
                            ("chat", "Chat"),
                        ],
                        default="email",
                        max_length=24,
                    ),
                ),
                ("note", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "lead",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="activity_notes", to="leads.lead"),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Reminder",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("task", models.CharField(max_length=180)),
                ("due_at", models.DateTimeField()),
                ("is_done", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "lead",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="reminders", to="leads.lead"),
                ),
            ],
        ),
    ]
