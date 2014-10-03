# This file is part of Archivematica.
#
# Copyright 2010-2013 Artefactual Systems Inc. <http://artefactual.com>
#
# Archivematica is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Archivematica is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Archivematica.  If not, see <http://www.gnu.org/licenses/>.

from django import forms
from components import helpers
from django.forms import ModelForm
from django.forms.widgets import TextInput, Textarea, RadioSelect, CheckboxInput
from main import models
from django.conf import settings
from components.administration.models import ArchivistsToolkitConfig

class AtomSettingsForm(forms.ModelForm):
    class Meta:
        model = models.StandardTaskConfig
        fields = ('arguments',)

    def __init__(self, *args, **kwargs):
        super(AtomSettingsForm, self).__init__(*args, **kwargs)
        # Should add this to Meta: widgets but unsure how to modify 'class' in place
        arguments_attrs = settings.TEXTAREA_ATTRS
        arguments_attrs['class'] += ' command'
        self.fields['arguments'].widget.attrs = arguments_attrs
        # TODO in Django 1.6 move this to Meta: help_texts
        self.fields['arguments'].help_text = "Note that a backslash is necessary for each new line."

class AgentForm(forms.ModelForm):
    class Meta:
        model = models.Agent
        fields = ('identifiervalue', 'name')
        widgets = {
            'identifiervalue': TextInput(attrs=settings.INPUT_ATTRS),
            'name': TextInput(attrs=settings.INPUT_ATTRS),
        }

class SettingsForm(forms.Form):
    def __init__(self, *args, **kwargs):
        self.reverse_checkboxes = kwargs.pop('reverse_checkboxes', [])
        super(SettingsForm, self).__init__(*args, **kwargs)

        for setting in self.reverse_checkboxes:
            # if it's enabled it shouldn't be checked and visa versa
            checked = not helpers.get_boolean_setting(setting)
            self.fields[setting] = forms.BooleanField(
                required=False,
                label=self.reverse_checkboxes[setting],
                initial=checked,
                widget=CheckboxInput()
            )

    def save(self, *args, **kwargs):
        """ Save each of the fields in the form to the Settings table. """
        for key in self.cleaned_data:
            # If it's one of the reverse_checkboxes, reverse the checkbox value
            if key in self.reverse_checkboxes:
                helpers.set_setting(key, not self.cleaned_data[key])
            # Otherwise, save the value
            else:
                helpers.set_setting(key, self.cleaned_data[key])


class StorageSettingsForm(SettingsForm):
    storage_service_url = forms.URLField(required=False,
        label="Full URL of the storage service")


class ArchivistsToolkitConfigForm(ModelForm):
    class Meta:
        model = ArchivistsToolkitConfig
        fields = ('host', 'port', 'dbname', 'dbuser', 'dbpass', 'atuser', 'premis', 'ead_actuate', 'ead_show', 'object_type', 'use_statement', 'uri_prefix', 'access_conditions', 'use_conditions')
        widgets = {
            'host': TextInput(attrs=settings.INPUT_ATTRS),
            'port': TextInput(attrs=settings.INPUT_ATTRS),
            'dbname': TextInput(attrs=settings.INPUT_ATTRS),
            'dbuser': TextInput(attrs=settings.INPUT_ATTRS),
            'dbpass': forms.PasswordInput(),
            'atuser': TextInput(attrs=settings.INPUT_ATTRS),
            'premis': RadioSelect(),
            'ead_actuate': RadioSelect(),
            'ead_show': RadioSelect(),
            'object_type': TextInput(attrs=settings.INPUT_ATTRS),
            'use_statement': TextInput(attrs=settings.INPUT_ATTRS),
            'uri_prefix': TextInput(attrs=settings.INPUT_ATTRS),
            'access_conditions': TextInput(attrs=settings.INPUT_ATTRS),
            'use_conditions': TextInput(attrs=settings.INPUT_ATTRS),
        }


class TaxonomyTermForm(ModelForm):
    class Meta:
        model = models.TaxonomyTerm
        fields = ('taxonomy', 'term')
        widgets = {
            "term": TextInput(attrs=settings.INPUT_ATTRS)
        }
