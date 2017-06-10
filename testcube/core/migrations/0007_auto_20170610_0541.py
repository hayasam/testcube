# -*- coding: utf-8 -*-
# Generated by Django 1.11.1 on 2017-06-10 05:41
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0006_auto_20170610_0526'),
    ]

    operations = [
        migrations.AddField(
            model_name='resulterror',
            name='exception_type',
            field=models.CharField(default='Unknown', max_length=100),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='resulterror',
            name='message',
            field=models.CharField(blank=True, max_length=1000, null=True),
        ),
    ]
