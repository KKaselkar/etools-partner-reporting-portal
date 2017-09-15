# -*- coding: utf-8 -*-
# Generated by Django 1.11.2 on 2017-09-15 02:23
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion
import mptt.fields


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('indicator', '0001_initial'),
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='location',
            name='reportable',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='locations', to='indicator.Reportable'),
        ),
        migrations.AddField(
            model_name='gatewaytype',
            name='workspace',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='gateway_types', to='core.Workspace'),
        ),
        migrations.AddField(
            model_name='cartodbtable',
            name='country',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='carto_db_tables', to='core.Country'),
        ),
        migrations.AddField(
            model_name='cartodbtable',
            name='location_type',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='core.GatewayType'),
        ),
        migrations.AddField(
            model_name='cartodbtable',
            name='parent',
            field=mptt.fields.TreeForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='children', to='core.CartoDBTable'),
        ),
        migrations.AlterUniqueTogether(
            name='location',
            unique_together=set([('title', 'p_code')]),
        ),
    ]
