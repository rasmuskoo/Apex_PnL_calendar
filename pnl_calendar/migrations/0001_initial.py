from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="PropFirm",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120, unique=True)),
                ("code", models.SlugField(max_length=40, unique=True)),
                ("is_active", models.BooleanField(default=True)),
                ("funded_account_limit", models.PositiveIntegerField(default=0)),
                ("display_order", models.PositiveIntegerField(default=0)),
            ],
            options={"ordering": ("display_order", "name")},
        ),
        migrations.CreateModel(
            name="PropAccount",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nickname", models.CharField(max_length=120)),
                ("external_id", models.CharField(blank=True, max_length=120)),
                (
                    "stage",
                    models.CharField(
                        choices=[("evaluation", "Evaluation"), ("funded", "Funded")],
                        default="evaluation",
                        max_length=20,
                    ),
                ),
                ("account_size", models.DecimalField(decimal_places=2, max_digits=12)),
                ("is_active", models.BooleanField(default=True)),
                (
                    "firm",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="accounts", to="pnl_calendar.propfirm"),
                ),
            ],
            options={"ordering": ("firm", "nickname"), "unique_together": {("firm", "nickname")}},
        ),
        migrations.CreateModel(
            name="Trade",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("trade_date", models.DateField()),
                ("instrument", models.CharField(blank=True, max_length=60)),
                ("gross_pnl", models.DecimalField(decimal_places=2, max_digits=12)),
                ("broker_fees", models.DecimalField(decimal_places=2, default="0.00", max_digits=10)),
                ("notes", models.TextField(blank=True)),
                (
                    "account",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="trades", to="pnl_calendar.propaccount"),
                ),
            ],
            options={"ordering": ("-trade_date", "id")},
        ),
    ]
