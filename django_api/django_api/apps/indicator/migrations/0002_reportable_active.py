# -*- coding: utf-8 -*-
# Generated by Django 1.11.5 on 2017-10-31 10:04
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('indicator', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='reportable',
            name='active',
            field=models.BooleanField(default=True),
        ),
    ]
