from rest_framework import serializers
from rest_framework.serializers import raise_errors_on_nested_writes
from rest_framework.utils import model_meta

from bot.models import Weibo
from hub.models import Post, Tag, Attribute, TagSnapshot
from hub.validators import TagDetailValidator


class BasicTagSerializer(serializers.ModelSerializer):
    main_name = serializers.SerializerMethodField()

    class Meta:
        model = Tag
        fields = ('type', 'name', 'main_name')

    def get_main_name(self, obj):
        name = obj.detail.get('name_main', None)
        if name:
            return name
        return obj.weibo_name


class ModifyTagSerializer(serializers.ModelSerializer):
    detail = serializers.JSONField()

    def validate_detail(self, value):
        return TagDetailValidator(
            attributes=Attribute.objects.filter(related_types__contains=[self.instance.type]))(value)

    def update(self, instance, validated_data):
        raise_errors_on_nested_writes('update', self, validated_data)
        info = model_meta.get_field_info(instance)
        for attr, value in validated_data.items():
            if attr in info.relations and info.relations[attr].to_many:
                field = getattr(instance, attr)
                field.set(value)
            else:
                setattr(instance, attr, value)

        instance.save(editor=self.context.get('request', dict()).user)

        return instance

    class Meta:
        model = Tag
        fields = ("detail", "order_of_keys")


class DetailTagSerializer(serializers.ModelSerializer):
    detail = serializers.SerializerMethodField()
    last_edit_user = serializers.SerializerMethodField()

    class Meta:
        model = Tag
        fields = ('type', 'name', 'override_name', 'is_editable', 'like_count', 'detail', 'last_edit_user')

    def get_detail(self, obj):
        info_list = list()
        for key in obj.order_of_keys:
            attr = Attribute.objects.get(code=key)
            info_list.append(
                {
                    'attribute': BasicAttributeSerializer(attr).data,
                    'value': obj.detail[key],
                    'formatted_value': attr.format.format(obj.detail[key]) if attr.format else None
                }
            )
        return info_list

    def get_last_edit_user(self, obj):
        snapshot = obj.snapshot_latest
        if snapshot:
            return snapshot.user_name
        return "System"


class IDTagSnapshotSerializer(serializers.Serializer):
    id = serializers.IntegerField()


class BasicTagSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = TagSnapshot
        fields = ('id', 'tag', 'hash', 'update_time', 'note', 'user_name', 'create_time')


class DetailTagSnapshotSerializer(serializers.ModelSerializer):
    content = serializers.SerializerMethodField()

    class Meta:
        model = TagSnapshot
        fields = ('id', 'tag', 'hash', 'update_time', 'note', 'user_name', 'create_time', 'content')

    def get_content(self, obj):
        info_list = list()
        for key, value in obj.content.items():
            attr = Attribute.objects.get(code=key)
            info_list.append(
                {
                    'attribute': BasicAttributeSerializer(attr).data,
                    'value': value,
                    'formatted_value': attr.format.format(value) if attr.format else None
                }
            )
        return info_list


class AttributeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Attribute
        exclude = ('format',)


class BasicAttributeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Attribute
        fields = ('name', 'code')


class BasicPostSerializer(serializers.ModelSerializer):
    weibo_image_url = serializers.SerializerMethodField()
    class Meta:
        model = Post
        fields = ('id', 'source', 'file_size', 'uploader', 'is_shown', 'is_pending', 'score', 'rating', 'tags',
                  'weibo_image_url', 'update_time', 'preview_url', 'media_url', 'sakugabooru_url')

    def get_weibo_image_url(self, obj):
        if obj.weibo:
            return obj.weibo.img_url


class WeiboSerializer(serializers.ModelSerializer):
    class Meta:
        model = Weibo
        fields = ('weibo_id', 'img_url', 'create_time', 'weibo_url')


class DetailPostSerializer(serializers.ModelSerializer):
    tags = BasicTagSerializer(many=True)
    weibo = WeiboSerializer()

    class Meta:
        model = Post
        fields = ('id', 'source', 'file_size', 'uploader', 'is_shown', 'is_pending', 'score', 'rating', 'tags', 'weibo',
                  'update_time', 'preview_url', 'media_url', 'sakugabooru_url')
