"""
AbiCare - Family Groups Models
================================
Groups patients into family units for administrative purposes only.
Individual patient health records remain completely private.
A patient's health data is NEVER visible through family membership.
Family view only shows: name, relationship, hospital number.
"""

import uuid
from django.db import models


class FamilyGroup(models.Model):
    """
    A named family unit — e.g. 'Olusun Family', 'Adeyemi Family'.
    Contains NO health data. Only identity and contact grouping.
    """
    family_id   = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    family_name = models.CharField(
        max_length=200,
        unique=True,
        help_text="e.g. Olusun Family, Adeyemi Family"
    )
    address    = models.TextField(blank=True, help_text="Shared family address (optional)")
    notes      = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True,
        related_name='created_families'
    )
    is_active  = models.BooleanField(default=True)

    class Meta:
        ordering            = ['family_name']
        verbose_name        = 'Family Group'
        verbose_name_plural = 'Family Groups'

    def __str__(self):
        return self.family_name

    @property
    def member_count(self):
        return self.members.filter(is_active=True).count()

    @property
    def head_of_family(self):
        head = self.members.filter(relationship='head', is_active=True).first()
        return head.patient if head else None


class FamilyMember(models.Model):
    """
    Links a Patient to a FamilyGroup with a relationship label.
    This is purely administrative grouping.
    Health records remain completely private per individual patient.
    """
    RELATIONSHIP_CHOICES = [
        ('head',        'Head of Family'),
        ('spouse',      'Spouse'),
        ('child',       'Child'),
        ('parent',      'Parent'),
        ('sibling',     'Sibling'),
        ('grandparent', 'Grandparent'),
        ('grandchild',  'Grandchild'),
        ('in_law',      'In-Law'),
        ('other',       'Other'),
    ]

    family       = models.ForeignKey(
        FamilyGroup, on_delete=models.CASCADE, related_name='members'
    )
    patient      = models.ForeignKey(
        'patients.Patient', on_delete=models.CASCADE,
        related_name='family_memberships'
    )
    relationship = models.CharField(
        max_length=20, choices=RELATIONSHIP_CHOICES, default='other'
    )
    is_active    = models.BooleanField(default=True)
    joined_at    = models.DateTimeField(auto_now_add=True)
    added_by     = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True,
        related_name='added_family_members'
    )
    notes        = models.CharField(max_length=300, blank=True)

    class Meta:
        unique_together     = [['family', 'patient']]
        ordering            = ['relationship', 'patient__last_name']
        verbose_name        = 'Family Member'
        verbose_name_plural = 'Family Members'

    def __str__(self):
        return (
            f"{self.patient.full_name} "
            f"({self.get_relationship_display()}) — "
            f"{self.family.family_name}"
        )
# Create your models here.
