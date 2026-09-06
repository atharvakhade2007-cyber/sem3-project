from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('study_core', '0012_add_persona_and_quiz_session_state'),
    ]

    operations = [
        migrations.AddField(
            model_name='sessionresponse',
            name='answered_at',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AlterModelOptions(
            name='sessionresponse',
            options={'ordering': ['answered_at', 'id']},
        ),
        migrations.AddIndex(
            model_name='sessionresponse',
            index=models.Index(fields=['session', 'answered_at'], name='study_core_session_i_d3a4bc_idx'),
        ),
    ]
