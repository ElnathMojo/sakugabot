import operator
from functools import reduce

from django.db.models import Q
from django_filters import rest_framework as filters

from hub.models import Post, Tag, Attribute, TagSnapshot


class NumArrayFilter(filters.BaseCSVFilter, filters.NumberFilter):
    pass


class CharInFilter(filters.BaseInFilter, filters.CharFilter):
    pass


class NumInFilter(filters.BaseInFilter, filters.NumberFilter):
    pass


class AttributeFilter(filters.FilterSet):
    related_types = NumArrayFilter(lookup_expr='contains')

    class Meta:
        model = Attribute
        fields = ('related_types',)


class TagFilter(filters.FilterSet):
    name = CharInFilter()
    type = NumInFilter()
    search = filters.CharFilter(label="Search Tag", method='search_by_name')

    def search_by_name(self, queryset, name, value):
        fields = ['name', 'override_name'] + ['_detail__{}'.format(attr.code) for attr in
                                              Attribute.objects.filter(code__startswith='name')]
        orm_lookups = ['{}__icontains'.format(field) for field in fields]
        or_queries = [Q(**{orm_lookup: value})
                      for orm_lookup in orm_lookups]
        queryset = queryset.filter(reduce(operator.or_, or_queries))
        return queryset.filter()

    class Meta:
        model = Tag
        fields = ('name', 'type', 'search')


class PostFilter(filters.FilterSet):
    id = NumInFilter()

    class Meta:
        model = Post
        fields = ('id',)


class TagSnapshotFilter(filters.FilterSet):
    user = filters.CharFilter(label='User',
                              field_name='_user__username')

    class Meta:
        model = TagSnapshot
        fields = ('tag', 'user')
