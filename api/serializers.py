from rest_framework import serializers
from rest_framework.serializers import raise_errors_on_nested_writes
from rest_framework.utils import model_meta

from bot.models import Weibo
from hub.models import Post, Tag, Attribute, TagSnapshot


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
        for k in value:
            attr = Attribute.get_attr_by_code(k, self.instance.type)
            if not attr:
                raise serializers.ValidationError("Invalid attribute [{}]".format(k))
            v = value[k]
            value[k] = attr.deserialize_value(v)
            if value[k] is None:
                raise serializers.ValidationError("Unable to parse [{}] to type [{}]".format(v,
                                                                                             attr.get_type_display()))
        return value

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

    class Meta:
        model = Tag
        fields = ('type', 'name', 'is_editable', 'like_count', 'detail')

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
        fields = '__all__'


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
        fields = '__all__'


class DetailPostSerializer(serializers.ModelSerializer):
    tags = BasicTagSerializer(many=True)
    weibo = WeiboSerializer()

    class Meta:
        model = Post
        fields = ('id', 'source', 'file_size', 'uploader', 'is_shown', 'is_pending', 'score', 'rating', 'tags', 'weibo',
                  'update_time', 'preview_url', 'media_url', 'sakugabooru_url')
