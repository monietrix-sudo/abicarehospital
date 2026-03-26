"""
AbiCare - Lab Results Views
=============================
Three template modes:
1. Scratch-built  → fill_lab_result_view   (text inputs per field)
2. PDF-uploaded   → annotate_pdf_result_view (Canva-style click-to-type)
3. Upload PDF template → upload_pdf_template_view
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST
import json

from .models import LabResult, LabTemplate
from apps.patients.models import Patient
from apps.audit_logs.utils import log_action


# ─────────────────────────────────────────────────────────────────────
# LIST
# ─────────────────────────────────────────────────────────────────────
@login_required
def lab_result_list_view(request):
    results = LabResult.objects.select_related('patient', 'template', 'ordered_by')

    if request.user.is_patient_user and hasattr(request.user, 'patient_profile'):
        results = results.filter(patient=request.user.patient_profile, status='released')
    elif request.user.is_doctor:
        results = results.filter(ordered_by=request.user)

    status_filter = request.GET.get('status', '')
    if status_filter:
        results = results.filter(status=status_filter)

    page_obj = Paginator(results, 20).get_page(request.GET.get('page', 1))

    return render(request, 'lab_results/result_list.html', {
        'page_title': 'Lab Results',
        'page_obj': page_obj,
        'status_choices': LabResult.STATUS_CHOICES,
        'status_filter': status_filter,
    })


# ─────────────────────────────────────────────────────────────────────
# ORDER
# ─────────────────────────────────────────────────────────────────────
@login_required
def order_lab_test_view(request, patient_hospital_number):
    if not (request.user.is_doctor or request.user.is_admin_staff):
        messages.error(request, "Only doctors can order lab tests.")
        return redirect('patients:dashboard')

    patient   = get_object_or_404(Patient, hospital_number=patient_hospital_number)
    templates = LabTemplate.objects.filter(is_active=True).order_by('category', 'name')

    if request.method == 'POST':
        template = get_object_or_404(LabTemplate, id=request.POST.get('template'))
        result   = LabResult.objects.create(
            patient=patient,
            template=template,
            result_date=request.POST.get('result_date', timezone.now().date()),
            ordered_by=request.user,
            status='pending',
        )
        log_action(request.user, 'CREATE', request,
                   f"Ordered '{template.name}' for {patient.hospital_number}")
        messages.success(request, f"Lab test '{template.name}' ordered.")

        # Route to correct fill view based on template type
        if template.is_pdf_based:
            return redirect('lab_results:annotate', pk=result.pk)
        return redirect('lab_results:fill', pk=result.pk)

    return render(request, 'lab_results/order_lab_test.html', {
        'page_title': 'Order Lab Test',
        'patient':    patient,
        'templates':  templates,
        'today':      timezone.now().date(),
    })


# ─────────────────────────────────────────────────────────────────────
# FILL (scratch-built template)
# ─────────────────────────────────────────────────────────────────────
@login_required
def fill_lab_result_view(request, pk):
    result = get_object_or_404(LabResult, pk=pk)

    if not (request.user.is_lab_tech or request.user.is_admin_staff or request.user.is_doctor):
        messages.error(request, "Permission denied.")
        return redirect('lab_results:list')

    # Redirect PDF-based results to the annotator
    if result.template and result.template.is_pdf_based:
        return redirect('lab_results:annotate', pk=pk)

    template_fields = result.template.fields if result.template else []

    if request.method == 'POST':
        values = {}
        for field in template_fields:
            name = field.get('name', '')
            values[name] = request.POST.get(f"field_{name}", '').strip()
        result.result_values  = values
        result.status         = 'ready'
        result.processed_by   = request.user
        result.notes          = request.POST.get('notes', '').strip()
        result.save()
        log_action(request.user, 'UPDATE', request, f"Filled lab result #{pk}")
        messages.success(request, "Result saved. Awaiting doctor review.")
        return redirect('lab_results:list')

    return render(request, 'lab_results/fill_result.html', {
        'page_title':      'Fill Lab Result',
        'result':          result,
        'template_fields': template_fields,
        'existing_values': result.result_values,
    })


# ─────────────────────────────────────────────────────────────────────
# ANNOTATE (PDF-based template — Canva-style)
# ─────────────────────────────────────────────────────────────────────
@login_required
def annotate_pdf_result_view(request, pk):
    result = get_object_or_404(LabResult, pk=pk)

    if not (request.user.is_lab_tech or request.user.is_admin_staff or request.user.is_doctor):
        messages.error(request, "Permission denied.")
        return redirect('lab_results:list')

    if not result.template or not result.template.is_pdf_based:
        return redirect('lab_results:fill', pk=pk)

    pdf_url = result.template.template_pdf.url if result.template.template_pdf else None

    return render(request, 'lab_results/annotate_pdf.html', {
        'page_title':       'Fill Lab Form',
        'result':           result,
        'pdf_url':          pdf_url,
        'existing_annotations': json.dumps(result.pdf_annotations),
        'save_url':         f'/lab-results/{pk}/save-annotations/',
    })


# ─────────────────────────────────────────────────────────────────────
# SAVE ANNOTATIONS (AJAX POST from annotator)
# ─────────────────────────────────────────────────────────────────────
@login_required
def save_annotations_view(request, pk):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST required'}, status=405)

    result = get_object_or_404(LabResult, pk=pk)

    if not (request.user.is_lab_tech or request.user.is_admin_staff or request.user.is_doctor):
        return JsonResponse({'ok': False, 'error': 'Permission denied'}, status=403)

    try:
        body        = json.loads(request.body)
        annotations = body.get('annotations', [])
        notes       = body.get('notes', '').strip()

        result.pdf_annotations = annotations
        result.notes           = notes
        result.status          = 'ready'
        result.processed_by    = request.user
        result.save()

        log_action(request.user, 'UPDATE', request,
                   f"Saved PDF annotations for lab result #{pk} ({len(annotations)} boxes)")
        return JsonResponse({'ok': True, 'count': len(annotations)})

    except (json.JSONDecodeError, Exception) as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)


# ─────────────────────────────────────────────────────────────────────
# DETAIL
# ─────────────────────────────────────────────────────────────────────
@login_required
def lab_result_detail_view(request, pk):
    result = get_object_or_404(LabResult, pk=pk)

    if request.user.is_patient_user:
        if not hasattr(request.user, 'patient_profile') or \
           request.user.patient_profile != result.patient or \
           not result.is_visible_to_patient:
            messages.error(request, "Access denied.")
            return redirect('patients:dashboard')

    template_fields = result.template.fields if result.template else []
    values          = result.result_values
    field_data = [
        {
            'name':         f.get('name', ''),
            'unit':         f.get('unit', ''),
            'normal_range': f.get('normal_range', ''),
            'value':        values.get(f.get('name', ''), '—'),
        }
        for f in template_fields
    ]

    log_action(request.user, 'VIEW', request, f"Viewed lab result #{pk}")

    return render(request, 'lab_results/result_detail.html', {
        'page_title': 'Lab Result',
        'result':     result,
        'field_data': field_data,
        'annotations': result.pdf_annotations,
        'pdf_url': result.template.template_pdf.url
                   if result.template and result.template.template_pdf else None,
    })


# ─────────────────────────────────────────────────────────────────────
# RELEASE
# ─────────────────────────────────────────────────────────────────────
@login_required
def release_lab_result_view(request, pk):
    if not (request.user.is_doctor or request.user.is_admin_staff):
        messages.error(request, "Only doctors can release results.")
        return redirect('lab_results:list')

    result = get_object_or_404(LabResult, pk=pk)

    if request.method == 'POST':
        result.status      = 'released'
        result.released_by = request.user
        result.released_at = timezone.now()
        result.notes       = request.POST.get('notes', result.notes).strip()
        result.save()
        log_action(request.user, 'APPROVE', request,
                   f"Released lab result #{pk} to {result.patient.hospital_number}")
        messages.success(request, "Lab result released to patient.")

    return redirect('lab_results:detail', pk=pk)


# ─────────────────────────────────────────────────────────────────────
# MANAGE TEMPLATES (scratch builder + PDF upload list)
# ─────────────────────────────────────────────────────────────────────
@login_required
def manage_templates_view(request):
    if not (request.user.is_admin_staff or request.user.is_lab_tech):
        messages.error(request, "Permission denied.")
        return redirect('patients:dashboard')

    if request.method == 'POST':
        fields_raw = request.POST.get('fields_json', '[]').strip()
        try:
            parsed_fields = json.loads(fields_raw)
        except json.JSONDecodeError:
            messages.error(request, "Invalid fields data.")
            return redirect('lab_results:templates')

        if not parsed_fields:
            messages.error(request, "Please add at least one parameter.")
            return redirect('lab_results:templates')

        template_id = request.POST.get('template_id', '').strip()
        if template_id:
            tpl             = get_object_or_404(LabTemplate, pk=template_id)
            tpl.name        = request.POST.get('name', tpl.name).strip()
            tpl.category    = request.POST.get('category', tpl.category)
            tpl.description = request.POST.get('description', '').strip()
            tpl.fields_json = fields_raw
            tpl.save()
            log_action(request.user, 'UPDATE', request, f"Updated template: {tpl.name}")
            messages.success(request, f"Template '{tpl.name}' updated.")
        else:
            name = request.POST.get('name', '').strip()
            if not name:
                messages.error(request, "Template name is required.")
                return redirect('lab_results:templates')
            if LabTemplate.objects.filter(name__iexact=name).exists():
                messages.error(request, f"'{name}' already exists.")
                return redirect('lab_results:templates')
            tpl = LabTemplate.objects.create(
                name=name,
                category=request.POST.get('category', 'other'),
                description=request.POST.get('description', '').strip(),
                fields_json=fields_raw,
                template_type=LabTemplate.TYPE_SCRATCH,
                created_by=request.user,
            )
            log_action(request.user, 'CREATE', request, f"Created template: {tpl.name}")
            messages.success(request, f"Template '{tpl.name}' created.")

        return redirect('lab_results:templates')

    templates_qs   = LabTemplate.objects.all().order_by('category', 'name')
    templates_list = []
    for tpl in templates_qs:
        templates_list.append({
            'pk':               tpl.pk,
            'name':             tpl.name,
            'category':         tpl.category,
            'category_display': tpl.get_category_display(),
            'description':      tpl.description,
            'is_active':        tpl.is_active,
            'template_type':    tpl.template_type,
            'is_pdf_based':     tpl.is_pdf_based,
            'fields':           tpl.fields,
            'fields_json':      tpl.fields_json,
            'created_at':       tpl.created_at,
            'field_count':      len(tpl.fields),
            'pdf_url':          tpl.template_pdf.url if tpl.template_pdf else None,
        })

    grouped = {}
    for tpl in templates_list:
        grouped.setdefault(tpl['category_display'], []).append(tpl)

    return render(request, 'lab_results/manage_templates.html', {
        'page_title':        'Lab Templates',
        'templates_list':    templates_list,
        'grouped_templates': grouped,
        'template_count':    len(templates_list),
        'category_choices':  LabTemplate.CATEGORY_CHOICES,
    })


# ─────────────────────────────────────────────────────────────────────
# UPLOAD PDF TEMPLATE
# ─────────────────────────────────────────────────────────────────────
@login_required
def upload_pdf_template_view(request):
    if not (request.user.is_admin_staff or request.user.is_lab_tech):
        messages.error(request, "Permission denied.")
        return redirect('patients:dashboard')

    if request.method == 'POST':
        name        = request.POST.get('name', '').strip()
        category    = request.POST.get('category', 'other')
        description = request.POST.get('description', '').strip()
        pdf_file    = request.FILES.get('template_pdf')

        if not name:
            messages.error(request, "Template name is required.")
            return redirect('lab_results:upload_pdf_template')

        if not pdf_file:
            messages.error(request, "Please select a PDF file to upload.")
            return redirect('lab_results:upload_pdf_template')

        if not pdf_file.name.lower().endswith('.pdf'):
            messages.error(request, "Only PDF files are accepted.")
            return redirect('lab_results:upload_pdf_template')

        if pdf_file.size > 20 * 1024 * 1024:
            messages.error(request, "PDF must be under 20MB.")
            return redirect('lab_results:upload_pdf_template')

        if LabTemplate.objects.filter(name__iexact=name).exists():
            messages.error(request, f"A template named '{name}' already exists.")
            return redirect('lab_results:upload_pdf_template')

        tpl = LabTemplate.objects.create(
            name=name,
            category=category,
            description=description,
            template_type=LabTemplate.TYPE_PDF,
            template_pdf=pdf_file,
            fields_json='[]',
            created_by=request.user,
        )
        log_action(request.user, 'UPLOAD', request,
                   f"Uploaded PDF lab template: {name}")
        messages.success(request, f"PDF template '{name}' uploaded successfully.")
        return redirect('lab_results:templates')

    return render(request, 'lab_results/upload_pdf_template.html', {
        'page_title':       'Upload PDF Template',
        'category_choices': LabTemplate.CATEGORY_CHOICES,
    })
