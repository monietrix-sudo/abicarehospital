"""
AbiCare - Family Groups Views
================================
IMPORTANT PRIVACY RULE enforced in every view:
- Searching or viewing a family shows names and hospital numbers ONLY
- Health data (records, results, medications) is NEVER shown here
- Each patient's health data is only accessible via their individual profile
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.http import JsonResponse

from .models import FamilyGroup, FamilyMember
from apps.patients.models import Patient
from apps.audit_logs.utils import log_action


@login_required
def family_list_view(request):
    """List all families with optional search by family name."""
    query    = request.GET.get('q', '').strip()
    families = FamilyGroup.objects.filter(is_active=True)

    if query:
        families = families.filter(family_name__icontains=query)

    families = families.prefetch_related('members__patient')

    return render(request, 'families/family_list.html', {
        'page_title': 'Family Groups',
        'families':   families,
        'query':      query,
    })


@login_required
def family_detail_view(request, pk):
    """Show one family and its members (names + hospital numbers only)."""
    family  = get_object_or_404(FamilyGroup, pk=pk, is_active=True)
    members = FamilyMember.objects.filter(
        family=family, is_active=True
    ).select_related('patient', 'added_by').order_by('relationship', 'patient__last_name')

    log_action(request.user, 'VIEW', request,
               f"Viewed family group: {family.family_name}")

    return render(request, 'families/family_detail.html', {
        'page_title':         family.family_name,
        'family':             family,
        'members':            members,
        'relationship_choices': FamilyMember.RELATIONSHIP_CHOICES,
    })


@login_required
def create_family_view(request):
    """Create a new family group."""
    if request.method == 'POST':
        name = request.POST.get('family_name', '').strip()

        if not name:
            messages.error(request, "Family name is required.")
            return render(request, 'families/create_family.html', {
                'page_title': 'Create Family Group',
            })

        # Check for duplicate name
        if FamilyGroup.objects.filter(family_name__iexact=name, is_active=True).exists():
            messages.error(request,
                f"A family named '{name}' already exists. "
                f"Search for it and add members instead.")
            return render(request, 'families/create_family.html', {
                'page_title': 'Create Family Group',
                'form_name':  name,
            })

        family = FamilyGroup.objects.create(
            family_name=name,
            address=request.POST.get('address', '').strip(),
            notes=request.POST.get('notes', '').strip(),
            created_by=request.user,
        )

        log_action(request.user, 'CREATE', request,
                   f"Created family group: {name}")
        messages.success(request,
            f"Family '{name}' created. Now add members below.")
        return redirect('families:detail', pk=family.pk)

    return render(request, 'families/create_family.html', {
        'page_title': 'Create Family Group',
    })


@login_required
def add_member_view(request, family_pk):
    """Add a patient to a family with a relationship."""
    family = get_object_or_404(FamilyGroup, pk=family_pk, is_active=True)

    if request.method == 'POST':
        patient_id   = request.POST.get('patient_id')
        relationship = request.POST.get('relationship', 'other')
        notes        = request.POST.get('notes', '').strip()

        if not patient_id:
            messages.error(request, "Please select a patient.")
            return redirect('families:detail', pk=family_pk)

        patient = get_object_or_404(Patient, pk=patient_id, is_active=True)

        # Check if this patient is already in this family
        existing = FamilyMember.objects.filter(
            family=family, patient=patient
        ).first()

        if existing:
            if existing.is_active:
                messages.warning(request,
                    f"{patient.full_name} is already a member of {family.family_name}.")
            else:
                # Re-activate if they were previously removed
                existing.is_active    = True
                existing.relationship = relationship
                existing.added_by     = request.user
                existing.save()
                messages.success(request,
                    f"{patient.full_name} re-added to {family.family_name}.")
        else:
            # Check if trying to add a second head of family
            if relationship == 'head':
                existing_head = FamilyMember.objects.filter(
                    family=family, relationship='head', is_active=True
                ).first()
                if existing_head:
                    messages.error(request,
                        f"{existing_head.patient.full_name} is already the Head of "
                        f"{family.family_name}. A family can only have one head. "
                        f"Remove them first or choose a different relationship.")
                    return redirect('families:detail', pk=family_pk)

            FamilyMember.objects.create(
                family=family,
                patient=patient,
                relationship=relationship,
                notes=notes,
                added_by=request.user,
            )
            log_action(request.user, 'CREATE', request,
                       f"Added {patient.hospital_number} to family {family.family_name} "
                       f"as {relationship}")
            messages.success(request,
                f"{patient.full_name} added to {family.family_name} "
                f"as {dict(FamilyMember.RELATIONSHIP_CHOICES).get(relationship, relationship)}.")

    return redirect('families:detail', pk=family_pk)


@login_required
def remove_member_view(request, member_pk):
    """Remove a patient from a family (soft remove)."""
    member = get_object_or_404(FamilyMember, pk=member_pk)
    family = member.family

    if request.method == 'POST':
        patient_name = member.patient.full_name
        member.is_active = False
        member.save()

        log_action(request.user, 'DELETE', request,
                   f"Removed {patient_name} from {family.family_name}")
        messages.success(request,
            f"{patient_name} removed from {family.family_name}.")

    return redirect('families:detail', pk=family.pk)


@login_required
def family_search_api(request):
    """AJAX endpoint — search families by name for quick search bar."""
    q = request.GET.get('q', '').strip()
    if len(q) < 2:
        return JsonResponse({'results': []})

    families = FamilyGroup.objects.filter(
        family_name__icontains=q, is_active=True
    )[:8]

    results = [
        {
            'id':    f.pk,
            'name':  f.family_name,
            'count': f.member_count,
            'url':   f'/families/{f.pk}/',
        }
        for f in families
    ]
    return JsonResponse({'results': results})


@login_required
def patient_search_for_family_api(request):
    """
    AJAX endpoint — search patients to add to a family.
    Returns name + hospital number ONLY (no health data).
    """
    q = request.GET.get('q', '').strip()
    if len(q) < 2:
        return JsonResponse({'results': []})

    patients = Patient.objects.filter(
        Q(first_name__icontains=q) |
        Q(last_name__icontains=q)  |
        Q(hospital_number__icontains=q),
        is_active=True
    )[:8]

    results = [
        {
            'id':              p.pk,
            'name':            p.full_name,
            'hospital_number': p.hospital_number,
            'age':             p.age,
        }
        for p in patients
    ]
    return JsonResponse({'results': results})

# Create your views here.
