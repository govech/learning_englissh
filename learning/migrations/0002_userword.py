# Generated by Django 4.2.18 on 2025-01-30 12:42

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('learning', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='UserWord',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('memory_strength', models.FloatField(default=3.0)),
                ('memory_interval', models.FloatField(default=1.0)),
                ('error_count', models.IntegerField(default=0)),
                ('last_review', models.DateTimeField(auto_now=True)),
                ('next_review', models.DateTimeField()),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
                ('word', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='learning.word')),
            ],
        ),
    ]
