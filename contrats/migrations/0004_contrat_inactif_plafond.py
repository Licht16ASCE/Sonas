from django.db import migrations, models


def epuise_vers_inactif(apps, schema_editor):
    Contrat = apps.get_model('contrats', 'Contrat')
    Contrat.objects.filter(statut='EPUISE').update(statut='INACTIF')


class Migration(migrations.Migration):

    dependencies = [
        ('contrats', '0003_contrat_visuel_pdf'),
    ]

    operations = [
        migrations.AlterField(
            model_name='contrat',
            name='statut',
            field=models.CharField(
                choices=[
                    ('BROUILLON', 'Brouillon'),
                    ('ACTIF', 'Actif'),
                    ('INACTIF', 'Inactif'),
                    ('EXPIRE', 'Expiré'),
                    ('RESILIE', 'Résilié'),
                    ('EPUISE', 'Inactif'),
                ],
                default='BROUILLON',
                max_length=15,
            ),
        ),
        migrations.RunPython(epuise_vers_inactif, migrations.RunPython.noop),
    ]
