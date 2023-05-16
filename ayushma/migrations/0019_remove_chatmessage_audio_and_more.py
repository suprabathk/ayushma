# Generated by Django 4.1.7 on 2023-05-15 17:25

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ayushma", "0018_chatmessage_audio"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="chatmessage",
            name="audio",
        ),
        migrations.AddField(
            model_name="chatmessage",
            name="ayushma_audio_url",
            field=models.URLField(blank=True, null=True),
        ),
    ]
