"""
AbiCare Nursing Module — Initial Migration
Creates: DutyRoster, RosterEntry, ShiftReport, VitalsRecord,
         MedicationAdminRecord, NursingNote, MaterialUsed
"""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('patients', '__first__'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [

        # ── DutyRoster ────────────────────────────────────────────────
        migrations.CreateModel(
            name='DutyRoster',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200)),
                ('ward', models.CharField(
                    choices=[
                        ('general_male',   'General Ward (Male)'),
                        ('general_female', 'General Ward (Female)'),
                        ('paediatric',     'Paediatric Ward'),
                        ('maternity',      'Maternity Ward'),
                        ('icu',            'ICU / Critical Care'),
                        ('surgical',       'Surgical Ward'),
                        ('medical',        'Medical Ward'),
                        ('emergency',      'Emergency Ward'),
                        ('all',            'All Wards'),
                    ],
                    default='all', max_length=20
                )),
                ('start_date',   models.DateField()),
                ('end_date',     models.DateField()),
                ('status', models.CharField(
                    choices=[
                        ('draft', 'Draft'),
                        ('confirmed', 'Confirmed — Distributed'),
                        ('archived', 'Archived'),
                    ],
                    default='draft', max_length=10
                )),
                ('notes',        models.TextField(blank=True)),
                ('confirmed_at', models.DateTimeField(blank=True, null=True)),
                ('created_at',   models.DateTimeField(auto_now_add=True)),
                ('confirmed_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='confirmed_rosters',
                    to=settings.AUTH_USER_MODEL
                )),
                ('created_by', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='created_rosters',
                    to=settings.AUTH_USER_MODEL
                )),
            ],
            options={'ordering': ['-start_date'], 'verbose_name': 'Duty Roster'},
        ),

        # ── RosterEntry ───────────────────────────────────────────────
        migrations.CreateModel(
            name='RosterEntry',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('date',  models.DateField()),
                ('shift', models.CharField(
                    choices=[
                        ('morning',   'Morning  07:00 — 15:00'),
                        ('afternoon', 'Afternoon 15:00 — 23:00'),
                        ('night',     'Night    23:00 — 07:00'),
                        ('day',       'Day      07:00 — 19:00'),
                        ('off',       'Day Off'),
                    ],
                    max_length=10
                )),
                ('ward',  models.CharField(blank=True, max_length=20)),
                ('notes', models.CharField(blank=True, max_length=200)),
                ('nurse', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='roster_entries',
                    to=settings.AUTH_USER_MODEL
                )),
                ('roster', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='entries',
                    to='nursing.dutyroster'
                )),
            ],
            options={
                'verbose_name': 'Roster Entry',
                'ordering': ['date', 'shift'],
                'unique_together': {('roster', 'nurse', 'date')},
            },
        ),

        # ── ShiftReport ───────────────────────────────────────────────
        migrations.CreateModel(
            name='ShiftReport',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('report_id',   models.UUIDField(default=uuid.uuid4,
                                                 editable=False, unique=True)),
                ('shift', models.CharField(
                    choices=[
                        ('morning',   'Morning  07:00–15:00'),
                        ('afternoon', 'Afternoon 15:00–23:00'),
                        ('night',     'Night    23:00–07:00'),
                        ('day',       'Day      07:00–19:00'),
                    ],
                    max_length=10
                )),
                ('ward',  models.CharField(default='general_female', max_length=20)),
                ('date',  models.DateField(default=django.utils.timezone.now)),
                ('shift_start', models.DateTimeField(default=django.utils.timezone.now)),
                ('shift_end',   models.DateTimeField(blank=True, null=True)),
                ('handover_summary',   models.TextField(blank=True)),
                ('outstanding_tasks',  models.TextField(blank=True)),
                ('incidents',          models.TextField(blank=True)),
                ('general_ward_notes', models.TextField(blank=True)),
                ('patients_admitted',   models.PositiveIntegerField(default=0)),
                ('patients_discharged', models.PositiveIntegerField(default=0)),
                ('patients_on_ward',    models.PositiveIntegerField(default=0)),
                ('is_submitted',  models.BooleanField(default=False)),
                ('submitted_at',  models.DateTimeField(blank=True, null=True)),
                ('created_at',    models.DateTimeField(auto_now_add=True)),
                ('updated_at',    models.DateTimeField(auto_now=True)),
                ('nurse', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='shift_reports',
                    to=settings.AUTH_USER_MODEL
                )),
                ('reviewed_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='reviewed_shift_reports',
                    to=settings.AUTH_USER_MODEL
                )),
                ('reviewed_at', models.DateTimeField(blank=True, null=True)),
            ],
            options={
                'verbose_name': 'Shift Report',
                'ordering': ['-date', '-shift_start'],
            },
        ),

        # ── VitalsRecord ──────────────────────────────────────────────
        migrations.CreateModel(
            name='VitalsRecord',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('recorded_at',        models.DateTimeField(default=django.utils.timezone.now)),
                ('temperature',        models.DecimalField(blank=True, decimal_places=1,
                                                           max_digits=4, null=True)),
                ('pulse_rate',         models.PositiveIntegerField(blank=True, null=True)),
                ('respiratory_rate',   models.PositiveIntegerField(blank=True, null=True)),
                ('blood_pressure_sys', models.PositiveIntegerField(blank=True, null=True)),
                ('blood_pressure_dia', models.PositiveIntegerField(blank=True, null=True)),
                ('oxygen_saturation',  models.DecimalField(blank=True, decimal_places=1,
                                                           max_digits=4, null=True)),
                ('blood_glucose',      models.DecimalField(blank=True, decimal_places=1,
                                                           max_digits=5, null=True)),
                ('weight_kg',          models.DecimalField(blank=True, decimal_places=1,
                                                           max_digits=5, null=True)),
                ('height_cm',          models.DecimalField(blank=True, decimal_places=1,
                                                           max_digits=5, null=True)),
                ('pain_score',         models.PositiveIntegerField(blank=True, null=True)),
                ('consciousness', models.CharField(
                    blank=True, max_length=15,
                    choices=[
                        ('alert',        'Alert'),
                        ('voice',        'Responds to Voice'),
                        ('pain',         'Responds to Pain'),
                        ('unresponsive', 'Unresponsive'),
                    ]
                )),
                ('urine_output_ml', models.PositiveIntegerField(blank=True, null=True)),
                ('notes', models.TextField(blank=True)),
                ('patient', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='vitals_records',
                    to='patients.patient'
                )),
                ('recorded_by', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    to=settings.AUTH_USER_MODEL
                )),
                ('shift_report', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='vitals',
                    to='nursing.shiftreport'
                )),
            ],
            options={'verbose_name': 'Vitals Record', 'ordering': ['-recorded_at']},
        ),

        # ── MedicationAdminRecord ─────────────────────────────────────
        migrations.CreateModel(
            name='MedicationAdminRecord',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('medication_name',  models.CharField(max_length=200)),
                ('dosage',           models.CharField(max_length=100)),
                ('route',            models.CharField(blank=True, max_length=50)),
                ('scheduled_time',   models.DateTimeField()),
                ('given_time',       models.DateTimeField(blank=True, null=True)),
                ('status', models.CharField(
                    choices=[
                        ('given',    'Given'),
                        ('withheld', 'Withheld'),
                        ('refused',  'Patient Refused'),
                        ('missed',   'Missed'),
                        ('late',     'Given Late'),
                    ],
                    default='given', max_length=10
                )),
                ('reason_withheld', models.TextField(blank=True)),
                ('notes',           models.TextField(blank=True)),
                ('administered_by', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='administered_medications',
                    to=settings.AUTH_USER_MODEL
                )),
                ('patient', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='mar_records',
                    to='patients.patient'
                )),
                ('shift_report', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='mar_entries',
                    to='nursing.shiftreport'
                )),
            ],
            options={
                'verbose_name': 'Medication Administration Record',
                'ordering': ['-scheduled_time'],
            },
        ),

        # ── NursingNote ───────────────────────────────────────────────
        migrations.CreateModel(
            name='NursingNote',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('note_type', models.CharField(
                    choices=[
                        ('observation',   'Clinical Observation'),
                        ('procedure',     'Procedure Performed'),
                        ('communication', 'Communication / Family Update'),
                        ('handover',      'Handover Note'),
                        ('incident',      'Incident Report'),
                        ('general',       'General Note'),
                    ],
                    default='observation', max_length=20
                )),
                ('content',    models.TextField()),
                ('was_voice',  models.BooleanField(default=False)),
                ('is_flagged', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('patient', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='nursing_notes',
                    to='patients.patient'
                )),
                ('written_by', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='nursing_notes',
                    to=settings.AUTH_USER_MODEL
                )),
                ('shift_report', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='notes',
                    to='nursing.shiftreport'
                )),
            ],
            options={'verbose_name': 'Nursing Note', 'ordering': ['-created_at']},
        ),

        # ── MaterialUsed ──────────────────────────────────────────────
        migrations.CreateModel(
            name='MaterialUsed',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('category', models.CharField(
                    choices=[
                        ('dressing',   'Dressing / Wound Care'),
                        ('cannula',    'IV Cannula / Lines'),
                        ('syringe',    'Syringe / Needle'),
                        ('gloves',     'Gloves / PPE'),
                        ('catheter',   'Catheter / Tubing'),
                        ('bandage',    'Bandage / Gauze'),
                        ('medication', 'Medication (unit used)'),
                        ('oxygen',     'Oxygen (litres)'),
                        ('blood',      'Blood / Blood Products'),
                        ('other',      'Other'),
                    ],
                    max_length=15
                )),
                ('item_name',   models.CharField(max_length=200)),
                ('quantity',    models.DecimalField(decimal_places=2, default=1, max_digits=8)),
                ('unit',        models.CharField(blank=True, max_length=30)),
                ('notes',       models.CharField(blank=True, max_length=300)),
                ('recorded_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('patient', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='materials_used',
                    to='patients.patient'
                )),
                ('recorded_by', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    to=settings.AUTH_USER_MODEL
                )),
                ('shift_report', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='materials',
                    to='nursing.shiftreport'
                )),
            ],
            options={
                'verbose_name': 'Material Used',
                'verbose_name_plural': 'Materials Used',
                'ordering': ['-recorded_at'],
            },
        ),
    ]
