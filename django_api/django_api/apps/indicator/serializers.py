from rest_framework import serializers

from unicef.models import LowerLevelOutput
from .models import Reportable, IndicatorBlueprint


class IndicatorBlueprintSimpleSerializer(serializers.ModelSerializer):

    class Meta:
        model = IndicatorBlueprint
        fields = (
            'id', 'title', 'unit',
        )


class IndicatorListSerializer(serializers.ModelSerializer):
    blueprint = IndicatorBlueprintSimpleSerializer()
    ref_num = serializers.CharField()
    achieved = serializers.IntegerField()
    progress_percentage = serializers.FloatField()

    class Meta:
        model = Reportable
        fields = (
            'id', 'target', 'baseline', 'blueprint',
            'ref_num', 'achieved', 'progress_percentage'
        )


class BaseIndicatorDataSerializer(serializers.ModelSerializer):

    llo_name = serializers.SerializerMethodField()
    llo_id = serializers.SerializerMethodField()
    overall_status = serializers.SerializerMethodField()
    narrative_assessemnt = serializers.SerializerMethodField()

    class Meta:
        model = Reportable
        fields = (
            'id',
            'llo_name',
            'llo_id',
            'target',
            'baseline',
            'achieved',
            'overall_status',
            'narrative_assessemnt',
        )

    def get_llo_name(self, obj):
        if isinstance(obj.content_object, LowerLevelOutput):
            return obj.content_object.title
        else:
            return ''

    def get_llo_id(self, obj):
        if isinstance(obj.content_object, LowerLevelOutput):
            return obj.content_object.id
        else:
            return ''

    def get_overall_status(self, obj):
        return None  # TODO later

    def get_narrative_assessemnt(self, obj):
        return None  # TODO later


class IndicatorDataSerializer(BaseIndicatorDataSerializer):

    indicators = serializers.SerializerMethodField()

    class Meta:
        model = Reportable
        fields = (
            'id',
            'llo_name',
            'llo_id',
            'target',
            'baseline',
            'achieved',
            'overall_status',
            'narrative_assessemnt',
            'indicators',
        )

    def get_indicators(self, obj):
        children = Reportable.objects.filter(parent_indicator=obj.id)
        serializer = BaseIndicatorDataSerializer(children, many=True)
        return serializer.data
