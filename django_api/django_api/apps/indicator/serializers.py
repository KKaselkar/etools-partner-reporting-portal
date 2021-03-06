from ast import literal_eval as make_tuple
from collections import defaultdict, OrderedDict

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.shortcuts import get_object_or_404

from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from ocha.imports.serializers import DiscardUniqueTogetherValidationMixin
from unicef.models import LowerLevelOutput
from partner.models import PartnerProject, PartnerActivity
from cluster.models import ClusterObjective, ClusterActivity

from core.common import OVERALL_STATUS, INDICATOR_REPORT_STATUS, FINAL_OVERALL_STATUS
from core.serializers import LocationSerializer, IdLocationSerializer
from core.models import Location
from core.validators import add_indicator_object_type_validator
from core.helpers import (
    generate_data_combination_entries,
    get_sorted_ordered_dict_by_keys,
    get_cast_dictionary_keys_as_tuple,
    get_cast_dictionary_keys_as_string,
)

from .models import (
    Reportable, IndicatorBlueprint,
    IndicatorReport, IndicatorLocationData,
    Disaggregation, DisaggregationValue,
    ReportableLocationGoal,
    create_pa_reportables_for_new_ca_reportable,
)


class DisaggregationValueListSerializer(serializers.ModelSerializer):

    class Meta:
        model = DisaggregationValue
        fields = (
            'id',
            'value',
            'active',
        )


class DisaggregationListSerializer(serializers.ModelSerializer):
    choices = DisaggregationValueListSerializer(
        many=True, source='disaggregation_values')

    @transaction.atomic
    def create(self, validated_data):
        disaggregation_values = validated_data.pop('disaggregation_values')

        if disaggregation_values:
            unique_list_dicts = list({v['value']: v for v in disaggregation_values}.values())

            if len(disaggregation_values) != len(unique_list_dicts):
                raise serializers.ValidationError({
                    "disaggregation_values": "Duplicated disaggregation value is not allowed",
                })

        instance = Disaggregation.objects.create(**validated_data)
        for choice in disaggregation_values:
            DisaggregationValue.objects.create(disaggregation=instance,
                                               value=choice['value'])
        return instance

    class Meta:
        model = Disaggregation
        fields = (
            'id',
            'name',
            'active',
            'response_plan',
            'choices',
        )


class IdDisaggregationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Disaggregation
        fields = ('id',)


class IndicatorBlueprintSimpleSerializer(serializers.ModelSerializer):
    # id added explicitly here since it gets stripped out from validated_data as its read_only.
    # https://stackoverflow.com/questions/36473795/django-rest-framework-model-id-field-in-nested-relationship-serializer
    id = serializers.IntegerField()

    class Meta:
        model = IndicatorBlueprint
        fields = (
            'id',
            'title',
            'unit',
            'display_type',
            'calculation_formula_across_periods',
            'calculation_formula_across_locations',
        )


class IndicatorReportSimpleSerializer(serializers.ModelSerializer):

    indicator_name = serializers.SerializerMethodField()
    target = serializers.SerializerMethodField()
    achieved = serializers.JSONField(source="total")

    class Meta:
        model = IndicatorReport
        fields = (
            'id',
            'indicator_name',
            'target',
            'achieved',
            'total',
            'report_status',
            'review_date',
            'sent_back_feedback'
        )

    def get_indicator_name(self, obj):
        # indicator_name can be indicator serialized or comes from blueprint
        # but when should be presented from blueprint? when entering data?
        return obj.reportable.blueprint.title

    def get_target(self, obj):
        return obj.reportable and obj.reportable.calculated_target


class IndicatorReportStatusSerializer(serializers.ModelSerializer):

    class Meta:
        model = IndicatorReport
        fields = (
            'remarks',
            'report_status',
        )


class ReportableSimpleSerializer(serializers.ModelSerializer):
    blueprint = IndicatorBlueprintSimpleSerializer()
    ref_num = serializers.CharField()
    achieved = serializers.JSONField()
    baseline = serializers.JSONField()
    target = serializers.JSONField()
    in_need = serializers.JSONField()
    progress_percentage = serializers.FloatField()
    content_type_key = serializers.SerializerMethodField()
    content_object_title = serializers.SerializerMethodField()

    class Meta:
        model = Reportable
        fields = (
            'id',
            'target',
            'baseline',
            'in_need',
            'blueprint',
            'ref_num',
            'achieved',
            'progress_percentage',
            'content_type_key',
            'content_object_title',
            'object_id',
        )

    def get_content_type_key(self, obj):
        return '.'.join(obj.content_type.natural_key())

    def get_content_object_title(self, obj):
        return obj.content_object.title


class ReportableLocationGoalBaselineInNeedListSerializer(serializers.ListSerializer):
    @transaction.atomic
    def update(self, instance, validated_data):
        loc_goal_mapping = {loc_goal.id: loc_goal for loc_goal in instance}
        data_mapping = {item['id']: item for item in validated_data}
        updated = list()

        if 'reportable_id' not in self.context['view'].kwargs:
            raise ValidationError("The view needs reportable_id from url")

        reportable_id = self.context['view'].kwargs['reportable_id']
        reportable = get_object_or_404(Reportable, id=reportable_id)

        # Handling creation and updates
        for data_id, data in data_mapping.items():
            loc_goal = loc_goal_mapping.get(data_id, None)
            data['reportable'] = reportable

            if not loc_goal:
                updated.append(self.child.create(data))

            else:
                updated.append(self.child.update(loc_goal, data))

        # Handling deletion from update
        for loc_goal_id, loc_goal in loc_goal_mapping.items():
            if loc_goal_id not in data_mapping:
                loc_goal.delete()

        return updated


class ReportableLocationGoalBaselineInNeedSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField()
    baseline = serializers.JSONField()
    in_need = serializers.JSONField()
    location = LocationSerializer(read_only=True)

    def validate_baseline(self, value):
        if 'd' not in value:
            value['d'] = 1

        elif value['d'] == 0:
            raise serializers.ValidationError("key 'd' cannot be zero")

        return value

    def validate_in_need(self, value):
        if 'd' not in value:
            value['d'] = 1

        elif value['d'] == 0:
            raise serializers.ValidationError("key 'd' cannot be zero")

        return value

    class Meta:
        model = ReportableLocationGoal
        list_serializer_class = ReportableLocationGoalBaselineInNeedListSerializer
        fields = (
            'id',
            'baseline',
            'in_need',
            'location',
        )


class ReportableLocationGoalSerializer(serializers.ModelSerializer):
    baseline = serializers.JSONField(required=False)
    in_need = serializers.JSONField(required=False, allow_null=True)
    target = serializers.JSONField()
    loc_type = serializers.SerializerMethodField()

    def get_loc_type(self, obj):
        return obj.location.gateway.admin_level

    def validate_baseline(self, value):
        if 'd' not in value:
            value['d'] = 1

        elif value['d'] == 0:
            raise serializers.ValidationError("key 'd' cannot be zero")

        return value

    def validate_in_need(self, value):
        if value:
            if 'd' not in value:
                value['d'] = 1

            elif value['d'] == 0:
                raise serializers.ValidationError("key 'd' cannot be zero")

        return value

    def validate_target(self, value):
        if 'd' not in value:
            value['d'] = 1

        elif value['d'] == 0:
            raise serializers.ValidationError("key 'd' cannot be zero")

        return value

    class Meta:
        model = ReportableLocationGoal
        fields = (
            'id',
            'baseline',
            'in_need',
            'target',
            'location',
            'loc_type',
        )


class IndicatorListSerializer(ReportableSimpleSerializer):
    """
    Useful anywhere a list of indicators needs to be shown with minimal
    amount of data.
    """
    disaggregations = DisaggregationListSerializer(many=True, read_only=True)
    locations = serializers.SerializerMethodField()
    cluster = serializers.SerializerMethodField()
    total_against_in_need = serializers.SerializerMethodField()
    total_against_target = serializers.SerializerMethodField()

    def get_total_against_in_need(self, obj):
        return obj.calculated_target / obj.calculated_in_need \
            if obj.calculated_in_need and obj.calculated_in_need != 0 else 0

    def get_total_against_target(self, obj):
        target = obj.calculated_target if obj.calculated_target != 0 else 1.0
        return obj.total['c'] / target

    def get_cluster(self, obj):
        if isinstance(obj.content_object, PartnerProject) \
                and obj.content_object.clusters.exists():
            return obj.content_object.clusters.first().id

        elif isinstance(obj.content_object, PartnerActivity) \
                and obj.content_object.cluster_activity:
            return obj.content_object.cluster_activity.cluster.id

        elif isinstance(obj.content_object, (ClusterObjective, ClusterActivity)):
            return obj.content_object.cluster.id

        return None

    def get_locations(self, obj):
        return ReportableLocationGoalSerializer(obj.reportablelocationgoal_set.all(), many=True).data

    class Meta:
        model = Reportable
        fields = ReportableSimpleSerializer.Meta.fields + (
            'means_of_verification',
            'cs_dates',
            'frequency',
            'pd_id',
            'disaggregations',
            'locations',
            'comments',
            'measurement_specifications',
            'start_date_of_reporting_period',
            'label',
            'numerator_label',
            'denominator_label',
            'cluster',
            'parent_indicator',
            'total_against_in_need',
            'total_against_target',
        )


class IndicatorLLoutputsSerializer(serializers.ModelSerializer):
    """
    Returns all indicator reports that belong to this reportable.
    """
    __narrative_and_assessment = None

    name = serializers.SerializerMethodField()
    llo_id = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    indicator_reports = serializers.SerializerMethodField()
    overall_status = serializers.SerializerMethodField()
    narrative_assessment = serializers.SerializerMethodField()
    display_type = serializers.SerializerMethodField()

    class Meta:
        model = Reportable
        fields = (
            'id',
            'name',
            'llo_id',
            'status',
            'overall_status',
            'narrative_assessment',
            'indicator_reports',
            'display_type',
            'total',
        )

    def get_name(self, obj):
        if isinstance(obj.content_object, LowerLevelOutput):
            return obj.blueprint.title
        else:
            return ''

    def get_llo_id(self, obj):
        if isinstance(obj.content_object, LowerLevelOutput):
            return obj.content_object.id
        else:
            return ''

    def get_status(self, obj):
        # first indicator report associated with this output
        indicator_report = obj.indicator_reports.first()
        serializer = IndicatorReportStatusSerializer(indicator_report)
        return serializer.data

    def get_indicator_reports(self, obj):
        children = obj.indicator_reports.all()
        serializer = IndicatorReportSimpleSerializer(children, many=True)
        return serializer.data

    def get_overall_status(self, obj):
        capture = self.__get_narrative_and_assessment(obj)
        if capture is not None:
            return capture['overall_status']
        return ''

    def get_narrative_assessment(self, obj):
        capture = self.__get_narrative_and_assessment(obj)
        if capture is not None:
            return capture['narrative_assessment'] or ''
        return ''

    def __get_narrative_and_assessment(self, obj):
        if self.__narrative_and_assessment is not None:
            return self.__narrative_and_assessment
        indicator_report = obj.indicator_reports.first()
        if indicator_report:
            self.__narrative_and_assessment = Reportable.get_narrative_and_assessment(
                indicator_report.progress_report_id)
        return self.__narrative_and_assessment

    def get_display_type(self, obj):
        return obj.blueprint.display_type


class OverallNarrativeSerializer(serializers.ModelSerializer):
    """
    Sets the overall status and narrative assessment on an IndicatorReport instance.
    """
    class Meta:
        model = IndicatorReport
        fields = (
            'overall_status',
            'narrative_assessment',
        )

    def validate_overall_status(self, overall_status):
        if self.instance and self.instance.progress_report and self.instance.progress_report.is_final:
            if overall_status not in FINAL_OVERALL_STATUS:
                error_msg = 'Only {} statuses are allowed for indicators within a final Progress Report.'.format(
                    ', '.join([v[1] for v in FINAL_OVERALL_STATUS])
                )
                raise ValidationError(error_msg)

        return overall_status


class SimpleIndicatorLocationDataListSerializer(serializers.ModelSerializer):

    location = LocationSerializer(read_only=True)
    disaggregation = serializers.SerializerMethodField()
    location_progress = serializers.SerializerMethodField()
    previous_location_progress = serializers.SerializerMethodField()
    display_type = serializers.SerializerMethodField()
    is_complete = serializers.BooleanField(read_only=True)

    def get_display_type(self, obj):
        return obj.indicator_report.display_type

    def get_disaggregation(self, obj):
        ordered_dict = get_cast_dictionary_keys_as_tuple(obj.disaggregation)

        ordered_dict = get_sorted_ordered_dict_by_keys(
            ordered_dict, reverse=True)

        ordered_dict = get_cast_dictionary_keys_as_string(ordered_dict)

        return ordered_dict

    def get_location_progress(self, obj):
        return obj.disaggregation['()']

    def get_previous_location_progress(self, obj):
        previous_location_data = obj.previous_location_data
        empty_progress = {'c': 0, 'd': 0, 'v': 0}
        if previous_location_data:
            return previous_location_data.disaggregation.get('()', empty_progress)

    class Meta:
        model = IndicatorLocationData
        fields = (
            'id',
            'indicator_report',
            'location',
            'display_type',
            'disaggregation',
            'num_disaggregation',
            'level_reported',
            'disaggregation_reported_on',
            'location_progress',
            'previous_location_progress',
            'is_complete',
        )


class IndicatorLocationDataUpdateSerializer(serializers.ModelSerializer):

    disaggregation = serializers.JSONField()
    is_complete = serializers.SerializerMethodField()

    class Meta:
        model = IndicatorLocationData
        fields = (
            'id',
            'indicator_report',
            'disaggregation',
            'num_disaggregation',
            'level_reported',
            'disaggregation_reported_on',
            'is_complete',
        )

    def get_is_complete(self, obj):
        return obj.is_complete

    def validate(self, data):
        """
        Check IndicatorLocationData object's disaggregation
        field is correctly mapped to the disaggregation values.
        """

        # level_reported and num_disaggregation validation
        if data['level_reported'] > data['num_disaggregation']:
            raise serializers.ValidationError(
                "level_reported cannot be higher than its num_disaggregation"
            )

        # level_reported and disaggregation_reported_on validation
        if data['level_reported'] != len(data['disaggregation_reported_on']):
            raise serializers.ValidationError(
                "disaggregation_reported_on list must have level_reported # of elements"
            )

        disaggregation_id_list = data['indicator_report'].disaggregations.values_list(
            'id', flat=True)

        # num_disaggregation validation with actual Disaggregation count
        # from Reportable
        if data['num_disaggregation'] != len(disaggregation_id_list):
            raise serializers.ValidationError(
                "num_disaggregation is not matched with its IndicatorReport's Reportable disaggregation counts"
            )

        # IndicatorReport membership validation
        if self.instance.id not in data['indicator_report'] \
                .indicator_location_data.values_list('id', flat=True):
            raise serializers.ValidationError(
                "IndicatorLocationData does not belong to this {}".format(
                    data['indicator_report'])
            )

        # disaggregation_reported_on element-wise assertion
        for disagg_id in data['disaggregation_reported_on']:
            if disagg_id not in disaggregation_id_list:
                raise serializers.ValidationError(
                    "disaggregation_reported_on list must have all its elements mapped to disaggregation ids"
                )

        # Filter disaggregation option IDs
        # from given disaggregation_reported_on Disaggregation IDs
        disaggregation_value_id_list = \
            data['indicator_report'].disaggregation_values(
                id_only=True,
                filter_by_id__in=data['disaggregation_reported_on'])

        valid_disaggregation_value_pairs = \
            generate_data_combination_entries(
                disaggregation_value_id_list,
                entries_only=True, key_type=set, r=data['level_reported'])

        if set() not in valid_disaggregation_value_pairs:
            valid_disaggregation_value_pairs.append(set())

        disaggregation_data_keys = data['disaggregation'].keys()

        valid_entry_count = len(valid_disaggregation_value_pairs)
        disaggregation_data_key_count = len(list(disaggregation_data_keys))

        # Assertion on all combinatoric entries for num_disaggregation and
        # level_reported against submitted disaggregation data
        if valid_entry_count < disaggregation_data_key_count:
            raise serializers.ValidationError(
                "Submitted disaggregation data entries contains extra combination pair keys"
            )

        valid_level_reported_key_count = len(list(filter(
            lambda key: len(key) == data['level_reported'],
            valid_disaggregation_value_pairs
        )))
        level_reported_key_count = 0

        # Disaggregation data coordinate space check from level_reported
        for key in disaggregation_data_keys:
            try:
                parsed_tuple = make_tuple(key)

            except Exception:
                raise serializers.ValidationError(
                    "%s key is not in tuple format" % (key)
                )

            if len(parsed_tuple) > data['level_reported']:
                raise serializers.ValidationError(
                    "%s Disaggregation data coordinate " % (key)
                    + "space cannot be higher than "
                    + "specified level_reported"
                )

            # Disaggregation data coordinate space check
            # from disaggregation choice ids
            elif set(parsed_tuple) not in valid_disaggregation_value_pairs:
                raise serializers.ValidationError(
                    "%s coordinate space does not " % (key)
                    + "belong to disaggregation value id list")

            elif not isinstance(data['disaggregation'][key], dict):
                raise serializers.ValidationError(
                    "%s coordinate space does not " % (key)
                    + "have a correct value dictionary")

            elif list(data['disaggregation'][key].keys()) != ['c', 'd', 'v']:
                raise serializers.ValidationError(
                    "%s coordinate space value does not " % (key)
                    + "have correct value key structure: c, d, v")

            if len(parsed_tuple) == data['level_reported']:
                level_reported_key_count += 1

            # Sanitizing data value
            if isinstance(data['disaggregation'][key]['c'], str):
                data['disaggregation'][key]['c'] = \
                    int(data['disaggregation'][key]['c'])

            if isinstance(data['disaggregation'][key]['d'], str):
                data['disaggregation'][key]['d'] = \
                    int(data['disaggregation'][key]['d'])

            if isinstance(data['disaggregation'][key]['v'], str):
                data['disaggregation'][key]['v'] = \
                    int(data['disaggregation'][key]['v'])

        if level_reported_key_count != valid_level_reported_key_count:
            raise serializers.ValidationError(
                "Submitted disaggregation data entries do not contain "
                + "all level %d combination pair keys" % (data['level_reported'])
            )

        return data


class IndicatorReportListSerializer(serializers.ModelSerializer):
    indicator_location_data = SimpleIndicatorLocationDataListSerializer(
        many=True, read_only=True)
    disagg_lookup_map = serializers.SerializerMethodField()
    disagg_choice_lookup_map = serializers.SerializerMethodField()
    total = serializers.JSONField()
    display_type = serializers.SerializerMethodField()
    overall_status_display = serializers.CharField(
        source='get_overall_status_display')
    labels = serializers.SerializerMethodField()

    class Meta:
        model = IndicatorReport
        fields = (
            'id',
            'title',
            'indicator_location_data',
            'time_period_start',
            'time_period_end',
            'due_date',
            'display_type',
            'submission_date',
            'total',
            'remarks',
            'report_status',
            'disagg_lookup_map',
            'disagg_choice_lookup_map',
            'overall_status',
            'overall_status_display',
            'narrative_assessment',
            'labels',
        )

    def get_labels(self, obj):
        return {
            'label': obj.reportable.label,
            'numerator_label': obj.reportable.numerator_label,
            'denominator_label': obj.reportable.denominator_label,
        }

    def get_display_type(self, obj):
        return obj.display_type

    def get_disagg_lookup_map(self, obj):
        serializer = DisaggregationListSerializer(
            obj.disaggregations, many=True)

        disagg_lookup_list = serializer.data
        disagg_lookup_list.sort(key=lambda item: len(item['choices']))

        return disagg_lookup_list

    def get_disagg_choice_lookup_map(self, obj):
        lookup_array = obj.disaggregation_values(id_only=False)
        lookup_array.sort(key=len)

        return lookup_array


class ClusterIndicatorReportListSerializer(IndicatorReportListSerializer):
    cluster = serializers.SerializerMethodField()
    partner = serializers.SerializerMethodField()
    progress_percentage = serializers.SerializerMethodField()
    indicator_id = serializers.SerializerMethodField()

    def get_cluster(self, obj):
        cluster = obj.reportable.content_object.partner.clusters.first()

        if cluster:
            return cluster.type

        else:
            return ''

    def get_partner(self, obj):
        return obj.reportable.content_object.partner.title

    def get_progress_percentage(self, obj):
        return obj.reportable.progress_percentage

    def get_indicator_id(self, obj):
        return obj.reportable.id

    class Meta(IndicatorReportListSerializer.Meta):
        fields = IndicatorReportListSerializer.Meta.fields + (
            'cluster',
            'partner',
            'progress_percentage',
            'indicator_id',
        )


class PDReportContextIndicatorReportSerializer(serializers.ModelSerializer):
    """
    A serializer for IndicatorReport model but specific information
    that is helpful in IP reporting from a Programme Document / Progress
    Report perspective (TODO: specify what is PD specfic?).
    """
    id = serializers.SerializerMethodField()
    reporting_period = serializers.SerializerMethodField()
    reportable_object_id = serializers.SerializerMethodField()
    submission_date = serializers.SerializerMethodField()
    due_date = serializers.SerializerMethodField()
    is_cluster_indicator = serializers.SerializerMethodField()
    reportable = ReportableSimpleSerializer()
    report_status_display = serializers.CharField(source='get_report_status_display')
    overall_status_display = serializers.CharField(source='get_overall_status_display')

    class Meta:
        model = IndicatorReport
        fields = (
            'id',
            'progress_report',
            'reportable',
            'reportable_object_id',
            'reporting_period',
            'progress_report_status',
            'report_status',
            'report_status_display',
            'submission_date',
            'is_draft',
            'is_cluster_indicator',
            'due_date',
            'total',
            'overall_status',
            'overall_status_display',
            'narrative_assessment',
            'is_complete',
        )

    def get_id(self, obj):
        return str(obj.id)

    def get_reporting_period(self, obj):
        return "%s - %s " % (
            obj.time_period_start.strftime(settings.PRINT_DATA_FORMAT),
            obj.time_period_end.strftime(settings.PRINT_DATA_FORMAT)
        )

    def get_reportable_object_id(self, obj):
        return obj.reportable.object_id

    def get_is_cluster_indicator(self, obj):
        return obj.reportable.is_cluster_indicator

    def get_submission_date(self, obj):
        return obj.submission_date and obj.submission_date.strftime(
            settings.PRINT_DATA_FORMAT)

    def get_due_date(self, obj):
        return obj.due_date and obj.due_date.strftime(
            settings.PRINT_DATA_FORMAT)


class IndicatorBlueprintSerializer(serializers.ModelSerializer):

    class Meta:
        model = IndicatorBlueprint
        fields = (
            'id',
            'title',
            'unit',
            'description',
            'disaggregatable',
            'calculation_formula_across_periods',
            'calculation_formula_across_locations',
            'display_type',
        )


class ClusterIndicatorSerializer(serializers.ModelSerializer):

    disaggregations = IdDisaggregationSerializer(many=True, read_only=True)
    object_type = serializers.CharField(
        validators=[add_indicator_object_type_validator], write_only=True)
    blueprint = IndicatorBlueprintSerializer()
    locations = ReportableLocationGoalSerializer(many=True, write_only=True)
    target = serializers.JSONField()
    baseline = serializers.JSONField()
    in_need = serializers.JSONField(required=False, allow_null=True)

    class Meta:
        model = Reportable
        fields = (
            'id',
            'means_of_verification',
            'blueprint',
            'object_id',
            'object_type',
            'locations',
            'disaggregations',
            'frequency',
            'cs_dates',
            'target',
            'baseline',
            'in_need',
            'comments',
            'measurement_specifications',
            'start_date_of_reporting_period',
            'label',
            'numerator_label',
            'denominator_label',
        )

    def check_disaggregation(self, disaggregations):
        if not isinstance(disaggregations, list) or False in [dis.get('id', False) for dis in disaggregations]:
            raise ValidationError(
                {"disaggregations": "List of dict disaggregation expected"}
            )

    def check_progress_values(self, validated_data):
        """
        Validates baseline, target, in-need
        """
        if 'baseline' not in validated_data:
            raise ValidationError(
                {"baseline": "baseline is required for IMO creating Cluster Indicator"}
            )

        if 'target' not in validated_data:
            raise ValidationError(
                {"target": "target is required for IMO creating Cluster Indicator"}
            )

        if 'd' not in validated_data['baseline']:
            validated_data['baseline']['d'] = 1

        if 'd' not in validated_data['target']:
            validated_data['target']['d'] = 1

        if validated_data['baseline']['d'] == 0:
            raise ValidationError(
                {"baseline": "denominator for baseline cannot be zero"}
            )

        if validated_data['target']['d'] == 0:
            raise ValidationError(
                {"target": "denominator for target cannot be zero"}
            )

        baseline_value = float(validated_data['baseline']['v']) if float(validated_data['baseline']['d']) == 1 else \
            float(validated_data['baseline']['v']) / float(validated_data['baseline']['d'])

        target_value = float(validated_data['target']['v']) if float(validated_data['target']['d']) == 1 else \
            float(validated_data['target']['v']) / float(validated_data['target']['d'])

        if baseline_value > target_value:
            raise ValidationError(
                {"baseline": "Cannot be greater than target"}
            )

        if 'in_need' in validated_data and validated_data['in_need']:
            if 'd' not in validated_data['in_need']:
                validated_data['in_need']['d'] = 1

            if validated_data['in_need']['d'] == 0:
                raise ValidationError(
                    {"in_need": "denominator for in_need cannot be zero"}
                )

            in_need_value = float(validated_data['in_need']['v']) if float(validated_data['in_need']['d']) == 1 else \
                float(validated_data['in_need']['v']) / float(validated_data['in_need']['d'])

            if target_value > in_need_value:
                raise ValidationError(
                    {"target": "Cannot be greater than In Need"}
                )

    def check_location_admin_levels(self, location_goal_queryset):
        if location_goal_queryset.exists() and location_goal_queryset.values_list(
            'gateway__admin_level', flat=True) \
                .distinct().count() != 1:
            raise ValidationError(
                {"locations": "Selected locations should share same admin level"})

    @transaction.atomic
    def create(self, validated_data):
        partner = self.context['request'].user.partner

        self.check_disaggregation(self.initial_data.get('disaggregations'))

        if not partner:
            self.check_progress_values(validated_data)

        if validated_data['blueprint']['display_type'] == IndicatorBlueprint.RATIO:
            validated_data['blueprint']['unit'] = IndicatorBlueprint.PERCENTAGE

        else:
            validated_data['blueprint']['unit'] = validated_data['blueprint']['display_type']

        if validated_data['blueprint']['unit'] == IndicatorBlueprint.PERCENTAGE:
            if validated_data['blueprint']['calculation_formula_across_periods'] != IndicatorBlueprint.SUM:
                raise ValidationError(
                    "calculation_formula_across_periods must be sum for Ratio Indicator type")

            if validated_data['blueprint']['calculation_formula_across_locations'] != IndicatorBlueprint.SUM:
                raise ValidationError(
                    "calculation_formula_across_locations must be sum for Ratio Indicator type")

        validated_data['blueprint']['disaggregatable'] = True
        blueprint = IndicatorBlueprintSerializer(
            data=validated_data['blueprint'])
        blueprint.is_valid(raise_exception=True)

        validated_data['blueprint'] = blueprint.save()

        reportable_object_content_type = ContentType.objects.get_by_natural_key(
            *validated_data.pop('object_type').split('.')
        )
        reportable_object_content_model = reportable_object_content_type.model_class()

        if reportable_object_content_model == ClusterObjective:
            get_object_or_404(ClusterObjective, pk=validated_data['object_id'])
            validated_data['is_cluster_indicator'] = True
        elif reportable_object_content_model == ClusterActivity:
            get_object_or_404(ClusterActivity, pk=validated_data['object_id'])
            validated_data['is_cluster_indicator'] = True
        elif reportable_object_content_model == PartnerProject:
            get_object_or_404(PartnerProject, pk=validated_data['object_id'])
            validated_data['is_cluster_indicator'] = False
        elif reportable_object_content_model == PartnerActivity:
            get_object_or_404(PartnerActivity, pk=validated_data['object_id'])
            validated_data['is_cluster_indicator'] = False
        else:
            raise NotImplemented()

        validated_data['content_type'] = reportable_object_content_type

        locations = validated_data.pop('locations', [])

        self.instance = Reportable.objects.create(**validated_data)

        location_ids = [l['location'].id for l in locations]

        # Duplicated location safeguard
        if len(location_ids) != len(set(location_ids)):
            raise ValidationError("Duplicated locations are not allowed")

        location_queryset = Location.objects.filter(
            id__in=location_ids
        )
        self.check_location_admin_levels(location_queryset)

        for loc_data in locations:
            if partner:
                # Filter out location goal level baseline, in_need
                loc_data.pop('baseline', None)
                loc_data.pop('in_need', None)

            else:
                # Location-level progress value validation
                self.check_progress_values(loc_data)

            loc_data['reportable'] = self.instance

            ReportableLocationGoal.objects.create(**loc_data)

        disaggregations = self.initial_data.get('disaggregations')
        self.instance.disaggregations.add(
            *Disaggregation.objects.filter(id__in=[d['id'] for d in disaggregations]))

        # Only trigger to create PartnerActivity Reportable if ClusterActivity Reportable is created
        if reportable_object_content_model == ClusterActivity:
            create_pa_reportables_for_new_ca_reportable(self.instance)

        return self.instance

    @transaction.atomic
    def update(self, reportable, validated_data):
        partner = self.context['request'].user.partner

        # Remove disaggregations to update
        validated_data.pop('disaggregations', [])

        if partner:
            # Filter out IndicatorBlueprint instance
            # and Indicator level baseline, in_need, and target
            validated_data.pop('blueprint', None)
            validated_data.pop('baseline', None)
            validated_data.pop('in_need', None)
            validated_data.pop('target', None)

        if not partner:
            self.check_progress_values(validated_data)

        # Swapping validated_data['locations'] with raw request.data['locations']
        # Due to missing id field as it is write_only field
        validated_data.pop('locations', [])
        locations = list(map(
            lambda item: OrderedDict(item),
            self.context['request'].data['locations']
        ))

        try:
            for loc_goal in locations:
                loc_goal.pop('loc_type', None)
                loc_goal['location'] = Location.objects.get(id=loc_goal['location'])
                loc_goal['reportable'] = reportable

                if partner:
                    # Filter out location goal level baseline, in_need
                    loc_goal.pop('baseline', None)
                    loc_goal.pop('in_need', None)

                if not partner:
                    # Location-level progress value validation
                    self.check_progress_values(loc_goal)

        except Location.DoesNotExist:
            raise ValidationError("Location ID %d does not exist" % loc_goal['location'])

        location_ids = [l['location'].id for l in locations]

        # Duplicated location safeguard
        if len(location_ids) != len(set(location_ids)):
            raise ValidationError("Duplicated locations are not allowed")

        location_queryset = Location.objects.filter(
            id__in=location_ids
        )

        self.check_location_admin_levels(location_queryset)

        existing_loc_goals = reportable.reportablelocationgoal_set.all()
        loc_goal_mapping = {
            loc_goal.id: loc_goal for loc_goal in existing_loc_goals}
        data_mapping = {loc_goal['id']: loc_goal for loc_goal in locations if 'id' in loc_goal}
        new_data_list = [loc_goal for loc_goal in locations if 'id' not in loc_goal]

        # Handling creation and updates
        for data in new_data_list:
            ReportableLocationGoal.objects.create(**data)

        for data_id, data in data_mapping.items():
            loc_goal = loc_goal_mapping.get(data_id, None)

            if partner:
                # Filter out location level baseline and in_need
                data.pop('baseline', None)
                data.pop('in_need', None)

            if loc_goal.location.id != data['location'].id:
                raise ValidationError(
                    "Location %s cannot be changed for updating location goal" % loc_goal.location,
                )

            for key, val in data.items():
                setattr(loc_goal, key, val)

            loc_goal.save()

        # Handling deletion from update
        for loc_goal_id, loc_goal in loc_goal_mapping.items():
            if loc_goal_id not in data_mapping:
                loc_goal.delete()

        blueprint_data = validated_data.pop('blueprint', {})
        reportable.blueprint.title = blueprint_data.get(
            'title', reportable.blueprint.title)
        reportable.blueprint.save()

        return super(ClusterIndicatorSerializer, self).update(reportable, validated_data)


class ClusterIndicatorDataSerializer(serializers.ModelSerializer):

    disaggregations = DisaggregationListSerializer(many=True)
    blueprint = IndicatorBlueprintSerializer()
    locations = IdLocationSerializer(many=True)

    class Meta:
        model = Reportable
        fields = (
            'id',
            'means_of_verification',
            'blueprint',
            'locations',
            'disaggregations',
            'frequency',
            'cs_dates',
        )


class ClusterIndicatorForPartnerActivitySerializer(
        serializers.ModelSerializer):
    blueprint = IndicatorBlueprintSerializer()
    locations = LocationSerializer(many=True)

    class Meta:
        model = Reportable
        fields = (
            'id',
            'blueprint',
            'locations',
            'frequency',
            'cs_dates',
        )


class IndicatorReportUpdateSerializer(serializers.ModelSerializer):

    overall_status = serializers.SerializerMethodField()
    narrative_assessment = serializers.SerializerMethodField()

    class Meta:
        model = IndicatorReport
        fields = (
            'reporting_period',
        )


class IndicatorReportReviewSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=[
        INDICATOR_REPORT_STATUS.sent_back,
        INDICATOR_REPORT_STATUS.accepted
    ])
    comment = serializers.CharField(required=False)

    def validate(self, data):
        """
        Make sure status is only accepted or sent back. Also overall_status
        should be set if accepting
        """
        if data['status'] not in {
            INDICATOR_REPORT_STATUS.sent_back, INDICATOR_REPORT_STATUS.accepted
        }:
            raise serializers.ValidationError({
                'status': 'Report status should be accepted or sent back'
            })

        if data['status'] == INDICATOR_REPORT_STATUS.sent_back and not data.get('comment'):
            raise serializers.ValidationError({
                'comment': 'Comment required when sending back report'
            })

        return data


class ClusterIndicatorReportSerializer(serializers.ModelSerializer):
    """
    Used to represent an individual indicator report in the cluster.
    """
    indicator_name = serializers.SerializerMethodField()
    reportable = IndicatorListSerializer()
    reporting_period = serializers.SerializerMethodField()
    cluster = serializers.SerializerMethodField()
    cluster_id = serializers.SerializerMethodField()
    project = serializers.SerializerMethodField()
    partner = serializers.SerializerMethodField()
    partner_id = serializers.SerializerMethodField()
    partner_activity = serializers.SerializerMethodField()
    cluster_objective = serializers.SerializerMethodField()
    cluster_activity = serializers.SerializerMethodField()
    is_draft = serializers.SerializerMethodField()
    can_submit = serializers.SerializerMethodField()

    class Meta:
        model = IndicatorReport
        fields = (
            'id',
            'indicator_name',
            'title',
            'reportable',
            'reporting_period',
            'due_date',
            'submission_date',
            'frequency',
            'total',
            'remarks',
            'report_status',
            'overall_status',
            'narrative_assessment',
            'sent_back_feedback',
            'review_date',
            'cluster',
            'cluster_id',
            'project',
            'partner',
            'partner_id',
            'partner_activity',
            'cluster_objective',
            'cluster_activity',
            'is_draft',
            'can_submit',
            'time_period_start',
            'time_period_end',
        )

    def get_indicator_name(self, obj):
        return obj.reportable.blueprint.title

    def get_reporting_period(self, obj):
        return "%s - %s " % (
            obj.time_period_start.strftime(settings.PRINT_DATA_FORMAT),
            obj.time_period_end.strftime(settings.PRINT_DATA_FORMAT)
        )

    def _get_cluster(self, obj):
        if isinstance(obj.reportable.content_object, (ClusterObjective, )):
            return obj.reportable.content_object.cluster
        elif isinstance(obj.reportable.content_object, (ClusterActivity, )):
            return obj.reportable.content_object.cluster_objective.cluster
        elif isinstance(obj.reportable.content_object, (PartnerActivity, )):
            if obj.reportable.content_object.cluster_activity:
                return obj.reportable.content_object.cluster_activity.cluster_objective.cluster
            else:
                return obj.reportable.content_object.cluster_objective.cluster
        elif isinstance(obj.reportable.content_object, (PartnerProject, )):
            return obj.reportable.content_object.clusters.first()
        else:
            return None

    def get_cluster(self, obj):
        cluster = self._get_cluster(obj)
        return {"id": cluster.id, "title": cluster.get_type_display()} if cluster else None

    def get_cluster_id(self, obj):
        cluster = self._get_cluster(obj)
        return cluster.id if cluster else None

    def get_project(self, obj):
        if isinstance(obj.reportable.content_object, (PartnerProject, )):
            return {"id": obj.reportable.content_object.id, "title": obj.reportable.content_object.title}
        elif isinstance(obj.reportable.content_object, (PartnerActivity, )):
            if obj.reportable.content_object.project:
                return {
                    "id": obj.reportable.content_object.project.id,
                    "title": obj.reportable.content_object.project.title
                }
        else:
            return None

    def _get_partner(self, obj):
        if isinstance(obj.reportable.content_object,
                      (PartnerProject, PartnerActivity)):
            return obj.reportable.content_object.partner
        else:
            return None

    def get_partner(self, obj):
        partner = self._get_partner(obj)

        return {"id": partner.id, "title": partner.title} if partner else None

    def get_partner_id(self, obj):
        partner = self._get_partner(obj)

        return partner.id if partner else None

    def get_partner_activity(self, obj):
        if isinstance(obj.reportable.content_object, (PartnerActivity, )):
            return {"id": obj.reportable.content_object.id, "title": obj.reportable.content_object.title}
        else:
            return None

    def get_cluster_objective(self, obj):
        if isinstance(obj.reportable.content_object, (ClusterObjective, )):
            return {"id": obj.reportable.content_object.id, "title": obj.reportable.content_object.title}
        else:
            return None

    def get_cluster_activity(self, obj):
        if isinstance(obj.reportable.content_object, (ClusterActivity, )):
            return {"id": obj.reportable.content_object.id, "title": obj.reportable.content_object.title}
        else:
            return None

    def get_is_draft(self, obj):
        return obj.is_draft

    def get_can_submit(self, obj):
        return obj.can_submit


class ReportableSimpleSerializer(serializers.ModelSerializer):

    title = serializers.SerializerMethodField()

    class Meta:
        model = Reportable
        fields = (
            'id',
            'title',
        )

    def get_title(self, obj):
        return obj.blueprint.title

# PMP API Serializers


class PMPIndicatorBlueprintSerializer(serializers.ModelSerializer):
    blueprint_id = serializers.CharField(source='external_id')

    class Meta:
        model = IndicatorBlueprint
        fields = (
            'blueprint_id',
            'title',
            'disaggregatable',
        )


class PMPDisaggregationSerializer(serializers.ModelSerializer):
    id = serializers.CharField(source='external_id')

    class Meta:
        model = Disaggregation
        fields = (
            'id',
            'name',
            'active',
        )


class PMPDisaggregationValueSerializer(DiscardUniqueTogetherValidationMixin, serializers.ModelSerializer):
    id = serializers.CharField(source='external_id')
    disaggregation = serializers.PrimaryKeyRelatedField(queryset=Disaggregation.objects.all())

    class Meta:
        model = DisaggregationValue
        fields = (
            'id',
            'value',
            'active',
            'disaggregation',
        )


class PMPReportableSerializer(serializers.ModelSerializer):
    id = serializers.CharField(source='external_id')
    title = serializers.CharField(source='means_of_verification')
    blueprint_id = serializers.PrimaryKeyRelatedField(queryset=IndicatorBlueprint.objects.all(), source="blueprint")
    disaggregation_ids = serializers.PrimaryKeyRelatedField(
        queryset=Disaggregation.objects.all(),
        many=True,
        allow_null=True,
        source="disaggregations"
    )

    class Meta:
        model = Reportable
        fields = (
            'id',
            'target',
            'baseline',
            'title',
            'is_cluster_indicator',
            'blueprint_id',
            'disaggregation_ids',
            'content_type',
            'object_id',
        )


class ClusterPartnerAnalysisIndicatorResultSerializer(serializers.ModelSerializer):
    blueprint = IndicatorBlueprintSimpleSerializer()
    achieved = serializers.JSONField()
    baseline = serializers.JSONField()
    target = serializers.JSONField()
    progress_percentage = serializers.FloatField()
    progress_by_location = serializers.SerializerMethodField()
    indicator_reports = serializers.SerializerMethodField()
    project = serializers.SerializerMethodField()
    cluster_activity = serializers.SerializerMethodField()
    latest_report_status = serializers.SerializerMethodField()

    def get_progress_by_location(self, obj):
        result = {}
        ir = obj.indicator_reports.latest('id')

        locations = Location.objects.filter(
            indicator_location_data__indicator_report=ir
        ).distinct()

        for loc in locations:
            progress = 0

            for loc_data in loc.indicator_location_data.values_list('disaggregation', flat=True):
                progress += loc_data['()']['c']

            result[loc.title] = progress

        return result

    def get_indicator_reports(self, obj):
        irs = obj.indicator_reports.order_by('-id')[:2]

        if irs:
            return IndicatorReportListSerializer(
                irs, many=True, read_only=True).data
        else:
            return []

    def get_project(self, obj):
        if isinstance(obj.content_object, PartnerActivity) \
                and obj.content_object.project:
            return obj.content_object.project.title
        else:
            return ""

    def get_cluster_activity(self, obj):
        if isinstance(obj.content_object, PartnerActivity) \
                and obj.content_object.cluster_activity:
            return obj.content_object.cluster_activity.title
        else:
            return ""

    def get_latest_report_status(self, obj):
        ir = obj.indicator_reports.latest('id')

        if ir:
            return ir.overall_status
        else:
            return ""

    class Meta:
        model = Reportable
        fields = (
            'id',
            'target',
            'baseline',
            'blueprint',
            'achieved',
            'progress_percentage',
            'progress_by_location',
            'indicator_reports',
            'project',
            'cluster_activity',
            'latest_report_status',
        )


class ClusterAnalysisIndicatorsListSerializer(serializers.ModelSerializer):
    content_type = serializers.SerializerMethodField()
    content_object = serializers.SerializerMethodField()
    total_against_in_need = serializers.SerializerMethodField()
    total_against_target = serializers.SerializerMethodField()
    blueprint = IndicatorBlueprintSimpleSerializer(read_only=True)
    baseline = serializers.JSONField()
    target = serializers.JSONField()

    def get_content_type(self, obj):
        return obj.content_type.model

    def get_total_against_in_need(self, obj):
        return obj.calculated_target / obj.calculated_in_need \
            if obj.calculated_in_need and obj.calculated_in_need != 0 else 0

    def get_total_against_target(self, obj):
        target = obj.calculated_target if obj.calculated_target != 0 else 1.0
        return obj.total['c'] / target

    def get_content_object(self, obj):
        if isinstance(obj.content_object, (PartnerProject, )):
            from partner.serializers import PartnerProjectSimpleSerializer
            return PartnerProjectSimpleSerializer(obj.content_object).data

        elif isinstance(obj.content_object, (PartnerActivity, )):
            from partner.serializers import PartnerActivitySimpleSerializer
            return PartnerActivitySimpleSerializer(obj.content_object).data

        elif isinstance(obj.content_object, (ClusterObjective, )):
            from cluster.serializers import ClusterObjectiveSerializer
            return ClusterObjectiveSerializer(obj.content_object).data

        elif isinstance(obj.content_object, (ClusterActivity, )):
            from cluster.serializers import ClusterActivitySerializer
            return ClusterActivitySerializer(obj.content_object).data

    class Meta:
        model = Reportable
        fields = (
            'id',
            'target',
            'baseline',
            'in_need',
            'blueprint',
            'achieved',
            'progress_percentage',
            'content_type',
            'content_object',
            'total_against_in_need',
            'total_against_target',
        )


class ClusterAnalysisIndicatorDetailSerializer(serializers.ModelSerializer):
    num_of_partners = serializers.SerializerMethodField()
    partners_by_status = serializers.SerializerMethodField()
    progress_over_time = serializers.SerializerMethodField()
    total_against_in_need = serializers.SerializerMethodField()
    total_against_target = serializers.SerializerMethodField()
    current_progress_by_partner = serializers.SerializerMethodField()
    current_progress_by_location = serializers.SerializerMethodField()
    indicator_type = serializers.SerializerMethodField()
    display_type = serializers.SerializerMethodField()
    baseline = serializers.JSONField()
    target = serializers.JSONField()
    in_need = serializers.JSONField()

    def get_total_against_in_need(self, obj):
        return obj.calculated_target / obj.calculated_in_need \
            if obj.calculated_in_need and obj.calculated_in_need != 0 else 0

    def get_total_against_target(self, obj):
        target = obj.calculated_target if obj.calculated_target != 0 else 1.0
        return obj.total['c'] / target

    def get_indicator_type(self, obj):
        if obj.content_type.model == "clusteractivity":
            return "Cluster Activity Indicator"

        elif obj.content_type.model == "clusterobjective":
            return "Cluster Objective Indicator"

        elif obj.content_type.model == "partneractivity":
            return "Partner Activity Indicator"

        elif obj.content_type.model == "partnerproject":
            return "Partner Project Indicator"

        else:
            return "Lower Level Output Indicator"

    def get_display_type(self, obj):
        return obj.blueprint.display_type

    def get_num_of_partners(self, obj):
        num_of_partners = 0

        if obj.children.exists() and isinstance(obj.content_object, (ClusterActivity, )):
            num_of_partners = obj.content_object.partner_activities.values_list(
                'partner', flat=True
            ).distinct().count()

        elif isinstance(obj.content_object, PartnerProject) or isinstance(obj.content_object, PartnerActivity):
            num_of_partners = 1

        else:
            num_of_partners = 0

        return num_of_partners

    def _increment_partner_by_status(self, reportable, num_of_partners):
        try:
            latest_ir = reportable.indicator_reports.latest(
                'time_period_start')

            overall_status = latest_ir.overall_status

            if overall_status == OVERALL_STATUS.met:
                num_of_partners["Met"] += 1

            elif overall_status == OVERALL_STATUS.on_track:
                num_of_partners["On Track"] += 1

            elif overall_status == OVERALL_STATUS.no_progress:
                num_of_partners["No Progress"] += 1

            elif overall_status == OVERALL_STATUS.constrained:
                num_of_partners["Constrained"] += 1

            elif overall_status == OVERALL_STATUS.no_status:
                num_of_partners["No Status"] += 1

        except IndicatorReport.DoesNotExist:
            # If there is no indicator report for this Reportable, then skip this process
            pass

    def get_partners_by_status(self, obj):
        num_of_partners = {
            "Met": 0,
            "On Track": 0,
            "No Progress": 0,
            "Constrained": 0,
            "No Status": 0,
        }

        if obj.children.exists():
            for child in obj.children.all():
                self._increment_partner_by_status(child, num_of_partners)

        else:
            self._increment_partner_by_status(obj, num_of_partners)

        return num_of_partners

    def get_progress_over_time(self, obj):
        return list(obj.indicator_reports.order_by('id').values_list('time_period_end', 'total'))

    def _get_progress_by_partner(self, reportable, partner_progresses):
        """
        Mutates partner_progresses to include partner name as key
        and its value as a list of progress dictionaries for
        consolidation later on.

        Arguments:
            reportable {Reportable} -- Reportable ORM object
            partner_progresses {Dict[str: List(Dict)]} -- A global dictionary for partner progresses
        """

        data = {
            'progress': int(reportable.total['c']),
            'target': reportable.target,
            'in_need': reportable.in_need,
            'locations': set(
                reportable.indicator_reports.values_list(
                    'indicator_location_data__location__title',
                    flat=True
                )
            ),
        }

        if reportable.content_object.partner.title not in partner_progresses:
            partner_progresses[reportable.content_object.partner.title] = list()

        partner_progresses[reportable.content_object.partner.title].append(data)

    def get_current_progress_by_partner(self, obj):
        partner_progresses = {}

        # Only if the indicator is cluster activity, the children (unicef indicators) will exist
        if obj.children.exists():
            for child in obj.children.all():
                self._get_progress_by_partner(child, partner_progresses)

        # If the indicator is UNICEF cluster which is linked as Partner, then show its progress only
        elif obj.content_type.model in ["partneractivity", "partnerproject"]:
            self._get_progress_by_partner(obj, partner_progresses)

        # Consolidation for progress info
        # partner_progresses is Dict[List[Dict]] type
        for progress in partner_progresses:
            consolidated = {
                'progress': 0,
                'target': {'d': 0, 'v': 0},
                'in_need': {'d': 0, 'v': 0},
                'locations': set(),
            }

            for progress_val in partner_progresses[progress]:
                consolidated['progress'] += progress_val['progress']
                consolidated['target']['d'] += int(progress_val['target']['d'])
                consolidated['target']['v'] += int(progress_val['target']['v'])
                consolidated['locations'] = consolidated['locations'].union(progress_val['locations'])

                if progress_val['in_need']:
                    consolidated['in_need']['d'] += int(progress_val['in_need']['d'])
                    consolidated['in_need']['v'] += int(progress_val['in_need']['v'])

            partner_progresses[progress] = consolidated

        return partner_progresses

    def _get_progress_by_location(self, location_data, location_progresses):
        """
        Mutates location_progresses to include location name as key
        and its value as a list of progress dictionaries for
        consolidation later on.

        Arguments:
            location_data {Iterator[IndicatorLocationData]} -- A iterator of IndicatorLocationData ORM objects
            location_progresses {Dict[str: Dict[List()]]} -- A global dictionary for location progresses
        """
        if not location_data:
            return

        for ild in location_data:
            reportable = ild.indicator_report.reportable

            partner_titles = set()
            partner_title = reportable.content_object.partner.title \
                + " (" + str(reportable.total['c']) + ")"
            partner_titles.add(partner_title)

            data = {
                'progress': ild.disaggregation['()']['c'],
                'partners': partner_titles,
            }

            if ild.location.title not in location_progresses:
                location_progresses[ild.location.title] = list()

            location_progresses[ild.location.title].append(data)

    def get_current_progress_by_location(self, obj):
        location_progresses = defaultdict()

        try:
            # Only if the indicator is cluster activity, the children (unicef indicators) will exist
            if obj.children.exists():
                latest_indicator_reports = map(
                    lambda x: x.indicator_reports.latest(
                        'time_period_start'), obj.children.all()
                )

                for ir in latest_indicator_reports:
                    self._get_progress_by_location(ir.indicator_location_data.all(), location_progresses)

            # If the indicator is UNICEF cluster which is linked as Partner, then show its progress only
            else:
                indicator_location_data = obj.indicator_reports \
                    .latest('time_period_start').indicator_location_data.all()

                self._get_progress_by_location(indicator_location_data, location_progresses)

        except IndicatorReport.DoesNotExist:
            # If there is no indicator report for this Reportable, then skip this process
            pass

        # Consolidation for progress info
        # location_progresses is Dict[List[Dict]] type
        for progress in location_progresses:
            consolidated = {
                'progress': 0,
                'partners': set(),
            }

            for progress_val in location_progresses[progress]:
                consolidated['progress'] += progress_val['progress']
                consolidated['partners'] = consolidated['partners'].union(progress_val['partners'])

            location_progresses[progress] = consolidated

        return location_progresses

    class Meta:
        model = Reportable
        fields = (
            'id',
            'target',
            'baseline',
            'in_need',
            'total',
            'blueprint',
            'indicator_type',
            'display_type',
            'frequency',
            'num_of_partners',
            'partners_by_status',
            'progress_over_time',
            'current_progress_by_partner',
            'current_progress_by_location',
            'total_against_in_need',
            'total_against_target',
        )


class ClusterIndicatorIMOMessageSerializer(serializers.Serializer):
    message = serializers.CharField(max_length=4048)
    cluster = serializers.IntegerField()
    reportable = serializers.IntegerField()

    def to_internal_value(self, data):
        from cluster.models import Cluster

        from partner.models import PartnerActivity

        cluster = get_object_or_404(
            Cluster,
            id=data['cluster']
        )

        data['cluster'] = cluster

        reportable = get_object_or_404(
            Reportable,
            id=data['reportable']
        )

        data['reportable'] = reportable

        if cluster not in self.context['request'].user.partner.clusters.all():
            raise ValidationError({
                "cluster": "Cluster does not belong to Partner",
            })

        elif reportable.content_type.model_class() != PartnerActivity:
            raise ValidationError({
                "reportable": "Indicator is not PartnerActivity Indicator",
            })

        elif reportable.content_type.model_class() == PartnerActivity \
                and not reportable.content_object.cluster_activity:
            raise ValidationError({
                "reportable": "Indicator is not PartnerActivity Indicator from ClusterActivity",
            })

        elif reportable.content_object.cluster_activity.cluster != cluster:
            raise ValidationError({
                "reportable": "Indicator does not belong to Cluster",
            })

        elif not cluster.imo_users.exists():
            raise ValidationError({
                "cluster": "There is no IMO user on the Cluster",
            })

        return {
            'message': data['message'],
            'cluster': cluster,
            'reportable': reportable,
        }

    def to_representation(self, data):
        return {
            'message': data['message'],
            'cluster': data['cluster'].id,
            'reportable': data['reportable'].id,
        }
