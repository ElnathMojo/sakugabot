import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from hub.models import Attribute


class TagDetailValidator(object):
    attributes = {}

    def __init__(self, attributes=None):
        if attributes:
            self.attributes = {attr.code: attr for attr in attributes}
        else:
            self.attributes = {attr.code: attr for attr in Attribute.objects.all()}

    def __call__(self, value):
        for k, v in value.items():
            attr = self.attributes.get(k, None)
            if not attr:
                raise ValidationError(_("Invalid attribute: [%(attr)s]"), params={'attr': k})
            if not v and v != 0:
                raise ValidationError(_("Value of [%(attr)s] can't be empty."), params={'attr': k})
            if attr.regex:
                if not re.compile(attr.regex).match(v):
                    raise ValidationError(_("[%(attr)s] got illegal value."),
                                          params={"attr": k})
            try:
                value[k] = attr.deserialize_value(v)
            except ValueError as e:
                raise ValidationError(_("Unable to parse value[%(value)s] to type[%(type)s]: %(message)s"),
                                      params={"value": v,
                                              "type": attr.get_type_display(),
                                              "message": str(e)})
        return value
