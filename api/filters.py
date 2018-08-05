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

    class Meta:
        model = Tag
        fields = ('name', 'type')


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
