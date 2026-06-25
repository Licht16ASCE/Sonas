from django import forms
from django.core.exceptions import ValidationError

from biens.models import Bien, BienStatut
from core.forms import apply_form_styles
from .models import Contrat, ContratStatut


def _bien_label(bien):
    return f'{bien.reference} — {bien.get_type_bien_display()} ({bien.ville})'


class ContratForm(forms.ModelForm):
    class Meta:
        model = Contrat
        fields = ('bien', 'date_debut', 'date_fin', 'montant_annuel', 'notes', 'statut')
        widgets = {
            'date_debut': forms.DateInput(attrs={'type': 'date'}),
            'date_fin': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
            'montant_annuel': forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'placeholder': '1200.00'}),
        }

    def __init__(self, *args, client=None, **kwargs):
        super().__init__(*args, **kwargs)
        apply_form_styles(self)
        if client:
            self.fields['bien'].queryset = Bien.objects.filter(
                client=client, statut=BienStatut.VALIDE
            )
            self.fields['bien'].label_from_instance = _bien_label

    def clean(self):
        cleaned = super().clean()
        date_debut = cleaned.get('date_debut')
        date_fin = cleaned.get('date_fin')
        if date_debut and date_fin and date_fin <= date_debut:
            raise ValidationError('La date de fin doit être postérieure à la date de début.')
        bien = cleaned.get('bien')
        if bien and not bien.is_validated:
            raise ValidationError('Le bien doit être validé avant de créer un contrat.')
        return cleaned


class ClientContratForm(forms.ModelForm):
    """Souscription contrat par le client — en attente d'activation interne."""

    class Meta:
        model = Contrat
        fields = ('bien', 'date_debut', 'date_fin', 'montant_annuel', 'notes')
        widgets = {
            'date_debut': forms.DateInput(attrs={'type': 'date'}),
            'date_fin': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Informations complémentaires (optionnel)'}),
            'montant_annuel': forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'placeholder': '1200.00'}),
        }
        labels = {
            'bien': 'Bien à assurer',
            'date_debut': 'Date de début souhaitée',
            'date_fin': 'Date de fin',
            'montant_annuel': 'Montant annuel (€)',
            'notes': 'Notes',
        }

    def __init__(self, *args, client=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.client = client
        apply_form_styles(self)
        if client:
            biens_pris = Contrat.objects.filter(
                client=client,
                statut__in=(ContratStatut.BROUILLON, ContratStatut.ACTIF),
            ).values_list('bien_id', flat=True)
            qs = Bien.objects.filter(
                client=client, statut=BienStatut.VALIDE,
            ).exclude(pk__in=biens_pris)
            self.fields['bien'].queryset = qs
            self.fields['bien'].label_from_instance = _bien_label
            self.fields['bien'].empty_label = 'Sélectionnez un bien validé'

    def clean_bien(self):
        bien = self.cleaned_data.get('bien')
        if bien and self.client and bien.client_id != self.client.id:
            raise ValidationError('Ce bien ne vous appartient pas.')
        if bien and self.client:
            existe = Contrat.objects.filter(
                client=self.client,
                bien=bien,
                statut__in=(ContratStatut.BROUILLON, ContratStatut.ACTIF),
            ).exists()
            if existe:
                raise ValidationError('Un contrat existe déjà pour ce bien.')
        return bien

    def clean(self):
        cleaned = super().clean()
        date_debut = cleaned.get('date_debut')
        date_fin = cleaned.get('date_fin')
        if date_debut and date_fin and date_fin <= date_debut:
            raise ValidationError('La date de fin doit être postérieure à la date de début.')
        bien = cleaned.get('bien')
        if bien and not bien.is_validated:
            raise ValidationError('Seuls les biens validés peuvent être souscrits.')
        return cleaned
