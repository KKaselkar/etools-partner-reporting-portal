# -*- coding: utf-8 -*-
# Generated by Django 1.11.5 on 2018-03-21 10:29
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('partner', '0009_auto_20180321_0958'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='fundingsource',
            unique_together=set([]),
        ),
        migrations.RemoveField(
            model_name='fundingsource',
            name='partner_project',
        ),
        migrations.AddField(
            model_name='partnerproject',
            name='funding_source',
            field=models.TextField(blank=True, max_length=2048, null=True),
        ),
        migrations.AlterField(
            model_name='partnerproject',
            name='total_budget',
            field=models.DecimalField(decimal_places=2, help_text='Total Budget (USD)', max_digits=12, null=True),
        ),
        migrations.DeleteModel(
            name='FundingSource',
        ),
    ]
