# Generated migration for agent indemnisation workflow

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('sinistres', '0002_plafonds_indemnisation'),
    ]

    operations = [
        migrations.AddField(
            model_name='sinistre',
            name='date_soumission',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='sinistre',
            name='indemnisation_accordee',
            field=models.BooleanField(
                blank=True,
                help_text='Décision agent : une indemnisation est-elle accordée pour ce sinistre ?',
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='sinistre',
            name='montant_indemnisation_propose',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="Montant proposé par l'agent pour indemnisation.",
                max_digits=12,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='sinistre',
            name='notes_traitement',
            field=models.TextField(
                blank=True,
                help_text='Notes internes de l\'agent sur le traitement du dossier.',
            ),
        ),
        migrations.AddField(
            model_name='sinistre',
            name='soumis_validation',
            field=models.BooleanField(
                default=False,
                help_text='Dossier transmis au gérant pour validation finale.',
            ),
        ),
        migrations.AddField(
            model_name='sinistre',
            name='traite_par',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='sinistres_traites',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
