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
        fields = ('bien', 'date_debut', 'date_fin', 'montant_annuel', 'plafond_indemnisation', 'notes', 'statut')
        widgets = {
            'date_debut': forms.DateInput(attrs={'type': 'date'}),
            'date_fin': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
            'montant_annuel': forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'placeholder': '1200.00'}),
            'plafond_indemnisation': forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'placeholder': '50000.00'}),
        }
        labels = {
            'plafond_indemnisation': 'Plafond d\'indemnisation (€)',
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


from contrats.services import INLINE_FIELD_CLASS


class ClientContratForm(forms.ModelForm):
    """Souscription contrat par le client — contrat visuel intégré."""

    acceptation_cg = forms.BooleanField(
        required=True,
        label=(
            'Je certifie l\'exactitude des informations et j\'accepte les conditions '
            'générales du contrat d\'assurance SONAS.'
        ),
        widget=forms.CheckboxInput(attrs={'class': 'rounded border-slate-300 text-indigo-600'}),
    )

    class Meta:
        model = Contrat
        fields = ('bien', 'date_debut', 'date_fin', 'montant_annuel', 'plafond_indemnisation', 'notes')
        widgets = {
            'date_debut': forms.DateInput(attrs={'type': 'date', 'class': INLINE_FIELD_CLASS}),
            'date_fin': forms.DateInput(attrs={'type': 'date', 'class': INLINE_FIELD_CLASS}),
            'notes': forms.Textarea(attrs={
                'rows': 2,
                'class': INLINE_FIELD_CLASS,
                'placeholder': 'Précisions complémentaires sur le bien ou la couverture souhaitée…',
            }),
            'montant_annuel': forms.NumberInput(attrs={
                'step': '0.01', 'min': '0', 'class': INLINE_FIELD_CLASS, 'placeholder': '1200',
            }),
            'plafond_indemnisation': forms.NumberInput(attrs={
                'step': '0.01', 'min': '0', 'class': INLINE_FIELD_CLASS, 'placeholder': '50000',
            }),
            'bien': forms.Select(attrs={'class': INLINE_FIELD_CLASS, 'id': 'id_bien_contrat'}),
        }
        labels = {
            'bien': 'Bien à assurer',
            'date_debut': 'Date de début',
            'date_fin': 'Date de fin',
            'montant_annuel': 'Prime annuelle (€)',
            'plafond_indemnisation': 'Plafond d\'indemnisation (€)',
            'notes': 'Observations du souscripteur',
        }

    def __init__(self, *args, client=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.client = client
        apply_form_styles(self)
        for name in ('bien', 'date_debut', 'date_fin', 'montant_annuel', 'plafond_indemnisation', 'notes'):
            if name in self.fields:
                cls = self.fields[name].widget.attrs.get('class', '')
                if INLINE_FIELD_CLASS not in cls:
                    self.fields[name].widget.attrs['class'] = f'{cls} {INLINE_FIELD_CLASS}'.strip()
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
