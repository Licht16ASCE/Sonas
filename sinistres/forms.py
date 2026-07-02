from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError

from contrats.models import Contrat, ContratStatut
from core.forms import apply_form_styles
from .models import Sinistre, SinistreStatut


def _contrat_label(contrat):
    return f'{contrat.reference} — {contrat.bien.reference} ({contrat.bien.ville})'


class SinistreForm(forms.ModelForm):
    class Meta:
        model = Sinistre
        fields = ('contrat', 'type_sinistre', 'description', 'date_sinistre', 'montant_estime', 'is_urgent')
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Décrivez les circonstances et les dommages…'}),
            'date_sinistre': forms.DateInput(attrs={'type': 'date'}),
            'montant_estime': forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'placeholder': 'Optionnel'}),
        }
        labels = {
            'contrat': 'Contrat concerné',
            'type_sinistre': 'Type de sinistre',
            'description': 'Description',
            'date_sinistre': 'Date du sinistre',
            'montant_estime': 'Montant estimé (€)',
            'is_urgent': 'Marquer comme urgent',
        }

    def __init__(self, *args, client=None, **kwargs):
        super().__init__(*args, **kwargs)
        apply_form_styles(self)
        self.client = client
        self.fields['is_urgent'].required = False
        if client:
            self.fields['contrat'].queryset = Contrat.objects.filter(
                client=client,
                statut=ContratStatut.ACTIF,
                sinistres_bloques=False,
            ).select_related('bien')
            self.fields['contrat'].label_from_instance = _contrat_label
            self.fields['contrat'].empty_label = 'Sélectionnez un contrat actif'
        else:
            self.fields['contrat'].queryset = Contrat.objects.none()
            self.fields['contrat'].empty_label = 'Sélectionnez d\'abord un client ci-dessus'

    def clean_contrat(self):
        contrat = self.cleaned_data.get('contrat')
        if not contrat:
            return contrat
        if self.client and contrat.client_id != self.client.id:
            raise ValidationError('Ce contrat ne vous appartient pas.')
        if not contrat.can_declare_sinistre:
            raise ValidationError('Ce contrat ne permet pas de déclarer un sinistre.')
        return contrat

    def clean(self):
        cleaned = super().clean()
        contrat = cleaned.get('contrat')
        montant_estime = cleaned.get('montant_estime')
        if contrat and montant_estime is not None:
            plafond = contrat.plafond_disponible
            if contrat.plafond_indemnisation > 0 and plafond <= 0:
                raise ValidationError('Le plafond d\'indemnisation de ce contrat est épuisé.')
            if plafond > 0 and Decimal(str(montant_estime)) > plafond:
                raise ValidationError(
                    f'Le montant estimé dépasse le plafond disponible du contrat ({plafond:.2f} €).'
                )
        return cleaned


class SinistreTraitementForm(forms.ModelForm):
    """Formulaire agent — décision d'indemnisation avant transmission au gérant."""

    INDEMNISATION_OUI = '1'
    INDEMNISATION_NON = '0'

    indemnisation_accordee = forms.TypedChoiceField(
        choices=[
            (INDEMNISATION_OUI, 'Oui — une indemnisation est accordée'),
            (INDEMNISATION_NON, 'Non — pas d\'indemnisation (clôture sans déduction)'),
        ],
        coerce=lambda value: value == SinistreTraitementForm.INDEMNISATION_OUI,
        widget=forms.RadioSelect,
        label='Indemnisation',
        help_text='Si vous choisissez « Non », aucun montant ne sera déduit du contrat à la validation.',
    )

    class Meta:
        model = Sinistre
        fields = ('montant_indemnisation_propose', 'notes_traitement')
        widgets = {
            'montant_indemnisation_propose': forms.NumberInput(attrs={
                'step': '0.01',
                'min': '0.01',
                'placeholder': 'Montant proposé pour indemnisation',
            }),
            'notes_traitement': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'Observations internes (optionnel)…',
            }),
        }
        labels = {
            'montant_indemnisation_propose': 'Montant proposé (€)',
            'notes_traitement': 'Notes de traitement',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_form_styles(self)
        if self.instance and self.instance.indemnisation_accordee is not None:
            self.fields['indemnisation_accordee'].initial = (
                self.INDEMNISATION_OUI if self.instance.indemnisation_accordee else self.INDEMNISATION_NON
            )
        if self.instance and self.instance.montant_estime:
            self.fields['montant_indemnisation_propose'].initial = (
                self.instance.montant_indemnisation_propose or self.instance.montant_estime
            )
        if self.instance and self.instance.plafond_indemnisation:
            plafond = self.instance.plafond_indemnisation
            self.fields['montant_indemnisation_propose'].help_text = (
                f'Plafond sinistre : {plafond:.2f} € — '
                f'Plafond contrat disponible : {self.instance.contrat.plafond_disponible:.2f} €'
            )

    def clean(self):
        cleaned = super().clean()
        accordee = cleaned.get('indemnisation_accordee')
        montant = cleaned.get('montant_indemnisation_propose')

        if accordee is None:
            raise ValidationError('Indiquez si une indemnisation est accordée.')

        if accordee:
            if montant is None:
                raise ValidationError(
                    'Le montant proposé est obligatoire lorsque l\'indemnisation est accordée.'
                )
            plafond_sinistre = self.instance.plafond_indemnisation or Decimal('0')
            plafond_contrat = self.instance.contrat.plafond_disponible
            if self.instance.contrat.plafond_indemnisation > 0 and plafond_contrat <= 0:
                raise ValidationError('Le plafond du contrat est épuisé.')
            if plafond_sinistre > 0 and montant > plafond_sinistre:
                raise ValidationError(
                    f'Le montant dépasse le plafond du sinistre ({plafond_sinistre:.2f} €).'
                )
        else:
            cleaned['montant_indemnisation_propose'] = None

        return cleaned

    def save(self, commit=True):
        sinistre = super().save(commit=False)
        sinistre.indemnisation_accordee = self.cleaned_data['indemnisation_accordee']
        if commit:
            sinistre.save()
        return sinistre


class SinistreValidationForm(forms.Form):
    """Clôture finale — boutons Clôturer / Rejeter (pas de liste statut)."""

    motif_rejet = forms.CharField(
        required=False,
        label='Motif de rejet',
        widget=forms.Textarea(attrs={
            'rows': 3,
            'placeholder': 'Obligatoire uniquement si vous rejetez le dossier',
        }),
    )

    def __init__(self, *args, sinistre=None, **kwargs):
        self.sinistre = sinistre
        super().__init__(*args, **kwargs)
        apply_form_styles(self)

    def clean_motif_rejet(self):
        return (self.cleaned_data.get('motif_rejet') or '').strip()

    def validate_cloture(self):
        """Vérifie que le sinistre peut être clôturé (validé)."""
        s = self.sinistre
        errors = []
        if s.statut != SinistreStatut.EN_COURS:
            errors.append('Seuls les sinistres en cours peuvent être clôturés.')
        if not s.soumis_validation:
            errors.append('L\'agent doit d\'abord transmettre le dossier avec sa décision d\'indemnisation.')
        if s.indemnisation_accordee is None:
            errors.append('La décision d\'indemnisation de l\'agent est manquante.')
        if s.indemnisation_accordee and not s.montant_indemnisation_propose:
            errors.append('Montant d\'indemnisation proposé manquant.')
        if errors:
            raise forms.ValidationError(errors)
        return True

    def validate_rejet(self):
        motif = self.cleaned_data.get('motif_rejet')
        if not motif:
            raise forms.ValidationError('Un motif de rejet est obligatoire.')
        if self.sinistre.statut != SinistreStatut.EN_COURS:
            raise forms.ValidationError('Seuls les sinistres en cours peuvent être rejetés.')
        return True
