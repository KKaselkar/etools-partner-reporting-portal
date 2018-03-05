# -*- coding: utf-8 -*-
# Generated by Django 1.11.5 on 2018-03-02 13:08
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('indicator', '0005_auto_20180227_0449'),
    ]

    operations = [
        migrations.AddField(
            model_name='reportable',
            name='external_source',
            field=models.TextField(blank=True, choices=[('HPC', 'HPC'), ('OPS', 'OPS')], null=True),
        ),
        migrations.AddField(
            model_name='reportable',
            name='external_url',
            field=models.URLField(blank=True, null=True),
        ),
    ]
