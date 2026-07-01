import uuid

from django import forms
from django.core.exceptions import ValidationError

from core.forms import apply_form_styles
from .models import Bien, BienType


class BienForm(forms.ModelForm):
    class Meta:
        model = Bien
        fields = (
            'type_bien', 'adresse', 'code_postal', 'ville',
            'surface_m2', 'description',
        )
        widgets = {
            'adresse': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Numéro et rue'}),
            'description': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Informations complémentaires (optionnel)'}),
            'code_postal': forms.TextInput(attrs={'placeholder': '75001'}),
            'ville': forms.TextInput(attrs={'placeholder': 'Paris'}),
            'surface_m2': forms.NumberInput(attrs={'placeholder': '85', 'step': '0.01', 'min': '0'}),
        }
        labels = {
            'type_bien': 'Type de bien',
            'adresse': 'Adresse',
            'code_postal': 'Code postal',
            'ville': 'Ville',
            'surface_m2': 'Surface (m²)',
            'description': 'Description',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_form_styles(self)

    def clean_code_postal(self):
        cp = self.cleaned_data.get('code_postal', '').strip()
        if cp and (len(cp) < 4 or len(cp) > 10):
            raise ValidationError('Code postal invalide.')
        return cp

    def save(self, commit=True):
        bien = super().save(commit=False)
        if not bien.reference:
            bien.reference = f'BIEN-{uuid.uuid4().hex[:8].upper()}'
        if commit:
            bien.save()
        return bien


class BienValidationForm(forms.ModelForm):
    class Meta:
        model = Bien
        fields = ('statut', 'motif_rejet')
        widgets = {
            'motif_rejet': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Obligatoire en cas de rejet'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_form_styles(self)

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('statut') == 'REJETE' and not cleaned.get('motif_rejet'):
            raise forms.ValidationError('Un motif de rejet est obligatoire.')
        return cleaned
