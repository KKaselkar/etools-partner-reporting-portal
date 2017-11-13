# -*- coding: utf-8 -*-
# Generated by Django 1.11.5 on 2017-10-30 16:23
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('unicef', '0004_auto_20171017_0921'),
    ]

    operations = [
        migrations.AddField(
            model_name='lowerleveloutput',
            name='active',
            field=models.BooleanField(default=True),
        ),
        migrations.AlterField(
            model_name='programmedocument',
            name='funds_received_to_date_currency',
            field=models.CharField(blank=True, choices=[('USD', '$'), ('EUR', '€'), ('JOD', 'JOD')], default='USD', max_length=16, null=True, verbose_name='Funds received Currency'),
        ),
        migrations.AlterField(
            model_name='programmedocument',
            name='status',
            field=models.CharField(choices=[('Dra', 'Draft'), ('Sig', 'Signed'), ('Act', 'Active'), ('Sus', 'Suspended'), ('End', 'Ended'), ('Clo', 'Closed')], default='Dra', max_length=256, verbose_name='PD/SSFA status'),
        ),
    ]
