from django import forms


INPUT_WIDGETS = (
    forms.TextInput,
    forms.EmailInput,
    forms.NumberInput,
    forms.URLInput,
    forms.DateInput,
    forms.Select,
    forms.Textarea,
    forms.PasswordInput,
    forms.ClearableFileInput,
    forms.FileInput,
)


def apply_form_styles(form):
    """Applique la classe form-input aux widgets des formulaires."""
    for field in form.fields.values():
        widget = field.widget
        if isinstance(widget, INPUT_WIDGETS):
            cls = widget.attrs.get('class', '')
            if 'form-input' not in cls and 'sonas-input' not in cls:
                widget.attrs['class'] = f'{cls} sonas-input form-input'.strip()
        if isinstance(widget, forms.CheckboxInput):
            widget.attrs['class'] = 'rounded border-slate-300 text-indigo-600 focus:ring-indigo-500'
        if isinstance(widget, forms.RadioSelect):
            widget.attrs['class'] = 'space-y-2'
