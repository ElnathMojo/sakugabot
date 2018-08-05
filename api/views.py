from rest_framework import viewsets, status, mixins
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser, IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView

from api import filters
from api import serializers
from api import throttles
from bot.services.sakugabooru_service import SakugabooruService
from hub.models import Post, Tag, TagSnapshot, Attribute


class AttributeViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Attribute.objects.all()
    serializer_class = serializers.AttributeSerializer
    filterset_class = filters.AttributeFilter
    pagination_class = None

    def get_queryset(self):
        if self.action == 'list':
            type = self.request.query_params.get("type", None)
            if type:
                return self.queryset.filter(type=type)
        return self.queryset


class TagSnapshotViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Tag History
    """
    queryset = TagSnapshot.objects.order_by('-update_time')
    filterset_class = filters.TagSnapshotFilter

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return serializers.DetailTagSnapshotSerializer
        return serializers.BasicTagSnapshotSerializer


class TagViewSet(mixins.ListModelMixin,
                 mixins.UpdateModelMixin,
                 mixins.RetrieveModelMixin,
                 viewsets.GenericViewSet):
    """
    Tag Information
    """
    queryset = Tag.objects.exclude(deletion_flag=True)
    serializer_class = serializers.BasicTagSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    filterset_class = filters.TagFilter

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return serializers.DetailTagSerializer
        if self.action == 'update':
            return serializers.ModifyTagSerializer
        return self.serializer_class

    def partial_update(self, request, *args, **kwargs):
        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)

    def update(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_object(), data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializers.DetailTagSerializer(self.get_object()).data)

    @action(detail=True, methods=['post'],
            permission_classes=[IsAdminUser],
            serializer_class=serializers.IDTagSnapshotSerializer)
    def revert(self, request, pk=None):
        tag = self.get_object()
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        print(serializer)
        if not tag.snapshots.filter(id=serializer.validated_data["id"]).exists():
            return Response({"detail": "Tag[{}] doesn't have a snapshot with ID[{}]".format(
                tag.name,
                serializer.validated_data["id"]
            )},
                status=status.HTTP_400_BAD_REQUEST)
        content = tag.snapshots.get(id=serializer.validated_data["id"]).content
        tag.detail = content
        tag.order_of_keys = [k[0] for k in content.items()]
        tag.save(editor=request.user)
        return Response(serializers.DetailTagSerializer(tag).data)


class PostViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Post Information
    """

    queryset = Post.objects.order_by('-id')
    filterset_class = filters.PostFilter

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return serializers.DetailPostSerializer
        return serializers.BasicPostSerializer

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def refresh(self, request, pk=None):
        post = self.get_object()
        post = SakugabooruService().update_post(post.id)
        return Response(self.get_serializer(post).data)

    @action(detail=False, methods=['post'], permission_classes=[IsAdminUser])
    def update_posts(self, request):
        page = request.query_params.get("page", 1)
        limit = request.query_params.get("limit", 100)
        posts = SakugabooruService().update_posts_by_page(page, limit)
        return Response(self.get_serializer(posts, many=True).data)

    @action(detail=False, methods=['post'], permission_classes=[IsAdminUser])
    def obtain(self, request):
        id = request.query_params.get("id", None)
        if id is None:
            return Response(data={"detail": "Must specify an id."}, status=status.HTTP_406_NOT_ACCEPTABLE)
        try:
            id = int(id)
        except ValueError:
            return Response(data={"detail": "id must be an integer."}, status=status.HTTP_406_NOT_ACCEPTABLE)
        post = SakugabooruService().update_post(id)
        return Response(self.get_serializer(post).data)


class TokenObtainPairViewWithThrottle(TokenObtainPairView):
    throttle_classes = [throttles.AuthThrottle]
