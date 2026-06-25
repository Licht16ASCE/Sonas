from django import forms
from django.core.exceptions import ValidationError

from contrats.models import Contrat, ContratStatut
from .models import Sinistre


def _contrat_label(contrat):
    return f'{contrat.reference} — {contrat.bien.reference} ({contrat.bien.ville})'


class SinistreForm(forms.ModelForm):
    class Meta:
        model = Sinistre
        fields = ('contrat', 'type_sinistre', 'description', 'date_sinistre', 'montant_estime', 'is_urgent')
        widgets = {'description': forms.Textarea(attrs={'rows': 4})}

    def __init__(self, *args, client=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.client = client
        if client:
            self.fields['contrat'].queryset = Contrat.objects.filter(
                client=client,
                statut=ContratStatut.ACTIF,
                sinistres_bloques=False,
            ).select_related('bien')
            self.fields['contrat'].label_from_instance = _contrat_label
            self.fields['contrat'].empty_label = 'Sélectionnez un contrat (bien associé)'
        else:
            self.fields['contrat'].queryset = Contrat.objects.none()
            self.fields['contrat'].empty_label = 'Sélectionnez d\'abord un client'

    def clean_contrat(self):
        contrat = self.cleaned_data.get('contrat')
        if not contrat:
            return contrat
        if self.client and contrat.client_id != self.client.id:
            raise ValidationError('Ce contrat ne vous appartient pas.')
        if not contrat.can_declare_sinistre:
            raise ValidationError('Ce contrat ne permet pas de déclarer un sinistre.')
        return contrat


class SinistreValidationForm(forms.ModelForm):
    class Meta:
        model = Sinistre
        fields = ('statut', 'motif_rejet')

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('statut') == 'REJETE' and not cleaned.get('motif_rejet'):
            raise forms.ValidationError('Un motif de rejet est obligatoire.')
        return cleaned
