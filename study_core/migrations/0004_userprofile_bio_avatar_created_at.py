import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("study_core", "0003_dailyquestion_category_dailyquestion_difficulty_tier_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="bio",
            field=models.TextField(
                blank=True,
                default="",
                help_text="Short bio shown on your public profile (max 300 chars).",
                max_length=300,
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="avatar",
            field=models.CharField(
                choices=[
                    ("owl", "🦉 Wise Owl"),
                    ("rocket", "🚀 Rocket"),
                    ("brain", "🧠 Brainiac"),
                    ("books", "📚 Bookworm"),
                    ("bolt", "⚡ Speedster"),
                    ("target", "🎯 Sharpshooter"),
                    ("wave", "🌊 Deep Thinker"),
                    ("fire", "🔥 Streak Master"),
                ],
                default="owl",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="created_at",
            field=models.DateTimeField(
                auto_now_add=True,
                default=django.utils.timezone.now,
            ),
            preserve_default=False,
        ),
    ]