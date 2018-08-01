import hashlib

from django.db import models


def hash_it(s):
    if not isinstance(s, str):
        raise TypeError("Type [{}] is not String.".format(type(s)))
    s = s.encode()
    return hashlib.md5(s).hexdigest()


class HashField(models.CharField):
    description = ('HashField is related to some other field in a model and'
                   'stores its hashed value for better indexing performance.')

    def __init__(self, original, *args, **kwargs):
        self.original = original
        kwargs['max_length'] = 40
        kwargs['null'] = False
        kwargs.setdefault('db_index', True)
        kwargs.setdefault('editable', False)
        super(HashField, self).__init__(*args, **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        del kwargs["max_length"]
        kwargs["original"] = self.original
        return name, path, args, kwargs

    def calculate_hash(self, model_instance):
        original_value = getattr(model_instance, self.original)
        setattr(model_instance, self.attname, hash_it(original_value))

    def pre_save(self, model_instance, add):
        self.calculate_hash(model_instance)
        return super(HashField, self).pre_save(model_instance, add)


class LengthField(models.IntegerField):
    description = ('LengthField is related to a text field in a model and'
                   'stores its length value.')

    def __init__(self, original, *args, **kwargs):
        self.original = original
        kwargs.setdefault('editable', False)
        super(LengthField, self).__init__(*args, **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        kwargs["original"] = self.original
        return name, path, args, kwargs

    def calculate_hash(self, model_instance):
        original_value = getattr(model_instance, self.original)
        setattr(model_instance, self.attname, len(original_value))

    def pre_save(self, model_instance, add):
        self.calculate_hash(model_instance)
        return super(LengthField, self).pre_save(model_instance, add)
