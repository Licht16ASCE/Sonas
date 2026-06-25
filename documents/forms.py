from django import forms
from django.core.exceptions import ValidationError

from biens.models import Bien
from core.forms import apply_form_styles
from sinistres.models import Sinistre
from .models import Document


class DocumentUploadForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = ('type_document', 'titre', 'fichier', 'sinistre', 'bien')
        labels = {
            'type_document': 'Type de document',
            'titre': 'Titre',
            'fichier': 'Fichier',
            'sinistre': 'Associer à un sinistre (optionnel)',
            'bien': 'Associer à un bien (optionnel)',
        }

    def __init__(self, *args, user=None, link_mode='both', **kwargs):
        """
        link_mode: 'both' | 'sinistre' | 'bien'
        """
        super().__init__(*args, **kwargs)
        self.user = user
        self.link_mode = link_mode
        apply_form_styles(self)

        if user and user.is_client:
            client = user.client_profile
            self.fields['sinistre'].queryset = Sinistre.objects.filter(
                contrat__client=client
            ).select_related('contrat', 'contrat__bien')
            self.fields['bien'].queryset = Bien.objects.filter(client=client)
            self.fields['sinistre'].label_from_instance = (
                lambda s: f'{s.reference} — {s.contrat.bien.reference}'
            )
            self.fields['bien'].label_from_instance = (
                lambda b: f'{b.reference} — {b.get_type_bien_display()} ({b.ville})'
            )
        elif user and user.is_internal:
            self.fields['sinistre'].queryset = Sinistre.objects.select_related(
                'contrat', 'contrat__bien', 'contrat__client'
            )
            self.fields['bien'].queryset = Bien.objects.select_related('client')
            self.fields['sinistre'].label_from_instance = (
                lambda s: f'{s.reference} — {s.contrat.client.display_name}'
            )
            self.fields['bien'].label_from_instance = (
                lambda b: f'{b.reference} — {b.client.display_name}'
            )
        else:
            self.fields['sinistre'].queryset = Sinistre.objects.none()
            self.fields['bien'].queryset = Bien.objects.none()

        self.fields['sinistre'].required = False
        self.fields['bien'].required = False

        if link_mode == 'sinistre':
            self.fields.pop('bien', None)
        elif link_mode == 'bien':
            self.fields.pop('sinistre', None)

    def clean(self):
        cleaned = super().clean()
        sinistre = cleaned.get('sinistre')
        bien = cleaned.get('bien')
        if not sinistre and not bien:
            raise ValidationError(
                'Associez le document à un bien ou à un sinistre.'
            )
        if sinistre and bien:
            raise ValidationError(
                'Associez le document à un bien ou à un sinistre, pas les deux.'
            )

        if self.user and self.user.is_client:
            client = self.user.client_profile
            if sinistre and sinistre.contrat.client_id != client.id:
                raise ValidationError('Ce sinistre ne vous appartient pas.')
            if bien and bien.client_id != client.id:
                raise ValidationError('Ce bien ne vous appartient pas.')

        return cleaned
