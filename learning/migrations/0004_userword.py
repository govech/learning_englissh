# Generated by Django 4.2.18 on 2025-02-01 11:00

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('learning', '0003_delete_userword'),
    ]

    operations = [
        migrations.CreateModel(
            name='UserWord',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('memory_strength', models.FloatField(default=3.0)),
                ('next_review', models.DateTimeField(auto_now_add=True)),
                ('error_count', models.IntegerField(default=0)),
                ('last_review', models.DateTimeField(auto_now=True)),
                ('priority', models.FloatField(default=0.0)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
                ('word', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='learning.word')),
            ],
            options={
                'unique_together': {('user', 'word')},
            },
        ),
    ]
