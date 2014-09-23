from django.db import models
from main.models import UUIDPkField

class ReplacementDict(models.Model):
    id = UUIDPkField()
    dictname = models.CharField(max_length=50)
    position = models.IntegerField(default=1)
    parameter = models.CharField(max_length=50)
    displayname = models.CharField(max_length=50)
    displayvalue = models.CharField(max_length=50)
    hidden = models.IntegerField()

    class Meta:
        db_table = u'ReplacementDict'


class ArchivistsToolkitConfig(models.Model):
    id = UUIDPkField()
    host = models.CharField(max_length=50, verbose_name='Database Host')
    port = models.IntegerField(default=3306, verbose_name='Database Port')
    dbname = models.CharField(max_length=50, verbose_name='Database Name')
    dbuser = models.CharField(max_length=50, verbose_name='Database User')
    dbpass = models.CharField(max_length=50, null=True, blank=True, verbose_name='Database Password')
    atuser = models.CharField(max_length=50, verbose_name='Archivists Toolkit Username')
    PREMIS_CHOICES = [('yes', 'Yes'), ('no', 'No'), ('premis', 'Base on PREMIS')]
    premis = models.CharField(max_length=10, choices=PREMIS_CHOICES, verbose_name='Restrictions Apply', blank=False, default='yes')
    EAD_ACTUATE_CHOICES = [('none', 'None'), ('onLoad','onLoad'), ('other','other'), ('onRequest', 'onRequest')]
    ead_actuate = models.CharField(max_length=50, choices=EAD_ACTUATE_CHOICES, verbose_name='EAD DAO Actuate', blank=False, default='none')
    EAD_SHOW_CHOICES = [('embed', 'Embed'), ('new', 'New'), ('none', 'None'), ('other', 'Other'), ('replace', 'Replace')]
    ead_show = models.CharField(max_length=50, choices=EAD_SHOW_CHOICES, verbose_name='EAD DAO Show', blank=False, default='embed')
    object_type = models.CharField(max_length=50, blank=True, null=True, verbose_name='Object type')
    use_statement = models.CharField(max_length=50, verbose_name='Use Statement')
    uri_prefix = models.CharField(max_length=50, verbose_name='URL prefix')
    access_conditions = models.CharField(max_length=50, blank=True, null=True, verbose_name='Conditions governing access')
    use_conditions = models.CharField(max_length=50, blank=True, null=True, verbose_name='Conditions governing use')

