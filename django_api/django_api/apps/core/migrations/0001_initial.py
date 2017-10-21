# -*- coding: utf-8 -*-
# Generated by Django 1.11.5 on 2017-10-12 06:07
from __future__ import unicode_literals

from decimal import Decimal
import django.contrib.gis.db.models.fields
import django.core.validators
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import model_utils.fields
import mptt.fields


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='CartoDBTable',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('domain', models.CharField(max_length=254)),
                ('api_key', models.CharField(max_length=254)),
                ('table_name', models.CharField(max_length=254)),
                ('lft', models.PositiveIntegerField(db_index=True, editable=False)),
                ('rght', models.PositiveIntegerField(db_index=True, editable=False)),
                ('tree_id', models.PositiveIntegerField(db_index=True, editable=False)),
                ('level', models.PositiveIntegerField(db_index=True, editable=False)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Country',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, editable=False, verbose_name='created')),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, editable=False, verbose_name='modified')),
                ('external_id', models.CharField(blank=True, help_text='An ID representing this instance in an external system', max_length=32, null=True)),
                ('name', models.CharField(max_length=100)),
                ('country_short_code', models.CharField(blank=True, max_length=10, null=True)),
                ('long_name', models.CharField(blank=True, max_length=255, null=True)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='GatewayType',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, editable=False, verbose_name='created')),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, editable=False, verbose_name='modified')),
                ('name', models.CharField(max_length=64L, unique=True)),
                ('admin_level', models.PositiveSmallIntegerField()),
                ('country', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='gateway_types', to='core.Country')),
            ],
            options={
                'ordering': ['name'],
                'verbose_name': 'Location Type',
            },
        ),
        migrations.CreateModel(
            name='Location',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, editable=False, verbose_name='created')),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, editable=False, verbose_name='modified')),
                ('external_id', models.CharField(blank=True, help_text='An ID representing this instance in an external system', max_length=32, null=True)),
                ('title', models.CharField(max_length=255)),
                ('latitude', models.DecimalField(blank=True, decimal_places=5, max_digits=8, null=True, validators=[django.core.validators.MinValueValidator(Decimal('-90')), django.core.validators.MaxValueValidator(Decimal('90'))])),
                ('longitude', models.DecimalField(blank=True, decimal_places=5, max_digits=8, null=True, validators=[django.core.validators.MinValueValidator(Decimal('-180')), django.core.validators.MaxValueValidator(Decimal('180'))])),
                ('p_code', models.CharField(blank=True, max_length=32, null=True)),
                ('geom', django.contrib.gis.db.models.fields.MultiPolygonField(blank=True, null=True, srid=4326)),
                ('point', django.contrib.gis.db.models.fields.PointField(blank=True, null=True, srid=4326)),
                ('carto_db_table', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='locations', to='core.CartoDBTable')),
                ('gateway', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='locations', to='core.GatewayType', verbose_name='Location Type')),
                ('parent', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='children', to='core.Location')),
            ],
            options={
                'ordering': ['title'],
            },
        ),
        migrations.CreateModel(
            name='ResponsePlan',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, editable=False, verbose_name='created')),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, editable=False, verbose_name='modified')),
                ('title', models.CharField(max_length=255, verbose_name='Response Plan')),
                ('plan_type', models.CharField(choices=[('HRP', 'HRP'), ('FA', 'FA')], default='HRP', max_length=3, verbose_name='Plan Type')),
                ('start', models.DateField(blank=True, null=True, verbose_name='Start date')),
                ('end', models.DateField(blank=True, null=True, verbose_name='End date')),
            ],
        ),
        migrations.CreateModel(
            name='Workspace',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, editable=False, verbose_name='created')),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, editable=False, verbose_name='modified')),
                ('external_id', models.CharField(blank=True, help_text='An ID representing this instance in an external system', max_length=32, null=True)),
                ('title', models.CharField(max_length=255)),
                ('workspace_code', models.CharField(max_length=8, unique=True)),
                ('business_area_code', models.CharField(blank=True, max_length=10, null=True)),
                ('latitude', models.DecimalField(blank=True, decimal_places=5, max_digits=8, null=True, validators=[django.core.validators.MinValueValidator(Decimal('-90')), django.core.validators.MaxValueValidator(Decimal('90'))])),
                ('longitude', models.DecimalField(blank=True, decimal_places=5, max_digits=8, null=True, validators=[django.core.validators.MinValueValidator(Decimal('-180')), django.core.validators.MaxValueValidator(Decimal('180'))])),
                ('initial_zoom', models.IntegerField(default=8)),
                ('countries', models.ManyToManyField(related_name='workspaces', to='core.Country')),
            ],
            options={
                'ordering': ['title'],
            },
        ),
        migrations.AddField(
            model_name='responseplan',
            name='workspace',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='response_plans', to='core.Workspace'),
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
            name='responseplan',
            unique_together=set([('title', 'plan_type', 'workspace')]),
        ),
        migrations.AlterUniqueTogether(
            name='location',
            unique_together=set([('title', 'p_code')]),
        ),
    ]
