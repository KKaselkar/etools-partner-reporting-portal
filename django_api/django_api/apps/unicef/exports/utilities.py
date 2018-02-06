from collections import defaultdict
from datetime import date

from django.conf import settings

from unicef.models import LowerLevelOutput


PARTNER_PORTAL_DATE_FORMAT_EXCEL = 'dd-mmm-yyyy'


def group_indicator_reports_by_lower_level_output(indicator_reports):
    results = defaultdict(list)
    for ir in indicator_reports:
        if type(ir.reportable.content_object) == LowerLevelOutput:
            results[ir.reportable.content_object.id].append(ir)

    return [
        results[key] for key in sorted(results.keys())
    ]


class HTMLTableCell(object):

    def __init__(self, value, colspan=None, rowspan=None, element='td'):
        self.value = value
        self.colspan = colspan
        self.rowspan = rowspan
        self.element = element

    def render(self):
        attrs_string = ''
        if self.rowspan:
            attrs_string += ' rowspan="{}"'.format(self.rowspan)
        if self.colspan:
            attrs_string += ' colspan="{}"'.format(self.colspan)

        return '<{0}{1}>{2}</{0}>'.format(self.element, attrs_string, self.render_value())

    def render_value(self):
        if type(self.value) == date:
            return self.value.strftime(settings.PRINT_DATA_FORMAT)
        if self.value in {'', None}:
            return '&nbsp;'  # Rendering empty tags brakes layout in pdf export
        return self.value

    def __str__(self):
        return self.render()
