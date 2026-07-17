import json
import uuid

from django import forms
from django.core.exceptions import ValidationError

from core.currency import format_usd
from core.forms import apply_form_styles
from .models import Bien, BienType


def _grille_label(grille):
    plafond = format_usd(grille.plafond_indemnisation)
    prime = format_usd(grille.prime_annuelle)
    return f'{grille.libelle} — prime {prime} / plafond {plafond}'


class BienForm(forms.ModelForm):
    class Meta:
        model = Bien
        fields = (
            'type_bien', 'ville', 'adresse', 'code_postal',
            'surface_m2', 'valeur_estimee', 'grille_tarifaire', 'description',
        )
        widgets = {
            'adresse': forms.Textarea(attrs={
                'rows': 2,
                'placeholder': 'Ex. Boulevard du 30 Juin',
                'autocomplete': 'street-address',
                'id': 'id_adresse',
            }),
            'description': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Informations complémentaires (optionnel)'}),
            'code_postal': forms.TextInput(attrs={'placeholder': 'ex. 01234'}),
            'ville': forms.Select(attrs={'id': 'id_ville'}),
            'surface_m2': forms.NumberInput(attrs={'placeholder': '85', 'step': '0.01', 'min': '0'}),
            'valeur_estimee': forms.NumberInput(attrs={'placeholder': '150000', 'step': '0.01', 'min': '0'}),
            'type_bien': forms.Select(attrs={'id': 'id_type_bien'}),
            'grille_tarifaire': forms.Select(attrs={'id': 'id_grille_tarifaire'}),
        }
        labels = {
            'type_bien': 'Type de bien',
            'adresse': 'Adresse',
            'code_postal': 'Code postal',
            'ville': 'Ville',
            'surface_m2': 'Surface (m²)',
            'valeur_estimee': 'Valeur estimée (USD)',
            'grille_tarifaire': 'Forfait d\'assurance',
            'description': 'Description',
        }
        help_texts = {
            'grille_tarifaire': 'Seuls les forfaits du type de bien sélectionné sont proposés.',
            'ville': 'Choisissez d\'abord la ville (RDC) pour cibler la recherche d\'adresse.',
            'adresse': 'Adresse vérifiable sur OpenStreetMap dans la ville sélectionnée.',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from contrats.models import GrilleTarifaire
        from contrats.workflow import ensure_default_grilles
        from core.geo_rdc import ville_choices

        ensure_default_grilles()
        type_bien = self._resolve_type_bien()
        qs = GrilleTarifaire.objects.filter(is_active=True).order_by('valeur_min', 'libelle')
        if type_bien:
            qs = qs.filter(type_bien=type_bien)

        self.fields['grille_tarifaire'].queryset = qs
        self.fields['grille_tarifaire'].required = False
        self.fields['grille_tarifaire'].empty_label = 'Automatique selon type / valeur'
        self.fields['grille_tarifaire'].label_from_instance = _grille_label

        self.fields['ville'] = forms.ChoiceField(
            choices=ville_choices(),
            label='Ville (RDC)',
            help_text='Choisissez d\'abord la ville (RDC) pour cibler la recherche d\'adresse.',
            widget=forms.Select(attrs={'id': 'id_ville'}),
        )
        current_ville = ''
        if self.data:
            current_ville = self.data.get('ville') or ''
        elif self.instance and getattr(self.instance, 'ville', None):
            current_ville = self.instance.ville
        if current_ville and current_ville not in dict(self.fields['ville'].choices):
            self.fields['ville'].choices = list(self.fields['ville'].choices) + [
                (current_ville, f'{current_ville} (existante)'),
            ]

        self.fields['code_postal'].widget.attrs['placeholder'] = 'ex. 01234'
        self.fields['code_postal'].required = False
        self.fields['adresse'].widget.attrs['placeholder'] = 'Ex. Boulevard du 30 Juin'
        self.fields['adresse'].widget.attrs['autocomplete'] = 'street-address'
        apply_form_styles(self)

    def _resolve_type_bien(self):
        if self.data:
            return self.data.get('type_bien') or ''
        if self.instance and self.instance.pk and self.instance.type_bien:
            return self.instance.type_bien
        return self.initial.get('type_bien') or BienType.APPARTEMENT

    def grilles_by_type_json(self):
        """JSON pour filtrer dynamiquement le select forfait côté navigateur."""
        from contrats.models import GrilleTarifaire
        from contrats.workflow import ensure_default_grilles

        ensure_default_grilles()
        data = {code: [] for code, _ in BienType.choices}
        for grille in GrilleTarifaire.objects.filter(is_active=True).order_by('valeur_min', 'libelle'):
            data.setdefault(grille.type_bien, []).append({
                'id': grille.pk,
                'label': _grille_label(grille),
            })
        return json.dumps(data, ensure_ascii=False)

    def clean(self):
        cleaned = super().clean()
        type_bien = cleaned.get('type_bien')
        grille = cleaned.get('grille_tarifaire')
        if grille and type_bien and grille.type_bien != type_bien:
            self.add_error(
                'grille_tarifaire',
                'Ce forfait ne correspond pas au type de bien sélectionné.',
            )
        adresse = cleaned.get('adresse')
        ville = cleaned.get('ville')
        if adresse and ville:
            from core.address_validation import validate_adresse_ville_rdc
            try:
                detail = validate_adresse_ville_rdc(adresse, ville, required=True)
                if detail and detail.get('postcode') and not cleaned.get('code_postal'):
                    cleaned['code_postal'] = detail['postcode']
            except ValidationError as exc:
                self.add_error('adresse', exc)
        return cleaned

    def clean_code_postal(self):
        cp = self.cleaned_data.get('code_postal', '').strip()
        if cp and len(cp) > 10:
            raise ValidationError('Code postal trop long.')
        return cp

    def clean_ville(self):
        ville = (self.cleaned_data.get('ville') or '').strip()
        if not ville:
            raise ValidationError('Veuillez sélectionner une ville de la RDC.')
        return ville

    def clean_adresse(self):
        return (self.cleaned_data.get('adresse') or '').strip()
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
