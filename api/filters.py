from django_filters import rest_framework as filters

from hub.models import Post, Tag


class CharInFilter(filters.BaseInFilter, filters.CharFilter):
    pass


class TagFilter(filters.FilterSet):
    name = CharInFilter()

    class Meta:
        model = Tag
        fields = ('name', 'type')


class NumInFilter(filters.BaseInFilter, filters.NumberFilter):
    pass


class PostFilter(filters.FilterSet):
    id = NumInFilter()

    class Meta:
        model = Post
        fields = ('id',)
