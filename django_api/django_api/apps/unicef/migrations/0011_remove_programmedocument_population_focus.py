# -*- coding: utf-8 -*-
# Generated by Django 1.11.5 on 2018-01-16 06:59
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('unicef', '0010_auto_20171110_1250'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='programmedocument',
            name='population_focus',
        ),
    ]
